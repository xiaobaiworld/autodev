'use strict';
const $ = id => document.getElementById(id);
let config, current = null, working = false, poll = null;
const labels = {'ready':'待处理','working':'正在梳理','reviewing':'正在审核','waiting-human':'等待你','completed':'已确认完成','error':'需要处理'};
const kinds = {clarify:'需求梳理',review:'独立审核',revise:'回应与修订'};
const example = '目标：让社区活动接受报名\n用户：活动组织者和居民\n功能：居民填写昵称报名，组织者查询报名清单\n范围：本期报名与查询，不做支付\n约束：只用匿名演示数据\n验收：居民报名后，组织者可以查询到昵称';
function notify(text='') { $('notice').textContent = text; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {cache:'no-store'} : {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':config.csrf_token},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || '请求失败');
  return data;
}
async function guarded(fn) { try { notify(); await fn(); } catch (e) { notify(e.message); } }
function node(tag, value, className) { const n = document.createElement(tag); n.textContent = value; if(className)n.className=className; return n; }
async function sessions() {
  const list = await api('/api/sessions');
  $('sessions').replaceChildren();
  for (const s of list) { const b=node('button','',s.id===current?.id?'active':''); b.append(node('span',s.project_id),node('small',`${labels[s.status]||s.status} · v${s.version}`)); b.onclick=()=>guarded(()=>load(s.id)); $('sessions').append(b); }
  if (!list.length) $('sessions').append(node('p','还没有需求会话','hint'));
}
function render(s) {
  current=s; $('empty').hidden=true; $('workspace').hidden=false;
  $('session-id').textContent=s.id; $('project').textContent=s.project_id;
  $('state').textContent=labels[s.status]||s.status;
  $('version').textContent=s.version ? `版本 ${s.version} · ${s.hash.slice(0,12)}` : '草稿尚未生成';
  $('document').textContent=s.markdown||'你的想法会逐步整理成需求说明书。';
  $('messages').replaceChildren();
  const timeline=[];
  for(const m of s.messages) timeline.push({at:m.at,role:'你',text:m.text,user:true});
  for(const c of s.calls) if(c.reply) timeline.push({at:c.finished_at||c.started_at,role:kinds[c.kind],text:c.reply,user:false});
  timeline.sort((a,b)=>a.at.localeCompare(b.at));
  for(const m of timeline) { const n=node('div','',`message${m.user?' user':''}`); n.append(node('small',m.role),node('div',m.text)); $('messages').append(n); }
  $('missing').textContent=s.check.missing.length?'待补充：'+s.check.missing.join('、'):'';
  const r=s.latest_review;
  $('review').textContent=r?`审核：${r.verdict}\n${r.reply}${r.findings.length?'\n'+r.findings.map(f=>`${f.id} · ${f.problem}\n预期：${f.expected}`).join('\n'):''}`:'内容齐全后，将交给另一个模型审核。';
  const busy=working||['working','reviewing'].includes(s.status);
  $('send').disabled=busy||s.status!=='waiting-human'; $('answer').disabled=busy||s.status!=='waiting-human';
  $('step').hidden=!['ready','working','reviewing'].includes(s.status); $('step').disabled=working;
  $('retry').hidden=s.status!=='error'; $('reopen').hidden=s.status!=='completed';
  $('confirm').disabled=busy||!s.check.ready_to_confirm||s.status!=='waiting-human';
  $('confirm').textContent=s.status==='completed'?'当前版本已确认完成':`确认版本 ${s.version||'—'} 并完成`;
  $('confirm-hint').textContent=s.status==='completed'?'已保存审核依据和人工确认。你可以下载该固定版本，或开启后续修订。':s.waiting_reason==='review-limit'?'两模型已达到自动审核上限。请阅读分歧并补充你的决定，再继续。':s.check.ready_to_confirm?'请阅读当前需求及审核意见。确认只对当前版本生效，后续修改需要重新审核与确认。':'先补齐内容并通过独立审核，才能确认。';
  $('download').hidden=!s.confirmations.length;
  if(s.confirmations.length) $('download').href=`/api/sessions/${s.id}/export?version=${s.confirmations.at(-1).version}`;
  $('calls').replaceChildren();
  for(const c of s.calls) $('calls').append(node('div',`${kinds[c.kind]} · 第 ${c.attempt} 次尝试 · ${c.status} · ${c.elapsed_ms===null?'耗时未知':(c.elapsed_ms/1000).toFixed(2)+' 秒'}\n${c.agent.vendor} / ${c.agent.model}`));
  if(s.error) notify(s.error.message);
}
async function load(id) { render(await api('/api/sessions/'+id)); await sessions(); schedule(); }
function schedule() { clearTimeout(poll); if(current && (working||['ready','working','reviewing'].includes(current.status))) poll=setTimeout(()=>guarded(async()=>{ const s=await api('/api/sessions/'+current.id); if(['waiting-human','completed','error'].includes(s.status)) working=false; render(s); await sessions(); schedule(); }),1000); }
async function step() { working=true; render(current); try{ await api(`/api/sessions/${current.id}/step`,{}); schedule(); }catch(e){working=false; render(current); throw e;} }
function openCreate(){ $('create-dialog').showModal(); $('project-input').focus(); }
$('new-session').onclick=openCreate; $('start').onclick=openCreate;
$('cancel-create').onclick=()=>$('create-dialog').close(); $('refresh').onclick=()=>guarded(sessions);
$('example').onclick=()=>{ $('project-input').value='社区活动报名'; $('initial').value=example; };
$('create-form').onsubmit=e=>{e.preventDefault(); guarded(async()=>{const s=await api('/api/sessions',{project_id:$('project-input').value,text:$('initial').value,analyst:$('analyst').value,reviewer:$('reviewer').value,review_limit:Number($('review-limit').value)}); $('create-dialog').close(); await load(s.id); await step();});};
$('reply-form').onsubmit=e=>{e.preventDefault(); guarded(async()=>{const text=$('answer').value;if(!text.trim())throw new Error('请先填写回答'); const s=await api(`/api/sessions/${current.id}/reply`,{text,message_id:crypto.randomUUID()});$('answer').value='';render(s);await step();});};
$('step').onclick=()=>guarded(step);
$('retry').onclick=()=>guarded(async()=>{render(await api(`/api/sessions/${current.id}/retry`,{}));await step();});
$('reopen').onclick=()=>guarded(async()=>{render(await api(`/api/sessions/${current.id}/reopen`,{}));$('answer').focus();});
$('confirm').onclick=()=>guarded(async()=>{const id=current.id,v=current.version,h=current.hash;render(await api(`/api/sessions/${id}/confirm`,{version:v,hash:h}));await sessions();});
for(const [file,target] of [['initial-file','initial'],['reply-file','answer']]) $(file).onchange=()=>guarded(async()=>{const f=$(file).files[0];if(!f)return;if(f.size>128000)throw new Error('资料不能超过 128KB');$(target).value=await f.text();$(file).value='';});
guarded(async()=>{config=await api('/api/config'); $('mode').textContent=config.demo?'无费用演示':'真实模型'; if(!config.model_connected)notify('尚未配置中台连接；可以阅读和创建需求，运行模型前需通过 --home 指定 AutoLoop。'); for(const id of ['analyst','reviewer'])for(const [name,a] of Object.entries(config.settings.agents)){if(!['claude','codex'].includes(a.cli))continue;const option=node('option',`${name} · ${a.vendor}`);option.value=name;$(id).append(option);} $('analyst').value=config.settings.analyst;$('reviewer').value=config.settings.reviewer;$('review-limit').value=config.settings.review_limit;await sessions();});
