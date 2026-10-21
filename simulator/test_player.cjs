// Exercise the deployed browser state machine without duplicating its logic.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const bank=JSON.parse(fs.readFileSync(__dirname+'/media.json')).recordings;
const scenarios=JSON.parse(fs.readFileSync(__dirname+'/../dra_catalog_v1.json')).scenarios;
const behaviors={'No tapping or banging':'none','Finger tapping':'tapping','Table banging':'banging'};
const families=['together','one','together','one','zero','pause'];
function makePlan(ids){return ids.map((id,i)=>{
  const s=scenarios.find(x=>x.scenario_id===id),group=Math.floor((id-1)/3),behavior=behaviors[s.behavior];
  const primary=bank.find(r=>r.behavior===behavior&&r.family===families[group])??bank.find(r=>r.behavior===behavior&&r.capacity===2);
  return {...s,group,trial:i+1,recording_id:primary.id};
});}
function harness(ids,appRoot='https://example.test/',staticVideos=false){
  const callbacks={},messages=[],elements={},actions={},timerButtons=[],resetButtons=[];
  let now=0,frame,current=0;
  class Element{
    constructor(){this.textContent='';this.style={};this.checked=false;this.disabled=false;this.dataset={};this.classList={toggle(){}};}
    append(){}remove(){}addEventListener(name,fn){callbacks[name]=fn;}
  }
  const video=new Element();video.readyState=4;video.seeking=false;
  video.pause=()=>{};video.play=()=>Promise.resolve();
  video.load=()=>{current=0;const f=callbacks.loadedmetadata;delete callbacks.loadedmetadata;if(f)f();};
  Object.defineProperty(video,'currentTime',{get:()=>current,set:v=>{current=v;const f=callbacks.seeked;delete callbacks.seeked;if(f)f();}});elements.video=video;
  for(const a of ['provide','direction','remove_sheet','give_toy','remove_toy','stop_tap','stop_bang','praise']){actions[a]=new Element();actions[a].dataset.action=a;}
  for(let i=0;i<2;i++){timerButtons[i]=new Element();timerButtons[i].dataset.timer=String(i);resetButtons[i]=new Element();resetButtons[i].dataset.reset=String(i);}
  const document={body:{scrollHeight:800},getElementById:id=>elements[id]??=(new Element()),
    querySelectorAll:s=>s==='[data-action]'?Object.values(actions):s==='[data-timer]'?timerButtons:resetButtons,
    querySelector:s=>timerButtons[Number(s.match(/\d/)[0])],addEventListener:()=>{},createElement:()=>new Element()};
  const window={location:{href:appRoot+'component/app.dra_session/index.html'},parent:{postMessage:m=>messages.push(m)},addEventListener:(name,fn)=>callbacks['window_'+name]=fn};
  const context={URL,window,document,performance:{now:()=>now},ResizeObserver:class{observe(){}},requestAnimationFrame:fn=>frame=fn,SpeechSynthesisUtterance:class{},console};
  vm.runInNewContext(fs.readFileSync(__dirname+'/frontend/player.js','utf8'),context);
  const run={id:'TEST',set_id:'TEST',trial_count:ids.length,plan:makePlan(ids)};
  callbacks.window_message({source:window.parent,data:{type:'streamlit:render',args:{run,recordings:bank,videos:Object.fromEntries(bank.map(r=>[r.id,staticVideos?'/app/static/dra-playback/'+r.id+'.mp4':'TEST:'+r.id])),rules_version:'test',media_version:'test'}}});
  function snapshot(){elements.save.onclick();return messages.filter(m=>m.type==='streamlit:setComponentValue').at(-1).value;}
  function tick(seconds=1){now+=seconds*1000;frame();}
  function clip(){const e=snapshot().events.filter(e=>e.event==='clip_started').at(-1);current=e.clip_end;tick();}
  return {actions,elements,video,run,snapshot,tick,clip,render:callbacks.window_message,parent:window.parent};
}
function trial(h,s){
  h.actions.provide.onclick();h.actions.direction.onclick();h.clip(); // presentation; then automatic work or waiting
  if([2,3].includes(s.group))h.actions.direction.onclick();
  if(s.group!==4){
    h.clip(); // first completed problem
    if(s.group===5)h.actions.direction.onclick();
    if(s.completed)h.clip(); // second completed problem
  }else{h.actions.direction.onclick();h.actions.direction.onclick();}
  let record=h.snapshot(),last=record.events.at(-1);
  assert.equal(last.problems,s.completed?2:s.group===4?0:1,`wrong problem count for scenario ${s.scenario_id}`);
  const source=h.video.currentTime;h.actions.stop_tap.onclick();h.actions.stop_bang.onclick();h.actions.praise.onclick();assert.equal(h.video.currentTime,source);
  h.actions.remove_sheet.onclick();
  if(!h.snapshot().ended)h.clip();
  if(s.completed){
    assert.equal(h.snapshot().ended,false,'Worksheet-first completion ended before earned dolphin delivery');
    h.actions.give_toy.onclick();if(h.elements.gap.style.display!=='flex')h.clip();
    h.actions.remove_toy.onclick();if(!h.snapshot().ended)h.clip();
  }
}
for(const s of makePlan(Array.from({length:18},(_,i)=>i+1))){
  const h=harness([s.scenario_id]);h.elements.begin.onclick();trial(h,s);
  assert.equal(h.snapshot().ended,true,`scenario ${s.scenario_id} did not end`);
  assert.equal(h.snapshot().events.filter(e=>e.event==='problem_completed').length,s.completed?2:s.group===4?0:1);
}
const ten=harness([1,5,13,18,8,10,2,14,16,6]);ten.elements.begin.onclick();
for(const s of ten.run.plan)trial(ten,s);
assert.equal(ten.snapshot().trials_presented,10);assert.equal(ten.snapshot().events.filter(e=>e.event==='worksheet_presented').length,10);
assert(ten.snapshot().events.some(e=>e.event==='footage_gap'),'Missing table-banging toy footage was not flagged');
const stopped=ten.snapshot().elapsed;ten.tick(20);assert.equal(ten.snapshot().elapsed,stopped);
const early=harness([14]);early.elements.begin.onclick();early.actions.provide.onclick();early.clip();early.actions.give_toy.onclick();
assert(early.snapshot().events.some(e=>e.event==='dolphin_provided'&&e.earned===false),'Early dolphin delivery was blocked');
const position=early.video.currentTime;early.render({source:early.parent,data:{type:'streamlit:render',args:{run:{id:'TEST'}}}});assert.equal(early.video.currentTime,position);
early.tick(601);assert.equal(early.snapshot().ended,true);
const interrupted=harness([1]);interrupted.elements.begin.onclick();interrupted.actions.provide.onclick();interrupted.clip();interrupted.actions.remove_sheet.onclick();
assert.equal(interrupted.snapshot().events.filter(e=>e.event==='problem_completed').length,0,'Aborted work counted as complete');
console.log('Session player passed: all 18 scenarios, 10-trial progression, worksheet-first reward order, early delivery, behavior persistence, missing footage, interrupted work, save continuity and cutoff.');

for(const root of ['https://example.test/','https://example.test/~/+/','https://example.test/custom/']){
  const h=harness([1],root,true);
  assert.equal(h.video.src,root+'app/static/dra-playback/'+h.run.plan[0].recording_id+'.mp4');
  h.elements.begin.onclick();h.actions.provide.onclick();
  assert(h.video.src.startsWith(root+'app/static/'));
}
console.log('Video URLs retain the local, custom-base and Community Cloud app paths.');
