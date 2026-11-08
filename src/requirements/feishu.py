"""Trusted local JSON pipe for the existing Feishu bridge; no second SDK connection."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from channels.feishu import FeishuRequirements
from channels.gateway import ChannelError,MessageGateway
from requirements.agent import DemoAgent,HubAgent,load_settings
from requirements.messaging import RequirementsMessages
from requirements.versioned_session import SessionError,SessionStore


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',required=True)
    ap.add_argument('--home')
    ap.add_argument('--config')
    ap.add_argument('--demo',action='store_true')
    args=ap.parse_args(argv)
    try:
        raw=sys.stdin.read(256001)
        if len(raw.encode())>256000:raise ValueError('oversized request')
        envelope=json.loads(raw)
        users=envelope['allowed_users']
        if not isinstance(users,list) or not all(isinstance(x,str) and x for x in users):raise ValueError('invalid whitelist')
        invoke=DemoAgent() if args.demo else HubAgent(args.root,args.home) if args.home else None
        store=SessionStore(args.root,invoke=invoke,settings=load_settings(args.config),demo=args.demo)
        gateway=MessageGateway(args.root,{'requirements':RequirementsMessages(store)},{('feishu',x) for x in users})
        result=FeishuRequirements(gateway).handle(envelope['actor'],envelope['chat_id'],envelope['message_id'],envelope['text'])
        result['text']=result['text'].replace('<at','〈at')
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (SessionError,ChannelError) as e:
        print(json.dumps(dict(text=str(e),error=e.code),ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps(dict(text='需求入口配置或记录异常，请先查看本机工作台；未自动重试。',error='bridge-error'),ensure_ascii=False))
        return 1

if __name__=='__main__':sys.exit(main())
