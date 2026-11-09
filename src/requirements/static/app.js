'use strict';
const $ = id => document.getElementById(id);
let config, current = null, sessionList = [], poll = null, loadSequence = 0, submitting = false;
const pending = new Set();
const labels = {ready:'准备处理',working:'正在梳理',reviewing:'独立审核中','waiting-human':'等待你回应',completed:'已确认完成',error:'需要处理'};
const kinds = {clarify:'需求梳理',review:'独立审核',revise:'回应与修订'};
const verdicts = {PASS:'通过',REWORK:'需要修订',NEEDS_HUMAN:'需要你决定'};
const names = {goal:'背景与目标',audience:'使用者与场景',scope:'本期范围',constraints:'约束要求',functions:'功能与规则',acceptance:'验收标准',draft:'需求草稿'};
const example = '目标：让社区活动接受报名\n用户：活动组织者和居民\n功能：居民填写昵称报名，组织者查询报名清单\n范围：本期报名与查询，不做支付\n约束：只用匿名演示数据\n验收：居民报名后，组织者可以查询到昵称';
function notify(text='') { $('notice').textContent = text; }
function node(tag, value, className) { const n=document.createElement(tag); n.textContent=value; if(className)n.className=className; return n; }
function missingName(value) { const parts=value.split('.'); return names[parts[1]] || names[parts[0]] || (parts[0]==='open_questions'?'待决定问题':'清单待补充项'); }
async function api(path, body) {
  const response=await fetch(path,body===undefined ? {cache:'no-store'} : {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':config.csrf_token},body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error?.message || '请求失败');
  return data;
}
async function guarded(fn) { try { notify(); await fn(); } catch(e) { notify(e.message); } }
function drawList() {
  $('sessions').replaceChildren();
  const query=$('search').value.trim().toLowerCase();
  const list=sessionList.filter(s=>(s.project_id+' '+s.id).toLowerCase().includes(query));
  for(const s of list) {
    const b=node('button','',s.id===current?.id?'active':'');
    if(s.id===current?.id)b.setAttribute('aria-current','page');
    b.append(node('span',s.project_id),node('small',`${labels[s.status]||s.status} · 版本 ${s.version}`));
    b.onclick=()=>guarded(()=>load(s.id)); $('sessions').append(b);
  }
  if(!list.length)$('sessions').append(node('p',query?'没有找到相关需求':'还没有需求会话','hint'));
}
async function sessions() { sessionList=await api('/api/sessions'); drawList(); }
function showTab(name) {
  for(const key of ['document','review','calls']) {
    $('tab-'+key).setAttribute('aria-selected',String(key===name));
    $('tab-'+key).tabIndex=key===name?0:-1;
    $('panel-'+key).hidden=key!==name;
  }
}
function documentView(draft) {
  const target=$('document'); target.replaceChildren();
  if(!draft) {
    target.append(node('div','需求说明书会在这里逐步成形。\n先描述你的想法，后续每轮补充都会保留版本。','document-empty')); return;
  }
  for(const [key,title] of [['goal','背景与目标'],['audience','使用者与场景'],['functions','功能与业务规则'],['scope','本期范围与不做事项'],['constraints','约束与特别要求'],['acceptance','验收标准']]) {
    target.append(node('h3',title));
    if(['functions','acceptance'].includes(key)) {
      const list=node('ul','');
      for(const item of draft[key])list.append(node('li',`${item.id} · ${item.text}`));
      target.append(draft[key].length?list:node('p','待补充'));
    } else target.append(node('p',draft.sections[key] || '待补充'));
  }
  for(const [key,title] of [['suggestions','建议与采纳状态'],['open_questions','待定问题']]) {
    if(!draft[key].length)continue;
    target.append(node('h3',title));
    for(const item of draft[key])target.append(node('p',`${item.text} · ${{proposed:'未采纳',accepted:'已采纳',rejected:'不采纳'}[item.status] || (item.blocking?'需先解决':'可后续补充')}`));
  }
}
function render(s) {
  const previous=current;
  current=s; $('empty').hidden=true; $('workspace').hidden=false;
  $('session-id').textContent=s.id; $('project').textContent=s.project_id;
  $('state').textContent=labels[s.status]||s.status;
  $('version').textContent=s.version?'v'+s.version:'草稿待生成';
  $('conversation-meta').textContent=`第 ${s.round} 轮 · ${s.messages.length} 条输入`;
  const phase=s.status==='completed' || s.check.ready_to_confirm?'confirm':s.status==='reviewing'||s.phase==='review'||s.phase==='revise'?'review':'clarify';
  const stages=['clarify','review','confirm'];
  for(const [i,k] of stages.entries())$('stage-'+k).className=i<stages.indexOf(phase)||s.status==='completed'?'done':k===phase?'active':'';
  const busy=pending.has(s.id)||['working','reviewing'].includes(s.status);
  const next=s.status==='completed'?'这个版本已确认，可以交给后续规划，也可以开启新修订。':busy?'模型正在处理。你可以查看文档和记录，完成后会自动更新。':s.waiting_reason==='review-limit'?'两模型尚有分歧：请查看审核意见，补充你的决定。':s.waiting_reason==='review-decision'?'有一项取舍需要你决定：请先看审核意见。':s.check.ready_to_confirm?'独立审核已通过。请阅读右侧文档，再确认当前版本。':s.status==='error'?'本次处理没有完成。请查看错误提示后显式重试。':'请补充你的背景、要求，或回答上一轮提出的问题。';
  $('next-action').textContent=next;
  const timeline=[];
  for(const m of s.messages)timeline.push({at:m.at,role:'你',text:m.text,user:true});
  for(const c of s.calls)if(c.reply)timeline.push({at:c.finished_at||c.started_at,role:kinds[c.kind],text:c.reply,user:false});
  timeline.sort((a,b)=>a.at.localeCompare(b.at));
  const box=$('messages');
  const nearBottom=box.scrollHeight-box.scrollTop-box.clientHeight<60;
  const scroll=box.scrollTop;
  box.replaceChildren();
  for(const m of timeline) {
    const n=node('div','',`message${m.user?' user':''}`),heading=node('small',m.role);
    const date=new Date(m.at);heading.append(node('time',Number.isNaN(date.getTime())?'':date.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})));
    n.append(heading,node('div',m.text,'message-text'));box.append(n);
  }
  if(!previous||previous.id!==s.id||nearBottom)box.scrollTop=box.scrollHeight;else box.scrollTop=scroll;
  documentView(s.draft);
  $('missing').textContent=s.check.missing.length?'还需要明确：'+[...new Set(s.check.missing.map(missingName))].join('、'):'';
  const r=s.latest_review;
  $('review').textContent=r?`${verdicts[r.verdict]||r.verdict}\n\n${r.reply}${r.findings.length?'\n\n'+r.findings.map(f=>`${f.id} · ${f.problem}\n依据：${f.evidence}\n需要处理：${f.expected}`).join('\n\n'):''}`:'还没有独立审核意见。\n\n需求内容齐全后，会交给另一个模型核对；需要修改时，先由两个模型交流修订。';
  $('send').disabled=busy||submitting||s.status!=='waiting-human'; $('answer').disabled=busy||s.status!=='waiting-human';
  $('step').hidden=!['ready','working','reviewing'].includes(s.status); $('step').disabled=pending.has(s.id);
  $('retry').hidden=s.status!=='error'; $('reopen').hidden=s.status!=='completed';
  $('confirm').disabled=busy||!s.check.ready_to_confirm||s.status!=='waiting-human';
  $('confirm').textContent=s.status==='completed'?'✓ 当前版本已确认完成':`确认版本 ${s.version||'—'} 并完成`;
  $('confirm-hint').textContent=s.status==='completed'?'需求与审核依据已保存。下载后可交给后续计划使用。':s.check.ready_to_confirm?'确认仅对当前版本生效。后续修改会重新审核，并再次由你确认。':'完成需求梳理与独立审核后，这里会开放版本确认。';
  $('download').hidden=!s.confirmations.length;
  if(s.confirmations.length)$('download').href=`/api/sessions/${s.id}/export?version=${s.confirmations.at(-1).version}`;
  $('calls').replaceChildren();
  if(!s.calls.length)$('calls').append(node('div','尚未调用模型。每次处理的角色、结果和耗时将保存在这里。'));
  for(const c of s.calls)$('calls').append(node('div',`${kinds[c.kind]} · 第 ${c.attempt} 次尝试\n${c.status==='succeeded'?'已返回':c.status==='running'?'处理中':c.status==='interrupted'?'调用中断':c.status==='timed-out'?'超时':'失败'} · ${c.elapsed_ms===null?'耗时未知':(c.elapsed_ms/1000).toFixed(2)+' 秒'}\n${c.agent.model}`));
  if(s.error)notify(s.error.message);
  drawList();
}
async function load(id) {
  clearTimeout(poll);const ticket=++loadSequence;
  const s=await api('/api/sessions/'+id);
  if(ticket!==loadSequence)return;
  if(current?.id!==id){$('answer').value='';showTab('document');}
  render(s);await sessions();schedule();
}
function schedule() {
  clearTimeout(poll);
  if(!current || !(pending.has(current.id)||['ready','working','reviewing'].includes(current.status)))return;
  const id=current.id,ticket=loadSequence;
  poll=setTimeout(async()=>{
    try {
      const s=await api('/api/sessions/'+id);
      if(ticket!==loadSequence||current?.id!==id)return;
      if(['waiting-human','completed','error'].includes(s.status))pending.delete(id);
      render(s);await sessions();schedule();
    } catch(e) { notify('状态更新失败，可以点击刷新重新连接。'+e.message); }
  },1000);
}
async function step(id=current.id) {
  pending.add(id);if(current?.id===id)render(current);
  try { await api(`/api/sessions/${id}/step`,{}); if(current?.id===id)schedule(); }
  catch(e) { pending.delete(id); if(current?.id===id)render(current); throw e; }
}
function openCreate() { $('create-dialog').showModal();$('project-input').focus(); }
$('new-session').onclick=openCreate;$('start').onclick=openCreate;
$('cancel-create').onclick=()=>$('create-dialog').close();
$('refresh').onclick=()=>guarded(async()=>{await sessions();if(current)await load(current.id);});
$('search').oninput=drawList;
$('example').onclick=()=>{$('project-input').value='社区活动报名';$('initial').value=example;};
$('create-form').onsubmit=e=>{
  e.preventDefault();guarded(async()=>{
    $('create-submit').disabled=true;
    try {
      const s=await api('/api/sessions',{project_id:$('project-input').value,text:$('initial').value,analyst:$('analyst').value,reviewer:$('reviewer').value,review_limit:Number($('review-limit').value)});
      $('create-dialog').close();await load(s.id);await step(s.id);
    } finally { $('create-submit').disabled=false; }
  });
};
$('reply-form').onsubmit=e=>{
  e.preventDefault();if(submitting)return;
  guarded(async()=>{
    const id=current.id,text=$('answer').value;
    if(!text.trim())throw new Error('请先填写回答');
    submitting=true;render(current);
    try {
      const s=await api(`/api/sessions/${id}/reply`,{text,message_id:crypto.randomUUID()});
      if(current?.id===id){$('answer').value='';render(s);}
      await step(id);
    } finally {submitting=false;if(current)render(current);}
  });
};
$('step').onclick=()=>guarded(()=>step());
$('retry').onclick=()=>guarded(async()=>{const id=current.id;const s=await api(`/api/sessions/${id}/retry`,{});if(current?.id===id)render(s);await step(id);});
$('reopen').onclick=()=>guarded(async()=>{const id=current.id;const s=await api(`/api/sessions/${id}/reopen`,{});if(current?.id===id){render(s);$('answer').focus();}});
$('confirm').onclick=()=>guarded(async()=>{const {id,version,hash}=current;$('confirm').disabled=true;try{const s=await api(`/api/sessions/${id}/confirm`,{version,hash});if(current?.id===id)render(s);await sessions();}finally{if(current)render(current);}});
for(const key of ['document','review','calls']){
  $('tab-'+key).onclick=()=>showTab(key);
  $('tab-'+key).onkeydown=e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const keys=['document','review','calls'];const next=keys[(keys.indexOf(key)+(e.key==='ArrowRight'?1:2))%3];showTab(next);$('tab-'+next).focus();};
}
for(const [file,target] of [['initial-file','initial'],['reply-file','answer']])$(file).onchange=()=>guarded(async()=>{const f=$(file).files[0];if(!f)return;if(f.size>128000)throw new Error('资料不能超过 128KB');$(target).value=await f.text();$(file).value='';});
guarded(async()=>{
  config=await api('/api/config');$('mode').textContent=config.demo?'无费用演示':'真实工作空间';
  $('cost-hint').textContent=config.demo?'当前是无费用演示，结果由模拟器生成。':'开始梳理会调用你选择的模型并消耗额度。';
  if(!config.model_connected)notify('尚未连接模型后端，可以先阅读已有需求。');
  for(const id of ['analyst','reviewer'])for(const [name,a] of Object.entries(config.settings.agents)){
    if(!['claude','codex'].includes(a.cli))continue;
    const option=node('option',`${name} · ${a.vendor}`);option.value=name;$(id).append(option);
  }
  $('analyst').value=config.settings.analyst;$('reviewer').value=config.settings.reviewer;$('review-limit').value=config.settings.review_limit;
  await sessions();
  if(sessionList.length)await load(sessionList[0].id);
});
