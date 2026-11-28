import hashlib
import hmac
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalize(record, run_tag, environment, source):
    sns = record["Sns"]
    message = json.loads(sns["Message"])
    notification_id = message["anomalyId"]
    if not isinstance(notification_id, str) or not notification_id.strip():
        raise ValueError("Cost Anomaly notifications need a stable anomalyId")
    return {
        "source": source,
        "notification_type": "aws.cost-anomaly",
        "notification_id": notification_id,
        "sns_message_id": sns["MessageId"],
        "day": sns["Timestamp"][:10],
        "run_tag": run_tag,
        "environment": environment,
        "spend_scope": {
            "account_id": message["accountId"],
            "monitor_arn": message["monitorArn"],
            "window_start": message["anomalyStartDate"],
            "window_end": message["anomalyEndDate"],
        },
    }


def webhook_sender(url, secret, signing_key=None):
    endpoint = urlsplit(url)
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username is not None:
        raise ValueError("Set an HTTPS webhook URL without embedded credentials")
    if not secret:
        raise ValueError("Set the Devin webhook secret")
    opener = build_opener(NoRedirects())

    def send(payload):
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json", "X-Webhook-Secret": secret}
        if signing_key is not None:
            digest = hmac.new(signing_key, body, hashlib.sha256).hexdigest()
            headers["X-FinOps-Replay-Signature"] = f"sha256={digest}"
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with opener.open(request, timeout=15) as response:
                return response.status
        except HTTPError as exc:
            return exc.code
        except (URLError, TimeoutError):
            return None

    return send


def forward(event, claim, send, *, release, run_tag, environment, source):
    receipts = []
    payloads = [normalize(record, run_tag, environment, source) for record in event["Records"]]
    for payload in payloads:
        key = f'{payload["notification_type"]}:{payload["notification_id"]}'
        receipt = {**payload, "dedupe_key": key, "result": "duplicate_suppressed"}
        if claim(key):
            status = send(payload)
            if status == 401:
                release(key)
            receipt["webhook_status"] = status
            receipt["result"] = "accepted" if status is not None and 200 <= status < 300 else "delivery_unconfirmed"
        receipts.append(receipt)
    return receipts


def lambda_handler(event, context):
    import boto3

    ledger = boto3.resource("dynamodb").Table(os.environ["FINOPS_DEDUPE_TABLE"])

    def claim(key):
        try:
            ledger.put_item(
                Item={"dedupe_key": key},
                ConditionExpression="attribute_not_exists(dedupe_key)",
            )
        except ledger.meta.client.exceptions.ConditionalCheckFailedException:
            return False
        return True

    def release(key):
        ledger.delete_item(Key={"dedupe_key": key})

    receipts = forward(
        event, claim, webhook_sender(os.environ["DEVIN_WEBHOOK_URL"], os.environ["DEVIN_WEBHOOK_SECRET"]),
        release=release,
        run_tag=os.environ["FINOPS_RUN_TAG"], environment=os.environ["FINOPS_ENVIRONMENT"], source="aws:sns",
    )
    print(json.dumps(receipts))
    if any(receipt["result"] == "delivery_unconfirmed" for receipt in receipts):
        raise RuntimeError("Webhook delivery unconfirmed; inspect the automation before retrying")
    return receipts
