"""Separate Streamlit entry point for the DRA video session mockup."""
from pathlib import Path
import json
import os
import re
import sys
import streamlit as st
import streamlit.components.v1 as components

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from scoring import RULES_VERSION
from simulator.media import manifest,available_playback,static_playback
from simulator.session import make_session

st.set_page_config(page_title='Mary · DRA Video Simulator',page_icon='🐬',layout='wide')
st.title('DRA Video Simulator')
st.caption('Mary’s Honors Thesis · Session mockup')
st.caption('This version records actions and tests video transitions. Research fidelity calculations are not enabled yet.')
settings=manifest()


@st.cache_resource(ttl=60,show_spinner=False)
def load_media():
    token=os.environ.get('DRA_GITHUB_TOKEN','')
    if not token:
        try: token=st.secrets.get('DRA_GITHUB_TOKEN','')
        except st.errors.StreamlitSecretNotFoundError: pass
    media=available_playback(token)
    return [r for r,path in media],static_playback(media)


start=False
if not st.session_state.get('video_session'):
    st.info('Run this simulator in Google Chrome. Firefox is not supported for this mockup. Use Test voice to check sound before starting.')
    with st.sidebar:
        st.header('Session setup')
        participant=st.text_input('Participant ID',value='TEST')
        session_id=st.text_input('Session ID',value='1')
        count=int(st.number_input('Number of trials',min_value=1,max_value=10,value=10,step=1))
        start=st.button('Start new session',type='primary')

if start:
    try:
        with st.spinner('Loading session videos…'): recordings,urls=load_media()
        run=make_session(count,participant,session_id,recordings)
    except (ValueError,RuntimeError) as exc: st.error('Session videos are not ready. '+str(exc))
    else:
        st.session_state['video_session']={'run':run,'recordings':recordings,'urls':urls}
        st.rerun()

saved=st.session_state.get('video_session')
if saved:
    st.markdown('<style>[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {display:none !important;}</style>',unsafe_allow_html=True)
    run=saved['run']
    component=components.declare_component('dra_session_v5',path=str(ROOT/'frontend'))
    base=st.get_option('server.baseUrlPath').strip('/')
    urls={k:('/'+base if base else '')+url for k,url in saved['urls'].items()}
    record=component(run=run,recordings=saved['recordings'],videos=urls,rules_version=RULES_VERSION,
        media_version=settings['version'],default=None,key='session_'+run['id'])
    if record:
        st.subheader('Session record')
        safe=lambda text:re.sub(r'[^A-Za-z0-9_-]+','_',text)[:60] or 'TEST'
        st.download_button('Download full JSON record',json.dumps(record,indent=2),
            file_name=f"P{safe(run['participant_id'])}_S{safe(run['session_id'])}_Video_Mockup.json",mime='application/json')
        st.dataframe(record.get('events',[]),use_container_width=True,hide_index=True)
        if record.get('ended') and st.button('Set up another session'):
            del st.session_state['video_session']
            st.rerun()
else: st.write('Enter the session information, choose the number of trials, and select **Start new session**.')
