#!/bin/bash
set -euo pipefail

echo "Initializing LocalStack resources..."

# Idempotent so re-runs on already-provisioned state (e.g. when DynamoDB tables
# are restored from a persisted snapshot with PERSISTENCE=1) do not abort under
# `set -e`. This ready.d hook runs on every container start.
bucket_exists() { awslocal s3api head-bucket --bucket "$1" >/dev/null 2>&1; }
table_exists()  { awslocal dynamodb describe-table --table-name "$1" >/dev/null 2>&1; }
make_bucket()   { bucket_exists "$1" || awslocal s3 mb "s3://$1"; }

# S3 Buckets
make_bucket otterworks-files
make_bucket otterworks-data-lake
make_bucket otterworks-audit-archive

# SQS Queue (create-queue is idempotent for an existing queue with the same name)
awslocal sqs create-queue --queue-name otterworks-notifications
awslocal sqs create-queue --queue-name otterworks-audit-events-queue
awslocal sqs create-queue --queue-name otterworks-search-events
awslocal sqs create-queue --queue-name otterworks-analytics-events
# Each consumer queue has its own DLQ, used by EventBridge for undeliverable events.
for q in otterworks-notifications otterworks-audit-events-queue otterworks-search-events otterworks-analytics-events; do
  awslocal sqs create-queue --queue-name "${q}-dlq" >/dev/null
done

# SNS Topic (create-topic returns the existing ARN if it already exists)
awslocal sns create-topic --name otterworks-events
NOTIFICATION_QUEUE_ARN=$(awslocal sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/otterworks-notifications \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)
awslocal sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:000000000000:otterworks-events \
  --protocol sqs \
  --notification-endpoint "$NOTIFICATION_QUEUE_ARN"
AUDIT_QUEUE_ARN=$(awslocal sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/otterworks-audit-events-queue \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)
awslocal sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:000000000000:otterworks-events \
  --protocol sqs \
  --notification-endpoint "$AUDIT_QUEUE_ARN"
SEARCH_QUEUE_ARN=$(awslocal sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/otterworks-search-events \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)
awslocal sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:000000000000:otterworks-events \
  --protocol sqs \
  --notification-endpoint "$SEARCH_QUEUE_ARN"

# EventBridge domain-event bus (mirrors infrastructure/terraform/modules/messaging).
# Publishers use it when EVENT_TRANSPORT is eventbridge or dual. Rules route on
# detail-type; a consumer without a detail-type list receives every event.
awslocal events describe-event-bus --name otterworks-events >/dev/null 2>&1 \
  || awslocal events create-event-bus --name otterworks-events
queue_arn() {
  awslocal sqs get-queue-attributes \
    --queue-url "http://localhost:4566/000000000000/$1" \
    --attribute-names QueueArn --query 'Attributes.QueueArn' --output text
}
route_events() {
  local rule="$1" queue="$2" pattern="$3" arn dlq_arn
  arn=$(queue_arn "$queue")
  dlq_arn=$(queue_arn "${queue}-dlq")
  awslocal events put-rule --event-bus-name otterworks-events --name "$rule" --event-pattern "$pattern" >/dev/null
  awslocal events put-targets --event-bus-name otterworks-events --rule "$rule" \
    --targets "Id=${queue},Arn=${arn},DeadLetterConfig={Arn=${dlq_arn}}" >/dev/null
}
route_events otterworks-notifications otterworks-notifications \
  '{"source":[{"prefix":"otterworks."}],"detail-type":["file_shared","comment_added","document_edited","user_mentioned"]}'
route_events otterworks-search-indexing otterworks-search-events \
  '{"source":[{"prefix":"otterworks."}],"detail-type":["document_created","document_updated","document_deleted","file_created","file_uploaded","file_updated","file_deleted","file_trashed","file_restored"]}'
route_events otterworks-analytics-events otterworks-analytics-events '{"source":[{"prefix":"otterworks."}]}'
route_events otterworks-audit-events otterworks-audit-events-queue '{"source":[{"prefix":"otterworks."}]}'


# DynamoDB Tables
table_exists otterworks-file-metadata || awslocal dynamodb create-table \
  --table-name otterworks-file-metadata \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

table_exists otterworks-audit-events || awslocal dynamodb create-table \
  --table-name otterworks-audit-events \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

table_exists otterworks-notifications || awslocal dynamodb create-table \
  --table-name otterworks-notifications \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=userId,AttributeType=S \
    AttributeName=createdAt,AttributeType=S \
  --key-schema \
    AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"userId-createdAt-index","KeySchema":[{"AttributeName":"userId","KeyType":"HASH"},{"AttributeName":"createdAt","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST

table_exists otterworks-notification-preferences || awslocal dynamodb create-table \
  --table-name otterworks-notification-preferences \
  --attribute-definitions AttributeName=userId,AttributeType=S \
  --key-schema AttributeName=userId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

table_exists otterworks-folders || awslocal dynamodb create-table \
  --table-name otterworks-folders \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

table_exists otterworks-file-versions || awslocal dynamodb create-table \
  --table-name otterworks-file-versions \
  --attribute-definitions \
    AttributeName=file_id,AttributeType=S \
    AttributeName=version,AttributeType=N \
  --key-schema \
    AttributeName=file_id,KeyType=HASH \
    AttributeName=version,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST

table_exists otterworks-file-shares || awslocal dynamodb create-table \
  --table-name otterworks-file-shares \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

echo "LocalStack initialization complete!"
