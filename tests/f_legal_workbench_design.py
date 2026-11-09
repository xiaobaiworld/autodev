"""Explicit paid integration: existing SRS handoff + Controller S2/S3 + V2.1 assets.

Use --real --root NEW_PROJECT design|review. Requirements are generated with the
shared clarification service first; browser validation runs between these phases.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import graphlib
import hashlib
import sys
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller
from cockpit.projects import register_project
from cockpit.store import Run, atomic_write, now_iso
from designsys.classify import classify, load_rules
from designsys.rules import load_library, select
from designsys.validate import validate_pack
from requirements.agent_runner import ParsedOutput, RunnerResult
from requirements.worker import run_model
from requirements.handoff import handoff_srs_to_pipeline
from requirements.session import ReqSessionStore
from requirements import service
from requirements.validator import inspect_srs_document


DESIGN_FILES = {
    'design.md', 'dev-plan.md', 'prototype.md',
    'design/artifacts/technical.json', 'design/artifacts/data.json',
    'design/artifacts/security.json', 'design/handoff.json',
    'design/artifacts/ui.json', 'design/artifacts/openapi.yaml',
    'design/artifacts/workflows.json', 'design/artifacts/ai.json',
}
CASE = {
    'features': ['ui', 'persistence', 'api', 'auth', 'sensitive_data',
                 'file_upload', 'ai', 'async_task', 'external_integration'],
    'risks': ['cross_tenant', 'high_impact_operation', 'high_risk_business'],
    'requirements_clear': True, 'multi_module': True,
}


def parse_files(reply, allowed):
    """Untrusted model output may only supply text/JSON at explicitly allowed paths."""
    raw = reply.strip()
    if raw.startswith('```') and raw.endswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {'files'}:
        raise ValueError('Expected one files object')
    files = payload['files']
    if not isinstance(files, dict) or set(files) != allowed:
        raise ValueError(f'Unexpected/missing files: {set(files) ^ allowed}')
    for path, value in files.items():
        if Path(path).is_absolute() or '..' in Path(path).parts:
            raise ValueError('Output path escapes stage')
        if not isinstance(value, (str, dict)):
            raise ValueError(f'Invalid content type: {path}')
    return files


def aggregate_reviews(reviews):
    """Keep every scoped finding; a PASS label cannot hide a blocking finding."""
    findings, coverage = [], []
    for review in reviews:
        if review.get('verdict') not in {'PASS', 'REWORK', 'BLOCK'}:
            raise ValueError('Invalid review verdict')
        for finding in review['findings']:
            if not {'id', 'severity', 'location', 'problem', 'expected'} <= finding.keys():
                raise ValueError('Incomplete review finding')
            if finding['severity'] not in {'critical', 'high', 'medium', 'low'}:
                raise ValueError('Invalid finding severity')
            findings.append(dict(finding, scope=review['scope']))
        coverage.extend(review['requirement_coverage'])
    if not reviews or not coverage:
        raise ValueError('Missing review evidence')
    verdict = 'PASS'
    if any(r['verdict'] == 'REWORK' for r in reviews) or any(f['severity'] in {'critical', 'high'} for f in findings):
        verdict = 'REWORK'
    if any(r['verdict'] == 'BLOCK' for r in reviews):
        verdict = 'BLOCK'
    return ('---\nverdict: ' + verdict + '\nfindings: ' + json.dumps(findings, ensure_ascii=False)
            + '\n---\n\n## 原文对照\n\n' + '\n'.join('- ' + item for item in coverage)
            + '\n\n原型业务服务均为模拟，不证明生产权限、法律正确性或Word兼容性。\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--real', action='store_true', required=True)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('phase', choices=['requirements', 'design', 'review', 'validate'])
    args = ap.parse_args()
    project = args.root.resolve()
    if args.phase == 'requirements':
        audit = project / 'workspace/requirements'
        audit.mkdir(parents=True, exist_ok=True)
        store = ReqSessionStore(str(audit / 'session.json'), str(project),
            'claude-opus', default_mode='cli_stateless', default_project=project.name)
        original = service.run_agent_turn

        def traced(*args, **kwargs):
            result = original(*args, **kwargs)
            n = len(list(audit.glob('cli-*.json'))) + 1
            atomic_write(audit / f'cli-{n}.json', json.dumps(asdict(result), ensure_ascii=False, indent=2))
            return result

        service.run_agent_turn = traced
        source = (project / 'docs/business-input.md').read_text() + '\n' + (project / 'docs/defaults.md').read_text()
        repair = ''
        for attempt in range(1, 4):
            prompt = f'''定稿。用户已授权默认设计，不再询问。严格使用9章节标准，第一节元数据用加粗项目符号，必须包含这两行：
- **归属项目**：`{project.name}`
- **需求编号**：REQ-LEGAL-WORKBENCH-MVP-001
五业务编号FR-01~FR-05；统一流程/Agent/复核/知识/安全编号FR-06~FR-10，验收AC-01~AC-15或更多。五业务和Word修订都保留正式设计范围，HTML原型模拟外部服务但不能删除功能。不带围栏、不加计划模式或文件操作说明。只回复完整SRS。修复说明：{repair}
原始输入与已授权默认值：\n{source}'''
            result = service.execute_clarification_turn(store, 'integration', prompt,
                timeout=600, req_type_override='SOFTWARE', channel='mvp-integration')
            atomic_write(audit / f'retry-{attempt}.json', json.dumps(asdict(result), ensure_ascii=False, indent=2))
            print(json.dumps(dict(attempt=attempt, ok=result.ok, path=result.archived_path,
                errors=result.validation.errors if result.validation else result.error), ensure_ascii=False), flush=True)
            if result.ok and result.validation and result.validation.is_valid:
                atomic_write(audit / 'result.json', json.dumps(dict(path=result.archived_path,
                    inspection=inspect_srs_document(result.reply_text)), ensure_ascii=False, indent=2))
                return
            repair = '; '.join(result.validation.errors) if result.validation else result.error
        raise SystemExit('SRS did not pass within three attempts; inspect audit')
    work = project / 'workspace/autodev'
    work.mkdir(parents=True, exist_ok=True)
    config = work / 'config.yaml'
    if not config.exists():
        source = (ROOT / 'config.yaml').read_text()
        tail = source[source.index('agent_registry:'):]
        tail = tail.replace('config/agents.toml', str(ROOT / 'config/agents.toml'))
        config.write_text(tail)
        result = register_project(work, project.name, str(project), init_git=True)
        assert result['status'] == 'registered'
        content = config.read_text().replace('\nagent_registry:',
            '\n    context:\n      - docs/business-input.md\n      - docs/defaults.md\n\nagent_registry:', 1)
        config.write_text(content)
    cfg = config.read_text()
    agents, roles, limits = parse_agents(cfg), parse_roles(cfg), parse_limits(cfg)
    limits['step_timeout_minutes'] = 15
    limits['step_retries'] = 1
    reference = work / 'handoff.json'
    if not reference.exists():
        srs = json.loads((project / 'workspace/requirements/result.json').read_text())['path']
        handoff = handoff_srs_to_pipeline(srs, root=work, project=project.name, config_yaml=config)
        atomic_write(reference, json.dumps(handoff, ensure_ascii=False, indent=2))
    handoff = json.loads(reference.read_text())
    run_dir = Path(handoff['run_dir'])
    classification = classify(load_rules(), CASE)
    selection = select(load_library(), dict(CASE, level=classification['level']), classification['security_override'])
    plan = dict(schema_version='1.0', need_type='SOFTWARE', project_type='web_application',
        design_level=classification['level'], features=CASE['features'], risks=CASE['risks'],
        required_artifacts=[f'A{i:02}' for i in range(1, 9)],
        mandatory_rules=[r['rule_id'] for r in selection['applicable']],
        classification_rationale=classification['reasons'],
        strategy=dict(independent_review=True, prototype_candidates=1, architecture_candidates=2),
        assumptions=['用户授权默认设计；HTML原型使用虚构数据，真实连接由后续开发实现'],
        open_questions=[])
    atomic_write(work / 'classification.json', json.dumps(dict(case=CASE, classification=classification, selection=selection), ensure_ascii=False, indent=2))

    if args.phase == 'validate':
        state = Run(run_dir).read()
        sd = run_dir / 'S2-design' / f"round-{state['round']}"
        pack = sd / 'design'
        result = validate_pack(pack)
        checks = []
        check = lambda name, passed: checks.append(dict(id=name, passed=bool(passed)))
        paths = ['manifest.json', 'plan.json', 'handoff.json', 'artifacts/ui.json',
            'artifacts/technical.json', 'artifacts/data.json', 'artifacts/security.json',
            'artifacts/openapi.yaml', 'artifacts/prototype/index.html']
        for path in paths:
            check('file:' + path, (pack / path).is_file())
        hand = json.loads((pack / 'handoff.json').read_text())
        srs = Path(handoff['source_srs']).read_text()
        requirements = {f'FR-{n:02}' for n in range(1, 11)}
        acceptance = set(re.findall(r'AC-[0-9]+', srs))
        check('requirement-task-coverage', requirements <= {r for t in hand['tasks'] for r in t['requirement_ids']})
        check('acceptance-task-coverage', acceptance <= {r for t in hand['tasks'] for r in t['acceptance_ids']})
        graphlib.TopologicalSorter({t['task_id']: t['dependencies'] for t in hand['tasks']}).prepare()
        check('task-dependencies-acyclic', True)
        data = json.loads((pack / 'artifacts/data.json').read_text())
        entity_ids = {e['id'] for e in data['entities']}
        for entity in data['entities']:
            names = {f['name'] for f in entity['fields']}
            check('primary-key:' + entity['id'], set(entity['primary_key']) <= names)
            check('data-relations:' + entity['id'], all(r['to'] in entity_ids for r in entity.get('relations', [])))
        api = json.loads((pack / 'artifacts/openapi.yaml').read_text())
        check('openapi-version', api.get('openapi') == '3.0.3')
        check('api-auth-default', bool(api.get('security')))
        api_schemas = api['components']['schemas']
        entities = {e['id']: e for e in data['entities']}
        canonical = lambda entity, field: next(f['enum'] for f in entities[entity]['fields'] if f['name'] == field)
        check('enum:Evidence.verification_status', api_schemas['VerificationStatus']['enum'] == canonical('Evidence', 'verification_status'))
        for entity, field in [('Approval', 'state'), ('KnowledgeItem', 'kind'), ('AgentRun', 'status'), ('ToolCall', 'status')]:
            check('enum:' + entity + '.' + field, api_schemas[entity]['properties'][field]['enum'] == canonical(entity, field))
        check('new-matter-citation-no-target-version', 'target_version_id' not in api_schemas['CitationCreate'].get('required', []))
        check('contract-version-maps-deliverable', 'deliverable_version_id' in api_schemas['ContractVersion']['required'] and not api_schemas['ContractVersion']['properties']['deliverable_version_id'].get('nullable', False))
        def refs(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == '$ref':
                        target = api
                        assert child.startswith('#/'), 'External API references not supported in this test'
                        for part in child[2:].split('/'):
                            target = target[part.replace('~1', '/').replace('~0', '~')]
                    else:
                        refs(child)
            elif isinstance(value, list):
                for child in value:
                    refs(child)
        refs(api)
        check('openapi-refs-resolve', True)
        ui = json.loads((pack / 'artifacts/ui.json').read_text())
        check('ui-pages', len(ui.get('pages', [])) >= 5)
        check('ui-interactions', len(ui.get('interactions', [])) >= 8)
        check('classification-not-self-reported', json.loads((pack / 'plan.json').read_text()) == plan)
        browser = pack / 'prototype-validation.json'
        check('browser-real-flow-tested', browser.is_file() and json.loads(browser.read_text()).get('passed') is True)
        result['supplemental_checks'] = checks
        result['ready_for_coding'] = result['ready_for_coding'] and all(c['passed'] for c in checks)
        atomic_write(pack / 'validation.json', json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result['ready_for_coding'] else 2)

    def invoke(sd, timeout_s):
        state = Run(run_dir).read()
        stage = state['stage']
        is_design = stage == 'S2'
        agent_name = roles['designer' if is_design else 'design_reviewer']
        allowed = DESIGN_FILES if is_design else {'review.md'}
        context = (sd / 'input.md').read_text()
        review_chunks = []
        paths = [project / 'docs/business-input.md', project / 'docs/defaults.md',
                 Path(handoff['source_srs'])]
        context += '\n\n' + '\n\n'.join(f'FILE {p.name}\n{p.read_text()}' for p in paths)
        if is_design:
            schemas = {p.name: json.loads(p.read_text()) for p in (ROOT / 'design-system/schemas').glob('*.json')}
            context += '\n程序固定计划（不要另写plan.json）：\n' + json.dumps(plan, ensure_ascii=False)
            context += '\n严格遵循本批附带的Schema；不允许增加未声明字段。'
            context += '''
本次用户授权扩展本轮设计输出：生成V2.1结构化设计文档和HTML原型的规格，不写目标产品代码，不修改旧模板。所有产物涵盖五类法律业务、六步核心流程、Agent自主工具计划/依据、律师复核和知识复用。Markdown仍满足原模板；其余按给定Schema。
SRS中的FR/AC编号必须原样映射；handoff引用设计包内路径如artifacts/technical.json。任务编号TASK-001等，每条适用规则绑到具体任务，安全规则交代所有程序选出的规则。每个数据实体要有tenant_id，明确客户client_id隔离、主键、枚举、时间规则、版本、证据和删除行为。technical的decisions必须比较至少2个架构/运行方案，说明默认取舍；ai.json设计工具白名单、注入隔离、成本/重试、证据与人工关口。workflows.json写完整状态转移及拒绝路径。ui.json包含pages与interactions数组，每项有id、requirement_ids、route、状态/预期结果；HTML后续按它生成。
openapi.yaml用JSON格式（JSON也是合法YAML），OpenAPI 3.0.3，必须有授权/客户隔离、事项、Agent运行、成果版本、退回复核/批准、交付/归档、知识复用和合同修订/Word导出接口，所有请求响应/错误的Schema引用可解析。Word修订设计为真正的OOXML跟踪修订，不能把文本改后缀伪装docx。演示数据不写未经核实的真实法律条文。生成完整而紧凑的设计，前端原型本次稍后生成，不假装已经测试。
'''
        else:
            design_sd = run_dir / 'S2-design' / f"round-{state['round']}"
            pack = design_sd / 'design'
            scopes = {
                'contracts': ['artifacts/data.json', 'artifacts/openapi.yaml', 'artifacts/consistency.json', 'handoff.json'],
                'frontend': ['artifacts/prototype/index.html', 'artifacts/prototype/styles.css', 'artifacts/prototype/app.js', 'artifacts/ui.json', 'prototype-validation.json', 'artifacts/consistency.json'],
                'orchestration': ['design.md', 'dev-plan.md', 'artifacts/technical.json', 'artifacts/security.json', 'artifacts/ai.json', 'artifacts/workflows.json', 'artifacts/consistency.json'],
            }
            reviews = []
            for scope, names in scopes.items():
                bodies = []
                hashes = {}
                for name in names:
                    body = (pack / name).read_text()
                    hashes[name] = hashlib.sha256(body.encode()).hexdigest()
                    if name.endswith(('.json', '.yaml')):
                        body = json.dumps(json.loads(body), ensure_ascii=False, separators=(',', ':'))
                    bodies.append('FILE ' + name + '\n' + body)
                prompt = context + '\n当前专项：' + scope + '\n' + '\n'.join(bodies)
                prompt += ('\n只审核本专项完整文件及相互一致性，其他专项另行审查，不因本专项未提供其他文件报全包缺失。'
                    '逐条对照SRS，HTML服务为模拟不是生产验证。仅实质critical/high导致REWORK。'
                    '只返回JSON，不带围栏：verdict(PASS/REWORK/BLOCK)、scope、findings列表'
                    '(id/severity/location/problem/expected)、requirement_coverage字符串列表。')
                reply = run_model(dict(role='design_reviewer', agent=agents[agent_name],
                    prompt='独立专项审查，返回JSON。', input=prompt), min(timeout_s, 240))
                result = json.loads(reply.strip().removeprefix('```json').removesuffix('```').strip())
                atomic_write(sd / f'focused-{scope}.json', json.dumps(result, ensure_ascii=False, indent=2))
                atomic_write(sd / f'focused-{scope}-raw.json', json.dumps(dict(
                    requested_model=agents[agent_name]['model'], input_sha256=hashes, reply=reply), ensure_ascii=False, indent=2))
                reviews.append(result)
            review = aggregate_reviews(reviews)
            atomic_write(sd / 'review.md', review)
            verdict = re.search(r'^verdict: (PASS|REWORK|BLOCK)$', review, re.M).group(1)
            atomic_write(sd / 'done.json', json.dumps(dict(id=state['id'], stage='S3', round=state['round'],
                role=state['step']['role'], verdict=verdict, outputs=['review.md'],
                summary='三个实际模型专项审查的确定性合并；保留所有发现', finished_at=now_iso()), ensure_ascii=False, indent=2))
            return dict(ok=True)
        context += '\n只返回一个合法JSON对象，不带解释或Markdown围栏，形如 {"files":{"path":"text or nested JSON object"}}。files的键必须恰好是：' + json.dumps(sorted(allowed))
        files = {}
        groups = [{path} for path in [
            'design/artifacts/technical.json', 'design.md', 'design/artifacts/data.json',
            'design/handoff.json', 'design/artifacts/security.json', 'dev-plan.md',
            'prototype.md', 'design/artifacts/ui.json', 'design/artifacts/openapi.yaml',
            'design/artifacts/workflows.json', 'design/artifacts/ai.json',
        ]] if is_design else [allowed]
        for index, group in enumerate(groups, 1):
            cached = {path: (sd / path) for path in group}
            if is_design and all(path.is_file() for path in cached.values()):
                for path, file in cached.items():
                    files[path] = json.loads(file.read_text()) if file.suffix in {'.json', '.yaml'} else file.read_text()
                print(f'{stage} reusing persisted artifact: {sorted(group)}', flush=True)
                continue
            batch_prompt = context + '\n本次分批生成以减少单次输出，最终键清单以上文为背景，本批只生成这些键：' + json.dumps(sorted(group))
            existing = {p: v for p, v in files.items() if p.endswith(('technical.json', 'handoff.json'))}
            batch_prompt += '\n已完成的关联设计（必须保持一致）：' + json.dumps(existing, ensure_ascii=False)
            if is_design:
                batch_schemas = {Path(path).stem+'.schema.json': schemas[Path(path).stem+'.schema.json'] for path in group if Path(path).stem+'.schema.json' in schemas}
                batch_prompt += '\n本批严格Schema：' + json.dumps(batch_schemas, ensure_ascii=False)
            batch_prompt += '\n每次仅生成当前一个文件，最大约3500汉字，JSON要完整，不要同义重复。\n原型已按定稿SRS生成并实测，页面路由为#/home、#/consultation、#/contracts、#/research、#/compliance、#/clients、#/knowledge、#/audit、#/matter/<id>。不要改名为另一套页面。每个文件紧凑但具体，禁止空壳、不得删除功能或只输出计划。'
            started = time.monotonic()
            try:
                reply = run_model(dict(role=state['step']['role'], agent=agents[agent_name],
                    prompt='按input内任务返回严格JSON文件映射。全部信息已给定，仅生成文本，不调用工具或请求许可。', input=batch_prompt), min(timeout_s, 180))
                parsed = ParsedOutput(reply=reply)
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                reply, parsed = '', ParsedOutput(error=str(exc))
            result = RunnerResult(ok=not parsed.error, parsed=parsed, duration_sec=time.monotonic()-started,
                output=reply, model_name=agent_name, full_model_id=agents[agent_name]['model'],
                vendor=agents[agent_name]['vendor'], mode='worker-tools-disabled')
            atomic_write(sd / f"model-call-a{state['step']['attempt']}-batch{index}.json", json.dumps(asdict(result), ensure_ascii=False, indent=2))
            if not result.ok:
                return dict(ok=False, reason='command_failed', detail=result.parsed.error)
            try:
                batch = parse_files(result.parsed.reply, group)
            except (ValueError, TypeError) as exc:
                return dict(ok=False, reason='invalid_output', detail=str(exc))
            files.update(batch)
            for path, value in batch.items():
                atomic_write(sd / path, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
            print(f'{stage} batch {index}/{len(groups)} persisted: {sorted(group)}', flush=True)
        try:
            assert set(files) == allowed
            for path, value in files.items():
                atomic_write(sd / path, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
            if is_design:
                atomic_write(sd / 'design/plan.json', json.dumps(plan, ensure_ascii=False, indent=2))
                verdict = 'DONE'
            else:
                text = files['review.md']
                verdict = re.search(r'^verdict:\s*(PASS|REWORK|BLOCK)\s*$', text, re.M).group(1)
            outputs = ['design.md', 'dev-plan.md', 'prototype.md'] if is_design else ['review.md']
            atomic_write(sd / 'done.json', json.dumps(dict(id=state['id'], project=state['project'],
                stage=stage, round=state['round'], role=state['step']['role'], summary='真实模型完成本轮设计/独立审查，详细证据见文件',
                verdict=verdict, outputs=outputs, finished_at=now_iso()), ensure_ascii=False, indent=2))
            return dict(ok=True)
        except (ValueError, TypeError, AttributeError) as exc:
            return dict(ok=False, reason='invalid_output', detail=str(exc))

    ctrl = Controller(work, agents, roles, limits, invoke_fn=invoke)
    for _ in range(30):
        state = Run(run_dir).read()
        if args.phase == 'design' and state['stage'] != 'S2':
            break
        if args.phase == 'review' and state['stage'] != 'S3':
            break
        if state['status'] != 'active':
            break
        print(ctrl.advance(run_dir), flush=True)
    print(json.dumps(Run(run_dir).read(), ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
