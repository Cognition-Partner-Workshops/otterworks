"""Durable workflow gates and a failing, optionally SMTP-delivered GL alert."""

import argparse
import json
import os
import smtplib
import sys
from email.message import EmailMessage

from lakehouse.billing.informatica import ORDER, save
from lakehouse.orchestration.graph import business_date
from lakehouse.runtime.layout import data_root


def control(root, day, action):
    business_date(day)
    if action == 'start':
        save(root / 'workflow.json', {'business_date': day, 'status': 'RUNNING'})
        (root / 'sessions.json').unlink(missing_ok=True)
        (root / 'inputs.json').unlink(missing_ok=True)
        for path in (root / 'sessions').glob('*.json'):
            path.unlink()
        return 0
    sessions = json.loads((root / 'sessions.json').read_text())
    if action.startswith('session:'):
        table = action.split(':', 1)[1]
        status = sessions.get(table, {}).get('Status')
        if status not in ('SUCCEEDED', 'NOTSTARTED'):
            raise RuntimeError('Mapping did not complete: ' + table)
        for suffix in ('', '_rejects', '_errors', '_transformation_rejects'):
            if not (root / (table.lower() + suffix + '.psv')).is_file():
                raise RuntimeError('Missing mapping output: ' + table + suffix)
        return 0
    if action == 'worklet':
        valid = all(sessions.get(t, {}).get('Status') == 'SUCCEEDED' for t in ORDER[:3])
        save(root / 'worklet.json', {'status': 'SUCCEEDED' if valid else 'FAILED'})
        return 0
    gl = sessions.get('GL_JOURNAL_LINE', {})
    posted = gl.get('Status') == 'SUCCEEDED' and gl.get('TgtFailedRows') == 0
    if action == 'decision':
        save(root / 'decision.json', {'Condition': int(posted)})
        return 0
    decision = json.loads((root / 'decision.json').read_text())['Condition']
    if action == 'payment':
        status = sessions.get('PAYMENT', {}).get('Status')
        if decision and status != 'SUCCEEDED':
            raise RuntimeError('Payment session failed on the true decision branch')
        if not decision and status == 'SUCCEEDED':
            raise RuntimeError('Payment incorrectly executed on the false decision branch')
        return 0
    if action == 'alert':
        if decision:
            save(root / 'alert.json', {'status': 'NOTSTARTED'})
            return 0
        alert = {'to': 'finance-data-oncall@otterworks.example',
                 'subject': f'GL posting for {day} did not balance',
                 'body': json.dumps(sessions, sort_keys=True), 'status': 'QUEUED'}
        save(root / 'outbox' / 'gl_posting_alert.json', alert)
        print('GL POSTING ALERT: ' + alert['subject'], file=sys.stderr, flush=True)
        if os.environ.get('SFX_LH_SMTP_HOST'):
            message = EmailMessage()
            message['To'], message['Subject'] = alert['to'], alert['subject']
            message['From'] = os.environ.get('SFX_LH_SMTP_FROM', 'lakehouse@localhost')
            message.set_content(alert['body'])
            with smtplib.SMTP(os.environ['SFX_LH_SMTP_HOST'], int(os.environ.get('SFX_LH_SMTP_PORT', '25')), timeout=30) as smtp:
                smtp.send_message(message)
            alert['status'] = 'SENT'
        save(root / 'alert.json', alert)
        save(root / 'workflow.json', {'business_date': day, 'status': 'FAILED'})
        return 1
    if action == 'finish':
        valid = decision and all(sessions.get(t, {}).get('Status') == 'SUCCEEDED' for t in ORDER)
        save(root / 'workflow.json', {'business_date': day, 'status': 'SUCCEEDED' if valid else 'FAILED'})
        return 0 if valid else 1
    raise ValueError('Unknown workflow action: ' + action)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--action', required=True)
    args = parser.parse_args()
    root = data_root() / 'informatica' / args.business_date
    raise SystemExit(control(root, args.business_date, args.action))


if __name__ == '__main__':
    main()
