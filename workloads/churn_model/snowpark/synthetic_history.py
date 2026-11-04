"""Seeded synthetic account history for churn_model.

Everything here is invented. The OtterWorks sources have no churn outcome, no
support notes and too little activity history to train or evaluate a model, so
this generator writes a labelled history to the SYNTHETIC schema. A model
evaluated against it proves the pipeline, the leakage check and the threshold
logic work. It says nothing about how real accounts behave.

Rule (one draw per account and week, in week order):
  * Each account has a tier, a weekly document-save rate, a daily login
    probability and a storage-usage path that grows towards its quota.
  * While engaged, an account starts to disengage with weekly probability
    sigmoid(-5.4 + 2.2 * quota_pressure + 0.5 * free - 0.5 * pro_or_enterprise),
    where quota_pressure = clip((used / quota - 0.75) / 0.25, 0, 1).
  * Disengaging accounts lose activity geometrically (saves x 0.55^k, logins
    x 0.6^k in week k of the decline) and leave DECLINE_WEEKS later, except
    RECOVERY_RATE of them, which return to normal instead (noise).
  * Engaged accounts also have VACATION_RATE quiet weeks with almost no
    activity (noise that looks like decline but is not).
  * Each decline has one reason. Storage pressure picks "storage limits" with
    probability 0.7; otherwise the reason is drawn from REASON_WEIGHTS.
  * Declining accounts file a support note about their reason with weekly
    probability NOTE_RATE_DECLINE, unless they are silent (SILENT_RATE).
    Every account files routine notes with weekly probability NOTE_RATE_ROUTINE.

Timestamps are naive UTC (TIMESTAMP_NTZ in Snowflake); dates are UTC dates.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

SEED = 20261104
N_ACCOUNTS = 3000
FIRST_WEEK = date(2026, 1, 5)
LAST_WEEK = date(2026, 10, 26)
CREATED_FROM = date(2025, 6, 2)
CREATED_SPAN_DAYS = 300
NAMESPACE = uuid.UUID('6f2a8c1e-3b7d-4e5f-9a10-c0de00000000')

TIERS = ['free', 'basic', 'pro', 'enterprise']
TIER_WEIGHTS = [0.45, 0.30, 0.20, 0.05]
QUOTA_BYTES = {'free': 5 * 1024**3, 'basic': 50 * 1024**3, 'pro': 500 * 1024**3, 'enterprise': 5 * 1024**4}

ONSET_INTERCEPT = -5.4
ONSET_QUOTA = 2.2
ONSET_FREE = 0.5
ONSET_PAID = -0.5
DECLINE_WEEKS = (2, 6)
RECOVERY_RATE = 0.15
VACATION_RATE = 0.04
SAVE_DECAY = 0.55
LOGIN_DECAY = 0.6
STORAGE_REASON_RATE = 0.7
NOTE_RATE_DECLINE = 0.6
NOTE_RATE_ROUTINE = 0.03
SILENT_RATE = 0.15

REASONS = ['storage limits', 'pricing', 'product defects', 'moving to a competitor', 'no longer needed']
REASON_WEIGHTS = [0.10, 0.30, 0.25, 0.20, 0.15]
ROUTINE = 'routine request'

NOTE_TEMPLATES = {
    'storage limits': [
        'Customer says uploads fail because the workspace is at {pct}% of its storage quota.',
        'Asked why they keep hitting the storage cap; they have {n} large files they cannot move.',
        'Complained that the quota is too small for their team and they are out of space again.',
    ],
    'pricing': [
        'Customer says the renewal price is too high for their budget this year.',
        'Asked for a discount; finance wants to cut software spend by {pct}%.',
        'Wants to downgrade because the plan costs more than they can justify.',
    ],
    'product defects': [
        'Reported that documents fail to save about {n} times a day and edits are lost.',
        'Customer frustrated by sync errors and slow loading that support has not fixed.',
        'Third ticket about the editor crashing when opening shared folders.',
    ],
    'moving to a competitor': [
        'Customer mentioned they are trialling another document platform.',
        'Asked how to export everything because the team is switching to a different tool.',
        'Said a competitor offered them a better deal and more integrations.',
    ],
    'no longer needed': [
        'Customer says the project that used this workspace has ended.',
        'Team is shrinking and they no longer need shared documents.',
        'Asked how to close the account once the last {n} files are archived.',
    ],
    ROUTINE: [
        'Asked how to reset two-factor authentication on a new phone.',
        'Requested an updated invoice with a new billing address.',
        'Asked whether folders can be shared with read-only links.',
        'Feature request: dark mode in the editor.',
    ],
}


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def weeks():
    out, w = [], FIRST_WEEK
    while w <= LAST_WEEK:
        out.append(w)
        w += timedelta(days=7)
    return out


def _ts(day, rng):
    return datetime.combine(day, time(0)) + timedelta(seconds=int(rng.integers(0, 86400)))


def generate(seed: int = SEED, n_accounts: int = N_ACCOUNTS) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    week_list = weeks()
    accounts, activity, snapshots, churn, notes = [], [], [], [], []
    for i in range(n_accounts):
        account_id = str(uuid.uuid5(NAMESPACE, f'{seed}-{i}'))
        tier = TIERS[rng.choice(4, p=TIER_WEIGHTS)]
        quota = QUOTA_BYTES[tier]
        created = CREATED_FROM + timedelta(days=int(rng.integers(0, CREATED_SPAN_DAYS)))
        save_rate = rng.gamma(2.0, 6.0) + 1.0
        login_p = rng.beta(4, 3)
        used_frac = rng.beta(2, 3) * 0.8
        growth = max(0.0, rng.normal(0.012, 0.01))
        accounts.append({'ACCOUNT_ID': account_id, 'TIER': tier, 'QUOTA_BYTES': quota,
                         'CREATED_AT': _ts(created, rng)})
        state, decline_week, decline_len, reason, silent, recovers = 'engaged', 0, 0, None, False, False
        for week in week_list:
            week_end = week + timedelta(days=7)
            if week_end <= created:
                continue
            if state == 'churned':
                break
            pressure = float(np.clip((used_frac - 0.75) / 0.25, 0, 1))
            save_mult, login_mult = rng.lognormal(0, 0.35), 1.0
            if state == 'engaged':
                hazard = _sigmoid(ONSET_INTERCEPT + ONSET_QUOTA * pressure + ONSET_FREE * (tier == 'free')
                                  + ONSET_PAID * (tier in ('pro', 'enterprise')))
                if rng.random() < hazard:
                    state, decline_week = 'declining', 0
                    decline_len = int(rng.integers(DECLINE_WEEKS[0], DECLINE_WEEKS[1] + 1))
                    recovers = rng.random() < RECOVERY_RATE
                    silent = rng.random() < SILENT_RATE
                    if pressure > 0.5 and rng.random() < STORAGE_REASON_RATE:
                        reason = 'storage limits'
                    else:
                        reason = REASONS[rng.choice(len(REASONS), p=REASON_WEIGHTS)]
                elif rng.random() < VACATION_RATE:
                    save_mult, login_mult = 0.1, 0.1
            if state == 'declining':
                decline_week += 1
                save_mult *= SAVE_DECAY ** decline_week
                login_mult *= LOGIN_DECAY ** decline_week
                if not silent and rng.random() < NOTE_RATE_DECLINE:
                    notes.append(_note(account_id, reason, week, created, rng))
                if decline_week >= decline_len:
                    if recovers:
                        state = 'engaged'
                    else:
                        churn_day = week + timedelta(days=int(rng.integers(0, 7)))
                        churned_at = max(_ts(churn_day, rng), accounts[-1]['CREATED_AT'] + timedelta(days=1))
                        churn.append({'ACCOUNT_ID': account_id, 'CHURNED_AT': churned_at,
                                      'GENERATOR_REASON': reason})
                        state = 'churned'
            if rng.random() < NOTE_RATE_ROUTINE:
                notes.append(_note(account_id, ROUTINE, week, created, rng))
            last_day = week_end if state != 'churned' else churn[-1]['CHURNED_AT'].date()
            first_day = max(week, created)
            days = [first_day + timedelta(days=d) for d in range((last_day - first_day).days)]
            if days:
                saves = rng.multinomial(rng.poisson(save_rate * save_mult), [1 / len(days)] * len(days))
                logins = rng.random(len(days)) < login_p * login_mult
                for day, s, lg in zip(days, saves, logins):
                    if s or lg:
                        activity.append({'ACCOUNT_ID': account_id, 'ACTIVITY_DATE': day,
                                         'DOCUMENT_SAVES': int(s), 'LOGINS': int(lg)})
            if state != 'churned':
                used_frac = min(1.0, used_frac + growth * (0.3 if state == 'declining' else 1.0)
                                + rng.normal(0, 0.004))
                used_frac = max(0.0, used_frac)
                snapshots.append({'ACCOUNT_ID': account_id, 'SNAPSHOT_DATE': week + timedelta(days=6),
                                  'TAKEN_AT': datetime.combine(week + timedelta(days=6), time(23, 0)),
                                  'USED_BYTES': int(used_frac * quota), 'QUOTA_BYTES': quota})
    notes_df = pd.DataFrame(notes)
    notes_df.insert(0, 'NOTE_ID', [str(uuid.uuid5(NAMESPACE, f'note-{seed}-{k}')) for k in range(len(notes_df))])
    return {
        'ACCOUNTS': pd.DataFrame(accounts),
        'DAILY_ACTIVITY': pd.DataFrame(activity),
        'QUOTA_SNAPSHOTS': pd.DataFrame(snapshots),
        'CHURN_EVENTS': pd.DataFrame(churn),
        'SUPPORT_NOTES': notes_df,
    }


def _note(account_id, reason, week, created, rng):
    template = NOTE_TEMPLATES[reason][rng.integers(len(NOTE_TEMPLATES[reason]))]
    text = template.format(pct=int(rng.integers(80, 100)), n=int(rng.integers(3, 40)))
    day = max(week + timedelta(days=int(rng.integers(0, 7))), created)
    return {'ACCOUNT_ID': account_id, 'CREATED_AT': _ts(day, rng), 'NOTE_TEXT': text, 'GENERATOR_REASON': reason}


def checksum(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()


def manifest(tables: dict[str, pd.DataFrame], seed: int = SEED) -> dict:
    return {
        'seed': seed,
        'n_accounts': int(len(tables['ACCOUNTS'])),
        'weeks': [FIRST_WEEK.isoformat(), LAST_WEEK.isoformat()],
        'rule': __doc__.split('Rule (', 1)[1].strip(),
        'tables': {name: {'rows': int(len(df)), 'sha256': checksum(df)} for name, df in tables.items()},
    }


if __name__ == '__main__':
    t = generate()
    print(json.dumps({k: v for k, v in manifest(t).items() if k != 'rule'}, indent=1))
