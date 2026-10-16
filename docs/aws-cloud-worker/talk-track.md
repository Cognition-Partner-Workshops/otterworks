# AWS cloud worker talk track

## Opening

Your team runs one AWS account with SNS, SQS, a consumer on EKS and DynamoDB, plus Terraform for all of it. Questions about the account, alarms at night and small change requests from product all reach the same few people, and nobody has ten minutes. For the next ten minutes Devin works as the AWS engineer on that team: asked a question, paged by CloudWatch and handed a change.

Say: "One team, one AWS account, and nobody has ten minutes. Watch Devin take the question, the page and the change."

The record describes two accounts, and this build uses one tenant and two IAM roles, a read-only observer and a narrow builder, and CloudTrail separates the two by role in act 4.

## Act 1: ask

The audience sees the AWS engineer ask Devin what runs in the demo tenant, how a file share becomes a notification, and whether the account matches Terraform. Devin reads the account under the read-only role and answers with the path from SNS to SQS to the Kotlin consumer to DynamoDB, the two IRSA roles, and one drift: the queue keeps messages for 14 days and Terraform says 4.

Say: "Devin read the account and the Terraform side by side, and found the drift before anyone ran a plan."

## Act 2: page

The audience sees the dashboard as messages pile into the dead-letter queue, then the alarm, then a new Devin session that nobody started. EventBridge posted the alarm to a Devin Automation. Devin reads the alarm, the queues, the consumer logs and the Helm history, finds that the live table name differs from git, restores the config from git under the builder role, redrives the queue, runs the after gate and opens a pull request that makes a bad table name fail at boot.

Say: "Somebody changed a setting by hand, and Devin found it in the telemetry, put git back in charge, replayed the lost notifications and proved it with a gate it cannot edit."

## Act 3: change

The audience sees a product manager ask, in plain language, for a "Signed in today" tile and a last sign-in column on the admin dashboard. Devin works from the demo branch, opens a pull request, Devin Review comments on it, and CD deploys the branch to its own tenant. The product manager opens the link and sees the tile on seeded data.

Say: "The person who knew what was needed asked for it directly, and the review and the deploy ran the way they run for your engineers."

## Act 4: close

The audience sees the CloudTrail table from `make cw-trail`. Reads show under the observer role, and the redrive shows under the builder role, each tagged with the Devin session that made the call.

Say: "Every call Devin made is in CloudTrail under a role you scoped and a session you can open."
