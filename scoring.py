"""Shared DRA scoring. Both apps submit canonical records to summarize()."""
from __future__ import annotations
from collections import Counter, defaultdict
import math
from typing import Any

RULES_VERSION = 'DRA-2026-10-03'
CORRECT, OMISSION, COMMISSION = 'Correct', 'Omission', 'Commission'
TIMING_OMISSION, TIMING_COMMISSION = 'Timing omission', 'Timing commission'
NA, INTERRUPTED, TERMINATED, MISSING = 'N/A', 'Interrupted', 'Terminated by participant', 'Missing'
EXCLUDED = {NA, INTERRUPTED, TERMINATED}
ERRORS = {OMISSION, COMMISSION, TIMING_OMISSION, TIMING_COMMISSION}
VALID_RESULTS = {CORRECT, *ERRORS, *EXCLUDED, MISSING}
TIMED_COMPONENTS = [
 {'key':'worksheet','label':'Worksheet presentation','guide':'Worksheet Presentation Scoring','window':(0,3)},
 {'key':'instruction','label':'Initial instruction','guide':'Initial Instruction Scoring','window':(0,3)},
 {'key':'prompt_1','label':'First prompt','guide':'First Prompt Scoring','window':(8,12)},
 {'key':'prompt_2','label':'Second prompt','guide':'Second Prompt Following No Work Scoring','window':(8,12)},
 {'key':'worksheet_removal','label':'Worksheet removal','guide':'Unfinished Worksheet Removal Scoring','window':None},
 {'key':'earned_dolphin','label':'Earned dolphin delivery','guide':'Earned Dolphin Delivery Scoring','window':(0,3)},
 {'key':'dolphin_removal','label':'Dolphin removal','guide':'Dolphin Removal Scoring','window':(13,17)},
]
BEHAVIOR_COMPONENTS = [
 {'key':'no_unearned','label':'No unearned dolphin delivery','guide':'Unearned Dolphin Delivery Scoring'},
 {'key':'no_excess','label':'No excess prompts','guide':'No Excess Prompts Scoring'},
 {'key':'no_work_prompts','label':'No prompts during ongoing work','guide':'No Prompts During Ongoing Work Scoring'},
 {'key':'no_tapping_comments','label':'No stop statements for tapping','guide':'Finger Tapping Scoring'},
 {'key':'no_banging_comments','label':'No stop statements for banging','guide':'Table Banging Scoring'},
]
COMPONENTS = {c['key']:c for c in TIMED_COMPONENTS+BEHAVIOR_COMPONENTS}

def _seconds(value: Any) -> float:
 value=float(value)
 if not math.isfinite(value): raise ValueError('Times must be finite numbers.')
 return value

def parse_time(value: Any) -> float | None:
 """Accept blank, seconds, or MM:SS.s, relative to session start."""
 if value is None or str(value).strip()=='': return None
 text=str(value).strip()
 if ':' in text:
  parts=text.split(':')
  if len(parts)!=2 or not parts[0].isdigit(): raise ValueError('Use seconds or MM:SS.s.')
  seconds=_seconds(parts[1])
  if not 0<=seconds<60: raise ValueError('Seconds must be from 0 to less than 60.')
  value=int(parts[0])*60+seconds
 else: value=_seconds(text)
 if value<0: raise ValueError('Session-relative timestamps cannot be negative.')
 return value

def timing_result(elapsed: float, minimum: float, maximum: float) -> str:
 elapsed,minimum,maximum=map(_seconds,(elapsed,minimum,maximum))
 if minimum>maximum: raise ValueError('Invalid timing window.')
 if elapsed<minimum: return TIMING_COMMISSION
 return TIMING_OMISSION if elapsed>maximum else CORRECT

def assess_timed_action(*,action_at: float|None,reference_at: float|None,
                        window: tuple[float,float],end_at: float,
                        end_reason: str='session',required: bool=True) -> dict[str,Any]:
 """Required action occurrence and timing, including cutoff and early removal.

 Extra inappropriate events must be scored separately, not passed as earned
 required actions. Before a removal reference exists, the event adapter uses
 explicit Correct/Timing commission for an actual premature removal.
 """
 end_at=_seconds(end_at)
 if action_at is not None:
  action_at=_seconds(action_at)
  if action_at>end_at: raise ValueError('Action is after the opportunity endpoint.')
 if not required or reference_at is None: return {'occurrence':NA,'timing':NA,'elapsed':None}
 reference_at=_seconds(reference_at)
 if reference_at>end_at: return {'occurrence':NA,'timing':NA,'elapsed':None}
 if action_at is not None:
  elapsed=action_at-reference_at
  return {'occurrence':CORRECT,'timing':timing_result(elapsed,*window),'elapsed':elapsed}
 if end_at>=reference_at+window[1]: return {'occurrence':OMISSION,'timing':NA,'elapsed':None}
 return {'occurrence':TERMINATED if end_reason=='participant' else INTERRUPTED,'timing':NA,'elapsed':None}

def score_prohibition(*,violations: int,applicable: bool=True,partial: bool=False,
                      exposure: float|None=None,minimum_exposure: float|None=None) -> str:
 """One per-trial score; retain all violation events separately."""
 if not isinstance(violations,int) or violations<0: raise ValueError('Invalid violation count.')
 if violations: return COMMISSION
 if not applicable: return NA
 if partial and minimum_exposure is not None:
  if exposure is None: return MISSING
  if _seconds(exposure)<minimum_exposure: return INTERRUPTED
 return CORRECT

def empty_trials() -> list[dict[str,Any]]:
 return [{'trial':i,'scenario_id':None,'trial_status':'Not reached',
          'observations':{'problems':None,'prompts_delivered':None,'tapping_seconds':None,
                          'banging_seconds':None,'incomplete_seconds':None,'timer_use':'Not recorded'},
          'actions':{c['key']:{'occurrence':MISSING,'timing':MISSING,'reference_at':'','action_at':'','notes':''}
                     for c in TIMED_COMPONENTS},
          'behaviors':{c['key']:MISSING for c in BEHAVIOR_COMPONENTS},'events':[],'notes':''}
         for i in range(1,11)]

def trial_records(trial: dict[str,Any]) -> list[dict[str,Any]]:
 if trial.get('trial_status')=='Not reached': return []
 records=[]
 base={'trial':trial['trial'],'scenario_id':trial.get('scenario_id')}
 for c in TIMED_COMPONENTS:
  action=trial.get('actions',{}).get(c['key'],{})
  occurrence=action.get('occurrence',MISSING)
  if c['key']=='dolphin_removal' and trial.get('actions',{}).get('earned_dolphin',{}).get('occurrence') in (OMISSION,NA,INTERRUPTED,TERMINATED):
   occurrence=NA
  timing=action.get('timing',MISSING) if occurrence==CORRECT else NA
  for measure,result in (('Occurrence',occurrence),('Timing',timing)):
   records.append({**base,'component':c['key'],'step':c['label'],'measure':measure,'result':result,
                   'reference_at':action.get('reference_at',''),'action_at':action.get('action_at',''),'notes':action.get('notes','')})
 for c in BEHAVIOR_COMPONENTS:
  records.append({**base,'component':c['key'],'step':c['label'],'measure':'Behavior',
                  'result':trial.get('behaviors',{}).get(c['key'],MISSING),'reference_at':'','action_at':'','notes':''})
 return records

def summarize(records: list[dict[str,Any]]) -> dict[str,Any]:
 """The sole denominator implementation used by both modes."""
 counts=Counter();groups=defaultdict(Counter)
 for record in records:
  result=record['result']
  if result not in VALID_RESULTS: raise ValueError(f'Unknown score: {result}')
  counts[result]+=1;groups[(record['component'],record['step'],record['measure'])][result]+=1
 correct=counts[CORRECT];incorrect=sum(counts[x] for x in ERRORS);applicable=correct+incorrect
 summary=[]
 for (component,step,measure),values in groups.items():
  denominator=values[CORRECT]+sum(values[x] for x in ERRORS)
  summary.append({'Component':component,'Step':step,'Measure':measure,
                  **{x:values[x] for x in [CORRECT,OMISSION,COMMISSION,TIMING_OMISSION,TIMING_COMMISSION,NA,INTERRUPTED,TERMINATED,MISSING]},
                  'Applicable':denominator,'Accuracy (%)':100*values[CORRECT]/denominator if denominator else None})
 return {'correct':correct,'incorrect':incorrect,'applicable':applicable,'missing':counts[MISSING],
         'percent':100*correct/applicable if applicable else None,'counts':{x:counts[x] for x in sorted(VALID_RESULTS)},
         'details':records,'step_summary':summary,'rules_version':RULES_VERSION}

def validate_trials(trials: list[dict[str,Any]]) -> list[str]:
 issues=[]
 for trial in trials:
  if trial.get('trial_status')=='Not reached': continue
  prefix=f"Trial {trial['trial']}";actions=trial.get('actions',{})
  for c in TIMED_COMPONENTS:
   action=actions.get(c['key'],{});occurrence=action.get('occurrence',MISSING)
   if c['key']=='dolphin_removal' and actions.get('earned_dolphin',{}).get('occurrence') in (OMISSION,NA,INTERRUPTED,TERMINATED): continue
   if occurrence not in {CORRECT,OMISSION,*EXCLUDED,MISSING}: issues.append(f"{prefix}: invalid occurrence for {c['label']}.")
   if occurrence==CORRECT and action.get('timing',MISSING) not in {CORRECT,TIMING_COMMISSION,TIMING_OMISSION,MISSING}:
    issues.append(f"{prefix}: delivered {c['label']} needs a timing score.")
   if c['key']=='earned_dolphin' and occurrence==CORRECT and action.get('timing')==TIMING_COMMISSION:
    issues.append(f'{prefix}: earned dolphin delivery can be on time or late; before-completion delivery is inappropriate delivery.')
   if not trial.get('manual_checkbox_coding'):
    for field in ('reference_at','action_at'):
     try: parse_time(action.get(field))
     except (ValueError,TypeError): issues.append(f"{prefix}: invalid {field} for {c['label']}.")
    try:
     reference=parse_time(action.get('reference_at'));at=parse_time(action.get('action_at'))
     if occurrence not in (CORRECT,MISSING) and at is not None:
      issues.append(f"{prefix}: {c['label']} has an action time but is marked not performed/excluded.")
     window=c['window']
     if c['key']=='worksheet_removal':
      branch=action.get('branch')
      window=(0,3) if branch=='Second problem completed' else (8,12) if branch in ('Second prompt; no work','First problem completed after both prompts') else None
     if occurrence==CORRECT and at is not None and reference is not None and window:
      expected=timing_result(at-reference,*window)
      if action.get('timing') not in (MISSING,expected): issues.append(f"{prefix}: {c['label']} timing conflicts with its timestamps.")
    except (ValueError,TypeError): pass
  obs=trial.get('observations',{})
  numeric_fields=('problems',) if trial.get('manual_checkbox_coding') else ('problems','prompts_delivered','tapping_seconds','banging_seconds','incomplete_seconds')
  for field in numeric_fields:
   value=obs.get(field)
   if value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):
    issues.append(f'{prefix}: invalid {field}.')
  if obs.get('problems') not in (None,0,1,2): issues.append(f'{prefix}: problems must be 0, 1, or 2.')
  if obs.get('problems_na') and actions.get('worksheet',{}).get('occurrence')==CORRECT:
   issues.append(f'{prefix}: problems completed can be N/A only when no worksheet was provided.')
  if obs.get('problems') in (0,1) and actions.get('earned_dolphin',{}).get('occurrence') in {CORRECT,OMISSION}:
   issues.append(f'{prefix}: earned delivery is N/A with fewer than two completed problems. Use no unearned delivery for early access.')
  if trial.get('trial_status')=='Partial':
   for key,field in (('no_unearned','incomplete_seconds'),('no_tapping_comments','tapping_seconds'),('no_banging_comments','banging_seconds')):
    if trial.get('behaviors',{}).get(key)==CORRECT:
     value=obs.get(field)
     eligibility=obs.get(field.replace('_seconds','_eligible'))
     eligible=eligibility is True if eligibility is not None and eligibility!=MISSING else isinstance(value,(int,float)) and math.isfinite(value) and value>=3
     if not eligible: issues.append(f"{prefix}: correct {COMPONENTS[key]['label']} on a partial trial needs confirmation of at least 3 seconds of exposure.")
  count=obs.get('prompts_delivered');result=trial.get('behaviors',{}).get('no_excess')
  if isinstance(count,(int,float)) and not trial.get('manual_checkbox_coding'):
   if count>2 and result!=COMMISSION: issues.append(f'{prefix}: more than two prompts requires an excess-prompt commission.')
   if count<=2 and result==COMMISSION: issues.append(f'{prefix}: excess-prompt commission conflicts with prompt count.')
  for c in BEHAVIOR_COMPONENTS:
   if trial.get('behaviors',{}).get(c['key'],MISSING) not in {CORRECT,COMMISSION,*EXCLUDED,MISSING}:
    issues.append(f"{prefix}: invalid score for {c['label']}.")
 return issues

def score_trials(trials: list[dict[str,Any]]) -> dict[str,Any]:
 result=summarize([r for t in trials for r in trial_records(t)])
 result['validation_issues']=validate_trials(trials)
 result['ready']=result['missing']==0 and not result['validation_issues'] and result['applicable']>0
 return result
