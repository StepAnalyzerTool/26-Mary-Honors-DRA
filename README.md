# DRA Session Coder

Streamlit application for coding recordings of in-person Differential Reinforcement of Alternative Behavior (DRA) sessions for Mary's honors thesis.

## Current scope

- A Session Selection tab with 324 validated fixed 10-trial sets, DRA-001 through DRA-324
- Random set selection or lookup of the set used in a recorded session; the stored order is never reshuffled
- Trial-by-trial coding with separate required-action occurrence and timing scores
- Correct, omission, commission, timing omission, timing commission, N/A, interrupted, and participant-terminated classifications
- Two optional independent timing aids
- A scoring appendix and concrete undergraduate-coder examples beside each measure
- A shared dependency-free `scoring.py` module for the future simulator and this coding app
- Overall procedural fidelity, individual occurrence/timing summaries, and error classifications
- Draft/final distinction: incomplete or inconsistent coding is not exported as a finalized graph point
- Excel exports with session summary, fixed plan, observations, action records, step summaries, scored opportunities, event log, and coding instructions
- CSV summary downloads and editable JSON backups for resuming a session
- Placeholder for the planned interobserver agreement module

The videos are stored and viewed outside this application. The app does not upload, process, or store video.

## Scoring and consistency

Rules version: `DRA-2026-10-03`. Catalog version: `DRA-v1.1`.

The agreed main dependent variable is correct applicable scores divided by all applicable scores, multiplied by 100. Occurrence and timing contribute separately. An action delivered late contributes occurrence correct and timing incorrect. An action entirely omitted contributes occurrence incorrect and timing N/A. N/A, Interrupted, and Terminated by participant are excluded. There is no fixed denominator.

Early required prompts and early worksheet removal receive occurrence correct and timing commission. Unearned dolphin delivery, excess prompts, prompts during ongoing work, and stop statements are commission behaviors. Each behavior measure is scored once per applicable trial; individual instances remain in the event log. One event may violate more than one independently agreed behavior measure.

The timer targets are 10 seconds for waits and 15 seconds for dolphin access. Accepted scoring windows are 8–12 and 13–17 seconds respectively. Worksheet presentation, initial instruction, earned delivery, and completed worksheet removal have 3-second deadlines. Tapping and banging do not alter task requirements.

Setup observations are retained descriptively and do not add unagreed measures to the main dependent variable. Partial trials may count correct withholding or no-stop-statement scores after at least 3 seconds of relevant exposure. All actual commissions remain recorded regardless of exposure length.

`scoring.py` is the only summary/denominator implementation. Both modes must submit the same canonical records to `summarize()`. It also supplies required-action timing and prohibition classifiers. The simulator's playback-event adapter will be implemented with that program; this revision does not build the simulator or infer live behavior from video.

## Coding workflow

1. Use Session Selection to randomly draw a set for a new live session or look up its existing ID. Download the fixed plan. Once coding begins the selected set is locked.
2. Enter session/observer information and the observed session endpoint.
3. Code each reached trial as Complete or Partial. Record observations, occurrence, timing, timestamps when available, and error events. Read the per-component rules/examples to decide applicability; the planned script never substitutes for observations.
4. Mark each reached trial reviewed. Results show validation issues and unscored fields. Timing selections that conflict with entered timestamps block finalization.
5. Download the final workbook/CSV for completed coding. Download a JSON backup to resume later; browser state alone is not durable storage.

The final graph field is blank in draft exports; provisional accuracy is in a separate column. Record the final numerator and denominator with the percentage. Primary and secondary observer identity is retained for future IOA comparison.

Legacy Excel exports used materially different rules (including 20-second access and removal following banging). Preserve them as historical files; they cannot be silently rescored as the new format. New JSON backups include schema, rules, catalog, and set-order checks.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Validation

```bash
python -m unittest -v test_dra
```

Tests cover timing boundaries, omission versus late delivery, session/participant cutoff, partial-trial exposure, separate occurrence/timing denominators, all 324 catalog sets/orders, backup integrity, and workbook summary/export consistency. `test_app.py` additionally exercises selection, navigation, scoring choices, and final summaries using Streamlit AppTest.

