"""Fixed document contracts, local completion checks and deterministic output."""
import hashlib
import json


class DocumentError(ValueError):
    pass


SECTIONS = {'goal': '项目背景与目标', 'audience': '使用者与业务场景',
            'scope': '本期范围与不做事项', 'constraints': '约束与特别要求'}
CHECKLIST = [{'id': key, 'question': question, 'required': True, 'allow_na': key == 'constraints'}
             for key, question in [
                 ('goal', '解决什么问题，本期想达到什么结果？'),
                 ('audience', '谁会使用，在什么场景下使用？'),
                 ('functions', '主要功能和业务规则是什么？'),
                 ('scope', '本期做什么、不做什么？'),
                 ('constraints', '有哪些技术、数据、时间或其他特别约束？'),
                 ('acceptance', '怎样判断交付符合需求？')]]
PLACEHOLDERS = {'', 'todo', '待补充', '待定', 'tbd', '...'}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(draft):
    return hashlib.sha256(encoded(draft).encode()).hexdigest()


def text(value):
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def require(condition, message):
    if not condition:
        raise DocumentError(message)


def fields(obj, required, optional=()):
    require(isinstance(obj, dict), '必须是 JSON 对象')
    require(set(required) <= set(obj) <= set(required) | set(optional),
            '对象字段不符合协议：' + ', '.join(sorted(obj)))


def items(value, keys, optional=()):
    require(isinstance(value, list), '必须是列表')
    seen = set()
    for item in value:
        fields(item, keys, optional)
        require(text(item.get('id')) and len(item['id']) <= 80 and item['id'] not in seen, 'ID 为空或重复')
        seen.add(item['id'])
        yield item


def validate_draft(draft, source_ids, checklist=None):
    checklist = CHECKLIST if checklist is None else checklist
    fields(draft, ['schema_version', 'sections', 'functions', 'acceptance', 'checklist', 'suggestions', 'open_questions'])
    require(type(draft['schema_version']) is int and draft['schema_version'] == 1, '不支持的 schema_version')
    fields(draft['sections'], SECTIONS)
    require(all(isinstance(v, str) for v in draft['sections'].values()), '章节必须是文本')
    for name in ['functions', 'acceptance']:
        for item in items(draft[name], ['id', 'text', 'sources']):
            require(isinstance(item['text'], str), '条目必须是文本')
    for item in items(draft['checklist'], ['id', 'status', 'answer', 'sources']):
        require(item['status'] in {'open', 'answered', 'not-applicable'}, '非法清单状态')
        require(isinstance(item['answer'], str), '清单回答必须是文本')
    require({x['id'] for x in draft['checklist']} == {x['id'] for x in checklist}, '清单条目不完整或未知')
    for item in items(draft['suggestions'], ['id', 'text', 'status'], ['sources']):
        require(isinstance(item['text'], str) and item['status'] in {'proposed', 'accepted', 'rejected'}, '非法建议')
    for item in items(draft['open_questions'], ['id', 'text', 'blocking'], ['sources']):
        require(isinstance(item['text'], str) and type(item['blocking']) is bool, '非法待定问题')
    for name in ['functions', 'acceptance', 'checklist', 'suggestions', 'open_questions']:
        for item in draft[name]:
            sources = item.get('sources', [])
            require(isinstance(sources, list) and all(isinstance(s, str) and s in source_ids for s in sources),
                    '来源引用不存在')
    return draft


def check_draft(draft, checklist=None):
    checklist = CHECKLIST if checklist is None else checklist
    missing = ['sections.' + k for k in SECTIONS if not text(draft['sections'][k])]
    for name in ['functions', 'acceptance']:
        if not draft[name] or any(not text(x['text']) or not x['sources'] for x in draft[name]):
            missing.append(name)
    by_id = {x['id']: x for x in draft['checklist']}
    for spec in checklist:
        item = by_id[spec['id']]
        valid = text(item['answer']) and bool(item['sources']) and (
            item['status'] == 'answered' or item['status'] == 'not-applicable' and spec['allow_na'])
        if spec['required'] and not valid:
            missing.append('checklist.' + spec['id'])
    missing.extend('open_questions.' + x['id'] for x in draft['open_questions'] if x['blocking'])
    for x in draft['suggestions']:
        if x['status'] == 'accepted' and not x.get('sources'):
            missing.append('suggestions.' + x['id'] + '.sources')
    return missing


def validate_review(review, version, content_hash):
    fields(review, ['reply', 'version', 'hash', 'verdict', 'findings'])
    require(isinstance(review['reply'], str), '审核回复必须是文本')
    require(type(review['version']) is int and review['version'] == version and review['hash'] == content_hash,
            '审核版本或哈希不匹配')
    require(review['verdict'] in {'PASS', 'REWORK', 'NEEDS_HUMAN'}, '非法审核结论')
    for item in items(review['findings'], ['id', 'location', 'evidence', 'problem', 'expected', 'blocking']):
        require(all(text(item[k]) for k in ['location', 'evidence', 'problem', 'expected'])
                and type(item['blocking']) is bool, '审核问题字段无效')
    require(review['verdict'] != 'PASS' or not any(x['blocking'] for x in review['findings']), 'PASS 不能含阻碍问题')
    require(review['verdict'] != 'REWORK' or bool(review['findings']), 'REWORK 必须说明问题')
    return review


def render(draft):
    lines = ['# 需求说明书', '']
    for key, title in SECTIONS.items():
        lines += ['## ' + title, '', draft['sections'][key] or '（待补充）', '']
    for key, title in [('functions', '功能与业务规则'), ('acceptance', '验收标准')]:
        lines += ['## ' + title, '']
        lines += [f"- {item['id']}：{item['text']}" for item in draft[key]] or ['（待补充）']
        lines += ['']
    lines += ['## 清单处理', '']
    lines += [f"- {item['id']} [{item['status']}]：{item['answer']}" for item in draft['checklist']]
    for key, title in [('suggestions', '建议及采纳状态'), ('open_questions', '待定问题')]:
        lines += ['', '## ' + title, '']
        lines += [f"- {item['id']}：{item['text']}（{item.get('status', '阻碍' if item.get('blocking') else '不阻碍')}）"
                  for item in draft[key]] or ['无']
    return '\n'.join(lines) + '\n'
