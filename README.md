# DRA Session Coder

Planning and coding in-person Differential Reinforcement of Alternative Behavior (DRA) sessions for Mary's honors thesis, 2026–2027.

## Independent records

- **Scenario Selection and Simulated-Learner Fidelity:** uniformly select one of 324 fixed 10-trial sets. Retain its set ID and exact order. Show short earpiece scripts, learner-fidelity Yes/No/Not observed checks, and notes. Download participant/session-named JSON and Excel files containing session information, fidelity totals, and the checklist.
- **Session Coding:** code only observed participant and learner behavior. The selected plan, scenario IDs, and organizer fidelity scores are not imported. Trials open as Complete; Partial and Not Observed are optional statuses.
- **Coding Instructions:** the only rules/examples location. Tables wrap text.
- **Results:** correct/applicable counts, overall fidelity, individual occurrence/timing summaries, errors, draft/final validation, Excel/CSV summaries, and full JSON session records.
- **IOA:** observer identities are retained; the comparison module is still planned.

Videos are viewed outside the app. This program does not upload or automatically analyze recordings.

## Scoring

The shared `scoring.py` engine computes correct applicable scores / all applicable scores × 100. Required-action occurrence and timing contribute separately. An on-time action is 2/2; a late required action is 1/2; an omitted action is 0/1 because its timing is N/A. N/A, Interrupted, Terminated by participant, and missing values are excluded from the denominator; missing values prevent a final summary.

Participant targets remain 10-second waits and 15-second earned dolphin access. Inclusive scoring windows are 8–12 seconds and 13–17 seconds. Worksheet presentation, initial instruction, earned dolphin delivery, and completed worksheet removal use three-second deadlines. There is no one-minute trial limit; sessions end after 10 trials or at 10 minutes.

Earned dolphin delivery has only on-time/late timing. Delivery before two completed problems is a separate inappropriate-delivery commission. Removal occurrence and access-duration timing apply **only after earned delivery**; inappropriate-only access produces no duration error and both removal measures are N/A. Action records and scored details in Excel use the same exclusions as the summary.

Two prompts maximum per trial exclude the initial instruction. First/second required prompts retain occurrence and timing; a separate Yes/No no-excess-prompts measure captures third/later prompts. No numeric count is required. Ongoing work continues from writing onset through answer completion, including brief pauses.

Finger tapping and table banging do not change the work requirement. No-stop-statement scores apply to observed behavior; actual statements remain commissions even in brief observations. Correct withholding/no-comment scores on partial trials need confirmation of at least three seconds of the relevant opportunity; no exact duration is entered.

Setup, observed problems/tapping/banging, and timer use are descriptive, outside the participant fidelity denominator. Organizer Simulated-Learner fidelity is a separate calculation: Yes / (Yes + No), excluding Not observed/unrecorded.

## Coding workflow

1. Enter participant, session, observer, and endpoint information independently of the organizer plan.
2. Open each observed trial. Use Partial or Not Observed as appropriate.
3. Record learner behavior, then participant actions and timing with compact left-aligned checkboxes. Exact per-action timestamps and numeric prompt counts are not required.
4. Consult Coding Instructions for definitions and examples. Optional notes/event details do not add denominator units.
5. Mark each trial reviewed. Resolve missing or inconsistent scores; drafts keep the final graph field blank.
6. Complete coding in one sitting, then download the final workbook/summary and full JSON record before leaving. Browser state is temporary.

Historical event times can remain as optional source details in archived records. In-person checkbox judgments govern manual coding; automatic event-based checks remain available for the future simulator. The simulator itself is not implemented.

## Run and test

```bash
pip install -r requirements.txt
streamlit run app.py
python -m unittest -v test_dra test_app
```

Tests cover all 324 catalog orders, separate denominators, early/late/omitted actions, cutoffs, partial exposure, earned-only duration, export consistency, independent coding, checkbox persistence, and planner fidelity.
