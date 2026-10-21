"""Separate Streamlit entry point for the DRA video playback mockup."""
from pathlib import Path
import base64
import json
import os
import re
import sys
import uuid

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from scoring import RULES_VERSION  # Same source used by the in-person app.
from simulator.media import manifest, prepare_video

st.set_page_config(page_title='Mary · DRA Video Simulator', page_icon='🐬', layout='wide')
st.title('DRA Video Simulator')
st.caption('Mary’s Honors Thesis · Video playback mockup')
st.info('Try the action buttons and check the video transitions. This is a playback test; it does not calculate research fidelity scores.')

settings = manifest()
profiles = settings['profiles']


@st.cache_resource(show_spinner=False)
def playback_video(profile_id):
    """Serialize first-load preparation for each recording across app reruns."""
    profile = next(p for p in profiles if p['id'] == profile_id)
    token = os.environ.get('DRA_GITHUB_TOKEN', '')
    if not token:
        try:
            token = st.secrets.get('DRA_GITHUB_TOKEN', '')
        except st.errors.StreamlitSecretNotFoundError:
            pass
    return prepare_video(profile, token)

with st.sidebar:
    st.header('Playback test')
    choice = st.selectbox('Recording', range(len(profiles)), format_func=lambda i: profiles[i]['label'])
    participant = st.text_input('Participant ID', value='TEST')
    session = st.text_input('Session ID', value='1')
    st.caption('These are individual test recordings, not a balanced 10-trial catalogue session.')
    if st.button('Load / restart test', type='primary'):
        st.session_state['playback_run'] = {
            'id': str(uuid.uuid4()), 'profile_id': profiles[choice]['id'],
            'participant_id': participant, 'session_id': session}
    st.markdown('**What to try**')
    st.write('Provide the worksheet, give a task direction, and try the other buttons. On the pause recordings, another task direction starts the second problem.')
    st.write('Some action orders have no matching footage yet. The mockup will identify those gaps instead of showing a contradictory worksheet state.')
    st.caption('Both timers are optional. Stop statements and praise do not stop tapping or banging. Browser speech is a temporary audio preview.')

run = st.session_state.get('playback_run')
if run:
    profile = next(p for p in profiles if p['id'] == run['profile_id'])
    try:
        with st.spinner('Preparing the recording. The first load can take several minutes…'):
            path = playback_video(profile['id'])
            encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    except RuntimeError as exc:
        st.error(str(exc))
    else:
        component = components.declare_component('dra_playback', path=str(ROOT / 'frontend'))
        record = component(
            run=run, profile=profile, rules_version=RULES_VERSION,
            media_version=settings['version'], video='data:video/mp4;base64,' + encoded,
            default=None, key='playback_' + run['id'])
        if record:
            st.subheader('Playback test record')
            st.caption('Raw actions, video events, and unsupported transitions. No fidelity score has been assigned.')
            safe = lambda text: re.sub(r'[^A-Za-z0-9_-]+', '_', text)[:60] or 'TEST'
            st.download_button('Download full JSON record', json.dumps(record, indent=2),
                file_name=f"P{safe(run['participant_id'])}_S{safe(run['session_id'])}_Video_Mockup.json",
                mime='application/json')
            st.dataframe(record.get('events', []), use_container_width=True, hide_index=True)
else:
    st.write('Choose a recording and select **Load / restart test** to begin.')

with st.expander('Deployment and playback notes'):
    st.markdown('''Deploy a **new** Streamlit app using this repository, branch `simulator-playback-mockup`, and entry point `simulator/app.py`.

The originals are stored in a draft GitHub release. Add `DRA_GITHUB_TOKEN` in this new app’s Streamlit secrets, using a fine-grained token with **Contents: read** access to `StepAnalyzerTool/26-Mary-Honors-DRA`. Do not paste the token into this page or commit it to GitHub. The backend downloads and verifies only the chosen recording and prepares a cached MP4 copy. The token stays on the server.

For local use, set `DRA_SOURCE_DIR` to the folder containing the original MOV files. Start with `streamlit run simulator/app.py` from the repository root.

Playback copies have no source audio, to avoid playing filming directions. Optional browser speech previews the buttons until recorded speech is available. Seek points and problem-completion markers are provisional. This mockup logs events, video loading, and unsupported transitions; it does not yet submit automatic scores to `scoring.py`. That shared engine remains the source for eventual matched calculations.''')
