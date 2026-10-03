"""Research scoring boundary, export, catalog, and session persistence tests."""
from copy import deepcopy
from io import BytesIO
import json
import unittest
import pandas as pd

from dra import load_catalog, select_session, session_plan, serialize_session, restore_session, make_workbook, summary_row
from scoring import *

def perfect_session(set_id='DRA-001'):
 catalog=load_catalog();selection=select_session(catalog,set_id);trials=empty_trials()
 scenarios={s['scenario_id']:s for s in catalog['scenarios']}
 for trial,sid in zip(trials,selection['ordered_scenario_ids']):
  s=scenarios[sid];trial.update(scenario_id=sid,trial_status='Complete',reviewed=True)
  trial['observations'].update(problems=2 if s['completed'] else 0 if sid in (13,14,15) else 1,
                               prompts_delivered=s['required_prompts'])
  for action in trial['actions'].values():action.update(occurrence=NA,timing=NA)
  def performed(key,at,reference=0):trial['actions'][key].update(occurrence=CORRECT,timing=CORRECT,action_at=str(at),reference_at=str(reference))
  performed('worksheet',1);performed('instruction',2)
  for n in range(s['required_prompts']):performed(f'prompt_{n+1}',10)
  performed('worksheet_removal',2 if s['completed'] else 10)
  trial['actions']['worksheet_removal']['branch']='Second problem completed' if s['completed'] else 'Second prompt; no work'
  if s['completed']:performed('earned_dolphin',2);performed('dolphin_removal',15)
  trial['behaviors'].update(no_unearned=CORRECT,no_excess=CORRECT,
                           no_work_prompts=CORRECT if trial['observations']['problems'] else NA,
                           no_tapping_comments=CORRECT if s['behavior']=='Finger tapping' else NA,
                           no_banging_comments=CORRECT if s['behavior']=='Table banging' else NA)
 return selection,trials

class TimingTests(unittest.TestCase):
 def test_inclusive_boundaries(self):
  for window in ((0,3),(8,12),(13,17)):
   lo,hi=window
   self.assertEqual(timing_result(lo,lo,hi),CORRECT)
   self.assertEqual(timing_result(hi,lo,hi),CORRECT)
   self.assertEqual(timing_result(lo-.001,lo,hi),TIMING_COMMISSION)
   self.assertEqual(timing_result(hi+.001,lo,hi),TIMING_OMISSION)
 def test_omitted_vs_late(self):
  late=assess_timed_action(action_at=15,reference_at=10,window=(0,3),end_at=20)
  omitted=assess_timed_action(action_at=None,reference_at=10,window=(0,3),end_at=20)
  self.assertEqual((late['occurrence'],late['timing']),(CORRECT,TIMING_OMISSION))
  self.assertEqual((omitted['occurrence'],omitted['timing']),(OMISSION,NA))
 def test_early_required_prompt(self):
  r=assess_timed_action(action_at=5,reference_at=0,window=(8,12),end_at=30)
  self.assertEqual((r['occurrence'],r['timing']),(CORRECT,TIMING_COMMISSION))
 def test_cutoff_and_participant_termination(self):
  base=dict(action_at=None,reference_at=10,window=(0,3))
  self.assertEqual(assess_timed_action(**base,end_at=12)['occurrence'],INTERRUPTED)
  self.assertEqual(assess_timed_action(**base,end_at=12,end_reason='participant')['occurrence'],TERMINATED)
  self.assertEqual(assess_timed_action(**base,end_at=13)['occurrence'],OMISSION)
  self.assertEqual(assess_timed_action(action_at=10,reference_at=0,window=(13,17),end_at=11)['timing'],TIMING_COMMISSION)
 def test_time_parsing_and_invalid_inputs(self):
  self.assertEqual(parse_time('01:03.5'),63.5)
  self.assertIsNone(parse_time(''))
  for value in ('nan','inf','-1','1:60','bad'):
   with self.assertRaises(ValueError):parse_time(value)

class SummaryTests(unittest.TestCase):
 def test_separate_scores_have_agreed_denominator(self):
  rows=[{'component':'test','step':'Test','measure':'Occurrence','result':CORRECT},
        {'component':'test','step':'Test','measure':'Timing','result':TIMING_OMISSION},
        {'component':'other','step':'Other','measure':'Occurrence','result':OMISSION},
        {'component':'other','step':'Other','measure':'Timing','result':NA}]
  result=summarize(rows)
  self.assertEqual((result['correct'],result['applicable']),(1,3))
  self.assertAlmostEqual(result['percent'],100/3)
 def test_perfect_session_and_step_totals(self):
  _,trials=perfect_session();r=score_trials(trials)
  self.assertEqual(r['validation_issues'],[])
  self.assertEqual(r['percent'],100)
  self.assertEqual(r['applicable'],144)
  self.assertEqual(sum(x['Applicable'] for x in r['step_summary']),r['applicable'])
 def test_late_delivery_not_an_entire_omission(self):
  _,trials=perfect_session();t=next(t for t in trials if t['actions']['earned_dolphin']['occurrence']==CORRECT)
  t['actions']['earned_dolphin'].update(timing=TIMING_OMISSION,action_at='5')
  r=score_trials(trials)
  self.assertEqual((r['correct'],r['applicable']),(143,144))
  self.assertEqual(r['counts'][TIMING_OMISSION],1)
  self.assertEqual(r['counts'][OMISSION],0)
 def test_omitted_delivery_removes_timing_from_denominator(self):
  _,trials=perfect_session();t=next(t for t in trials if t['actions']['earned_dolphin']['occurrence']==CORRECT)
  t['actions']['earned_dolphin'].update(occurrence=OMISSION,timing=NA,action_at='')
  r=score_trials(trials)
  self.assertEqual((r['correct'],r['applicable']),(142,143))
 def test_multiple_extra_events_one_trial_score(self):
  _,trials=perfect_session();t=trials[0]
  t['observations']['prompts_delivered']=4;t['behaviors']['no_excess']=COMMISSION
  t['events']=[{'Event':'Third prompt'},{'Event':'Fourth prompt'}]
  r=score_trials(trials)
  self.assertEqual(r['counts'][COMMISSION],1)
  self.assertEqual(r['applicable'],144)
 def test_behavior_partial_exposure(self):
  self.assertEqual(score_prohibition(violations=0,partial=True,exposure=3,minimum_exposure=3),CORRECT)
  self.assertEqual(score_prohibition(violations=0,partial=True,exposure=2.9,minimum_exposure=3),INTERRUPTED)
  self.assertEqual(score_prohibition(violations=1,partial=True,exposure=0.1,minimum_exposure=3),COMMISSION)
 def test_missing_not_reinterpreted_as_omission(self):
  t=empty_trials()[0];t['trial_status']='Complete';r=score_trials([t])
  self.assertGreater(r['missing'],0);self.assertEqual(r['counts'][OMISSION],0);self.assertIsNone(r['percent'])
 def test_timestamp_conflict_and_bad_partial_input(self):
  _,trials=perfect_session();trials[0]['actions']['instruction']['action_at']='10'
  self.assertTrue(score_trials(trials)['validation_issues'])
  trials[0]['trial_status']='Partial';trials[0]['observations']['incomplete_seconds']='bad'
  self.assertTrue(score_trials(trials)['validation_issues'])
 def test_same_canonical_records_same_summary_in_both_modes(self):
  _,trials=perfect_session();live=score_trials(trials)
  # A simulator submits these same record fields to the dependency-free reducer.
  simulator=summarize(deepcopy(live['details']))
  for field in ('correct','incorrect','applicable','percent','counts','step_summary'):
   self.assertEqual(live[field],simulator[field])

class CatalogAndPersistenceTests(unittest.TestCase):
 def test_all_324_orders_balanced_and_fixed(self):
  c=load_catalog();self.assertEqual(len(c['sets']),324)
  a=select_session(c,'DRA-001');b=select_session(c,'DRA-001')
  self.assertEqual(a['ordered_scenario_ids'],[9,11,12,1,8,4,5,18,6,2])
  self.assertEqual(a['ordered_scenario_ids'],b['ordered_scenario_ids'])
  self.assertEqual(len(session_plan(a,c)),10)
 def test_roundtrip_and_order_tampering(self):
  session,trials=perfect_session();payload=serialize_session(session,{},trials)
  restored=restore_session(payload);self.assertEqual(restored['trials'],trials)
  altered=json.loads(payload);altered['session']['ordered_scenario_ids'].reverse()
  with self.assertRaises(ValueError):restore_session(json.dumps(altered).encode())
 def test_legacy_files_are_not_silently_rescored(self):
  with self.assertRaises(ValueError):restore_session(b'{"schema_version":1}')
 def test_workbook_contains_real_summary_and_preserves_order(self):
  session,trials=perfect_session();session.update(participant_id='P1',session_number='1',notes='=2+2')
  scores=score_trials(trials);data=make_workbook(session,{},trials,scores,final=True)
  book=pd.ExcelFile(BytesIO(data))
  self.assertIn('Session Summary',book.sheet_names);self.assertIn('Event Log',book.sheet_names)
  summary=pd.read_excel(book,sheet_name='Session Summary')
  self.assertEqual(summary.iloc[0]['Overall fidelity (%)'],100)
  self.assertEqual(summary.iloc[0]['Applicable scores'],144)
  plan=pd.read_excel(book,sheet_name='Fixed Trial Plan')
  self.assertEqual(plan['Scenario'].tolist(),session['ordered_scenario_ids'])
  self.assertIsNone(summary_row(session,scores,final=False)['Overall fidelity (%)'])

if __name__=='__main__':unittest.main()
