# legacy-portal-lambda-preferences

AWS Lambda port of the legacy-portal `userpreferences` bounded context
(`GET`/`PUT /api/preferences/{userId}`), backed by the Aurora Serverless RDS
Data API against the `user_preferences.user_preference` table.

## Build

```bash
mvn -f services/legacy-portal-lambda/preferences/pom.xml verify
```

Produces a shaded fat jar at `target/legacy-portal-lambda-preferences-1.0.0.jar`.

## Deploy

```bash
aws lambda update-function-code \
  --function-name <function-name> \
  --zip-file fileb://services/legacy-portal-lambda/preferences/target/legacy-portal-lambda-preferences-1.0.0.jar
```

Handler string: `com.otterworks.legacyportal.lambda.preferences.PreferencesHandler::handleRequest`

Runtime: `java21`. Required environment: `CLUSTER_ARN`, `SECRET_ARN`, `DB_NAME`,
`DB_SCHEMA` (validated against `^[a-z_][a-z0-9_]*$`).
