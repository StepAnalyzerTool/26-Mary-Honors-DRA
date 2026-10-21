import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import urllib.request
from simulator.media import manifest,available_playback,_SafeRedirect
from simulator.session import make_session
from dra import load_catalog


class SimulatorTests(unittest.TestCase):
    def test_all_distinct_footage_is_mapped(self):
        rows=manifest()['recordings']
        self.assertEqual(len(rows),18)
        self.assertEqual(len({r['sha256'] for r in rows}),18)
        self.assertEqual({r['behavior'] for r in rows},{'none','tapping','banging'})
        for r in rows:
            for start,end in r['segments'].values(): self.assertTrue(0<=start<end)

    def test_every_catalogue_set_preserves_exact_order(self):
        rows=manifest()['recordings']
        for item in load_catalog()['sets']:
            run=make_session(10,'P','S',rows,item['set_id'])
            self.assertEqual(run['planned_scenario_ids'],item['ordered_scenario_ids'])
            self.assertEqual(sum(s['completed'] for s in run['plan']),5)
            self.assertEqual(sum(s['required_prompts'] for s in run['plan']),13)
            self.assertEqual(len(run['plan']),10)

    def test_short_sessions_are_prefixes_not_new_sets(self):
        run=make_session(3,'P','S',manifest()['recordings'],'DRA-001')
        self.assertEqual(run['planned_scenario_ids'],run['ordered_scenario_ids'][:3])
        self.assertEqual(len(run['ordered_scenario_ids']),10)
        for count in (0,11,True,2.5):
            with self.assertRaises(ValueError): make_session(count,'P','S',manifest()['recordings'])

    def test_partial_media_bank_can_run_catalogue_patterns(self):
        rows=[r for r in manifest()['recordings'] if r['id'] in ('n2dwt','f11dwt','b11dtw')]
        run=make_session(10,'P','S',rows,'DRA-001')
        self.assertEqual(len(run['plan']),10)
        self.assertTrue(any(s['footage_adapted'] for s in run['plan']))

    def test_no_video_access_is_an_empty_bank(self):
        with TemporaryDirectory() as d,patch.dict('os.environ',{'DRA_PLAYBACK_CACHE':d}): self.assertEqual(available_playback(),[])

    def test_cached_copies_do_not_download_originals(self):
        r=manifest()['recordings'][0]
        with TemporaryDirectory() as d,patch.dict('os.environ',{'DRA_PLAYBACK_CACHE':d}):
            (Path(d)/(r['sha256']+'-audio-v3.mp4')).write_bytes(b'x'*1001)
            self.assertEqual(available_playback()[0][0]['id'],r['id'])

    def test_redirect_strips_access_token(self):
        request=urllib.request.Request('https://api.github.com/repos/example',headers={'Authorization':'Bearer TEST'})
        redirected=_SafeRedirect().redirect_request(request,None,302,'Found',{},'https://release-assets.githubusercontent.com/file')
        self.assertFalse(redirected.has_header('Authorization'))

    def test_session_screen_does_not_render_setup_fields(self):
        from streamlit.testing.v1 import AppTest
        rows=manifest()['recordings']
        app=AppTest.from_file('simulator/app.py')
        app.session_state['video_session']={'run':make_session(1,'TEST','1',rows),
            'recordings':rows,'urls':{r['id']:'/app/static/test.mp4' for r in rows}}
        app.run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.text_input),0)
        self.assertEqual(len(app.number_input),0)
        self.assertFalse(any(b.label=='Start new session' for b in app.button))

    def test_setup_is_session_based_and_contains_no_deployment_instructions(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file('simulator/app.py').run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.number_input[0].value,10)
        self.assertEqual(len(app.selectbox),0)
        self.assertTrue(any('Google Chrome' in item.value for item in app.info))
        self.assertEqual(app.button[0].label,'Start new session')
        self.assertEqual(len(app.expander),0)
        with TemporaryDirectory() as d,patch.dict('os.environ',{'DRA_PLAYBACK_CACHE':d,'DRA_GITHUB_TOKEN':''}):
            app.button[0].click().run()
            self.assertEqual(len(app.exception),0)
            self.assertTrue(app.error)


if __name__=='__main__': unittest.main()
