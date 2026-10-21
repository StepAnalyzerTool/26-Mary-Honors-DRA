# DRA video session mockup

This separate Streamlit app runs a session using the available footage. The
in-person coding app and shared scoring engine are unchanged.

## Participant flow

1. Enter participant and session IDs. Choose **1–10 trials**, default **10**.
2. Select **Start new session**. There is no recording selector.
3. After the first video has loaded, select **BEGIN** to start the session clock.
4. Use the worksheet, task-direction, dolphin, stop-statement and praise buttons.
   Two independent unlabelled timers remain optional.
5. Providing a worksheet starts the next trial when the prior worksheet is
   absent. The session ends after the final trial closes, at ten minutes, or
   when **End session** is selected. If the last completed worksheet is removed
   before dolphin delivery, the session stays open for that delivery and access.
6. Save/download the full JSON session record.

The app uniformly selects one of the existing 324 fixed catalogue sets and
retains its ID, full ordered scenario list, requested trial count and exact
prefix used for a shorter mockup. Short prefixes are not claimed to preserve
the balance of a full ten-trial set. Scenario identity is kept in the data and
optional playback details, not presented as participant instructions.

## Footage coverage

All **18 distinct original recordings** are mapped in `media.json`; duplicates
are excluded. Immediate starts, nonstarts, no completed problems, one completed
problem, two together, and completion after a reminder are supported. Both finger
tapping and table banging remain in the design. Immediate scenarios begin work
after worksheet presentation even if the participant omits the initial direction.
The first task direction with a worksheet is the initial instruction; subsequent
directions are prompts. Nonresponsive scenarios stay nonresponsive after prompts.

The one table-banging recording supplies reusable waiting/working states for
several scenarios, so some paths use adapted cuts. The current footage does not
cover every combination of material state, problem count and behavior.

Every response button remains available after BEGIN. Early dolphin delivery,
premature worksheet removal, excess prompts and other participant actions are
recorded; actions are not blocked to force correct performance. Stop statements
and praise do not stop the simulated learner's prescribed behavior.

When an action animation is missing but its resulting state exists, playback
cuts directly to that state and logs `direct_cut`. If the resulting state is
also unavailable, a clear **Footage pending** slate replaces the video while
the session and buttons continue. Matching video resumes when a supported state
is reached. The program must never fill a missing branch by revealing two
completed answers before two problems were completed or by changing the scripted
behavior. Cross-take joins, loop restarts, missing clips and playback errors are
retained for review. After work begins, worksheet-visible clips stay within the
primary worksheet identity; worksheet-absent clips may be shared across takes.

Original source audio is retained during playback, including any audible filming
instructions, for student test-run review. Optional browser speech previews the
agreed button wording. Final speech recordings, loop seams,
transition cuts and precise completion tags still require review.

## Data and calculation boundary

These are **mockup session event records**, not scored research records. They
include fixed set/order, assigned source provenance, IDs, session/trial events,
task directions, provisional completion markers, material actions, timer use,
and footage gaps. They use a separate schema and are not ready for coding/IOA
imports. `scoring.RULES_VERSION` is imported from the same module as the
in-person app; no duplicate fidelity calculations have been introduced. The
event adapter must be validated against that engine before research scoring.

## Deployment (administrator documentation only)

- Repository: `StepAnalyzerTool/26-Mary-Honors-DRA`
- Branch: `simulator-playback-mockup`
- Main file: `simulator/app.py`
- Python dependencies: `simulator/requirements.txt`
- Root `packages.txt`: FFmpeg for preparing originals
- Root `.streamlit/config.toml`: enables serving generated playback MP4s

The app reads a server-side secret named `DRA_GITHUB_TOKEN`, restricted to
**Contents: read and write** (required to list private draft releases) on this repository. The token is not passed to the browser.
Keep app access limited to the research team while reviewing footage. Viewers
can retrieve the playback copies, so app access controls govern access to them.

Original recordings remain in the source **draft** release. The preparation
workflow verifies each original and creates a compressed MP4 retaining original source audio in a
separate **draft** release, `dra-mockup-playback-v3-audio`. Neither release is published.
The app downloads available compressed copies, verifies their byte length and
checksum and caches them. This avoids downloading/transcoding 20 GB of originals
on every new Streamlit server. Generated `simulator/static/dra-playback/` files are ignored
by Git and are served by the separate app's static handler.

If new playback copies are still being prepared, a session can use already
available recordings for a behavior, adapting cuts as needed. Starting a new
session after preparation completes uses the expanded footage bank.

For local use, prepared files are cached under `DRA_PLAYBACK_CACHE` (default
`/tmp/dra-playback-v1`) with filenames based on source SHA-256. Use a server-side
`DRA_GITHUB_TOKEN` to download prepared files, or use `prepare_video` from
`simulator/media.py` to transcode originals from `DRA_SOURCE_DIR` first.

```bash
pip install -r requirements.txt
streamlit run simulator/app.py
python -m unittest -q test_dra test_app test_simulator
node simulator/test_player.cjs
```
