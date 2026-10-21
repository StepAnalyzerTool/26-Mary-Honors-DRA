// Exercise the actual player with a minimal browser harness. No copied state
// machine or video substitute is used in the deployed app.
const assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm');
const profiles=JSON.parse(fs.readFileSync(__dirname+'/media.json')).profiles;
function harness(profile){
  const callbacks={},messages=[],elements={},actions={},timerButtons=[],resetButtons=[];
  let now=0, frame;
  class Element{
    constructor(){this.textContent='';this.style={};this.checked=false;this.disabled=false;this.dataset={};this.classList={toggle(){}};}
    append(){} remove(){} addEventListener(name,fn){callbacks[name]=fn;}
  }
  const video=new Element();video.readyState=4;video.seeking=false;let current=0;
  video.pause=()=>{};video.play=()=>Promise.resolve();video.load=()=>{};
  Object.defineProperty(video,'currentTime',{get:()=>current,set:v=>{current=v;const f=callbacks.seeked;delete callbacks.seeked;if(f)f();}});
  elements.video=video;
  for(const a of ['provide','direction','remove_sheet','give_toy','remove_toy','stop_tap','stop_bang','praise']){actions[a]=new Element();actions[a].dataset.action=a;}
  for(let i=0;i<2;i++){timerButtons[i]=new Element();timerButtons[i].dataset.timer=String(i);resetButtons[i]=new Element();resetButtons[i].dataset.reset=String(i);}
  const document={body:{scrollHeight:800},getElementById:id=>elements[id]??=(new Element()),
    querySelectorAll:s=>s==='[data-action]'?Object.values(actions):s==='[data-timer]'?timerButtons:resetButtons,
    querySelector:s=>timerButtons[Number(s.match(/\d/)[0])],addEventListener:()=>{},createElement:()=>new Element()};
  const window={parent:{postMessage:m=>messages.push(m)},addEventListener:(name,fn)=>callbacks['window_'+name]=fn};
  const context={window,document,performance:{now:()=>now},ResizeObserver:class{observe(){}},
    requestAnimationFrame:fn=>frame=fn,SpeechSynthesisUtterance:class{},console};
  vm.runInNewContext(fs.readFileSync(__dirname+'/frontend/player.js','utf8'),context);
  callbacks.window_message({source:window.parent,data:{type:'streamlit:render',args:{run:{id:profile.id},profile,video:'TEST',rules_version:'test',media_version:'test'}}});
  function tick(seconds=1){now+=seconds*1000;frame();}
  function clip(name){current=profile.segments[name][1];tick();}
  function snapshot(){elements.save.onclick();return messages.filter(m=>m.type==='streamlit:setComponentValue').at(-1).value;}
  return {elements,actions,video,messages,tick,clip,snapshot,render:callbacks.window_message,parent:window.parent};
}
for(const p of profiles){
  const h=harness(p);h.elements.begin.onclick();h.actions.provide.onclick();h.clip('present');
  h.actions.direction.onclick();h.clip('work_1');
  if(!p.automatic_second){const old=h.video.currentTime;h.actions.stop_tap.onclick();assert.equal(h.video.currentTime,old);h.actions.direction.onclick();}
  h.clip('work_2');
  h.actions.give_toy.onclick();h.clip('give_sheet');
  if(p.id==='banging_pause'){
    h.actions.remove_sheet.onclick();assert(h.snapshot().events.some(e=>e.event==='unsupported_transition'));
    h.actions.remove_toy.onclick();h.clip('remove_toy_sheet_2');h.actions.remove_sheet.onclick();h.clip('remove_sheet_2');
  }else{
    h.actions.remove_sheet.onclick();h.clip('remove_sheet_toy_2');h.actions.remove_toy.onclick();h.clip('remove_toy_no_sheet');
  }
  const r=h.snapshot();assert.equal(r.events.filter(e=>e.event==='problem_completed').length,2);
  assert(r.events.some(e=>e.event==='dolphin_removed'));assert(r.events.some(e=>e.event==='worksheet_removed'));
  const time=h.video.currentTime;
  h.render({source:h.parent,data:{type:'streamlit:render',args:{run:{id:p.id}}}});
  assert.equal(h.video.currentTime,time,'Saving a record restarted the video');
  h.elements.end.onclick();const stopped=h.snapshot().elapsed;h.tick(20);assert.equal(h.snapshot().elapsed,stopped,'Ended clock kept advancing');
}
const h=harness(profiles[1]);h.elements.begin.onclick();h.actions.provide.onclick();h.clip('present');
const before=h.video.currentTime;h.actions.give_toy.onclick();assert.equal(h.video.currentTime,before);
assert(h.snapshot().events.some(e=>e.event==='unsupported_transition'&&e.requested_action==='give_toy'));
h.tick(601);assert.equal(h.snapshot().ended,true);
console.log('Player checks passed: all three filmed paths, behavior persistence, missing branches, save continuity, cutoff and stopped clock.');
