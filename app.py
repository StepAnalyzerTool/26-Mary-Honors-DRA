from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from dra import (load_catalog, load_guide, select_session, session_plan,
                 serialize_session, restore_session, summary_row, make_workbook)
from planner import learner_steps, fidelity_rows, fidelity_summary

from scoring import (TIMED_COMPONENTS, BEHAVIOR_COMPONENTS, RULES_VERSION,
                     CORRECT, OMISSION, COMMISSION, TIMING_OMISSION, TIMING_COMMISSION,
                     NA, INTERRUPTED, TERMINATED, MISSING, empty_trials, score_trials,
                     parse_time, timing_result)

st.set_page_config(page_title='DRA Session Coder', layout='wide')

@st.cache_data
def catalog_data():
    return load_catalog()

@st.cache_data
def guide_data():
    return load_guide()

def initialize():
    st.session_state.setdefault('trials', empty_trials())
    st.session_state.setdefault('session', {'date': str(date.today()), 'mode':'in_person'})
    st.session_state.setdefault('setup', {'arrange_materials':'Not recorded', 'prepare_reinforcers':'Not recorded'})
    st.session_state.setdefault('trial_index', 1)

def clear_plan_from_coding():
    # Strip plan data even from older restored backups; retain observed records.
    for key in ('set_id','catalog_version','ordered_scenario_ids','selected_at'):
        st.session_state.session.pop(key,None)
    for trial in st.session_state.trials:
        trial['scenario_id']=None

def has_coding():
    return any(t['trial_status']!='Not reached' or t.get('events') for t in st.session_state.trials)

def set_selection(selection):
    st.session_state['planner_selection']=dict(selection)
    st.session_state['learner_fidelity']={}
    for key in list(st.session_state):
        if key.startswith('leader_trial_'): del st.session_state[key]

def choice(label, options, current, key, **kwargs):
    if key not in st.session_state:
        st.session_state[key]=current if current in options else options[0]
    if st.session_state[key] not in options:
        st.session_state[key]=options[0]
    return st.selectbox(label, options, key=key, **kwargs)

def checked_choice(label, options, current, key, disabled=False):
    """Exclusive checkboxes; preserve canonical scores and clear sibling choices."""
    if key not in st.session_state: st.session_state[key]=current
    if disabled: st.session_state[key]=current
    def changed(selected, value):
        st.session_state[key]=value if st.session_state[selected] else MISSING
        for i in range(len(options)):
            sibling=f'{key}_check_{i}'
            st.session_state[sibling]=st.session_state[key]==options[i][1]
    st.write(label)
    columns=st.columns(len(options))
    for i,(caption,value) in enumerate(options):
        widget=f'{key}_check_{i}'
        st.session_state[widget]=st.session_state[key]==value
        with columns[i]:
            st.checkbox(caption,key=widget,disabled=disabled,on_change=changed,args=(widget,value))
    return st.session_state[key]

ACTION_QUESTIONS={
 'worksheet':('Was the worksheet presented?','Was it presented within 3 seconds of the session start or preceding trial ending?'),
 'instruction':('Was an initial instruction given?','Was it given within 3 seconds of worksheet presentation?'),
 'prompt_1':('Was the first required prompt given?','Was it given on time (8–12 seconds after the applicable reference)?'),
 'prompt_2':('Was the second required prompt given?','Was it given on time (8–12 seconds after the applicable reference)?'),
 'worksheet_removal':('Was the worksheet removed?','Was it removed on time for the selected removal reference?'),
 'earned_dolphin':('Was the dolphin given after two problems were completed?','Was it given within 3 seconds of the second problem being completed?'),
 'dolphin_removal':('Was the dolphin removed?','Was it removed after 13–17 seconds of access?'),
}
BEHAVIOR_QUESTIONS={
 'no_unearned':'Was the dolphin withheld while fewer than two problems were complete?',
 'no_excess':'Did the participant give no more than two prompts in this trial?',
 'no_work_prompts':'Did the participant refrain from prompting during ongoing work?',
 'no_tapping_comments':'Did the participant refrain from telling the learner to stop tapping?',
 'no_banging_comments':'Did the participant refrain from telling the learner to stop banging?',
}

def text(label, value, key, **kwargs):
    if key not in st.session_state:
        st.session_state[key]=str(value or '')
    return st.text_input(label, key=key, **kwargs)

def rule_help(sections):
    for section in sections:
        entries=guide_data().get(section, [])
        if entries:
            st.markdown(f'**{section}**')
            st.dataframe(pd.DataFrame([{'Entry':e['entry'],'Rule':e['rule'],'Example':e.get('example','')} for e in entries]), hide_index=True, use_container_width=True)

def timers():
    with st.expander('Optional timing tools'):
        st.caption('Independent timers for coding aids. They do not score events or change the learner’s behavior.')
        components.html('''
        <style>body{font:15px Arial;color:#203a52}.timers{display:flex;gap:25px;flex-wrap:wrap}.clock{font-size:32px;margin:8px 0}button{padding:7px 11px;margin:2px;border:1px solid #b3c5d1;background:#edf3f8;border-radius:5px}input{width:75px}</style>
        <div class="timers" id="timers"></div>
        <script>
        const root=document.getElementById('timers');
        for(let i=0;i<2;i++){
          const block=document.createElement('div');
          block.innerHTML='<div class="clock">00:00.0</div><button>Start</button><button>Stop</button><button>Reset</button><br><input type="number" min="0" value="0" aria-label="Countdown seconds"> <button>Countdown</button><button>Count up</button>';
          root.appendChild(block);let elapsed=0,base=0,running=false,down=false,duration=0;
          const clock=block.querySelector('.clock'),buttons=block.querySelectorAll('button');
          function now(){return elapsed+(running?(performance.now()-base)/1000:0);}
          function display(){let n=down?Math.max(0,duration-now()):now();let mins=Math.floor(n/60),secs=Math.floor(n%60),d=Math.floor(n%1*10);clock.textContent=String(mins).padStart(2,'0')+':'+String(secs).padStart(2,'0')+'.'+d;}
          buttons[0].onclick=()=>{if(!running){base=performance.now();running=true;}};
          buttons[1].onclick=()=>{elapsed=now();running=false;display();};
          buttons[2].onclick=()=>{elapsed=0;running=false;display();};
          buttons[3].onclick=()=>{duration=Math.max(0,Number(block.querySelector('input').value));elapsed=0;running=false;down=true;display();};
          buttons[4].onclick=()=>{elapsed=0;running=false;down=false;display();};
          setInterval(display,50);display();
        }
        </script>''', height=160)

def selector_tab():
    st.subheader('1. Select a fixed 10-trial session')
    st.write('Each catalog ID identifies both the scenarios and their exact order.')
    records=st.session_state.setdefault('learner_fidelity',{})
    records_before=deepcopy(records)
    disabled=any(r.get('notes') or any(v!='Not recorded' for v in r.get('scores',{}).values()) for r in records.values())
    if disabled:
        st.info('This plan is locked because learner fidelity recording has begun. Download the record before starting a new plan.')
        if st.button('Start a new scenario plan'):
            st.session_state.pop('planner_selection',None)
            st.session_state['learner_fidelity']={}
            for key in list(st.session_state):
                if key.startswith('leader_trial_'): del st.session_state[key]
            st.rerun()
    c1,c2=st.columns(2)
    with c1:
        if st.button('Randomly select a session', disabled=disabled, type='primary'):
            set_selection(select_session(catalog_data()))
            st.rerun()
    with c2:
        selected=st.selectbox('Use an existing set ID', [s['set_id'] for s in catalog_data()['sets']])
        if st.button('Use this set', disabled=disabled):
            set_selection(select_session(catalog_data(),selected))
            st.rerun()
    session=st.session_state.get('planner_selection',{})
    if session.get('set_id'):
        st.markdown(f"**{session['set_id']} · {session['catalog_version']}**")
        plan=pd.DataFrame(session_plan(session,catalog_data()))
        st.dataframe(plan,hide_index=True,use_container_width=True)
        st.download_button('Download session plan (CSV)',plan.to_csv(index=False).encode(),file_name=session['set_id']+'_trial_plan.csv',mime='text/csv')
        st.subheader('2. Enter session information')
        leader=st.session_state.setdefault('leader_information',{})
        participant_column,=st.columns(1)
        with participant_column: leader['participant_id']=text('Participant ID',leader.get('participant_id',''),'leader_participant_id')
        a,b,c=st.columns(3)
        with a: leader['session_id']=text('Session ID',leader.get('session_id',''),'leader_session_id')
        with b: leader['session_leader']=text('Session leader',leader.get('session_leader',''),'leader_name')
        with c: leader['simulated_learner']=text('Simulated Learner',leader.get('simulated_learner',''),'leader_learner')
        st.subheader('3. Give earpiece instructions and record Simulated Learner fidelity')
        st.write('Read the short instructions, in full and as written, through the Bluetooth earpiece. You may repeat the instructions if the simulated learner indicates they need more information. If they make a mistake that can be corrected before it affects participant behavior (for example, not starting table banging), you may remind them. Otherwise, allow the scenario to play out.')
        st.write('Code simulated learner fidelity in real time. Indicate what the simulated learner actually did, rather than what is anticipated.')
        st.caption('Check Yes when the instruction was followed, No for a learner error, or Not observed when the cue/opportunity never occurred or the session ended first. Leave unchecked until assessed. These scores are separate from participant fidelity.')
        for number,sid in enumerate(session['ordered_scenario_ids'],1):
            record=records.setdefault(str(number),{'scores':{},'notes':''})
            with st.container(border=True):
                st.subheader(f'Trial {number}')
                st.caption(f'(scenario {sid})')
                steps=learner_steps(sid)
                st.markdown('**Instructions:**')
                st.write(' '.join(step['instruction'] for step in steps))
                st.markdown('**Fidelity check:**')
                for step in steps:
                    answer=checked_choice(step['instruction'],[('Yes','Yes'),('No','No'),('Not observed','Not observed')],record['scores'].get(step['id'],MISSING),f"leader_trial_{number}_{step['id']}")
                    record['scores'][step['id']]='Not recorded' if answer==MISSING else answer
                    if 'reminder' in step['instruction'].lower():
                        st.caption('Note that "reminder" means the participant gave another task direction after the initial instruction.')
                note_key=f'leader_trial_{number}_notes'
                if note_key not in st.session_state: st.session_state[note_key]=record.get('notes','')
                record['notes']=st.text_area('Other mistakes / notes',key=note_key)
        if records!=records_before:
            st.rerun()
        rows=fidelity_rows(session,records)
        summary=fidelity_summary(rows)
        st.subheader('4. Review and download the learner fidelity record')
        st.metric('Simulated Learner fidelity (recorded items)',f"{summary['percent']:.1f}%" if summary['percent'] is not None else '—')
        st.caption(f"{summary['correct']} / {summary['applicable']} recorded applicable items followed. {summary['unrecorded']} items not yet recorded. Not observed items are excluded.")
        payload={'record_type':'simulated_learner_fidelity','selection':session,'leader':leader,'trials':records}
        st.download_button('Download learner fidelity record (JSON)',json.dumps(payload,indent=2).encode(),file_name=session['set_id']+'_learner_fidelity.json',mime='application/json')
        st.download_button('Download learner fidelity checklist (CSV)',pd.DataFrame(rows).to_csv(index=False).encode(),file_name=session['set_id']+'_learner_fidelity.csv',mime='text/csv')
        st.caption('Download your record before leaving this browser session. The set ID and exact trial order are retained in the JSON record.')

def session_info():
    session=st.session_state.session
    st.subheader('Session information')
    a,b,c=st.columns(3)
    with a:
        session['participant_id']=text('Participant ID',session.get('participant_id',''),'meta_participant').strip()
        session['session_number']=text('Session number',session.get('session_number',''),'meta_number').strip()
        session['date']=text('Date (YYYY-MM-DD)',session.get('date',str(date.today())),'meta_date')
    with b:
        session['data_collector']=text('Data collector',session.get('data_collector',''),'meta_collector').strip()
        session['collector_role']=choice('Collector role',['Primary','Secondary'],session.get('collector_role','Primary'),'meta_role')
        session['simulated_learner']=text('Simulated learner',session.get('simulated_learner',''),'meta_learner')
    with c:
        session['end_reason']=choice('Session end reason',['Not recorded','10 trials completed','10-minute limit reached'],session.get('end_reason','Not recorded'),'meta_end_reason')
        session['end_at']=text('Session endpoint (seconds or MM:SS.s)',session.get('end_at',''),'meta_end_at',help='Session-relative time. Session start is 0:00.')
        session['notes']=text('Session notes',session.get('notes',''),'meta_notes')
    st.markdown('**Setup observations**')
    st.caption('Descriptive observations; excluded from fidelity.')
    for key,label in [('arrange_materials','Were materials arranged outside reach?'),('prepare_reinforcers','Were reinforcers prepared?')]:
        with st.container(border=True):
            current=st.session_state.setup.get(key,'Not recorded')
            answer=checked_choice(label,[('Yes','Yes'),('No','No'),('N/A','N/A')],MISSING if current=='Not recorded' else current,'setup_'+key)
            st.session_state.setup[key]='Not recorded' if answer==MISSING else answer

def optional_number(label, value, key, integer=False):
    raw=text(label,'' if value is None else value,key)
    if not raw.strip(): return None
    try:
        number=float(raw)
        if number<0 or not pd.notna(number) or number==float('inf'): raise ValueError()
        if integer and not number.is_integer(): raise ValueError()
        return int(number) if integer else number
    except ValueError:
        st.error(f'{label}: enter a nonnegative '+('integer.' if integer else 'number.'))
        return raw  # preserve invalid input so validation blocks finalization

def collection_tab():
    session_info()
    timers()
    st.subheader('Trial-by-trial coding')
    st.caption('Changes are retained while this browser session is open. Download a JSON backup before leaving; restore it to continue later.')
    index=st.radio('Trial to code',list(range(1,11)),format_func=lambda i:f'T{i}',horizontal=True,key='trial_index')
    trial=st.session_state.trials[index-1]
    before=deepcopy(trial)
    prefix=f'code_{index}_'
    with st.container(border=True):
        status=checked_choice('Trial observation status',[(value,value) for value in ['Not reached','Complete','Partial']],trial['trial_status'],prefix+'status')
        trial['trial_status']=status if status!=MISSING else 'Not reached'
        st.caption('Partial: cut short by the session cutoff or premature worksheet removal. A fully observed trial with unfinished math is Complete.')
    if trial['trial_status']=='Not reached':
        st.write('This trial contributes no scores until marked Complete or Partial.')
        return
    st.markdown('**Observed learner behavior and prompt count**')
    obs=trial['observations']
    a,b,c=st.columns(3)
    with a:
        obs['problems']=choice('Problems completed',[None,0,1,2],obs.get('problems'),prefix+'problems',format_func=lambda x:'Not recorded' if x is None else str(x))
        obs['prompts_delivered']=optional_number('Prompts delivered (exclude initial instruction)',obs.get('prompts_delivered'),prefix+'prompt_count',True)
    with b:
        obs['tapping_seconds']=optional_number('Observable tapping (seconds)',obs.get('tapping_seconds'),prefix+'tap_seconds')
        obs['banging_seconds']=optional_number('Observable banging (seconds)',obs.get('banging_seconds'),prefix+'bang_seconds')
    with c:
        obs['incomplete_seconds']=optional_number('Time with fewer than two problems complete (seconds)',obs.get('incomplete_seconds'),prefix+'incomplete_seconds')
        obs['timer_use']=choice('Participant timer use',['Not recorded','Used','Not used'],obs.get('timer_use','Not recorded'),prefix+'timer')
    st.caption('Beginning: first writing movement directed at solving the problem. Completion: written answer finished. Brief pauses within a problem remain ongoing work.')
    for component in TIMED_COMPONENTS:
        key=component['key'];action=trial['actions'][key]
        with st.container(border=True):
            st.markdown(f"**{component['label']}**")
            sections=[component['guide']]
            if key.startswith('prompt'):
                sections+=['Prompt After One Completed Problem Scoring','Task Direction Classification and Prompt Limit']
            if key=='worksheet_removal':
                sections+=['One Problem Completed After Both Prompts: Removal Scoring','Completed Worksheet Removal Scoring','Worksheet Removal: Component Assignment']
            with st.expander('Scoring rules and examples'):
                rule_help(sections)
            question,timing_question=ACTION_QUESTIONS[key]
            action['occurrence']=checked_choice(question,[('Yes',CORRECT),('No',OMISSION),('N/A',NA),('Interrupted',INTERRUPTED),('Ended early by participant',TERMINATED)],action.get('occurrence',MISSING),prefix+key+'_occ')
            st.caption('N/A: no opportunity arose. Interrupted: the session ended before the deadline. Ended early: premature worksheet removal closed this opportunity.')
            with st.container(border=True):
                timing_key=prefix+key+'_timing'
                if action['occurrence']!=CORRECT:
                    action['timing']=NA
                    st.session_state.pop(timing_key,None)
                    st.session_state.pop(prefix+key+'_direction',None)
                    for i in range(2): st.session_state[f'{timing_key}_check_{i}']=False
                    st.write(timing_question)
                    st.caption('Timing: N/A until the action is scored Yes.')
                else:
                    timing_current=action.get('timing',MISSING)
                    answer=checked_choice(timing_question,[('Yes',CORRECT),('No','Outside window')],CORRECT if timing_current==CORRECT else 'Outside window' if timing_current in (TIMING_COMMISSION,TIMING_OMISSION) else MISSING,timing_key)
                    if answer=='Outside window':
                        action['timing']=checked_choice('Was it early or late?',[('Early',TIMING_COMMISSION),('Late',TIMING_OMISSION)],timing_current,prefix+key+'_direction')
                    else: action['timing']=answer
            a,b=st.columns(2)
            with a: action['reference_at']=text('Reference event time',action.get('reference_at',''),prefix+key+'_reference',help='Seconds or MM:SS.s relative to session start. Identify the reference event using the rule above.')
            with b: action['action_at']=text('Action time',action.get('action_at',''),prefix+key+'_action',help='Speech onset for instructions/prompts. Leave blank if the action never occurred.')
            window=component['window']
            if key=='worksheet_removal':
                branch=choice('Removal reference',['Select reference','Second problem completed','Second prompt; no work','First problem completed after both prompts','Premature removal before a valid reference'],action.get('branch','Select reference'),prefix+key+'_branch')
                action['branch']=branch
                window=(0,3) if branch=='Second problem completed' else (8,12) if branch in ['Second prompt; no work','First problem completed after both prompts'] else None
            try:
                reference=parse_time(action['reference_at']);at=parse_time(action['action_at'])
                if window and reference is not None and at is not None:
                    predicted=timing_result(at-reference,*window)
                    st.caption(f'Elapsed: {at-reference:.2f} seconds · timing calculation: {predicted}')
                    if action['occurrence']==CORRECT and action['timing'] not in (MISSING,predicted):
                        st.warning('Selected timing differs from timestamps. Correct the timestamps or score before finalizing.')
            except (ValueError,TypeError) as exc:
                st.error(str(exc))
            action['notes']=text('Reference description / coding notes',action.get('notes',''),prefix+key+'_notes')
    for component in BEHAVIOR_COMPONENTS:
        with st.container(border=True):
            st.markdown(f"**{component['label']}**")
            with st.expander('Scoring rules and examples'):
                rule_help([component['guide']])
            trial['behaviors'][component['key']]=checked_choice(BEHAVIOR_QUESTIONS[component['key']],[('Yes',CORRECT),('No',COMMISSION),('N/A',NA),('Interrupted',INTERRUPTED),('Ended early by participant',TERMINATED)],trial['behaviors'].get(component['key'],MISSING),prefix+component['key'])
    with st.expander('Detailed event log'):
        st.caption('Record individual errors and learner events here. Repeated commissions are logged individually; the per-trial behavior measure is still scored once. The event log does not silently add scores to the overall denominator.')
        event_frame=pd.DataFrame(trial.get('events',[]),columns=['Time','Event','Classification','Notes'])
        edited=st.data_editor(event_frame,num_rows='dynamic',hide_index=True,use_container_width=True,key=prefix+'events',column_config={'Time':st.column_config.TextColumn('Time (seconds or MM:SS.s)')})
        trial['events']=json.loads(edited.fillna('').to_json(orient='records'))
    trial['notes']=st.text_area('Trial notes',value=trial.get('notes',''),key=prefix+'notes')
    if trial!=before:
        trial['reviewed']=False
    trial_scores=score_trials([trial])
    for issue in trial_scores['validation_issues']:
        st.error(issue)
    if st.button('Mark this trial reviewed',key=prefix+'review',disabled=bool(trial_scores['missing'] or trial_scores['validation_issues'])):
        trial['reviewed']=True
    st.caption('Reviewed' if trial.get('reviewed') else 'Not reviewed / scores incomplete')

def finalization_issues(scores):
    session=st.session_state.session;issues=list(scores['validation_issues'])
    for key,label in [('participant_id','Participant ID'),('session_number','Session number'),('data_collector','Data collector')]:
        if not session.get(key): issues.append(label+' is required for a final summary.')
    try:
        date.fromisoformat(session.get('date',''))
    except (ValueError,TypeError): issues.append('Enter a valid date in YYYY-MM-DD format.')
    try: end=parse_time(session.get('end_at'))
    except (ValueError,TypeError): end=None
    if end is None or end>600: issues.append('Record a valid session endpoint, no later than 10:00.')
    reason=session.get('end_reason')
    if reason=='Not recorded' or reason is None: issues.append('Record the session end reason.')
    if reason=='10-minute limit reached' and end!=600: issues.append('The 10-minute cutoff endpoint must be 10:00.')
    reached=[t for t in st.session_state.trials if t['trial_status']!='Not reached']
    for trial in reached:
        obs=trial['observations']
        if obs.get('problems') is None or obs.get('prompts_delivered') is None:
            issues.append(f"Trial {trial['trial']}: record problems completed and prompts delivered.")
        for action in trial.get('actions',{}).values():
            for field in ('reference_at','action_at'):
                try:
                    timestamp=parse_time(action.get(field))
                    if timestamp is not None and end is not None and timestamp>end:
                        issues.append(f"Trial {trial['trial']}: an action/reference timestamp is after session end.")
                except (ValueError,TypeError): pass
    if not reached: issues.append('No trial has been coded.')
    if reason=='10 trials completed' and (len(reached)!=10 or any(t['trial_status']!='Complete' for t in reached)):
        issues.append('All ten trials must be Complete for the ten-trial endpoint.')
    if [t['trial'] for t in reached]!=list(range(1,len(reached)+1)): issues.append('Reached trials must form a consecutive sequence from trial 1.')
    if any(not t.get('reviewed') for t in reached): issues.append('Mark each reached trial reviewed after scoring it.')
    if scores['missing']: issues.append(f"{scores['missing']} score(s) are still missing.")
    return issues

def filename():
    s=st.session_state.session
    return re.sub(r'[^A-Za-z0-9_.-]+','_',f"DRA_{s.get('participant_id') or 'participant'}_session-{s.get('session_number') or 'unknown'}_{s.get('data_collector') or 'collector'}")

def results_tab():
    scores=score_trials(st.session_state.trials)
    issues=finalization_issues(scores)
    final=not issues and scores['applicable']>0
    st.subheader('Session summary')
    a,b,c=st.columns(3)
    a.metric('Overall fidelity' if final else 'Provisional fidelity',f"{scores['percent']:.1f}%" if scores['percent'] is not None else '—')
    b.metric('Correct / applicable scores',f"{scores['correct']} / {scores['applicable']}")
    c.metric('Missing scores',scores['missing'])
    st.caption('Occurrence and timing each contribute separately. Timing is N/A for omitted actions. Excluded opportunities do not enter the denominator.')
    if not final:
        st.warning('Draft: do not use this provisional percentage as a finalized graph point.')
        with st.expander('What remains to finalize',expanded=bool(scores['validation_issues'])):
            for issue in issues: st.write('• '+issue)
    else: st.success('Coding complete: final session summary available.')
    st.markdown('**Individual step and measure summaries**')
    st.dataframe(pd.DataFrame(scores['step_summary']),hide_index=True,use_container_width=True)
    with st.expander('All scored opportunities'):
        st.dataframe(pd.DataFrame(scores['details']),hide_index=True,use_container_width=True)
    name=filename()
    st.download_button('Download '+('final' if final else 'draft')+' session workbook',make_workbook(st.session_state.session,st.session_state.setup,st.session_state.trials,scores,final=final),file_name=name+('.xlsx' if final else '_DRAFT.xlsx'),mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    row=summary_row(st.session_state.session,scores,final=final)
    st.download_button('Download '+('final' if final else 'draft')+' summary (CSV)',pd.DataFrame([row]).to_csv(index=False).encode(),file_name=name+('_summary.csv' if final else '_DRAFT_summary.csv'),mime='text/csv')
    st.download_button('Download editable session backup (JSON)',serialize_session(st.session_state.session,st.session_state.setup,st.session_state.trials),file_name=name+'.json',mime='application/json')

def restore_tab():
    st.subheader('Resume or start a coding session')
    st.write('Upload the JSON backup exported by this version. Restoring replaces the current browser session; download a backup first if needed.')
    upload=st.file_uploader('Session backup',type=['json'],key='restore_upload')
    acknowledge=st.checkbox('Replace the current browser session',key='replace_ack')
    if st.button('Restore session',disabled=upload is None or not acknowledge):
        try:
            payload=restore_session(upload.getvalue())
            for key in list(st.session_state):
                if key.startswith(('code_','meta_','setup_')): del st.session_state[key]
            st.session_state.session=payload['session'];st.session_state.setup=payload['setup'];st.session_state.trials=payload['trials']
            clear_plan_from_coding()
            st.session_state.trial_index=1
            st.rerun()
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc: st.error(str(exc))
    if st.button('Start a new blank session',disabled=not acknowledge):
        for key in list(st.session_state):
            if key.startswith(('code_','meta_','setup_')): del st.session_state[key]
        st.session_state.trials=empty_trials();st.session_state.session={'date':str(date.today()),'mode':'in_person'};st.session_state.setup={'arrange_materials':'Not recorded','prepare_reinforcers':'Not recorded'};st.session_state.trial_index=1
        st.rerun()

initialize()
clear_plan_from_coding()
st.title('DRA Session Coder')
st.caption("Mary’s Honors Thesis · 2026-2027 - Planning and Coding Recordings of In-Person Simulated-Learner Sessions")
selection,collection,results,instructions,resume,ioa=st.tabs(['Scenario Selection and Simulated-Learner Fidelity','DRA Data Collection','Results','Scoring Instructions','Resume / New Session','IOA'])
with selection:
    st.header('Scenario Selection and Simulated-Learner Fidelity')
    selector_tab()
with collection:
    st.header('DRA Data Collection')
    collection_tab()
with results:
    st.header('Results')
    results_tab()
with instructions:
    st.header('Scoring Instructions')
    st.subheader('Scoring appendix and coder examples')
    for section in guide_data():
        with st.expander(section): rule_help([section])
with resume:
    st.header('Resume / New Session')
    restore_tab()
with ioa:
    st.header('IOA')
    st.subheader('Interobserver agreement')
    st.info('Primary and secondary coding identities are retained in exports. The comparison module remains to be implemented.')
