from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from dra import (load_catalog, load_guide, select_session, session_plan,
                 serialize_session, summary_row, make_workbook)
from planner import learner_steps, fidelity_rows, fidelity_summary, fidelity_filename, fidelity_workbook

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
    if st.session_state[key] not in [value for _,value in options]:
        st.session_state[key]=MISSING
    def changed(selected, value):
        st.session_state[key]=value if st.session_state[selected] else MISSING
        for i in range(len(options)):
            sibling=f'{key}_check_{i}'
            st.session_state[sibling]=st.session_state[key]==options[i][1]
    st.write(label)
    with st.container(width=min(650,130*len(options))):
        columns=st.columns(len(options))
        for i,(caption,value) in enumerate(options):
            widget=f'{key}_check_{i}'
            st.session_state[widget]=st.session_state[key]==value
            with columns[i]:
                st.checkbox(caption,key=widget,disabled=disabled,on_change=changed,args=(widget,value))
    return st.session_state[key]

ACTION_QUESTIONS={
 'worksheet':('Was the worksheet presented?','Was it presented within 3 seconds of session start (trial 1), or removal of the dolphin or preceding unfinished worksheet (trials 2–10)?'),
 'instruction':('Was an initial instruction given?','Was it given within 3 seconds of worksheet presentation?'),
 'prompt_1':('Was the first required prompt given?','Was it given after 8–12 seconds without starting work since the initial instruction, or since completing the first problem if work started without a prompt?'),
 'prompt_2':('Was the second required prompt given?','Was it given after 8–12 seconds without starting work since the first prompt, or since completing the first problem if that happened after the first prompt?'),
 'worksheet_removal':('Was the worksheet removed?','Was it removed within 3 seconds of completing the second problem, or after 8–12 seconds without work since the second prompt (or since the first problem was completed after both prompts)?'),
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

ACTION_NA={
 'instruction':'N/A: no worksheet was provided, so a post-presentation initial instruction was not required.',
 'prompt_1':'N/A: no first prompt was needed because the learner began or continued work without a required pause.',
 'prompt_2':'N/A: no second prompt was needed because work began or both problems were completed before another prompt was required.',
 'worksheet_removal':'N/A: no worksheet was provided to remove.',
 'earned_dolphin':'N/A: the learner did not complete two problems.',
 'dolphin_removal':'N/A: the dolphin was never provided, including any unearned delivery.',
}
BEHAVIOR_NA={
 'no_work_prompts':'N/A: the learner never began working on a problem, so there was no ongoing work during which to withhold prompts.',
 'no_tapping_comments':'N/A: finger tapping did not occur.',
 'no_banging_comments':'N/A: table banging did not occur.',
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
            table=pd.DataFrame([{'Entry':e['entry'],'Rule':e['rule'],'Example':e.get('example','')} for e in entries]).to_html(index=False,escape=True,classes='scoring-rules')
            st.html('<style>.scoring-rules{width:100%;table-layout:fixed;border-collapse:collapse}.scoring-rules th,.scoring-rules td{white-space:normal!important;overflow-wrap:anywhere;padding:10px;border:1px solid #aaa;vertical-align:top;text-align:left}.scoring-rules th:first-child{width:20%}</style>'+table)

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
        st.write('Check Yes when the instruction was followed, No for a learner error, or Not observed when the cue/opportunity never occurred or the session ended first. Leave unchecked until assessed.')
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
        name=fidelity_filename(leader)
        st.download_button('Download learner fidelity record (JSON)',json.dumps(payload,indent=2).encode(),file_name=name+'.json',mime='application/json')
        st.download_button('Download learner fidelity workbook (Excel)',fidelity_workbook(session,leader,records),file_name=name+'.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
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
        session['notes']=text('Session notes',session.get('notes',''),'meta_notes')
    st.subheader('Setup Observations')
    st.caption('Descriptive observations; excluded from fidelity.')
    for key,label in [('arrange_materials','Were materials arranged outside reach?'),('prepare_reinforcers','Were reinforcers prepared?')]:
        with st.container(border=True):
            current=st.session_state.setup.get(key,'Not recorded')
            answer=checked_choice(label,[('Yes','Yes'),('No','No')],MISSING if current=='Not recorded' else current,'setup_'+key)
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
    st.caption('Complete and review this session in one sitting. Entries remain available across tabs while this browser session is open. Download the full JSON record and results before leaving.')
    index=st.radio('Trial to code',list(range(1,11)),format_func=lambda i:f'T{i}',horizontal=True,key='trial_index')
    trial=st.session_state.trials[index-1]
    before=deepcopy(trial)
    trial['manual_checkbox_coding']=True
    prefix=f'code_{index}_'
    if prefix+'status_initialized' not in st.session_state:
        if trial['trial_status']=='Not reached': trial['trial_status']='Complete'
        st.session_state[prefix+'status_initialized']=True
    label='Not Observed' if trial['trial_status']=='Not reached' else trial['trial_status']
    st.write(f'Trial Status: {label}')
    a,b,c,_=st.columns([1,1,1,5])
    with a:
        if st.button('Partial',key=prefix+'partial'):
            trial['trial_status']='Partial'; trial['reviewed']=False; st.rerun()
    with b:
        if st.button('Not Observed',key=prefix+'not_observed'):
            trial['trial_status']='Not reached'; trial['reviewed']=False; st.rerun()
    with c:
        if trial['trial_status']!='Complete' and st.button('Complete',key=prefix+'complete'):
            trial['trial_status']='Complete'; trial['reviewed']=False; st.rerun()
    st.caption('Partial: cut short by the session cutoff or premature worksheet removal. A fully observed trial with unfinished math is Complete. Not Observed trials are excluded from scores.')
    if trial['trial_status']=='Not reached':
        st.write('This trial is marked Not Observed and contributes no scores. Select Complete or Partial to code it.')
        return
    st.subheader('Simulated Learner Behavior')
    obs=trial['observations']
    obs['prompts_delivered']=None
    obs.pop('prompts_na',None)
    problems=checked_choice('Problems completed',[('0',0),('1',1),('2',2),('N/A',None)],None if obs.get('problems_na') else obs.get('problems',MISSING) if obs.get('problems') is not None else MISSING,prefix+'problems')
    obs['problems_na']=problems is None
    obs['problems']=problems if problems in (0,1,2) else None
    st.caption('N/A: no worksheet was provided.')
    for field,label in [('tapping_observed','Was finger tapping observed?'),('banging_observed','Was table banging observed?')]:
        value=checked_choice(label,[('Yes',True),('No',False)],obs.get(field,MISSING),prefix+field)
        obs[field]=value
    if trial['trial_status']=='Partial':
        st.write('Partial-trial scoring checks')
        st.caption('Judge whether there was at least 3 seconds of opportunity; no exact duration needs to be entered.')
        for field,label in [('incomplete_eligible','Was there at least 3 seconds with fewer than two problems completed?'),('tapping_eligible','Was finger tapping observable for at least 3 seconds?'),('banging_eligible','Was table banging observable for at least 3 seconds?')]:
            obs[field]=checked_choice(label,[('Yes',True),('No',False)],obs.get(field,MISSING),prefix+field)
    st.caption('Beginning: first writing movement directed at solving the problem. Completion: written answer finished. Brief pauses within a problem remain ongoing work.')
    st.subheader('Participant Behavior')
    def action_fields(component):
        key=component['key'];action=trial['actions'][key]
        label={'worksheet':'Worksheet Presented','instruction':'Instruction Given'}.get(key,component['label'])
        st.markdown(f'**{label}**')
        question,timing_question=ACTION_QUESTIONS[key]
        options=[('Yes',CORRECT),('No',OMISSION)]
        if key in ACTION_NA and key!='dolphin_removal': options.append(('N/A',NA))
        options.extend([('Interrupted',INTERRUPTED),('Ended early by participant',TERMINATED)])
        action['occurrence']=checked_choice(question,options,action.get('occurrence',MISSING),prefix+key+'_occ')
        if key in ACTION_NA and key!='dolphin_removal': st.caption(ACTION_NA[key])
        st.caption('Interrupted: the session ended before the deadline. Ended early: premature worksheet removal closed this opportunity.')
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
                    if key=='earned_dolphin':
                        action['timing']=TIMING_OMISSION
                        st.caption('Late: the dolphin was given more than 3 seconds after the second problem was completed. Delivery before two problems were completed is scored separately as unearned delivery.')
                    else:
                        action['timing']=checked_choice('Was it early or late?',[('Early',TIMING_COMMISSION),('Late',TIMING_OMISSION)],timing_current,prefix+key+'_direction')
                else: action['timing']=answer
        if key=='worksheet_removal':
            action['branch']=choice('Removal reference',['Select reference','Second problem completed','Second prompt; no work','First problem completed after both prompts','Premature removal before a valid reference'],action.get('branch','Select reference'),prefix+key+'_branch')
        action['notes']=text('Reference description / coding notes',action.get('notes',''),prefix+key+'_notes')
    for component in TIMED_COMPONENTS:
        key=component['key']
        if key=='dolphin_removal': continue
        with st.container(border=True):
            action_fields(component)
            if key=='earned_dolphin':
                st.markdown('**Dolphin access duration**')
                earned=trial['actions']['earned_dolphin']['occurrence']
                inappropriate=trial['behaviors']['no_unearned']
                provided=True if earned==CORRECT else False if earned!=MISSING else MISSING
                obs['earned_dolphin_provided']=provided
                obs.pop('dolphin_provided',None)
                removal=trial['actions']['dolphin_removal']
                if provided is False:
                    removal['occurrence']=NA; removal['timing']=NA
                    removal['reference_at']=''; removal['action_at']=''
                    for stored in list(st.session_state):
                        if stored.startswith(prefix+'dolphin_removal_'): del st.session_state[stored]
                    st.caption('Access duration and removal: N/A because no earned dolphin delivery occurred. Any inappropriate delivery is scored separately.')
                elif provided is True:
                    if removal.get('occurrence')==NA:
                        removal['occurrence']=MISSING; removal['timing']=MISSING
                    st.caption('Score the 13–17 second access duration only for dolphin delivery after two problems were completed.')
                    action_fields(next(c for c in TIMED_COMPONENTS if c['key']=='dolphin_removal'))
                else:
                    st.caption('Answer the earned-delivery question above before scoring access duration.')
                st.markdown('**Inappropriate dolphin delivery**')
                current=trial['behaviors'].get('no_unearned',MISSING)
                value=checked_choice('Was the dolphin given before two problems were completed?',[('Yes',COMMISSION),('No',CORRECT)],CORRECT if current==INTERRUPTED else current,prefix+'no_unearned')
                if value==CORRECT and trial['trial_status']=='Partial' and obs.get('incomplete_eligible') is False:
                    value=INTERRUPTED
                    st.caption('No inappropriate delivery occurred, but this partial trial had less than 3 seconds of opportunity, so withholding is excluded from fidelity.')
                trial['behaviors']['no_unearned']=value
                if value!=current:
                    st.rerun()
    for component in BEHAVIOR_COMPONENTS:
        if component['key']=='no_unearned': continue
        with st.container(border=True):
            st.markdown(f"**{component['label']}**")
            behavior_key=component['key']
            options=[('Yes',CORRECT),('No',COMMISSION)]
            if behavior_key in BEHAVIOR_NA: options.append(('N/A',NA))
            options.extend([('Interrupted',INTERRUPTED),('Ended early by participant',TERMINATED)])
            trial['behaviors'][behavior_key]=checked_choice(BEHAVIOR_QUESTIONS[behavior_key],options,trial['behaviors'].get(behavior_key,MISSING),prefix+behavior_key)
            if behavior_key in BEHAVIOR_NA: st.caption(BEHAVIOR_NA[behavior_key])
    obs['timer_use']=checked_choice('Did the participant use a timer?',[('Yes','Used'),('No','Not used')],obs.get('timer_use',MISSING),prefix+'timer')
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
    reason=session.get('end_reason')
    if reason=='Not recorded' or reason is None: issues.append('Record the session end reason.')
    reached=[t for t in st.session_state.trials if t['trial_status']!='Not reached']
    for trial in reached:
        obs=trial['observations']
        if obs.get('problems') is None and not obs.get('problems_na'):
            issues.append(f"Trial {trial['trial']}: record problems completed.")
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
    a,b,c,d=st.columns(4)
    included={record['trial'] for record in scores['details'] if record['result'] in (CORRECT,OMISSION,COMMISSION,TIMING_OMISSION,TIMING_COMMISSION)}
    a.metric('Trials included in calculations',len(included))
    b.metric('Overall fidelity' if final else 'Provisional fidelity',f"{scores['percent']:.1f}%" if scores['percent'] is not None else '—')
    c.metric('Correct / applicable scores',f"{scores['correct']} / {scores['applicable']}")
    d.metric('Missing scores',scores['missing'])
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
    st.download_button('Download full session record (JSON)',serialize_session(st.session_state.session,st.session_state.setup,st.session_state.trials),file_name=name+'.json',mime='application/json')


initialize()
clear_plan_from_coding()
st.title('DRA Session Coder')
st.caption("Mary’s Honors Thesis · 2026-2027 - Planning and Coding Recordings of In-Person Simulated-Learner Sessions")
selection,collection,results,instructions,ioa=st.tabs(['Scenario Selection and Simulated-Learner Fidelity','Session Coding','Results','Coding Instructions','IOA'])
with selection:
    st.header('Scenario Selection and Simulated-Learner Fidelity')
    selector_tab()
with collection:
    st.header('Session Coding')
    collection_tab()
with results:
    st.header('Results')
    results_tab()
with instructions:
    st.header('Coding Instructions')
    st.subheader('Coding rules and examples')
    st.write('Use these instructions for Session Coding. Timing examples illustrate the scoring windows; exact timestamps and numeric prompt counts are not required. Scenario selection and Simulated-Learner fidelity remain separate from observer coding.')
    for section in guide_data():
        with st.expander(section): rule_help([section])
with ioa:
    st.header('IOA')
    st.subheader('Interobserver agreement')
    st.info('Primary and secondary coding identities are retained in exports. The comparison module remains to be implemented.')
