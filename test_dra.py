from dra import empty_trials, score_session


def test_empty_session_has_no_applicable_scores():
    result = score_session(
        {"arrange_materials": None, "prepare_reinforcers": None},
        empty_trials()[:1],
    )
    assert result["applicable"] == 0
    assert result["missing"] > 0


def test_clear_correct_trial_scores_as_correct():
    trial = empty_trials()[0]
    trial.update({
        "worksheet": "Y",
        "instruction": "Y",
        "prompt": "N",
        "began_within_10": "Y",
        "problems": 2,
        "target_behavior": "N",
        "minor_behavior": "N",
        "reinforcer_within_3": "Y",
        "reinforcer_20_seconds": "Y",
        "reinforcer_for_target": "NA",
        "worksheet_removed_for_target": "NA",
        "reinforcer_other_time": "N",
        "other_stimulus_for_two": "N",
        "other_stimulus_for_target": "NA",
        "other_stimulus_other_time": "N",
    })
    result = score_session(
        {"arrange_materials": "Y", "prepare_reinforcers": "Y"}, [trial]
    )
    assert result["incorrect"] == 0
    assert result["percent"] == 100


def test_missing_prompt_when_needed_is_incorrect():
    trial = empty_trials()[0]
    trial.update({"began_within_10": "N", "prompt": "N"})
    details = score_session(
        {"arrange_materials": None, "prepare_reinforcers": None}, [trial]
    )["details"]
    prompt = next(row for row in details if row["Step"] == "Provide an additional prompt when needed")
    assert prompt["Result"] == "Incorrect"

