"""Train, threshold and evaluate churn_model inside Snowflake (Snowpark stored procedure).

The gates below are fixed before the holdout is scored. The operating
threshold is picked on the validation weeks and then applied unchanged to the
holdout accounts and weeks.

Why these numbers:
  * MIN_PRECISION 0.50: the account team calls every flagged account. At
    least half of those calls should reach an account that really leaves in
    the next 28 days; the base rate is a few percent, so random calls would
    almost never do that.
  * MIN_RECALL 0.50: the list must catch at least half of the accounts that
    leave, or it misses most of the problem.
  * MIN_ROC_AUC 0.80 and MIN_PR_AUC_LIFT 3.0: a pipeline with misaligned
    windows or broken joins ranks close to random (ROC AUC 0.5, PR AUC near
    the base rate).
  * The trained model must beat the rules_v1 points on holdout PR AUC, or
    there is no reason to replace it.
  * MAX_SINGLE_FEATURE_AUC 0.95: one feature that separates the classes
    almost perfectly on its own is a leak signal, given the noise the
    generator adds.
"""

import json

import numpy as np
import pandas as pd

try:
    from snowflake.snowpark import Session
except ImportError:  # offline unit tests run without Snowpark
    Session = object

MODEL_VERSION = 'snowpark_lr_v1'
MIN_PRECISION = 0.50
MIN_RECALL = 0.50
MIN_ROC_AUC = 0.80
MIN_PR_AUC_LIFT = 3.0
MIN_FLAGGED = 10
MAX_SINGLE_FEATURE_AUC = 0.95
RULES_HIGH = 60

DRIVER_TEXT = {
    'days_since_last_login': 'no recent login',
    'logins_last_7d': 'few logins this week',
    'logins_last_28d': 'few logins in 4 weeks',
    'saves_last_7d': 'few document saves this week',
    'saves_prior_4wk_avg': 'low save baseline',
    'save_drop_pct': 'document saves dropped',
    'active_days_last_28d': 'few active days',
    'login_ratio_7d': 'logins down vs own baseline',
    'login_ratio_prev_7d': 'logins already down the week before',
    'active_days_last_7d': 'few active days this week',
    'active_days_ratio_7d': 'active days down vs own baseline',
    'save_ratio_7d': 'saves down vs own baseline',
    'save_ratio_prev_7d': 'saves already down the week before',
    'account_age_days': 'account age',
    'quota_used_pct': 'storage near quota',
    'quota_used_pct_change_28d': 'storage filling fast',
    'quota_at_or_over_80pct': 'storage at or over 80%',
    'tier_free': 'free tier',
    'tier_basic': 'basic tier',
    'tier_pro': 'pro tier',
}


def rules_v1_score(f: pd.DataFrame) -> pd.Series:
    """rules_v1 points from workloads/churn_model.yaml, on the synthetic features (no suspensions)."""
    d = f['days_since_last_login']
    login = np.select([d >= 30, d >= 14, d >= 7], [40, 25, 10], 0)
    prior, week, drop = f['saves_prior_4wk_avg'], f['saves_last_7d'], f['save_drop_pct']
    activity = np.select([(prior == 0) & (week == 0), prior == 0, drop >= 0.75, drop >= 0.5, drop >= 0.25],
                         [30, 0, 40, 25, 10], 0)
    return pd.Series(login + activity, index=f.index, dtype=float)


def confusion(y: np.ndarray, flagged: np.ndarray) -> dict:
    tp = int(((y == 1) & flagged).sum())
    n_flag = int(flagged.sum())
    pos = int((y == 1).sum())
    precision = tp / n_flag if n_flag else 0.0
    recall = tp / pos if pos else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {'flagged': n_flag, 'true_positives': tp, 'precision': precision, 'recall': recall, 'f1': f1}


def choose_threshold(y: np.ndarray, p: np.ndarray, min_precision: float = MIN_PRECISION,
                     min_flagged: int = MIN_FLAGGED) -> tuple[float, bool]:
    """Lowest probability cut-off whose precision is at least min_precision.

    Lower cut-offs flag more accounts, so the lowest one that keeps precision
    catches the most leavers. Returns (threshold, met); met is False if no
    cut-off reaches min_precision, in which case the max-F1 cut-off is used.
    """
    best, best_f1 = None, (-1.0, 1.0)
    for t in np.unique(p)[::-1]:
        c = confusion(y, p >= t)
        if c['flagged'] < min_flagged:
            continue
        if c['precision'] >= min_precision:
            best = float(t)
        if c['f1'] > best_f1[0]:
            best_f1 = (c['f1'], float(t))
    if best is not None:
        return best, True
    return best_f1[1], False


def evaluate_rows(split: str, model: str, y, score, threshold) -> dict:
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = np.asarray(y)
    score = np.asarray(score, dtype=float)
    base = float(y.mean())
    has_both = 0 < y.sum() < len(y)
    row = {'SPLIT': split, 'MODEL': model, 'N_ROWS': int(len(y)), 'POSITIVES': int(y.sum()), 'BASE_RATE': base,
           'ROC_AUC': float(roc_auc_score(y, score)) if has_both else None,
           'PR_AUC': float(average_precision_score(y, score)) if has_both else None,
           'THRESHOLD': float(threshold)}
    c = confusion(y, score >= threshold)
    row.update({k.upper(): v for k, v in c.items()})
    row['LIFT'] = row['PRECISION'] / base if base else None
    return row


def gates(holdout_model: dict, holdout_rules: dict, threshold_met: bool) -> list[dict]:
    m, r = holdout_model, holdout_rules
    checks = [
        ('validation threshold reaches precision', MIN_PRECISION, 1.0 if threshold_met else 0.0, threshold_met),
        ('holdout ROC AUC', MIN_ROC_AUC, m['ROC_AUC'], m['ROC_AUC'] is not None and m['ROC_AUC'] >= MIN_ROC_AUC),
        ('holdout PR AUC / base rate', MIN_PR_AUC_LIFT, (m['PR_AUC'] or 0) / m['BASE_RATE'],
         m['PR_AUC'] is not None and m['PR_AUC'] >= MIN_PR_AUC_LIFT * m['BASE_RATE']),
        ('holdout precision at threshold', MIN_PRECISION, m['PRECISION'], m['PRECISION'] >= MIN_PRECISION),
        ('holdout recall at threshold', MIN_RECALL, m['RECALL'], m['RECALL'] >= MIN_RECALL),
        ('holdout PR AUC beats rules_v1', r['PR_AUC'], m['PR_AUC'],
         m['PR_AUC'] is not None and r['PR_AUC'] is not None and m['PR_AUC'] > r['PR_AUC']),
    ]
    return [{'GATE': g, 'REQUIRED': float(req), 'OBSERVED': float(obs), 'PASSED': bool(ok)} for g, req, obs, ok in checks]


def top_drivers(x_std: np.ndarray, coef: np.ndarray, names: list[str], k: int = 2) -> list[list[str]]:
    contrib = x_std * coef
    order = np.argsort(-contrib, axis=1)[:, :k]
    return [[DRIVER_TEXT[names[j]] if contrib[i, j] > 0 else None for j in row] for i, row in enumerate(order)]


def train_evaluate(session: Session, schema: str, run_id: str, features_json: str) -> str:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    names = json.loads(features_json)
    cols = ', '.join(f'f.{c}' for c in names)
    df = session.sql(
        f'select p.prediction_date, p.account_id, p.split, p.label, {cols} from {schema}.CHURN_POPULATION p '
        f'join {schema}.CHURN_FEATURES f on f.prediction_date = p.prediction_date and f.account_id = p.account_id '
        'order by p.prediction_date, p.account_id').to_pandas()
    df.columns = [c.lower() for c in df.columns]
    train = df[df.split == 'train']
    scaler = StandardScaler().fit(train[names].values)
    model = LogisticRegression(C=1.0, max_iter=2000).fit(scaler.transform(train[names].values), train.label.astype(int))
    x_std = scaler.transform(df[names].values)
    df['churn_probability'] = model.predict_proba(x_std)[:, 1]
    df['rules_v1_score'] = rules_v1_score(df)

    val = df[df.split == 'validation']
    threshold, met = choose_threshold(val.label.astype(int).values, val.churn_probability.values)
    df['flagged'] = df.churn_probability >= threshold
    drivers = top_drivers(x_std, model.coef_[0], names)
    df['top_driver_1'] = [d[0] for d in drivers]
    df['top_driver_2'] = [d[1] for d in drivers]

    evaluation = []
    for split in ('train', 'validation', 'holdout'):
        part = df[df.split == split]
        y = part.label.astype(int).values
        evaluation.append(evaluate_rows(split, MODEL_VERSION, y, part.churn_probability.values, threshold))
        evaluation.append(evaluate_rows(split, 'rules_v1', y, part.rules_v1_score.values, RULES_HIGH))
    hold = [r for r in evaluation if r['SPLIT'] == 'holdout']
    gate_rows = gates(hold[0], hold[1], met)

    y_train = train.label.astype(int).values
    sentinel = []
    for c in names:
        auc = float(roc_auc_score(y_train, train[c].values))
        sentinel.append({'FEATURE': c, 'TRAIN_AUC': max(auc, 1 - auc),
                         'PASSED': max(auc, 1 - auc) <= MAX_SINGLE_FEATURE_AUC})

    coef = pd.DataFrame({'FEATURE': names, 'MEAN': scaler.mean_, 'SCALE': scaler.scale_, 'COEF': model.coef_[0]})
    coef['INTERCEPT'] = float(model.intercept_[0])
    coef['THRESHOLD'] = threshold
    coef['MODEL_VERSION'] = MODEL_VERSION
    coef['RUN_ID'] = run_id
    coef['TRAIN_ROWS'] = len(train)

    scores = df[['prediction_date', 'account_id', 'split', 'label', 'churn_probability', 'rules_v1_score',
                 'flagged', 'top_driver_1', 'top_driver_2']].copy()
    scores['model_version'] = MODEL_VERSION
    scores.columns = [c.upper() for c in scores.columns]
    tables = {'CHURN_MODEL_COEFFICIENTS': coef, 'CHURN_SCORES': scores,
              'CHURN_EVALUATION': pd.DataFrame(evaluation), 'CHURN_EVALUATION_GATES': pd.DataFrame(gate_rows),
              'FEATURE_AUC_SENTINEL': pd.DataFrame(sentinel)}
    for name, frame in tables.items():
        frame['RUN_ID'] = run_id
        session.write_pandas(frame, name, schema=schema, auto_create_table=True, overwrite=True,
                             use_logical_type=True)
    for name in ('CHURN_EVALUATION', 'CHURN_EVALUATION_GATES'):
        session.write_pandas(tables[name], f'{name}_HISTORY', schema=schema, auto_create_table=True,
                             overwrite=False, use_logical_type=True)
    return json.dumps({'threshold': threshold, 'threshold_met': met,
                       'passed': all(g['PASSED'] for g in gate_rows) and all(s['PASSED'] for s in sentinel)})
