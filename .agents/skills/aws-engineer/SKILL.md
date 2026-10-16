---
name: aws-engineer
description: >
  How a session works as the AWS engineer on OtterWorks: the engineer role for
  Terraform applies, the read-only console user for screen recordings, the AWS
  documentation MCP server, the run_token and Expires tags every resource
  carries, and the evidence a session leaves in its own timeline.
---

# Working as the AWS engineer on OtterWorks

The account runs in `us-east-1`, with the cluster `otterworks-dev`. Everything a session creates in AWS comes from Terraform under `infrastructure/terraform/` and carries the tags `run_token` and `Expires`, so the monthly reaper and `make lp-verify-clean` can find it afterwards.

## 1. Credentials

`cloudworker/assume.sh` turns the `CW_*` secrets in the environment into a role session named after the Devin session, so CloudTrail shows each call under `devin-<session id>`. Three roles exist. Use the lowest one that does the job and switch back to the observer when the write is done.

| Role | Assume | Use for |
| --- | --- | --- |
| `devin-cw-observer` | `source <(cloudworker/assume.sh observer devin-<session id>)` | Every read: metrics, logs, CloudTrail, describe calls |
| `devin-cw-builder` | `source <(cloudworker/assume.sh builder devin-<session id>)` | Deploying code into a run that already exists (Lambda code and configuration, redrives, alarm state) |
| `devin-aws-engineer` | `source <(cloudworker/assume.sh engineer devin-<session id>)` | `terraform apply` and `destroy`: PowerUserAccess plus IAM on roles and policies named `lp-*` or `otterworks-*` |

The engineer role cannot touch the Devin roles, the console user or any human user. Other AWS variables may be present on the machine; leave them alone and let `assume.sh` set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`.

```bash
source <(cloudworker/assume.sh engineer devin-<session id>)
aws sts get-caller-identity --query Arn --output text   # assumed-role/devin-aws-engineer/devin-<session id>
```

## 2. The AWS Management Console

The secrets `AWS_CONSOLE_SIGNIN_URL`, `AWS_CONSOLE_USERNAME` and `AWS_CONSOLE_PASSWORD` sign a browser into the console as an IAM user in the READONLY group. It can open every page and change nothing. Use it for the screen recording of the evidence a reviewer would look at: the Lambda function page with its alias and versions, the HTTP API routes, the EventBridge rule and its targets, the Aurora cluster, the CloudWatch alarm history and the log group. Maximize the browser before recording, record the whole flow in one take and attach the recording and the screenshots to the session before the final message.

## 3. AWS documentation through MCP

The AWS MCP server is available in the session as `aws-agent-toolkit`, with `aws___search_documentation` for a search that returns page text and `aws___read_documentation` for a whole page. It starts through `uvx`; if the server fails to connect, install it with `python3 -m pip install --user uv` and make sure `~/.local/bin` is on the path. Before choosing a service setting that matters (Lambda alias routing, CodeDeploy deployment configurations, API Gateway payload format, Aurora Data API limits, EventBridge input transformers), search the documentation through it and quote the page in the timeline with the decision it informed.

## 4. Tags, tokens and lifetime

A run token looks like `lp-<yyyymmdd>-<two letters>` and prefixes every resource name of that run. `run_token=<token>` and `Expires=<RFC 3339 date>` go on every resource through the Terraform `default_tags`. `make lp-verify-clean RUN=<token>` lists what a token still owns. The reaper automation deletes expired tokens, so a stack that must outlive the session needs `Expires` in the future and a line in the session's final message saying why it was kept.

## 5. Evidence a session leaves behind

The final message of a session carries, inside the session itself: the replay or test table it ran, the console recording and screenshots, the pull request link when code changed, the CloudTrail rows for its role session, the run token with its expiry, and the cleanup command that removes what it made. Nothing the audience needs should sit only on the machine.
