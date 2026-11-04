from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import features as F  # noqa: E402
import synthetic_history as G  # noqa: E402
import train_evaluate as T  # noqa: E402


def test_generate_is_deterministic_by_seed() -> None:
    first = G.generate(seed=17, n_accounts=200)
    repeated = G.generate(seed=17, n_accounts=200)
    different = G.generate(seed=18, n_accounts=200)

    assert {name: G.checksum(frame) for name, frame in first.items()} == {
        name: G.checksum(frame) for name, frame in repeated.items()
    }
    assert G.checksum(first["ACCOUNTS"]) != G.checksum(different["ACCOUNTS"])


def test_generated_history_invariants() -> None:
    tables = G.generate(n_accounts=300)
    accounts = tables["ACCOUNTS"]
    activity = tables["DAILY_ACTIVITY"]
    snapshots = tables["QUOTA_SNAPSHOTS"]
    churn = tables["CHURN_EVENTS"]
    notes = tables["SUPPORT_NOTES"]

    assert (snapshots["USED_BYTES"] <= snapshots["QUOTA_BYTES"]).all()
    assert churn["ACCOUNT_ID"].is_unique

    activity_with_accounts = activity.merge(accounts[["ACCOUNT_ID", "CREATED_AT"]], on="ACCOUNT_ID")
    assert (activity_with_accounts["ACTIVITY_DATE"] >= activity_with_accounts["CREATED_AT"].dt.date).all()

    activity_with_churn = activity.merge(churn[["ACCOUNT_ID", "CHURNED_AT"]], on="ACCOUNT_ID")
    assert (activity_with_churn["ACTIVITY_DATE"] < activity_with_churn["CHURNED_AT"].dt.date).all()
    snapshots_with_churn = snapshots.merge(churn[["ACCOUNT_ID", "CHURNED_AT"]], on="ACCOUNT_ID")
    assert (snapshots_with_churn["SNAPSHOT_DATE"] <= snapshots_with_churn["CHURNED_AT"].dt.date).all()

    assert set(notes["GENERATOR_REASON"]).issubset(set(G.REASONS) | {G.ROUTINE})

    timestamp_columns = {
        "ACCOUNTS": ("CREATED_AT",),
        "QUOTA_SNAPSHOTS": ("TAKEN_AT",),
        "CHURN_EVENTS": ("CHURNED_AT",),
        "SUPPORT_NOTES": ("CREATED_AT",),
    }
    for table_name, columns in timestamp_columns.items():
        for column in columns:
            assert all(value.tzinfo is None for value in tables[table_name][column].dropna())


def test_split_gaps_detects_overlapping_label_windows() -> None:
    assert F.check_split_gaps() == []

    overlapping = dict(F.PERIODS)
    overlapping["validation"] = [max(F.PERIODS["train"]) + timedelta(days=7)]
    assert F.check_split_gaps(overlapping)


def test_static_label_check_rejects_label_table_references() -> None:
    assert F.static_label_check(F.features_sql()) == []
    assert F.static_label_check("select * from SYNTHETIC.CHURN_EVENTS") == ["CHURN_EVENTS"]


def test_feature_select_canary_and_feature_aliases() -> None:
    args = ("spine", "activity", "snapshots", "accounts")
    assert "saves_next_7d" not in F.feature_select(*args, canary=False)
    assert "saves_next_7d" in F.feature_select(*args, canary=True)

    sql = F.features_sql().lower()
    assert all(f"as {name}" in sql for name in F.FEATURES)


def test_choose_threshold_returns_lowest_qualifying_cutoff() -> None:
    y = np.array([1, 1, 0, 1, 0, 0])
    probabilities = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4])

    threshold, met = T.choose_threshold(y, probabilities, min_flagged=1)

    assert threshold == 0.4
    assert met is True


def test_choose_threshold_reports_when_precision_target_is_unreachable() -> None:
    y = np.array([0, 0, 1, 0])
    probabilities = np.array([0.9, 0.8, 0.7, 0.6])

    _, met = T.choose_threshold(y, probabilities, min_flagged=1)

    assert met is False


def test_choose_threshold_ignores_cutoffs_below_min_flagged() -> None:
    y = np.array([1, 0, 1, 1])
    probabilities = np.array([0.99, 0.8, 0.7, 0.6])

    threshold, met = T.choose_threshold(y, probabilities, min_precision=0.75, min_flagged=2)

    assert threshold == 0.6
    assert met is True


def test_rules_v1_score_covers_login_and_save_drop_bands() -> None:
    features = pd.DataFrame(
        {
            "days_since_last_login": [30, 14, 7, 0, 0, 0, 0, 0, 0],
            "saves_prior_4wk_avg": [1, 1, 1, 1, 0, 0, 1, 1, 1],
            "saves_last_7d": [1, 1, 1, 1, 0, 1, 1, 1, 1],
            "save_drop_pct": [0, 0, 0, 0, 0, 0, 0.75, 0.5, 0.25],
        }
    )

    assert T.rules_v1_score(features).tolist() == [40, 25, 10, 0, 30, 0, 40, 25, 10]


def _holdout(precision: float = 0.6, model_pr_auc: float = 0.2) -> dict:
    return {
        "ROC_AUC": 0.85,
        "PR_AUC": model_pr_auc,
        "BASE_RATE": 0.05,
        "PRECISION": precision,
        "RECALL": 0.7,
    }


def test_gates_all_pass_for_good_holdout() -> None:
    rows = T.gates(_holdout(), {"PR_AUC": 0.15}, threshold_met=True)

    assert all(row["PASSED"] for row in rows)


def test_gates_fail_holdout_precision_below_target() -> None:
    rows = T.gates(_holdout(precision=0.49), {"PR_AUC": 0.15}, threshold_met=True)

    assert rows[3]["PASSED"] is False


def test_gates_fail_when_model_pr_auc_does_not_beat_rules() -> None:
    rows = T.gates(_holdout(model_pr_auc=0.2), {"PR_AUC": 0.2}, threshold_met=True)

    assert rows[-1]["PASSED"] is False


def test_top_drivers_describe_positive_contributions_only() -> None:
    names = ["days_since_last_login", "logins_last_7d"]
    standardized = np.array([[1.0, 1.0], [-1.0, -1.0]])
    coefficients = np.array([1.0, -1.0])

    assert T.top_drivers(standardized, coefficients, names) == [
        ["no recent login", None],
        ["few logins this week", None],
    ]
    assert set(F.FEATURES).issubset(T.DRIVER_TEXT)
