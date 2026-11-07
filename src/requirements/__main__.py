"""CLI client for the reusable SessionStore application API."""
import argparse
import json
from pathlib import Path
import sys
import uuid

from .agent import DemoAgent, HubAgent, ROOT, load_settings
from .session import SessionError, SessionStore


def parser():
    ap = argparse.ArgumentParser(description='需求工作台：CLI 与网页共享同一会话后端')
    ap.add_argument('--root', default=str(ROOT), help='AutoDev 数据根目录')
    ap.add_argument('--config', default=str(ROOT / 'config.yaml'))
    ap.add_argument('--home', help='运行中的 AutoLoop home；真实 step 必需')
    ap.add_argument('--demo', action='store_true', help='无费用模拟模式，与真实会话隔离')
    ap.add_argument('--json', action='store_true', help='输出结构化结果')
    sub = ap.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--project', required=True)
    source = create.add_mutually_exclusive_group(required=True)
    source.add_argument('--text'); source.add_argument('--request', type=Path)
    create.add_argument('--analyst'); create.add_argument('--reviewer')
    create.add_argument('--review-limit', type=int)
    sub.add_parser('list')
    for name in ['show', 'step', 'retry', 'reopen', 'reply', 'confirm', 'export']:
        cmd = sub.add_parser(name)
        cmd.add_argument('id')
        if name == 'reply':
            src = cmd.add_mutually_exclusive_group(required=True)
            src.add_argument('--text'); src.add_argument('--file', type=Path)
            cmd.add_argument('--message-id', default=None)
        if name in {'confirm', 'export'}:
            cmd.add_argument('--version', type=int, required=True)
        if name == 'confirm':
            cmd.add_argument('--hash', required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', default=8765, type=int)
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        invoke = DemoAgent() if args.demo else HubAgent(args.root, args.home) if args.home else None
        store = SessionStore(args.root, invoke=invoke, settings=load_settings(args.config), demo=args.demo)
        cmd = args.command
        if cmd == 'serve':
            from .web import make_server
            server = make_server(store, host=args.host, port=args.port)
            print(f'需求工作台 http://{args.host}:{server.server_port}（{"无费用演示" if args.demo else "真实模型模式"}）', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        if cmd == 'create':
            result = store.create(args.project, args.request.read_text() if args.request else args.text,
                                  analyst=args.analyst, reviewer=args.reviewer, review_limit=args.review_limit)
        elif cmd == 'list':
            result = store.list_sessions()
        elif cmd == 'reply':
            result = store.submit(args.id, args.file.read_text() if args.file else args.text, args.message_id or uuid.uuid4().hex)
        elif cmd == 'show':
            result = store.status(args.id)
        elif cmd == 'step':
            result = store.advance(args.id)
        elif cmd == 'confirm':
            result = store.confirm(args.id, args.version, args.hash)
        elif cmd == 'export':
            result = store.export(args.id, args.version)
        else:
            result = getattr(store, cmd)(args.id)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif cmd == 'export':
            print(result['markdown'], end='')
        elif isinstance(result, list):
            for s in result:
                print(s['id'], s['project_id'], s['status'], 'v' + str(s['version']))
        else:
            print(f"{result['id']} · {result['project_id']} · {result['status']} · v{result['version']}")
            if result['demo']:
                print('无费用演示：草稿和审核由模拟器生成')
            for call in result['calls'][-2:]:
                if call['reply']:
                    print(call['reply'])
            if result['check']['missing']:
                print('待补充：' + '、'.join(result['check']['missing']))
            if result['error']:
                print(result['error']['message'])
            if result['check']['ready_to_confirm'] and result['status'] != 'completed':
                print(result['markdown'])
                print(f"确认当前版本：confirm {result['id']} --version {result['version']} --hash {result['hash']}")
        return 2 if isinstance(result, dict) and result.get('status') == 'error' else 0
    except (SessionError, ValueError, OSError) as e:
        error = dict(code=getattr(e, 'code', 'configuration-error'), message=str(e))
        if args.json:
            print(json.dumps(dict(error=error), ensure_ascii=False))
        else:
            print(error['message'], file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
