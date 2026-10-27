#!/usr/bin/env python3
"""Run offline parity-comparison checks against the recorded JSF corpus."""

import json
from pathlib import Path

import record
import replay

HERE = Path(__file__).resolve().parent


def actual_response(response, body=None, media_type=None, replay_day=None):
    return {
        "status": response["status"],
        "mediaType": response["mediaType"] if media_type is None else media_type,
        "location": response.get("location"),
        "body": response["body"] if body is None else body,
        "replayDay": replay_day,
    }


def compare(expected, actual, case, recorded_on, replay_day):
    return replay.compare(
        expected, actual, case, strict=False,
        recorded_on=recorded_on, replay_day=replay_day,
    )


def main():
    requests = json.loads((HERE / "requests.json").read_text(encoding="utf-8"))
    recorded = json.loads((HERE / "recorded.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in requests["cases"]}
    responses = {
        entry["id"]: entry["response"]
        for entries in recorded["contexts"].values()
        for entry in entries
    }
    recorded_on = recorded["recordedOn"]
    if len(cases) != 40 or set(cases) != set(responses):
        raise AssertionError(f"expected the same 40 cases in corpus and recording, got {len(cases)}")

    health_case = next(case for case in cases.values() if case.get("path") == "/health")
    health = responses[health_case["id"]]
    health_actual = actual_response(health, body="broken", media_type="text/html", replay_day=recorded_on)
    health_problems = compare(health, health_actual, health_case, recorded_on, recorded_on)
    if not any(problem.startswith("mediaType:") for problem in health_problems):
        raise AssertionError("health media-type change was not detected")
    if "normalised non-HTML body differs" not in health_problems:
        raise AssertionError("health body change was not detected")
    print("health body/mediaType change: DIFFERENT")

    wizard_case = next(
        case for case in cases.values()
        if "Fahrzeug: HH-VS 7629" in responses[case["id"]]["body"]
    )
    wizard = responses[wizard_case["id"]]
    changed_confirmation = wizard["body"].replace("Fahrzeug: HH-VS 7629", "Fahrzeug: NO CAR")
    wizard_actual = actual_response(wizard, body=changed_confirmation, replay_day=recorded_on)
    wizard_problems = compare(wizard, wizard_actual, wizard_case, recorded_on, recorded_on)
    if "observed block differs" not in wizard_problems:
        raise AssertionError("wizard confirmation text change was not detected")
    print(f"{wizard_case['id']} confirmation text change: DIFFERENT")

    shifted_differences = []
    for case_id, case in cases.items():
        expected = responses[case_id]
        shifted_body = expected["body"].replace("27.10.2026", "28.10.2026")
        shifted_body = shifted_body.replace("2026-10-27", "2026-10-28")
        actual = actual_response(expected, body=shifted_body, replay_day="2026-10-28")
        problems = compare(expected, actual, case, recorded_on, "2026-10-28")
        if problems:
            shifted_differences.append(f"{case_id}: {problems}")
    if shifted_differences:
        raise AssertionError("date-shift differences: " + "; ".join(shifted_differences))
    print(f"recording-day to replay-day date shift: IDENTICAL ({len(cases)}/{len(cases)})")

    differences = []
    for case_id, case in cases.items():
        expected = responses[case_id]
        actual = actual_response(expected, replay_day=recorded_on)
        problems = compare(expected, actual, case, recorded_on, recorded_on)
        if problems:
            differences.append(f"{case_id}: {problems}")
    if differences:
        raise AssertionError("unmodified response differences: " + "; ".join(differences))
    print(f"unmodified responses: IDENTICAL ({len(cases)}/{len(cases)})")

    visible_text = record.extract_observed(
        "<head>head-only</head><body> visible <script>script-only j_idt4</script>"
        "<style>style-only</style> text j_idt7 j_id1:javax.faces.ViewState "
        "<input name='javax.faces.ViewState' value='secret'></body>"
    )["text"]
    if visible_text != "visible text":
        raise AssertionError(f"visible text was not filtered correctly: {visible_text!r}")
    print("visible-text filtering: PASS (scripts, styles, generated IDs, and ViewState excluded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
