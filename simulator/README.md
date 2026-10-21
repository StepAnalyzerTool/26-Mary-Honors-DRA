# DRA video playback mockup

Separate Streamlit app for testing the current recordings and response buttons.
The existing in-person entry point, `app.py`, is unchanged.

## Deploy the separate app

In Streamlit Community Cloud choose **Create app**, then:

- Repository: `StepAnalyzerTool/26-Mary-Honors-DRA`
- Branch: `simulator-playback-mockup`
- Main file: `simulator/app.py`
- Suggested subdomain: `mary-dra-video-mockup` (availability is not guaranteed)

The source recordings remain in the existing **draft** GitHub release. They
are not published by this change. In the new app's Advanced settings / Secrets,
add a fine-grained GitHub token restricted to this repository with
**Contents: read** permission:

```toml
DRA_GITHUB_TOKEN = "YOUR_READ_ONLY_TOKEN"
```

Keep the new app's access limited to the research team while reviewing footage.
The app sends the selected playback video to its viewers, so app access controls
govern who can view it. The token itself is server-side only.

The branch's root `packages.txt` installs FFmpeg and `simulator/requirements.txt` reuses
the existing Python requirements. First load downloads one full original,
verifies its size/SHA-256 and prepares a 960-pixel H.264 MP4 playback copy.
Subsequent loads use the cache. Originals and playback files are not committed.

## Local testing

Install FFmpeg, then from the repository root:

```bash
pip install -r requirements.txt
export DRA_SOURCE_DIR=/absolute/path/to/originals
streamlit run simulator/app.py
```

Alternatively set `DRA_GITHUB_TOKEN` in the environment or `.streamlit/secrets.toml`.
No Dropbox links, temporary download URLs, or access tokens belong in source.

## Included playback tests

Three original recordings are mapped in `media.json`:

1. No tapping/banging: two problems together; dolphin; worksheet removed;
   continued play; dolphin removed.
2. Finger tapping: one problem; wait; second problem after another task
   direction; dolphin; worksheet removed; continued play; dolphin removed.
3. Table banging: one problem; wait; second problem after another task
   direction; dolphin; dolphin removed; worksheet removed; continued banging.

Click **Load / restart test**, then **BEGIN**. Provide the worksheet, give a
task direction, and try the available response options. Two optional independent
timers are unlabelled. The session clock ends the test at ten minutes. Providing
the next worksheet starts the next test trial after the prior materials have
been removed. This repeats the chosen recording; it does not select a balanced
catalogue session. At most ten test trials can be presented.

The action controls execute in the browser without a Streamlit rerun. Native
video seeking changes segments in a single video element. Waiting segments loop;
their visible joins are intentionally available for inspection. Stop statements
and praise never change the learner's behavior or task progress. Task directions
are classified provisionally; in pause tests another direction starts the second
problem regardless of its timing, allowing early-prompt playback testing.

This is intentionally a limited playback mockup. Only filmed transitions in
the chosen recording are enabled. Early dolphin delivery, unfinished worksheet
removal, actions during working/transition clips, and alternative removal orders
are logged as **unsupported transitions** when no matching clip exists. The
video stays in its existing state; it must not reveal already completed answers
or switch behavior to simulate a missing branch. This is not a restriction to
carry into the final assessment: all participant error opportunities must be
supported before research use. Additional recordings can extend the manifest.

Source audio is omitted because it may include filming instructions. Optional
browser speech previews button wording until recorded speech clips are ready.
Seek points and completion markers remain provisional and need fine adjustment.

## Data and scoring boundary

Use **Save test record** at any point or **End test**, then download the JSON
under the video. Saving does not restart playback. Records contain participant
and session IDs, run UUID, source provenance, elapsed times, source-video times,
button attempts, provisional problem markers, video loading/loop events, timer
use and unsupported transitions. They have a distinct mockup schema and must
not be imported into in-person coding/IOA as scored sessions.

The app imports the original `scoring.RULES_VERSION`; it neither duplicates nor
changes the in-person scoring functions. It does **not** calculate fidelity.
The later event-to-score adapter must be tested against `scoring.py` for the
same actions, exclusions, cutoffs and denominators before scored research use.

Validation commands:

```bash
python -m unittest -q test_dra test_app test_simulator
node simulator/test_player.cjs
```
