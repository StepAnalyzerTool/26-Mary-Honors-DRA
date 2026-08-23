from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from typing import Any

import pandas as pd


OBSERVATION_FIELDS = [
    {"key": "worksheet", "label": "Worksheet provided?", "kind": "yn"},
    {"key": "instruction", "label": "Initial instruction presented?", "kind": "yn"},
    {"key": "prompt", "label": "Additional prompt provided?", "kind": "yn"},
    {"key": "began_within_10", "label": "Learner began within 10 seconds of initial instruction?", "kind": "yn"},
    {"key": "problems", "label": "Math problems completed", "kind": "count"},
    {"key": "target_behavior", "label": "Target challenging behavior occurred?", "kind": "yn"},
    {"key": "minor_behavior", "label": "Minor behavior occurred?", "kind": "yn"},
    {"key": "reinforcer_within_3", "label": "Reinforcer provided within 3 seconds of 2 problems?", "kind": "yn", "allow_na": True},
    {"key": "reinforcer_20_seconds", "label": "Reinforcer access lasted 20 seconds?", "kind": "yn", "allow_na": True},
    {"key": "reinforcer_for_target", "label": "Reinforcer provided contingent on target behavior?", "kind": "yn", "allow_na": True},
    {"key": "worksheet_removed_for_target", "label": "Worksheet removed contingent on target behavior?", "kind": "yn", "allow_na": True},
    {"key": "reinforcer_other_time", "label": "Reinforcer provided at another time?", "kind": "yn"},
    {"key": "other_stimulus_for_two", "label": "Other stimulus provided contingent on 2 problems?", "kind": "yn", "allow_na": True},
    {"key": "other_stimulus_for_target", "label": "Other stimulus provided contingent on target behavior?", "kind": "yn", "allow_na": True},
    {"key": "other_stimulus_other_time", "label": "Other stimulus provided at another time?", "kind": "yn"},
]


STEP_LABELS = {
    "arrange_materials": "Arrange materials outside of reach",
    "prepare_reinforcers": "Prepare reinforcers",
    "worksheet": "Provide worksheet",
    "instruction": "Present initial instruction",
    "prompt": "Provide an additional prompt when needed",
    "reinforcer_within_3": "Deliver reinforcer within 3 seconds",
    "reinforcer_20_seconds": "Provide 20 seconds of reinforcer access",
    "reinforcer_for_target": "Do not reinforce target challenging behavior",
    "worksheet_removed_for_target": "Remove worksheet following target challenging behavior",
    "reinforcer_other_time": "Do not provide reinforcer at another time",
    "other_stimulus_for_two": "Do not provide another stimulus for 2 problems",
    "other_stimulus_for_target": "Do not provide another stimulus for target challenging behavior",
    "other_stimulus_other_time": "Do not provide another stimulus at another time",
}


ERROR_TYPES = {
    "arrange_materials": "Omission",
    "prepare_reinforcers": "Omission",
    "worksheet": "Omission",
    "instruction": "Omission",
    "prompt": "Omission or commission",
    "reinforcer_within_3": "Omission",
    "reinforcer_20_seconds": "Omission",
    "reinforcer_for_target": "Commission",
    "worksheet_removed_for_target": "Omission",
    "reinforcer_other_time": "Commission",
    "other_stimulus_for_two": "Commission",
    "other_stimulus_for_target": "Commission",
    "other_stimulus_other_time": "Commission",
}


def empty_trials() -> list[dict[str, Any]]:
    return [{"trial": i, **{f["key"]: (0 if f["kind"] == "count" else None) for f in OBSERVATION_FIELDS}} for i in range(1, 11)]


def _result(value: Any, expected: str, applicable: bool = True) -> str:
    if not applicable or value == "NA":
        return "N/A"
    if value is None:
        return "Missing"
    return "Correct" if value == expected else "Incorrect"


def score_trial(trial: dict[str, Any]) -> list[dict[str, Any]]:
    began = trial.get("began_within_10")
    problems = int(trial.get("problems") or 0)
    target = trial.get("target_behavior")
    rules = [
        ("worksheet", _result(trial.get("worksheet"), "Y")),
        ("instruction", _result(trial.get("instruction"), "Y")),
        # A prompt is required only when the learner did not begin within 10 seconds
        # of the INITIAL instruction. This assumption was confirmed 2026-08-23.
        ("prompt", _result(trial.get("prompt"), "N" if began == "Y" else "Y", began in {"Y", "N"})),
        ("reinforcer_within_3", _result(trial.get("reinforcer_within_3"), "Y", problems >= 2)),
        # The paper sheet treats this item as applicable whenever access occurred;
        # coders indicate N/A when no access occurred.
        ("reinforcer_20_seconds", _result(trial.get("reinforcer_20_seconds"), "Y", trial.get("reinforcer_20_seconds") != "NA")),
        ("reinforcer_for_target", _result(trial.get("reinforcer_for_target"), "N", target == "Y")),
        ("worksheet_removed_for_target", _result(trial.get("worksheet_removed_for_target"), "Y", target == "Y")),
        ("reinforcer_other_time", _result(trial.get("reinforcer_other_time"), "N")),
        ("other_stimulus_for_two", _result(trial.get("other_stimulus_for_two"), "N", problems >= 2)),
        ("other_stimulus_for_target", _result(trial.get("other_stimulus_for_target"), "N", target == "Y")),
        ("other_stimulus_other_time", _result(trial.get("other_stimulus_other_time"), "N")),
    ]
    return [
        {
            "Trial": trial["trial"],
            "Step": STEP_LABELS[key],
            "Result": result,
            "Error label": ERROR_TYPES[key] if result == "Incorrect" else "",
        }
        for key, result in rules
    ]


def score_session(setup: dict[str, Any], trials: list[dict[str, Any]]) -> dict[str, Any]:
    details = [
        {"Trial": "Setup", "Step": STEP_LABELS[key], "Result": _result(setup.get(key), "Y"), "Error label": ERROR_TYPES[key] if _result(setup.get(key), "Y") == "Incorrect" else ""}
        for key in ("arrange_materials", "prepare_reinforcers")
    ]
    for trial in trials:
        details.extend(score_trial(trial))

    correct = sum(d["Result"] == "Correct" for d in details)
    incorrect = sum(d["Result"] == "Incorrect" for d in details)
    missing = sum(d["Result"] == "Missing" for d in details)
    applicable = correct + incorrect
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in details:
        grouped[item["Step"]][item["Result"]] += 1
    summary = []
    for step, values in grouped.items():
        step_applicable = values["Correct"] + values["Incorrect"]
        summary.append({
            "Step": step,
            "Correct": values["Correct"],
            "Incorrect": values["Incorrect"],
            "N/A": values["N/A"],
            "Missing": values["Missing"],
            "Accuracy": f"{(100 * values['Correct'] / step_applicable):.1f}%" if step_applicable else "N/A",
        })
    return {
        "correct": correct,
        "incorrect": incorrect,
        "applicable": applicable,
        "missing": missing,
        "percent": 100 * correct / applicable if applicable else 0.0,
        "details": details,
        "step_summary": summary,
    }


def make_workbook(session: dict[str, Any], setup: dict[str, Any], trials: list[dict[str, Any]], scores: dict[str, Any]) -> bytes:
    output = BytesIO()
    session_rows = [{"Field": k.replace("_", " ").title(), "Value": str(v)} for k, v in {**session, **setup}.items()]
    completed = int(session.get("completed_trials", 10))
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(session_rows).to_excel(writer, sheet_name="Session", index=False)
        pd.DataFrame(trials[:completed]).to_excel(writer, sheet_name="Observations", index=False)
        pd.DataFrame(scores["step_summary"]).to_excel(writer, sheet_name="Results", index=False)
        pd.DataFrame(scores["details"]).to_excel(writer, sheet_name="Scoring Details", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                width = min(max(len(str(cell.value or "")) for cell in column) + 2, 55)
                sheet.column_dimensions[column[0].column_letter].width = width
    return output.getvalue()

