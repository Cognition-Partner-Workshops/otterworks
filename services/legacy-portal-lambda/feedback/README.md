# Feedback Lambda

Standalone Java 21 port of the legacy portal feedback context. It uses the RDS Data API
and reads `CLUSTER_ARN`, `SECRET_ARN`, `DB_NAME`, and `DB_SCHEMA` (defaults to `feedback`)
from the Lambda environment.

Build and test:

```bash
mvn -q verify
```

Deploy the shaded JAR directly as the Lambda deployment archive:

```bash
aws lambda update-function-configuration \
  --function-name lp-20261005-mp-feedback \
  --runtime java21 \
  --handler com.otterworks.legacyportal.lambda.feedback.FeedbackHandler::handleRequest
aws lambda wait function-updated-v2 --function-name lp-20261005-mp-feedback
aws lambda update-function-code \
  --function-name lp-20261005-mp-feedback \
  --zip-file fileb://target/feedback-1.0.0.jar
```
