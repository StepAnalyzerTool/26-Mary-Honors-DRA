"""Streamlit workflow tests; no browser session or participant data required."""
import logging
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from test_dra import perfect_session
from scoring import CORRECT, TIMING_COMMISSION, TIMING_OMISSION, NA

class AppWorkflowTests(unittest.TestCase):
 def setUp(self):
  logging.disable(logging.WARNING)
 def tearDown(self):
  logging.disable(logging.NOTSET)
 def app(self):
  return AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30)
 def assert_no_exception(self,app):
  self.assertFalse(app.exception,[e.message for e in app.exception])
 def test_selection_navigation_and_separate_score_controls(self):
  app=self.app().run();self.assert_no_exception(app)
  app.radio(key='workspace').set_value('Session planner').run()
  next(b for b in app.button if b.label=='Use this set').click().run()
  self.assertEqual(app.session_state['planner_selection']['set_id'],'DRA-001')
  fixed=list(app.session_state['planner_selection']['ordered_scenario_ids'])
  self.assertNotIn('set_id',app.session_state['session'])
  self.assertTrue(all(t['scenario_id'] is None for t in app.session_state['trials']))
  app.radio(key='workspace').set_value('Session coder').run()
  app.checkbox(key='code_1_status_check_1').check().run()
  app.checkbox(key='code_1_worksheet_occ_check_0').check().run()
  app.checkbox(key='code_1_worksheet_timing_check_1').check().run()
  app.checkbox(key='code_1_worksheet_direction_check_0').check().run()
  app.radio(key='trial_index').set_value(2).run()
  app.radio(key='trial_index').set_value(1).run();self.assert_no_exception(app)
  self.assertEqual(app.session_state['trials'][0]['actions']['worksheet']['timing'],TIMING_COMMISSION)
  self.assertEqual(app.session_state['planner_selection']['ordered_scenario_ids'],fixed)
  self.assertFalse(any('Expected prompts' in x.value for x in app.info))
 def test_completed_session_final_summary_and_dirty_review(self):
  session,trials=perfect_session()
  session.update(participant_id='P1',session_number='1',data_collector='Mary',collector_role='Primary',
                 date='2026-10-03',end_reason='10 trials completed',end_at='8:00')
  app=self.app();app.session_state['session']=session;app.session_state['trials']=trials
  app.run();self.assert_no_exception(app)
  self.assertEqual(next(m.value for m in app.metric if m.label=='Overall fidelity'),'100.0%')
  app.checkbox(key='code_1_instruction_timing_check_1').check().run()
  app.checkbox(key='code_1_instruction_direction_check_1').check().run()
  self.assertTrue(any('timing conflicts' in e.value for e in app.error))
  self.assertFalse(app.session_state['trials'][0]['reviewed'])
  self.assertTrue(any(m.label=='Provisional fidelity' for m in app.metric))
 def test_random_selection_does_not_redraw_on_rerun(self):
  app=self.app().run()
  app.radio(key='workspace').set_value('Session planner').run()
  next(b for b in app.button if b.label=='Randomly select a session').click().run()
  selection=dict(app.session_state['planner_selection'])
  app.run()
  self.assertEqual(app.session_state['planner_selection']['set_id'],selection['set_id'])
  self.assertEqual(app.session_state['planner_selection']['selected_at'],selection['selected_at'])

if __name__=='__main__':unittest.main()
