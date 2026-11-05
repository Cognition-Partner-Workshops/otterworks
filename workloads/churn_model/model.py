"""Point-in-time dataset and evaluation rules shared with the warehouse handler."""

import hashlib
import json

import numpy as np
import pandas as pd

FEATURES = (
    "login_days", "documents_7d", "documents_prior_week", "document_drop",
    "searches_7d", "searches_prior_28d", "zero_result_share", "quota_ratio", "tier",
)
CHURNED = {"suspended", "deleted"}


def document_input(document):
    for column in ("body", "content", "text"):
        value = document.get(column)
        if value is not None and pd.notna(value) and str(value).strip():
            return "text", str(value)
    title = document.get("title")
    if title is not None and pd.notna(title) and str(title).strip():
        return "title_only", str(title)
    return "metadata_only", json.dumps({key: str(document.get(key, "")) for key in ("is_template", "owner_id")})


def document_batch(frame):
    return frame.loc[~frame.is_deleted.fillna(False).astype(bool)].sort_values("id").head(10)


def monday(value):
    value = pd.Timestamp(value).normalize().tz_localize(None)
    return value - pd.Timedelta(days=value.weekday())


def latest(frame, account, prediction):
    rows = frame[(frame.user_id == account) & (frame.effective_at < prediction)]
    return None if rows.empty else rows.sort_values(["effective_at", "id"]).iloc[-1]


def label(auth, admin, account, prediction):
    end = prediction + pd.Timedelta(days=28)
    rows = auth[(auth.user_id == account) & (auth.effective_at > prediction) & (auth.effective_at <= end)]
    if rows.is_deleted.fillna(False).any():
        return 1
    rows = admin[admin.user_id == account].sort_values(["effective_at", "id"])
    previous = rows.status.shift()
    transitions = rows.status.isin(CHURNED) & previous.notna() & ~previous.isin(CHURNED)
    return int((transitions & (rows.effective_at > prediction) & (rows.effective_at <= end)).any())


def features(account, prediction, auth, documents, events, quotas):
    result = {"account_id": account, "prediction_date": prediction}

    def emit(name, value, source):
        result[name] = value
        result[name + "_source_ts"] = source

    state = latest(auth, account, prediction)
    login = pd.NaT if state is None else state.last_login_at
    emit("login_days", (prediction - login).total_seconds() / 86400 if pd.notna(login) else None,
         max(state.effective_at, login) if state is not None and pd.notna(login)
         else state.effective_at if state is not None else pd.NaT)
    for frame, owner, time, prefix in [(documents, "created_by", "created_at", "documents"),
                                       (events[events.event_type == "search.performed"], "user_id", "occurred_at", "searches")]:
        rows = frame[(frame[owner] == account) & (frame[time] < prediction)
                     & (frame[time] >= prediction - pd.Timedelta(days=35))]
        recent = rows[rows[time] >= prediction - pd.Timedelta(days=7)]
        prior = rows[rows[time] < prediction - pd.Timedelta(days=7)]
        emit(prefix + "_7d", len(recent), recent[time].max())
        emit("documents_prior_week" if prefix == "documents" else "searches_prior_28d",
             len(prior) / 4 if prefix == "documents" else len(prior), prior[time].max())
        if prefix == "documents":
            emit("document_drop", 1 - len(recent) / (len(prior) / 4) if len(prior) else None, rows[time].max())
        else:
            def zero(value):
                try:
                    return str(json.loads(value).get("result_count")) == "0"
                except (TypeError, ValueError, AttributeError):
                    return False
            emit("zero_result_share", recent.metadata.map(zero).mean() if len(recent) else None, recent[time].max())
    quota = quotas[(quotas.user_id == account) & (quotas.updated_at < prediction)
                   & (quotas._snapshot_date < prediction)].sort_values(["updated_at", "_snapshot_date"])
    row = None if quota.empty else quota.iloc[-1]
    source = max(row.updated_at, row._snapshot_date) if row is not None else pd.NaT
    emit("quota_ratio", row.used_bytes / row.quota_bytes if row is not None and row.quota_bytes else None, source)
    emit("tier", row.tier if row is not None else None, source)
    return result


def accounts(tables):
    created = dict(zip(tables["AUTH_USERS"].id, tables["AUTH_USERS"].created_at))
    history = pd.concat([tables["AUTH_USER_STATE_HISTORY"], tables["ADMIN_USER_STATE_HISTORY"]])
    for row in history.sort_values(["effective_at", "id"]).itertuples(index=False):
        if pd.isna(created.get(row.user_id)):
            timestamp = getattr(row, "created_at", pd.NaT)
            # Without a creation timestamp, first capture is a conservative account-age bound.
            created[row.user_id] = timestamp if pd.notna(timestamp) else row.effective_at
    return pd.DataFrame(created.items(), columns=["id", "created_at"])


def dataset(tables, predictions, observation_end):
    users = accounts(tables)
    output = []
    for prediction in predictions:
        for user in users.itertuples(index=False):
            if pd.isna(user.created_at) or user.created_at >= prediction - pd.Timedelta(days=28):
                continue
            auth = latest(tables["AUTH_USER_STATE_HISTORY"], user.id, prediction)
            admin = latest(tables["ADMIN_USER_STATE_HISTORY"], user.id, prediction)
            if (auth is not None and pd.notna(auth.is_deleted) and bool(auth.is_deleted)) or (admin is not None and admin.status in CHURNED):
                continue
            row = features(user.id, prediction, tables["AUTH_USER_STATE_HISTORY"],
                           tables["DOCUMENT_DOCUMENT_VERSIONS"], tables["ANALYTICS_ANALYTICS_EVENTS"],
                           tables["ADMIN_STORAGE_QUOTAS"])
            row["label_window_start"] = prediction + pd.Timedelta(nanoseconds=1)
            row["churned"] = (label(tables["AUTH_USER_STATE_HISTORY"], tables["ADMIN_USER_STATE_HISTORY"], user.id, prediction)
                              if prediction + pd.Timedelta(days=28) <= observation_end else None)
            output.append(row)
    return pd.DataFrame(output, columns=["account_id", "prediction_date", "label_window_start", "churned",
                                         *FEATURES, *(f + "_source_ts" for f in FEATURES)])


def leakage(frame):
    checks = []
    for feature in (*FEATURES, "label_window"):
        source = frame["label_window_start" if feature == "label_window" else feature + "_source_ts"]
        bad = source <= frame.prediction_date if feature == "label_window" else source >= frame.prediction_date
        checks.append(dict(feature=feature, rows_checked=len(frame), violations=int(bad.sum()),
                           max_source_ts=source.max(), max_prediction_date=frame.prediction_date.max(), passed=not bad.any()))
    return checks


def split(frame):
    if frame.prediction_date.nunique() > 1:
        holdout = frame.prediction_date == frame.prediction_date.max()
        rule = "latest_labelled_monday"
    else:
        holdout = frame.account_id.map(lambda value: int(hashlib.sha256(str(value).encode()).hexdigest(), 16) % 10 >= 7)
        rule = "account_sha256_70_30"
    holdout = holdout.astype(bool)
    return frame.loc[~holdout].copy(), frame.loc[holdout].copy(), rule


def threshold(labels, scores):
    labels, scores = np.asarray(labels), np.asarray(scores)
    if not (labels == 1).any():
        return None
    return max(float(t) for t in np.unique(scores) if ((scores >= t) & (labels == 1)).sum() / (labels == 1).sum() >= 0.5)


def evaluate(labels, scores, cutoff, source_cause=""):
    labels = np.asarray(labels, dtype=int)
    predicted = np.zeros(len(labels), dtype=bool) if cutoff is None else np.asarray(scores) >= cutoff
    positives = int((labels == 1).sum())
    tp = int((predicted & (labels == 1)).sum())
    fp = int((predicted & (labels == 0)).sum())
    recall = tp / positives if positives else None
    auc = None
    if positives and positives < len(labels) and cutoff is not None:
        ranks = pd.Series(scores).rank(method="average").to_numpy()
        auc = float((ranks[labels == 1].sum() - positives * (positives + 1) / 2)
                    / (positives * (len(labels) - positives)))
    cause = ("holdout has 0 churn events: " + source_cause if not positives else
             "model not trainable" if cutoff is None else "holdout recall below 0.50" if recall < 0.5 else "passed")
    return dict(n=len(labels), positives=positives, negatives=len(labels) - positives, tp=tp, fp=fp,
                fn=positives - tp, tn=len(labels) - positives - fp, recall=recall,
                precision=tp / (tp + fp) if tp + fp else None, auc=auc,
                passed=recall is not None and recall >= 0.5 and cutoff is not None, cause=cause)
