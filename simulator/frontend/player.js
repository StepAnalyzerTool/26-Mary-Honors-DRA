/* Browser-side timing and playback stay in one component, so pressing a
   response never reruns Streamlit or reconstructs the video element. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const video = $('video');
  let args, profile, session, runId, segment = null, afterSegment = null;
  let started = false, ended = false, startingAt = null, stoppedAt = null, trial = 0;
  let sheet = false, toy = false, problems = 0, writing = false, busy = false;
  let transitionToken = 0, events = [], timers = [{at:null,elapsed:0},{at:null,elapsed:0}];
  let sendTimer = null;

  function post(type, data) { window.parent.postMessage({isStreamlitMessage:true,type,...data}, '*'); }
  function resize() { post('streamlit:setFrameHeight', {height:document.body.scrollHeight + 14}); }
  function elapsed() { return startingAt === null ? null : ((stoppedAt??performance.now())-startingAt)/1000; }
  function stamp() { const t=elapsed(); return t===null?null:Math.round(t*1000)/1000; }
  function state() { return {worksheet:sheet,dolphin:toy,problems,writing,transition:busy}; }
  function log(event, extra={}) {
    events.push({event,elapsed:stamp(),trial,source_time:Math.round(video.currentTime*1000)/1000,
      segment:segment?.name || null,...state(),...extra});
    details();
  }
  function payload() { return {schema:'dra-playback-mockup-1',purpose:'Playback testing only; not research fidelity data',
    run:session,rules_version:args.rules_version,media_version:args.media_version,
    source:{filename:profile.filename,asset_id:profile.asset_id,sha256:profile.sha256},
    ended,elapsed:stamp(),events}; }
  function save() { post('streamlit:setComponentValue', {value:payload(),dataType:'json'}); }
  function details() {
    $('details').textContent = `${profile?.filename || ''} | Trial ${trial} | ${problems} completed | `+
      `Worksheet ${sheet?'present':'absent'} | Dolphin ${toy?'present':'absent'} | Segment ${segment?.name || 'none'} | ${events.length} logged events`;
  }
  function notice(message) { $('notice').textContent=message; $('notice').classList.toggle('show',Boolean(message)); resize(); }
  function missing(action) {
    log('unsupported_transition',{requested_action:action});
    notice('No matching clip is configured for this action in this recording. The video state has been kept unchanged. This is a footage/editing gap, not a performance score. You can continue with another action or end the test.');
  }
  function speak(text) {
    if (!$('speech').checked || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
  }
  function controls() {
    document.querySelectorAll('[data-action]').forEach(b => { b.disabled=!started || ended; });
    $('begin').disabled=started || !video.readyState;
    $('end').disabled=!started || ended;
    $('save').disabled=!started;
  }
  function playSegment(name, loop=true, callback=null) {
    const range=profile.segments[name];
    if (!range) throw new Error(`Undefined segment: ${name}`);
    const token=++transitionToken;
    video.pause();
    segment={name,start:range[0],end:range[1],loop}; afterSegment=callback;
    const play=()=>{
      if (token!==transitionToken || ended) return;
      video.play().catch(()=>{
        $('status').textContent='Playback paused by the browser. Use Resume video.';
        let resume=$('resume');
        if (!resume) {resume=document.createElement('button');resume.id='resume';resume.textContent='Resume video';$('status').append(resume);}
        resume.onclick=()=>{video.play().then(()=>resume.remove()).catch(()=>{});};
        log('playback_blocked');
      });
      log('segment_started',{clip:name});
    };
    if (Math.abs(video.currentTime-range[0])<.02) play();
    else { video.addEventListener('seeked',play,{once:true}); video.currentTime=range[0]; }
    details();
  }
  function wait() {
    busy=false;writing=false;
    const name=toy ? (sheet?`toy_sheet_${problems}`:'toy_no_sheet') : (sheet?`wait_${problems}`:'finished');
    if (profile.segments[name]) playSegment(name); else {video.pause();log('missing_wait_clip',{clip:name});notice('A matching waiting clip is not available for this state.');}
    $('status').textContent='Playback test in progress'; details();
  }
  function move(name, change) {
    busy=true;
    playSegment(name,false,()=>{change();wait();});
  }
  function work(n) {
    busy=false; writing=true;
    log('problem_started',{problem:n});
    playSegment(`work_${n}`,false,()=>{
      problems=n; writing=false;log('problem_completed',{problem:n,marker:'Provisional clip endpoint'});
      if (n===1 && profile.automatic_second) work(2); else wait();
    });
  }
  function action(action) {
    if (!started || ended) return;
    log('button_pressed',{action}); notice('');
    const words={direction:'Do your math work',stop_tap:'Please stop tapping the table',stop_bang:'Please stop banging the table',praise:'Good job!'};
    if (words[action]) speak(words[action]);
    if (['stop_tap','stop_bang','praise'].includes(action)) return;
    if (action==='direction') {
      log('task_direction',{classification:sheet&&problems===0&&!events.some(e=>e.trial===trial&&e.event==='instruction_delivered')?'initial':'additional'});
      if (busy || writing || !sheet || toy || problems===2) return;
      if (problems===0) {log('instruction_delivered');work(1);} else work(2);
      return;
    }
    if (busy || writing) {missing(action);return;}
    if (action==='provide') {
      if (sheet || toy) {missing(action);return;}
      if (trial>=10) {notice('Ten test trials have been presented. End this test or load a new test.');return;}
      trial++; problems=0; sheet=true; log('worksheet_presentation_requested');
      $('trial').textContent=`Trial ${trial} · Playback test`;
      move('present',()=>log('worksheet_presented'));return;
    }
    if (action==='give_toy') {
      // This first manifest contains two-answer delivery clips only. Early
      // delivery must not reveal answers that the learner has not completed.
      if (toy || !sheet || problems!==2 || !profile.segments.give_sheet) {missing(action);return;}
      move('give_sheet',()=>{toy=true;log('dolphin_provided');});return;
    }
    if (action==='remove_sheet') {
      const clip=toy?`remove_sheet_toy_${problems}`:`remove_sheet_${problems}`;
      if (!sheet || !profile.segments[clip]) {missing(action);return;}
      move(clip,()=>{sheet=false;log('worksheet_removed');});return;
    }
    if (action==='remove_toy') {
      const clip=sheet?`remove_toy_sheet_${problems}`:'remove_toy_no_sheet';
      if (!toy || !profile.segments[clip]) {missing(action);return;}
      move(clip,()=>{toy=false;log('dolphin_removed');});
    }
  }
  function finish(reason) {
    if (ended || !started) return;
    stoppedAt=performance.now();ended=true;video.pause();transitionToken++;log('test_ended',{reason});
    timers.forEach(t=>{if(t.at!==null){t.elapsed+=(stoppedAt-t.at)/1000;t.at=null;}});
    $('finished').style.display='block';$('status').textContent='Test ended';
    controls(); save(); resize();
  }
  function start() {
    if (started || !video.readyState) return;
    started=true;startingAt=performance.now();log('session_started');
    playSegment('idle');controls();
  }
  function format(seconds) { const x=Math.max(0,Math.floor(seconds));return String(Math.floor(x/60)).padStart(2,'0')+':'+String(x%60).padStart(2,'0'); }
  function tick() {
    const now=elapsed();
    $('clock').textContent=format(now || 0);
    if (started && !ended && now>=600) finish('10-minute cutoff');
    timers.forEach((t,i)=>{$('timer'+i).textContent=format(t.elapsed+(t.at===null?0:(performance.now()-t.at)/1000));});
    if (!ended && segment && !video.seeking && video.currentTime>=segment.end-.025) {
      const callback=afterSegment;afterSegment=null;
      if (segment.loop) {video.currentTime=segment.start;log('loop_restart');}
      else {video.pause();segment=null;if(callback) callback();}
    }
    requestAnimationFrame(tick);
  }
  video.addEventListener('waiting',()=>{if(started&&!ended){$('status').textContent='Loading video…';log('video_waiting');}});
  video.addEventListener('playing',()=>{$('status').textContent=started?'Playback test in progress':'Ready. Select BEGIN.';});
  video.addEventListener('loadeddata',()=>{controls();$('status').textContent='Ready. Select BEGIN.';});
  video.addEventListener('error',()=>{notice('The browser could not play this recording. Try reloading the test.');log('video_error',{code:video.error?.code});});
  document.addEventListener('visibilitychange',()=>{if(started&&!ended)log('page_visibility',{hidden:document.hidden});});
  $('begin').onclick=start;$('save').onclick=save;$('end').onclick=()=>finish('tester ended');
  $('fullscreen').onclick=()=>{if(video.requestFullscreen)video.requestFullscreen().catch(()=>{});else if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();};
  document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>action(b.dataset.action));
  document.querySelectorAll('[data-timer]').forEach(b=>b.onclick=()=>{
    const i=Number(b.dataset.timer),t=timers[i];
    if(t.at===null){t.at=performance.now();b.textContent='Stop';}else{t.elapsed+=(performance.now()-t.at)/1000;t.at=null;b.textContent='Start';}
    if(started&&!ended)log('timer_toggle',{timer:i+1,running:t.at!==null});
  });
  document.querySelectorAll('[data-reset]').forEach(b=>b.onclick=()=>{const i=Number(b.dataset.reset);timers[i]={at:null,elapsed:0};document.querySelector(`[data-timer="${i}"]`).textContent='Start';if(started&&!ended)log('timer_reset',{timer:i+1});});
  window.addEventListener('message', event=>{
    if (event.source!==window.parent || event.data?.type!=='streamlit:render') return;
    const next=event.data.args;
    if (next.run.id===runId) return; // Saving a snapshot must not restart playback.
    args=next;profile=args.profile;session=args.run;runId=session.id;
    $('recording').textContent=profile.label;
    video.src=args.video;video.load();controls();details();resize();
  });
  new ResizeObserver(resize).observe(document.body);
  post('streamlit:componentReady',{apiVersion:1});resize();requestAnimationFrame(tick);
})();
