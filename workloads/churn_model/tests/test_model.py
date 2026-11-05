import pandas as pd
import pytest

from workloads.churn_model import model as m
from workloads.churn_model.provision import ROLE, provision_sql
from workloads.churn_model.warehouse import insert_statement

P = pd.Timestamp("2026-10-05")


def history(rows, admin=False):
    columns = ["id", "user_id", "effective_at", "status"] if admin else ["id", "user_id", "effective_at", "last_login_at", "is_deleted"]
    frame = pd.DataFrame(rows, columns=columns)
    frame["effective_at"] = pd.to_datetime(frame.effective_at)
    if not admin:
        frame["last_login_at"] = pd.to_datetime(frame.last_login_at)
    return frame


def test_labels_transition_not_capture_and_strict_window():
    auth = history([])
    admin = history([(1, "a", P, "suspended"), (2, "b", P, "active"),
                     (3, "b", P + pd.Timedelta(days=28), "deleted"),
                     (4, "c", P, "active"), (5, "c", P + pd.Timedelta(days=29), "suspended")], True)
    assert m.label(auth, admin, "a", P) == 0
    assert m.label(auth, admin, "b", P) == 1
    assert m.label(auth, admin, "c", P) == 0
    assert m.label(history([(1, "a", P, P, True)]), admin, "a", P) == 0
    assert m.label(history([(1, "a", P + pd.Timedelta(days=1), P, True)]), admin, "a", P) == 1


def inputs():
    auth = history([(1, "a", P - pd.Timedelta(days=2), P - pd.Timedelta(days=3), False),
                    (2, "a", P, P, False)])
    docs = pd.DataFrame({"created_by": ["a"] * 4,
                         "created_at": [P - pd.Timedelta(days=d) for d in [0, 1, 7, 35]]})
    events = pd.DataFrame({"user_id": ["a"] * 3, "event_type": ["search.performed"] * 3,
                           "occurred_at": [P, P - pd.Timedelta(days=1), P - pd.Timedelta(days=2)],
                           "metadata": ['{"result_count":0}', '{"result_count":"0"}', "invalid"]})
    quotas = pd.DataFrame({"user_id": ["a", "a"], "updated_at": [P - pd.Timedelta(days=2), P],
                           "_snapshot_date": [P - pd.Timedelta(days=1), P],
                           "used_bytes": [50, 99], "quota_bytes": [100, 100], "tier": ["basic", "pro"]})
    return auth, docs, events, quotas


def test_asof_features_and_empty_sources():
    args = inputs()
    row = m.features("a", P, *args)
    assert row["login_days"] == 3
    assert row["documents_7d"] == 2
    assert row["documents_prior_week"] == 0.25
    assert row["zero_result_share"] == 0.5
    assert row["quota_ratio"] == 0.5
    assert row["tier"] == "basic"
    empty = m.features("unknown", P, *args)
    assert empty["login_days"] is None
    assert empty["quota_ratio"] is None
    assert empty["searches_7d"] == 0
    assert all(check["passed"] for check in m.leakage(pd.DataFrame([dict(row, label_window_start=P + pd.Timedelta(nanoseconds=1))])))


def test_leakage_catches_injected_future_source_and_label_boundary():
    row = m.features("a", P, *inputs())
    row.update(login_days_source_ts=P + pd.Timedelta(days=1), label_window_start=P)
    checks = {r["feature"]: r for r in m.leakage(pd.DataFrame([row]))}
    assert checks["login_days"]["violations"] == 1
    assert not checks["label_window"]["passed"]
    assert all(r["rows_checked"] == 1 for r in checks.values())


def test_threshold_is_highest_training_threshold_with_recall_gate():
    assert m.threshold([1, 1, 0, 0], [0.8, 0.3, 0.9, 0.2]) == 0.8
    assert m.threshold([0, 0], [0.2, 0.8]) is None
    assert m.threshold([], []) is None


def test_evaluation_undefined_and_below_gate():
    result = m.evaluate([0, 0], [0.9, 0.1], 0.5, "no transitions")
    assert not result["passed"] and result["recall"] is None and result["auc"] is None
    assert result["cause"] == "holdout has 0 churn events: no transitions"
    assert not m.evaluate([1, 1, 1], [0.9, 0.1, 0.1], 0.5)["passed"]
    assert not m.evaluate([1], [0], None)["passed"]
    assert m.evaluate([], [], None)["n"] == 0
    result = m.evaluate([1, 0, 1, 0], [0.9, 0.8, 0.1, 0.0], 0.5)
    assert result["passed"] and result["recall"] == 0.5 and result["precision"] == 0.5
    assert result["auc"] == pytest.approx(0.75)


def test_split_is_temporal_or_stable_account_hash():
    frame = pd.DataFrame({"account_id": [str(i) for i in range(100)], "prediction_date": [P] * 100})
    train, holdout, rule = m.split(frame)
    assert rule == "account_sha256_70_30" and len(train) > len(holdout) > 0
    assert set(train.account_id).isdisjoint(holdout.account_id)
    frame.loc[0, "prediction_date"] = P + pd.Timedelta(days=7)
    train, holdout, rule = m.split(frame)
    assert rule == "latest_labelled_monday" and len(holdout) == 1
    assert train.prediction_date.max() < holdout.prediction_date.min()
    empty_train, empty_holdout, _ = m.split(frame.head(0))
    assert empty_train.empty and empty_holdout.empty
    assert list(empty_train.columns) == list(frame.columns)


def test_provision_grants_explicit_sources_and_outputs():
    sql = "\n".join(provision_sql("PUBLICKEY"))
    assert ROLE in sql and "RAW.PIPELINE_EXPORTS" in sql and "RAW.SUPPORT_NOTES" in sql
    assert "APP.CHURN_MODEL_EVALUATION" in sql and "ALL TABLES" not in sql


def test_document_inputs_and_hard_bound():
    assert m.document_input(dict(body="body", title="title")) == ("text", "body")
    assert m.document_input(dict(title="title")) == ("title_only", "title")
    assert m.document_input(dict(title="  ", is_template=True))[0] == "metadata_only"
    assert m.document_input(dict(title=None))[0] == "metadata_only"
    frame = pd.DataFrame(dict(id=list(range(30, 0, -1)), is_deleted=[True] + [False] * 29))
    chosen = m.document_batch(frame)
    assert list(chosen.id) == list(range(1, 11))
    assert len(m.document_batch(frame.head(0))) == 0


def test_dataset_eligibility_and_label_observation_end():
    auth, docs, events, quotas = inputs()
    tables = {"AUTH_USERS": pd.DataFrame(dict(id=["a", "new", "suspended"],
              created_at=[P - pd.Timedelta(days=29), P - pd.Timedelta(days=28), P - pd.Timedelta(days=100)])),
              "AUTH_USER_STATE_HISTORY": auth,
              "ADMIN_USER_STATE_HISTORY": history([(1, "suspended", P - pd.Timedelta(days=1), "suspended")], True),
              "DOCUMENT_DOCUMENT_VERSIONS": docs, "ANALYTICS_ANALYTICS_EVENTS": events,
              "ADMIN_STORAGE_QUOTAS": quotas}
    rows = m.dataset(tables, [P], P + pd.Timedelta(days=28))
    assert rows.account_id.tolist() == ["a"] and rows.churned.tolist() == [0]
    assert m.dataset(tables, [P], P + pd.Timedelta(days=27)).churned.isna().all()
    assert m.dataset(tables, [], P).empty


def test_insert_uses_sql_null_and_explicit_timestamp_conversion():
    sql, params = insert_statement("CHURN_LEAKAGE_CHECK", "run", dict(source=pd.NaT, cutoff=None, prediction=P, passed=True))
    assert "VALUES (?,NULL,NULL,TO_TIMESTAMP_NTZ(?),?)" in sql
    assert params == ["run", P.isoformat(), True]


@pytest.mark.parametrize("has_created_at", [True, False])
def test_history_only_deleted_account_is_labelled(has_created_at):
    _, docs, events, quotas = inputs()
    auth = history([(2, "deleted", P + pd.Timedelta(days=7), P, True),
                    (1, "deleted", P - pd.Timedelta(days=35), P - pd.Timedelta(days=36), False)])
    if has_created_at:
        auth["created_at"] = P - pd.Timedelta(days=100)
    tables = {"AUTH_USERS": pd.DataFrame(columns=["id", "created_at"]),
              "AUTH_USER_STATE_HISTORY": auth, "ADMIN_USER_STATE_HISTORY": history([], True),
              "DOCUMENT_DOCUMENT_VERSIONS": docs, "ANALYTICS_ANALYTICS_EVENTS": events,
              "ADMIN_STORAGE_QUOTAS": quotas}
    users = m.accounts(tables)
    expected_age = 100 if has_created_at else 35
    assert users.created_at.tolist() == [P - pd.Timedelta(days=expected_age)]
    rows = m.dataset(tables, [P, P + pd.Timedelta(days=14)], P + pd.Timedelta(days=42))
    assert rows.account_id.tolist() == ["deleted"]
    assert rows.prediction_date.tolist() == [P]
    assert rows.churned.tolist() == [1]
    assert all(check["passed"] for check in m.leakage(rows))


def test_history_account_universe_preserves_point_in_time_eligibility():
    auth, docs, events, quotas = inputs()
    auth["created_at"] = P - pd.Timedelta(days=100)
    admin = history([(5, "admin_only", P + pd.Timedelta(days=1), "suspended"),
                     (1, "admin_only", P - pd.Timedelta(days=40), "active"),
                     (2, "young", P - pd.Timedelta(days=28), "active"),
                     (3, "already_churned", P - pd.Timedelta(days=40), "suspended"),
                     (4, "future", P + pd.Timedelta(days=1), "active")], True)
    tables = {"AUTH_USERS": pd.DataFrame(dict(id=["a"], created_at=[P - pd.Timedelta(days=28)])),
              "AUTH_USER_STATE_HISTORY": auth, "ADMIN_USER_STATE_HISTORY": admin,
              "DOCUMENT_DOCUMENT_VERSIONS": docs, "ANALYTICS_ANALYTICS_EVENTS": events,
              "ADMIN_STORAGE_QUOTAS": quotas}
    assert m.accounts(tables).set_index("id").loc["a", "created_at"] == P - pd.Timedelta(days=28)
    rows = m.dataset(tables, [P], P + pd.Timedelta(days=28))
    assert rows.account_id.tolist() == ["admin_only"]
    assert rows.churned.tolist() == [1]
    tables["AUTH_USERS"] = tables["AUTH_USERS"].head(0)
    tables["AUTH_USER_STATE_HISTORY"] = auth.head(0)
    tables["ADMIN_USER_STATE_HISTORY"] = admin.head(0)
    assert m.accounts(tables).empty
    assert m.dataset(tables, [P], P + pd.Timedelta(days=28)).empty


def test_account_creation_priority_ignores_history_capture_order():
    _, docs, events, quotas = inputs()
    auth = history([(2, "deleted", P - pd.Timedelta(days=1), P, False),
                    (3, "deleted", P + pd.Timedelta(days=7), P, True),
                    (4, "current", P - pd.Timedelta(days=1), P, False),
                    (5, "missing", P - pd.Timedelta(days=2), P, False),
                    (6, "fallback", P - pd.Timedelta(days=35), P, False)])
    auth["created_at"] = pd.to_datetime([P - pd.Timedelta(days=60), P - pd.Timedelta(days=100),
                                         P - pd.Timedelta(days=100), P - pd.Timedelta(days=90), pd.NaT])
    admin = history([(1, "deleted", P - pd.Timedelta(days=5), "active"),
                     (2, "fallback", P - pd.Timedelta(days=40), "active")], True)
    tables = {"AUTH_USERS": pd.DataFrame(dict(id=["current", "missing"],
                                              created_at=[P - pd.Timedelta(days=28), pd.NaT])),
              "AUTH_USER_STATE_HISTORY": auth, "ADMIN_USER_STATE_HISTORY": admin,
              "DOCUMENT_DOCUMENT_VERSIONS": docs, "ANALYTICS_ANALYTICS_EVENTS": events,
              "ADMIN_STORAGE_QUOTAS": quotas}
    created = m.accounts(tables).set_index("id").created_at.to_dict()
    assert created == {"current": P - pd.Timedelta(days=28), "deleted": P - pd.Timedelta(days=100),
                       "missing": P - pd.Timedelta(days=90), "fallback": P - pd.Timedelta(days=40)}
    rows = m.dataset(tables, [P], P + pd.Timedelta(days=28)).set_index("account_id")
    assert "current" not in rows.index
    assert rows.loc["deleted", "churned"] == 1
