# Cost Anomaly webhook

The forwarder accepts SNS Lambda events whose JSON message contains `anomalyId`, `accountId`, `monitorArn`, `anomalyStartDate` and `anomalyEndDate`. The outgoing payload gives Devin the notification date and ID, the scoped window, the run tag and the environment. The claim key combines notification type with the upstream anomaly ID.

For a no-cloud replay, supply `DEVIN_WEBHOOK_URL`, `DEVIN_WEBHOOK_SECRET` and `FINOPS_REPLAY_KEY` through the environment. Run both envelopes against the same ledger outside the repository:

```sh
python3 -m demos.finops.signals.replay --state "$FINOPS_REPLAY_STATE" \
  demos/finops/fixtures/anomaly-sns.json demos/finops/fixtures/anomaly-sns-duplicate.json
```

Devin authenticates the request through `X-Webhook-Secret`, and the additional `X-FinOps-Replay-Signature` header signs the posted bytes with HMAC-SHA256 for replay verification only.

For an approved AWS deployment, bind the SNS subscription to `forwarder.lambda_handler` and grant the Lambda `dynamodb:PutItem` and `dynamodb:DeleteItem` on a DynamoDB table keyed by the string `dedupe_key`. Set the same webhook URL and secret plus `FINOPS_DEDUPE_TABLE`, `FINOPS_RUN_TAG` and `FINOPS_ENVIRONMENT`. The AWS handler sends the same payload shape without a replay signature.

The forwarder claims a notification before sending. HTTP 401 or 403 releases the claim so you can replay after correcting the secret. An ambiguous HTTP outcome leaves the claim in place to avoid starting a second run; inspect Devin's run list before clearing the claim or replaying that delivery. A 2xx receipt acknowledges the request; check the automation run list for the spawned session ID.
