"""Feishu text commands over the platform-neutral authenticated message gateway."""
import re

from .gateway import ChannelError

HELP = '''需求工作台（CLI、网页与飞书共用后端）
/需求 新建 项目名 | 你的想法
/需求 列表
/需求 查看 会话ID
/需求 回复 会话ID | 补充或修改
/需求 继续 会话ID
/需求 重试 会话ID
/需求 确认 会话ID 版本号 完整哈希
/需求 导出 会话ID 版本号
/需求 修订 会话ID
/需求 绑定 本机生成的配对码
新建和回复会调用模型；确认必须明确指定已审核的当前版本。
也可使用 /req 前缀。'''
ACTIONS={'列表':'list','查看':'show','继续':'step','重试':'retry','修订':'reopen',
         '确认':'confirm','导出':'export','绑定':'bind','新建':'create','回复':'reply'}


def parse_command(text):
    from requirements.versioned_session import SessionError
    if not isinstance(text,str) or len(text.encode())>128000:
        raise SessionError('invalid-input','需求消息为空或过大')
    head,_,rest=text.strip().partition(' ')
    if head not in {'/需求','/req'}:
        raise SessionError('invalid-input','使用 /需求 或 /req 开始命令')
    rest=rest.strip()
    if rest in {'','帮助','help'}:
        return {'action':'help'}
    verb,_,args=rest.partition(' ')
    verb=ACTIONS.get(verb,verb)
    args=args.strip()
    if verb=='list' and not args:
        return dict(action=verb)
    if verb in {'create','reply'}:
        target,sep,body=args.partition('|')
        if not sep or not target.strip() or not body.strip():
            raise SessionError('invalid-input','请用“项目名或会话ID | 内容”格式，参见 /需求 帮助')
        return dict(action=verb,**{('project_id' if verb=='create' else 'session_id'):target.strip()},text=body.strip())
    if verb=='bind' and re.fullmatch('[a-f0-9]{12}',args):
        return dict(action='bind',code=args)
    parts=args.split()
    if verb in {'show','step','retry','reopen'} and len(parts)==1:
        return dict(action=verb,session_id=parts[0])
    if verb in {'confirm','export'} and len(parts)==(3 if verb=='confirm' else 2):
        if not re.fullmatch('[1-9][0-9]*',parts[1]) or verb=='confirm' and not re.fullmatch('[a-f0-9]{64}',parts[2]):
            raise SessionError('invalid-input','确认需完整版本号和64位哈希；请复制“查看”返回的确认命令')
        result=dict(action=verb,session_id=parts[0],version=int(parts[1]))
        if verb=='confirm':result['hash']=parts[2]
        return result
    raise SessionError('invalid-input','不支持的需求命令，请发送 /需求 帮助')


def present(result):
    value=result['session']
    if isinstance(value,list):
        lines=[f"{s['id']} · {s['project_id']} · {s['status']} · v{s['version']}" for s in value]
        return dict(text='需求列表\n'+('\n'.join(lines) or '暂无已绑定需求。发送 /需求 新建 项目名 | 想法'))
    if 'confirmation' in value:
        return dict(text=f"已确认需求 {value['session_id']} · v{value['version']}",
                    file=dict(filename=f"{value['session_id']}-v{value['version']}.md",text=value['markdown']))
    s=value
    lines=[f"{s['project_id']} · {s['id']} · v{s['version']} · {s['status']}"]
    if s['demo']:lines.append('无费用演示：模拟草稿和审核')
    for call in s['calls'][-2:]:
        if call.get('reply'):lines.append(call['reply'])
    if s['check']['missing']:lines.append('待补充：'+'、'.join(s['check']['missing']))
    review=s.get('latest_review')
    if review:
        lines.append('独立审核：'+review['verdict'])
        lines.extend(f"{x['id']}：{x['problem']}\n待处理：{x['expected']}" for x in review['findings'])
    if s['error']:lines.append(s['error']['message'])
    if s['waiting_reason']=='review-limit':lines.append('自动审核达到上限，请补充你的决定后再继续。')
    if s['check']['ready_to_confirm'] and s['status']=='waiting-human':
        lines += ['请先阅读随附需求文档，再复制以下命令确认：',f"/需求 确认 {s['id']} {s['version']} {s['hash']}"]
    elif s['status']=='waiting-human':
        lines.append(f"补充：/需求 回复 {s['id']} | 你的回答")
    elif s['status']=='error':lines.append(f"显式重试：/需求 重试 {s['id']}")
    if s['status']=='completed':lines.append(f"导出：/需求 导出 {s['id']} {s['version']}")
    out=dict(text='\n\n'.join(lines))
    if s['markdown']:out['file']=dict(filename=f"{s['id']}-v{s['version']}.md",text=s['markdown'])
    return out


class FeishuRequirements:
    def __init__(self,gateway):
        self.gateway=gateway

    def handle(self,actor,chat_id,message_id,text):
        if ('feishu',actor) not in self.gateway.allowed:
            raise ChannelError('forbidden','消息来源不在授权名单中')
        command=parse_command(text)
        if command['action']=='help':return dict(text=HELP)
        result=self.gateway.receive('feishu',actor,chat_id,message_id+':command','requirements',command)
        if command['action'] in {'create','reply','retry'}:
            sid=result['session']['id']
            result=self.gateway.receive('feishu',actor,chat_id,message_id+':advance','requirements',dict(action='step',session_id=sid))
        return present(result)
