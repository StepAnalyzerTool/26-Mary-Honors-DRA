# DRA Session Coder

Streamlit application for video-based coding of Differential Reinforcement of Alternative Behavior (DRA) sessions for Mary's honors thesis.

## Current scope

- Participant-ID-only session metadata
- Two session-setup observations
- Up to 10 trials, with early termination for the 10-minute session limit
- Reusable 3-, 10-, and 20-second countdowns plus a count-up stopwatch
- Draft conversion of observations to Correct, Incorrect, or N/A
- Session procedural-fidelity and step-level results
- Excel download containing metadata, observations, results, and scoring details
- Placeholder for the planned interobserver agreement module

The videos are stored and viewed outside this application. The app does not upload, process, or store video.

## Important research-status note

The scoring rules in `dra.py` are an initial implementation based on the current paper data sheet, a completed example, and the prior thesis. They must be reviewed and validated by the research team before research use. Measure wording and scoring logic are intentionally centralized for revision.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

