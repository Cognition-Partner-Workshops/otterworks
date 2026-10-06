# Strangler carve-out: preferences, run `lp-pref-20261006-a1` in front of `lp-ec2-20261006-b1`

The preferences bounded context of `services/legacy-portal` runs on API Gateway (HTTP API), a Java 21 Lambda and
Aurora Serverless v2, while every other route stays on the EC2 monolith of `lp-ec2-20261006-b1` through the API's
`$default` route. Same root, harness and corpus as announcements (see [strangler.md](strangler.md)); the Lambda is
main's `services/legacy-portal-lambda/preferences`, unchanged.

| | |
|---|---|
| Run token | `lp-pref-20261006-a1` |
| `Expires` | `2026-10-08` |
| Strangles | `lp-ec2-20261006-b1` (ALB `lp-ec2-20261006-b1`, instance `i-071dd05b8b26d8f4f`, `Expires` 2026-10-09) |
| HTTP API | `lp-pref-20261006-a1` (`oj7p5xpzx4`): `ANY /api/preferences`, `ANY /api/preferences/{proxy+}` on the Lambda alias, `$default` HTTP_PROXY to the ALB |
| Lambda | `lp-pref-20261006-a1-preferences`, `java21`, x86_64, 1024 MB, SnapStart on, alias `live` -> version **1** |
| Aurora | `lp-pref-20261006-a1`, aurora-postgresql 16.13, Serverless v2 0-1 ACU, Data API on, table `user_preferences.user_preference` |
| Events | none (preferences publishes nothing; no bus, rule or queue in this run) |
| State | `s3://otterworks-terraform-state/otterworks/legacy-portal-strangler/lp-pref-20261006-a1/terraform.tfstate` |

## Parity

`make lp-mod-replay RUN=lp-pref-20261006-a1`, 2026-10-06 11:01-11:02 UTC, first attempt, corpus checksums OK
(`SHA256SUMS`). The run held the EC2 lock throughout. Each replay started from empty tables with ids restarting at 1, and both
were compared with `java-reference.json`.

| Context | Cases | Served by (new) | EC2 ALB identical | HTTP API identical |
|---|---|---|---|---|
| common | 10 | EC2 | 10/10 | 10/10 |
| announcements | 36 | EC2 | 36/36 | 36/36 |
| preferences | 20 | Lambda + Aurora | 20/20 | 20/20 |
| feedback | 29 | EC2 | 29/29 | 29/29 |
| **total** | **95** | | **95/95** | **95/95** |

The API access log for the API replay shows 19 requests on `ANY /api/preferences/{proxy+}` and 76 on `$default`.
`pref-18` (`GET /API/preferences/alice`) does not match the case-sensitive route key, so `$default` sends it to the
monolith, which answers 404 as recorded. `pref-15` (`GET /api/preferences/`) reaches the Lambda and gets the same 404.

## Gap found on the way

Right after `terraform apply`, the published version stays `Pending` while SnapStart takes its snapshot, and during that
window the HTTP API answers `500 {"message":"Internal Server Error"}` for the module's routes. The first `lp-mod-status`
probe of `/api/preferences/u1` hit this window. The base now carries the fix (f9808c12): `lp-mod-up` waits with
`aws lambda wait function-active-v2 --qualifier live` before printing the outputs. Once `live` was Active, all four status
probes (`/health`, `/api/announcements`, `/api/preferences/u1`, `/api/feedback/average-rating`) returned 200.

## AWS documentation read (AWS MCP `aws___read_documentation`)

- [Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html): "Java 21 | `java21` | Amazon Linux 2023 | Jun 30, 2029"; "We recommend customers upgrade to an Amazon Linux 2023-based runtime as soon as possible." The function uses `java21`.
- [HTTP API Lambda integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html): "Format `2.0` has `rawPath`", "All headernames are lowercased", and API Gateway infers the response only when the function "doesn't return a `statusCode`". `PreferencesHandler` always returns `statusCode`, headers and body, so the 406 and 415 cases keep their status.
- [HTTP API routes](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-routes.html): "The `$default` route catches requests that don't explicitly match other routes… API Gateway sends the full request path to the integration". Precedence is full match, then greedy `{proxy+}`, then `$default`.

## Cleanup

The stack is left running until its `Expires` date. It costs little while idle: Aurora pauses at 0 ACU and the Lambda and HTTP API are pay per request.

```bash
make lp-mod-down RUN=lp-pref-20261006-a1 && make lp-mod-verify-clean RUN=lp-pref-20261006-a1
```

This does not touch `lp-ec2-20261006-b1`, which `lp-mod-down` reads only through `data "aws_lb"`.
