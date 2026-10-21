"""Boundary checks for the playback mockup; the original scorer is unchanged."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import urllib.request
from simulator.media import manifest, prepare_video, _SafeRedirect


class SimulatorTests(unittest.TestCase):
    def test_manifest_preserves_both_behavior_types_and_finite_ranges(self):
        data = manifest()
        self.assertEqual({p['behavior'] for p in data['profiles']}, {'none', 'tapping', 'banging'})
        for p in data['profiles']:
            self.assertEqual(len(p['sha256']), 64)
            for start, end in p['segments'].values():
                self.assertGreaterEqual(start, 0)
                self.assertGreater(end, start)
            for key in ('idle', 'present', 'wait_0', 'work_1', 'work_2', 'wait_2', 'finished'):
                self.assertIn(key, p['segments'])

    def test_draft_access_is_required_without_local_media(self):
        with TemporaryDirectory() as d, patch.dict('os.environ', {'DRA_PLAYBACK_CACHE': d, 'DRA_SOURCE_DIR': ''}):
            with self.assertRaisesRegex(RuntimeError, 'not configured'):
                prepare_video(manifest()['profiles'][0])

    def test_cached_playback_does_not_download_original_again(self):
        profile = manifest()['profiles'][0]
        with TemporaryDirectory() as d, patch.dict('os.environ', {'DRA_PLAYBACK_CACHE': d}):
            target = Path(d) / (profile['sha256'] + '.mp4')
            target.write_bytes(b'x' * 1001)
            with patch('urllib.request.build_opener', side_effect=AssertionError('Unexpected download')):
                self.assertEqual(prepare_video(profile), target)

    def test_redirect_never_sends_github_token_to_storage_host(self):
        request = urllib.request.Request('https://api.github.com/repos/example', headers={'Authorization': 'Bearer TEST'})
        redirected = _SafeRedirect().redirect_request(request, None, 302, 'Found', {}, 'https://release-assets.githubusercontent.com/file')
        self.assertFalse(redirected.has_header('Authorization'))

    def test_landing_page_and_missing_access_state(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file('simulator/app.py').run()
        self.assertEqual(len(app.exception), 0)
        with TemporaryDirectory() as d, patch.dict('os.environ', {'DRA_PLAYBACK_CACHE': d, 'DRA_SOURCE_DIR': '', 'DRA_GITHUB_TOKEN': ''}):
            app.button[0].click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any('not configured' in item.value for item in app.error))


if __name__ == '__main__':
    unittest.main()
