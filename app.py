from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from dra import (
    OBSERVATION_FIELDS,
    empty_trials,
    make_workbook,
    score_session,
)


st.set_page_config(page_title="DRA Session Coder", page_icon="⏱️", layout="wide")


def initialize_state() -> None:
    if "trials" not in st.session_state:
        st.session_state.trials = empty_trials()
    if "setup" not in st.session_state:
        st.session_state.setup = {
            "arrange_materials": None,
            "prepare_reinforcers": None,
        }
    if "session" not in st.session_state:
        st.session_state.session = {}


def timing_tools() -> None:
    with st.expander("⏱️ Timing tools", expanded=False):
        st.caption(
            "Use a preset countdown or the count-up stopwatch while viewing the video. "
            "Timers are aids only and do not alter a response automatically."
        )
        components.html(
            """
            <style>
              body { font-family: Arial, sans-serif; margin: 0; color: #17324d; }
              .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
              button { border:0; border-radius:7px; padding:9px 14px; cursor:pointer;
                       background:#e8f0f7; color:#17324d; font-weight:600; }
              button.primary { background:#1864ab; color:white; }
              #clock { font-size:38px; font-weight:700; min-width:135px; text-align:center; }
              #status { margin-top:8px; color:#536779; font-size:13px; }
            </style>
            <div class="row">
              <button onclick="preset(3)">3 seconds</button>
              <button onclick="preset(10)">10 seconds</button>
              <button onclick="preset(20)">20 seconds</button>
              <button onclick="countup()">Count up</button>
              <span id="clock">00:10.0</span>
            </div>
            <div class="row" style="margin-top:8px">
              <button class="primary" onclick="start()">Start</button>
              <button onclick="pause()">Pause</button>
              <button onclick="resetTimer()">Reset</button>
            </div>
            <div id="status">10-second countdown ready</div>
            <script>
              let mode='down', duration=10, remaining=10, elapsed=0;
              let running=false, startedAt=0, interval=null;
              const clock=document.getElementById('clock');
              const status=document.getElementById('status');
              function render(v) {
                v=Math.max(0,v); const m=Math.floor(v/60); const s=Math.floor(v%60);
                const d=Math.floor((v-Math.floor(v))*10);
                clock.textContent=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')+'.'+d;
              }
              function preset(sec){ pause(); mode='down'; duration=sec; remaining=sec; elapsed=0;
                render(sec); status.textContent=sec+'-second countdown ready'; }
              function countup(){ pause(); mode='up'; elapsed=0; remaining=0; render(0);
                status.textContent='Count-up stopwatch ready'; }
              function start(){ if(running) return; running=true; startedAt=performance.now();
                status.textContent='Timer running'; interval=setInterval(tick,50); }
              function tick(){ const delta=(performance.now()-startedAt)/1000; startedAt=performance.now();
                if(mode==='down'){ remaining-=delta; if(remaining<=0){remaining=0; pause(); status.textContent='Time expired'; beep();} render(remaining); }
                else { elapsed+=delta; render(elapsed); } }
              function pause(){ if(running){clearInterval(interval); running=false; status.textContent='Timer paused';} }
              function resetTimer(){ pause(); if(mode==='down'){remaining=duration; render(duration); status.textContent=duration+'-second countdown ready';}
                else {elapsed=0; render(0); status.textContent='Count-up stopwatch ready';} }
              function beep(){ try { const a=new AudioContext(); const o=a.createOscillator(); const g=a.createGain();
                o.connect(g);g.connect(a.destination);o.frequency.value=700;g.gain.value=.08;o.start();o.stop(a.currentTime+.18);} catch(e){} }
              render(10);
            </script>
            """,
            height=155,
        )


def yn(label: str, key: str, allow_na: bool = False, help_text: str | None = None):
    options = [None, "Y", "N"] + (["NA"] if allow_na else [])
    labels = {None: "Select...", "Y": "Yes", "N": "No", "NA": "Not applicable"}
    return st.selectbox(
        label,
        options,
        format_func=lambda value: labels[value],
        key=key,
        help=help_text,
    )


def collection_tab() -> None:
    st.subheader("Session information")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        participant_id = st.text_input("Participant ID", value=st.session_state.session.get("participant_id", ""))
        session_number = st.text_input("Session number", value=st.session_state.session.get("session_number", ""))
    with c2:
        simulated_learner = st.text_input("Simulated learner", value=st.session_state.session.get("simulated_learner", ""))
        script_number = st.text_input("Script number", value=st.session_state.session.get("script_number", ""))
    with c3:
        data_collector = st.text_input("Data collector", value=st.session_state.session.get("data_collector", ""))
        collector_role = st.selectbox("Collector role", ["Primary", "Secondary"])
    with c4:
        session_date = st.date_input("Date", value=st.session_state.session.get("date", date.today()))
        end_reason = st.selectbox("Session end reason", ["10 trials completed", "10-minute timer reached"])

    st.session_state.session = {
        "participant_id": participant_id.strip(),
        "session_number": session_number.strip(),
        "simulated_learner": simulated_learner.strip(),
        "script_number": script_number.strip(),
        "data_collector": data_collector.strip(),
        "collector_role": collector_role,
        "date": session_date,
        "end_reason": end_reason,
    }

    st.subheader("Session setup")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.setup["arrange_materials"] = yn(
            "Were materials arranged outside of reach?",
            "setup_arrange",
        )
    with c2:
        st.session_state.setup["prepare_reinforcers"] = yn(
            "Were reinforcers prepared?",
            "setup_prepare",
        )

    timing_tools()

    st.subheader("Trial observations")
    completed_trials = st.number_input(
        "Number of trials completed",
        min_value=1,
        max_value=10,
        value=10,
        help="Use fewer than 10 when the session ended because the timer was reached.",
    )
    trial_number = st.select_slider("Trial to code", options=list(range(1, int(completed_trials) + 1)))
    current = st.session_state.trials[trial_number - 1]

    with st.form(f"trial_form_{trial_number}"):
        st.markdown(f"#### Trial {trial_number}")
        c1, c2, c3 = st.columns(3)
        responses = {}
        for index, field in enumerate(OBSERVATION_FIELDS):
            container = (c1, c2, c3)[index % 3]
            with container:
                if field["kind"] == "count":
                    responses[field["key"]] = st.number_input(
                        field["label"], min_value=0, step=1,
                        value=int(current.get(field["key"], 0) or 0),
                        key=f"t{trial_number}_{field['key']}",
                    )
                else:
                    choices = [None, "Y", "N"] + (["NA"] if field.get("allow_na") else [])
                    responses[field["key"]] = st.selectbox(
                        field["label"], choices,
                        index=choices.index(current.get(field["key"])) if current.get(field["key"]) in choices else 0,
                        format_func=lambda v: {None:"Select...","Y":"Yes","N":"No","NA":"Not applicable"}[v],
                        key=f"t{trial_number}_{field['key']}",
                    )
        saved = st.form_submit_button("Save trial", type="primary", use_container_width=True)
        if saved:
            st.session_state.trials[trial_number - 1].update(responses)
            st.success(f"Trial {trial_number} saved.")

    notes = st.text_area("Session notes", value=st.session_state.session.get("notes", ""))
    st.session_state.session["notes"] = notes
    st.session_state.session["completed_trials"] = int(completed_trials)


def results_tab() -> None:
    scores = score_session(
        st.session_state.setup,
        st.session_state.trials[: int(st.session_state.session.get("completed_trials", 10))],
    )
    st.subheader("Current session results")
    if scores["applicable"] == 0:
        st.info("Enter and save session observations to calculate results.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Procedural fidelity", f"{scores['percent']:.1f}%")
    c2.metric("Correct opportunities", f"{scores['correct']} / {scores['applicable']}")
    c3.metric("Unscored observations", scores["missing"])

    st.caption(
        "Draft scoring rules are based on the current DRA sheet and thesis. "
        "They are centralized in dra.py and should be reviewed before research use."
    )
    summary = pd.DataFrame(scores["step_summary"])
    st.dataframe(summary, hide_index=True, use_container_width=True)

    with st.expander("Trial-by-trial scoring details"):
        st.dataframe(pd.DataFrame(scores["details"]), hide_index=True, use_container_width=True)

    workbook = make_workbook(st.session_state.session, st.session_state.setup, st.session_state.trials, scores)
    name_parts = [
        st.session_state.session.get("participant_id") or "participant",
        f"session-{st.session_state.session.get('session_number') or 'unknown'}",
        st.session_state.session.get("data_collector") or "collector",
    ]
    st.download_button(
        "Download session workbook",
        data=workbook,
        file_name="DRA_" + "_".join(name_parts) + ".xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


initialize_state()
st.title("DRA Session Coder")
st.caption("Mary's Honors Thesis · Video-based procedural-fidelity coding")

collection, results, ioa = st.tabs(["DRA Data Collection", "Results", "IOA"])
with collection:
    collection_tab()
with results:
    results_tab()
with ioa:
    st.subheader("Interobserver agreement")
    st.info("The IOA file-comparison module will be added after the session workbook format is validated.")

