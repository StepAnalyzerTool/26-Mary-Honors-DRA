/* Actions and session timing stay in the browser. No Streamlit rerun occurs
   when an action is pressed. Missing footage never prevents an action. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id),video=$('video');
  let args,run,bank=[],runId,trial=0,scenario,primary,currentRecord=null;
  let started=false,ended=false,startingAt=null,stoppedAt=null,events=[];
  let sheet=false,toy=false,problems=0,writing=false,instruction=false,prompts=0;
  let flow=false,earnedDelivered=false,resumeWork=null,segment=null,onEnd=null,sequence=0;
  let timers=[{at:null,elapsed:0},{at:null,elapsed:0}];
  const post=(type,data)=>window.parent.postMessage({isStreamlitMessage:true,type,...data},'*');
  const resize=()=>post('streamlit:setFrameHeight',{height:document.body.scrollHeight+14});
  const elapsed=()=>startingAt===null?null:((stoppedAt??performance.now())-startingAt)/1000;
  const stamp=()=>elapsed()===null?null:Math.round(elapsed()*1000)/1000;
  const state=()=>({worksheet:sheet,dolphin:toy,problems,writing});
  function log(event,extra={}){
    events.push({event,elapsed:stamp(),trial,scenario_id:scenario?.scenario_id??null,
      source_time:Math.round(video.currentTime*1000)/1000,recording_id:currentRecord?.id??null,
      segment:segment?.name??null,...state(),...extra});details();
  }
  function payload(){return {schema:'dra-video-session-mockup-2',purpose:'Playback testing; not scored research data',
    session:run,rules_version:args.rules_version,media_version:args.media_version,
    sources:bank.map(r=>({id:r.id,filename:r.filename,asset_id:r.asset_id,sha256:r.sha256})),
    ended,elapsed:stamp(),trials_presented:trial,events};}
  const save=()=>post('streamlit:setComponentValue',{value:payload(),dataType:'json'});
  function details(){
    $('details').textContent=`Trial ${trial}/${run?.trial_count??0} | Scenario ${scenario?.scenario_id??'—'} | `+
      `Set ${run?.set_id??'—'} | ${problems} completed | Worksheet ${sheet?'present':'absent'} | `+
      `Dolphin ${toy?'present':'absent'} | ${currentRecord?.filename??'No source'} | `+
      `${segment?.name??'Footage gap'} | ${events.length} events`;
  }
  function controls(){
    document.querySelectorAll('[data-action]').forEach(b=>b.disabled=!started||ended);
    $('begin').disabled=!args||started||video.readyState<2;$('save').disabled=!started;$('end').disabled=!started||ended;
  }
  function speech(text){
    if(!$('speech').checked||!('speechSynthesis' in window))return;
    window.speechSynthesis.cancel();window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
  }
  function chooseClip(key){
    let candidates=[currentRecord,primary,...bank].filter(Boolean);
    candidates=candidates.filter((r,i,a)=>a.findIndex(x=>x.id===r.id)===i&&r.behavior===primary.behavior&&r.segments[key]);
    const noSheet=['idle','finished','give_no_sheet','toy_no_sheet','remove_toy_no_sheet'].includes(key);
    if(key.startsWith('work_'))candidates=candidates.filter(r=>r.id===primary.id);
    else if(!noSheet&&problems>0)candidates=candidates.filter(r=>r.worksheet_key===primary.worksheet_key);
    return candidates[0]??null;
  }
  function gap(key){
    sequence++;video.pause();segment=null;onEnd=null;
    $('gap').textContent=`Footage pending for this state: ${primary.behavior==='none'?'no tapping or banging':primary.behavior==='tapping'?'finger tapping':'table banging'}; `+
      `${problems} problem(s) completed; worksheet ${sheet?'present':'absent'}; dolphin ${toy?'available':'absent'}. `+
      'Your action was recorded. You can continue using the buttons.';
    $('gap').style.display='flex';$('status').textContent='Mockup footage gap';
    log('footage_gap',{requested_clip:key});resize();
  }
  function play(key,loop=true,done=null){
    const record=chooseClip(key);
    if(!record){gap(key);return false;}
    const token=++sequence,range=record.segments[key],changed=currentRecord?.id!==record.id;
    video.pause();segment={name:key,start:range[0],end:range[1],loop};onEnd=done;
    if(changed&&currentRecord)log('cross_take_cut',{from:currentRecord.id,to:record.id});
    currentRecord=record;$('gap').style.display='none';
    const beginPlay=()=>{
      if(token!==sequence||ended)return;
      video.play().catch(()=>{
        $('status').textContent='Browser paused the video. Select Resume video.';
        let b=$('resume');if(!b){b=document.createElement('button');b.id='resume';b.textContent='Resume video';$('status').append(b);}
        b.onclick=()=>video.play().then(()=>b.remove()).catch(()=>{});log('playback_blocked');
      });
      log('clip_started',{clip:key,clip_start:range[0],clip_end:range[1]});
    };
    const seek=()=>{
      if(token!==sequence)return;
      if(Math.abs(video.currentTime-range[0])<.02)beginPlay();
      else{video.addEventListener('seeked',beginPlay,{once:true});video.currentTime=range[0];}
    };
    if(changed){video.addEventListener('loadedmetadata',seek,{once:true});video.src=args.videos[record.id];video.load();}
    else seek();
    details();return true;
  }
  function wait(){
    writing=false;
    const key=toy?(sheet?`toy_sheet_${problems}`:'toy_no_sheet'):(sheet?`wait_${problems}`:'finished');
    play(key);$('status').textContent=segment?'Session in progress':'Mockup footage gap';
  }
  function finish(reason){
    if(ended||!started)return;
    stoppedAt=performance.now();ended=true;sequence++;video.pause();log('session_ended',{reason});
    timers.forEach(t=>{if(t.at!==null){t.elapsed+=(stoppedAt-t.at)/1000;t.at=null;}});
    $('finished').style.display='block';$('status').textContent='Session ended';controls();save();resize();
  }
  function settle(){
    if(ended)return;
    if(trial===run.trial_count&&!sheet&&!toy&&(problems<2||earnedDelivered)){finish('planned trials completed');return;}
    if(sheet&&!toy){
      if(resumeWork){const n=resumeWork;resumeWork=null;work(n);return;}
      if(problems===0&&[0,1,5].includes(scenario.group)){work(1);return;}
      if(problems===1&&(scenario.group===0||(scenario.group===2&&flow))){work(2);return;}
    }
    wait();
  }
  function transition(key){
    if(!play(key,false,settle)){
      log('direct_cut',{missing_transition:key});settle();
    }
  }
  function work(n){
    if(ended||!sheet||toy)return;
    writing=true;log('problem_started',{problem:n});
    if(!play(`work_${n}`,false,()=>{
      problems=n;writing=false;log('problem_completed',{problem:n,marker:'Provisional clip endpoint'});settle();
    }))writing=false;
  }
  function interrupt(reason){
    if(writing){resumeWork=problems+1;log('work_interrupted',{reason});}
    writing=false;
  }
  function action(name){
    if(!started||ended)return;
    log('button_pressed',{action:name});
    const words={direction:'Do your math work',stop_tap:'Please stop tapping the table',stop_bang:'Please stop banging the table',praise:'Good job!'};
    if(words[name])speech(words[name]);
    if(['stop_tap','stop_bang','praise'].includes(name))return;
    if(name==='direction'){
      if(!sheet){log('task_direction',{classification:'without worksheet'});return;}
      if(!instruction){instruction=true;log('initial_instruction');return;}
      prompts++;log('prompt_delivered',{prompt_number:prompts,during_work:writing});
      if(writing||toy)return;
      if(problems===0&&[2,3].includes(scenario.group)){flow=true;work(1);}
      else if(problems===1&&scenario.group===5)work(2);
      return;
    }
    if(name==='provide'){
      if(sheet){log('additional_worksheet_attempt');return;}
      if(trial>=run.trial_count){log('worksheet_attempt_after_planned_trials');return;}
      scenario=run.plan[trial];trial++;primary=bank.find(r=>r.id===scenario.recording_id);
      problems=0;writing=false;instruction=false;prompts=0;flow=false;earnedDelivered=false;resumeWork=null;sheet=true;
      $('trial').textContent=`Trial ${trial} of ${run.trial_count}`;
      log('worksheet_presented',{toy_carried_over:toy,footage_adapted:scenario.footage_adapted});
      if(toy)wait();else transition('present');
      return;
    }
    if(name==='remove_sheet'){
      if(!sheet){log('worksheet_removal_attempt_without_worksheet');return;}
      interrupt('worksheet removal');resumeWork=null;sheet=false;
      log('worksheet_removed');transition(toy?`remove_sheet_toy_${problems}`:`remove_sheet_${problems}`);return;
    }
    if(name==='give_toy'){
      if(toy){log('dolphin_delivery_attempt_while_available');return;}
      interrupt('dolphin delivery');toy=true;earnedDelivered=earnedDelivered||problems===2;log('dolphin_provided',{earned:problems===2});
      transition(sheet?`give_sheet_${problems}`:'give_no_sheet');return;
    }
    if(name==='remove_toy'){
      if(!toy){log('dolphin_removal_attempt_without_dolphin');return;}
      toy=false;log('dolphin_removed');transition(sheet?`remove_toy_sheet_${problems}`:'remove_toy_no_sheet');
    }
  }
  function start(){
    if(started||!args)return;
    started=true;startingAt=performance.now();log('session_started');play('idle');controls();
  }
  function format(seconds){const n=Math.max(0,Math.floor(seconds));return String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0');}
  function tick(){
    $('clock').textContent=format(elapsed()??0);
    if(started&&!ended&&elapsed()>=600)finish('10-minute cutoff');
    timers.forEach((t,i)=>$('timer'+i).textContent=format(t.elapsed+(t.at===null?0:(performance.now()-t.at)/1000)));
    if(started&&!ended&&segment&&!video.seeking&&video.currentTime>=segment.end-.025){
      if(segment.loop){video.currentTime=segment.start;log('loop_restart');}
      else{const callback=onEnd;onEnd=null;segment=null;video.pause();if(callback)callback();}
    }
    requestAnimationFrame(tick);
  }
  $('begin').onclick=start;$('save').onclick=save;$('end').onclick=()=>finish('participant ended');
  $('fullscreen').onclick=()=>{if(video.requestFullscreen)video.requestFullscreen().catch(()=>{});else if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();};
  document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>action(b.dataset.action));
  document.querySelectorAll('[data-timer]').forEach(b=>b.onclick=()=>{
    const i=Number(b.dataset.timer),t=timers[i];
    if(t.at===null){t.at=performance.now();b.textContent='Stop';}else{t.elapsed+=(performance.now()-t.at)/1000;t.at=null;b.textContent='Start';}
    if(started&&!ended)log('timer_toggle',{timer:i+1,running:t.at!==null});
  });
  document.querySelectorAll('[data-reset]').forEach(b=>b.onclick=()=>{
    const i=Number(b.dataset.reset);timers[i]={at:null,elapsed:0};document.querySelector(`[data-timer="${i}"]`).textContent='Start';
    if(started&&!ended)log('timer_reset',{timer:i+1});
  });
  video.addEventListener('waiting',()=>{if(started&&!ended){$('status').textContent='Loading video…';log('video_waiting');}});
  video.addEventListener('loadeddata',controls);
  video.addEventListener('playing',()=>{$('status').textContent=started?'Session in progress':'Ready. Select BEGIN.';});
  video.addEventListener('error',()=>{log('video_error',{code:video.error?.code});$('status').textContent='Video playback failed. The session record retains this error.';});
  document.addEventListener('visibilitychange',()=>{if(started&&!ended)log('page_visibility',{hidden:document.hidden});});
  window.addEventListener('message',event=>{
    if(event.source!==window.parent||event.data?.type!=='streamlit:render')return;
    const next=event.data.args;if(next.run.id===runId)return;
    args=next;run=args.run;runId=run.id;bank=args.recordings;primary=bank.find(r=>r.id===run.plan[0].recording_id);
    $('recording').textContent=`${run.trial_count} trials · maximum 10 minutes`;
    $('trial').textContent='Session ready';$('status').textContent='Select BEGIN, then provide the first worksheet.';
    currentRecord=primary;
    video.addEventListener('loadedmetadata',()=>{if(!started)video.currentTime=primary.segments.idle[0];},{once:true});
    video.src=args.videos[primary.id];video.load();
    controls();details();resize();
  });
  new ResizeObserver(resize).observe(document.body);
  post('streamlit:componentReady',{apiVersion:1});resize();requestAnimationFrame(tick);
})();
