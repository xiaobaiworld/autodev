"""Explicit paid smoke: isolated AutoLoop, anonymous requirement, two real models.

Run only with --real. No automatic user confirmation or external messages.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from requirements.agent import HubAgent, load_settings
from requirements.session import SessionStore
from driver.hub import Hub, load_config


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--real',action='store_true',required=True)
    ap.add_argument('--root',type=Path,required=True)
    args=ap.parse_args()
    root=args.root.resolve(); root.mkdir(parents=True,exist_ok=True)
    home=root/'hub'
    if home.exists():
        raise SystemExit('Use a fresh root; do not reuse an existing hub')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    bindir=root/'bin';bindir.mkdir()
    notify=bindir/'osascript';notify.write_text('#!/bin/sh\nexit 0\n');notify.chmod(0o755)
    env=dict(os.environ,AGENT_AUTOLOOP_HOME=str(home),PATH=str(bindir)+':'+os.environ['PATH'])
    cli=['node','--disable-warning=ExperimentalWarning',str(Path('~/code/agent-autoloop/bin/agent-autoloop.ts').expanduser())]
    subprocess.run(cli+['init','--command','true {prompt}','--no-service','--port',str(port)],env=env,check=True,capture_output=True)
    proc=subprocess.Popen(cli+['up'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        hub=Hub(load_config(home))
        for _ in range(60):
            try:
                hub.state();break
            except Exception:
                time.sleep(.1)
        settings=load_settings();settings['timeout_s']=100;settings['review_limit']=2
        for agent in settings['agents'].values():agent['effort']='low'
        store=SessionStore(root,invoke=HubAgent(root,home,hub=hub),settings=settings)
        text='''目标：本机社区活动报名演示，组织者查看报名。
用户：组织者和匿名居民；单用户本机使用，不做账号登录。
功能：居民填写非空昵称报名；重复昵称拒绝；组织者可以查看昵称列表。
范围：只报名和查询，不做支付、通知、删除、公开部署或真实个人信息。
约束：只用匿名演示资料，存本机 JSON；只监听本机，不要求联网或并发。
验收：提交昵称“小树”后查询能看到一条；重复提交仍一条并提示重复；空昵称拒绝且数据不变。
暂无其他需求；以上规则已经由提出者决定，其他建议不自动采纳。'''
        s=store.create('匿名真实模型验收',text)
        print('session',s['id'],flush=True)
        s=store.advance(s['id'])
        summary={k:s[k] for k in ['id','status','version','hash','waiting_reason','error','check']}
        summary['calls']=[{k:c[k] for k in ['kind','status','elapsed_ms','agent']} for c in s['calls']]
        (root/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
        return 0 if s['check']['ready_to_confirm'] else 2
    finally:
        os.killpg(proc.pid,signal.SIGTERM)
        try:proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait()

if __name__=='__main__':sys.exit(main())
