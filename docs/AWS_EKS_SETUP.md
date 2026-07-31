# AWS and EKS deployment setup

This guide provisions and deploys the OtterWorks development environment to AWS. It is intended for each developer who needs to run `make deploy-dev` from their own workstation.

The deployment creates AWS infrastructure with Terraform, builds and pushes images to ECR, configures Kubernetes runtime settings from Terraform outputs, and deploys services to EKS with Helm.

## 1. Prerequisites

Install and authenticate the following command-line tools:

- AWS CLI v2
- Docker Desktop
- Terraform 1.7 or later
- `kubectl`
- Helm 3
- `jq`
- OpenSSL
- GNU Make

Verify the tools before starting:

```sh
aws --version
docker version --format '{{.Server.Version}}'
terraform version
kubectl version --client
helm version
jq --version
openssl version
```

Your AWS identity needs permission to use the Terraform state bucket, provision the repository's AWS resources, push images to ECR, and access the EKS cluster. Use an individual AWS IAM Identity Center (SSO) profile; do not share AWS access keys.

## 2. Authenticate to AWS

`otterworks` here is a **profile name**: a local alias stored in `~/.aws/config` on your machine. It is not the AWS account, and it is unrelated to the EKS cluster name. You may name it anything; if you use a different name, replace `otterworks` consistently throughout this guide.

Choose one of the two authentication methods below. IAM Identity Center (SSO) is recommended because its credentials expire automatically and are not stored on disk as long-lived keys.

### Option A: IAM Identity Center (SSO) — recommended

Configure the profile once. This is interactive and prompts for your organization's SSO start URL (for example `https://your-org.awsapps.com/start`), the AWS account, and the role to assume:

```sh
aws configure sso --profile otterworks
```

At the beginning of each new terminal session, sign in. SSO sessions expire, so this step is required whenever the session lapses:

```sh
export AWS_PROFILE=otterworks
aws sso login --profile "$AWS_PROFILE"
aws sts get-caller-identity
```

### Option B: Static access keys

Use this if your organization does not use SSO. Configure the profile once with a long-lived access key ID and secret access key:

```sh
aws configure --profile otterworks
```

Static keys do not expire, so there is no `aws sso login` step. In each new terminal session, select the profile and confirm your identity:

```sh
export AWS_PROFILE=otterworks
aws sts get-caller-identity
```

Static keys are long-lived secrets: never commit them, and rotate them regularly.

> This guide provisions a single development environment. If you later need to target multiple isolated AWS accounts, create a separate profile and a separate local environment file (see [section 3](#3-create-a-local-deployment-environment-file)) per account, and switch between them with `AWS_PROFILE`.

## 3. Create a local deployment environment file

Shell `export` commands only apply to the terminal in which they are run. Keep non-committed deployment settings in a local `.env` file, which this repository already ignores.

```sh
cat > .env <<'EOF'
export AWS_PROFILE=otterworks
export AWS_REGION=us-east-1
export EKS_CLUSTER=otterworks-dev
export NAMESPACE=otterworks
export AWS_ACCOUNT_ID=REPLACE_WITH_AWS_ACCOUNT_ID
export DB_PASSWORD=REPLACE_WITH_RDS_PASSWORD
export JWT_SECRET=REPLACE_WITH_JWT_SECRET
EOF
```

Set the account ID from your authenticated identity:

```sh
aws sts get-caller-identity --query Account --output text
```

Generate a compliant JWT secret. The auth service requires at least 32 bytes for HS256:

```sh
openssl rand -base64 48
```

Replace the corresponding values in `.env`, lock down its permissions, then load it whenever you need to deploy:

```sh
chmod 600 .env
source .env
```

Never commit `.env`, AWS access keys, database passwords, or JWT secrets. For a team environment, store `DB_PASSWORD` and `JWT_SECRET` in an approved shared secret manager such as AWS Secrets Manager or a team password-manager vault. Every developer should use their own AWS identity to retrieve those values.

## 4. Install the monitoring prerequisite

Every service chart creates a Prometheus Operator `ServiceMonitor`. EKS does not install its CRD by default, so install the operator once per EKS cluster:

```sh
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace
```

Confirm that the CRD exists before deploying OtterWorks:

```sh
kubectl get crd servicemonitors.monitoring.coreos.com
```

If this command returns `NotFound`, every Helm service deployment will fail before creating its workload.

## 5. Deploy

Load your local environment and run the full deployment:

```sh
source .env
make deploy-dev
```

The deployment script performs these steps:

1. Applies platform Terraform for VPC, EKS, and ECR.
2. Applies application Terraform for RDS, ElastiCache, S3, DynamoDB, SQS/SNS, Cognito, and IAM roles for service accounts (IRSA).
3. Configures `kubectl` for the EKS cluster and creates the `otterworks` namespace.
4. Reads Terraform outputs and creates per-service Kubernetes ConfigMaps and Secrets.
5. Builds and pushes service images to ECR.
6. Deploys Helm charts with their matching IRSA role ARN.

The runtime configuration bridge is implemented in `scripts/deploy-dev.sh`. Do not manually add AWS access keys to Pods: workloads access AWS resources through IRSA.

## 6. Verify the deployment

```sh
kubectl get pods -n otterworks -o wide
kubectl get deployments -n otterworks
kubectl get events -n otterworks --sort-by=.lastTimestamp
helm list --namespace otterworks
```

All deployments should show the desired replicas as available. To inspect an unhealthy service:

```sh
kubectl logs -n otterworks -l app.kubernetes.io/instance=SERVICE --previous
kubectl describe pod -n otterworks POD_NAME
```

Replace `SERVICE` and `POD_NAME` with the affected resource.

## 7. Redis TLS

The development ElastiCache replication group requires TLS. The deployment script sets `REDIS_TLS=true`, and the Redis-backed services are configured to use TLS. Do not replace the generated ElastiCache endpoint with `localhost` or a plain `redis://` URL.

Verify the AWS setting:

```sh
aws elasticache describe-replication-groups \
  --replication-group-id otterworks-redis-dev \
  --region "$AWS_REGION" \
  --query 'ReplicationGroups[0].{Endpoint:NodeGroups[0].PrimaryEndpoint.Address,Port:NodeGroups[0].PrimaryEndpoint.Port,TlsEnabled:TransitEncryptionEnabled,TlsMode:TransitEncryptionMode,AuthEnabled:AuthTokenEnabled}' \
  --output table
```

Expected development settings are `TlsEnabled=True`, `TlsMode=required`, and `AuthEnabled=False`.

## 8. Common failures

| Symptom | Cause | Resolution |
|---|---|---|
| `AWS_ACCOUNT_ID must be set` | Environment variables were not loaded in this shell. | Run `source .env`. |
| `NoCredentials` or AWS access denied | The AWS SSO session has expired, static keys are missing/invalid, or the profile lacks access. | For SSO, run `aws sso login --profile "$AWS_PROFILE"`; for static keys, verify them with `aws configure --profile "$AWS_PROFILE"`. Request the required AWS permissions if access is still denied. |
| `AmazonEBSCSIDriverPolicyV2 does not exist` | An obsolete/nonexistent AWS managed-policy ARN was configured. | Use `AmazonEBSCSIDriverPolicy`; the Terraform module is already corrected. |
| `BucketAlreadyExists` for OtterWorks buckets | S3 names are global across all AWS accounts. | The Terraform module includes the AWS account ID in bucket names; apply the current configuration. Do not import a bucket unless this AWS account owns and intends to manage it. |
| RDS says `Still creating` | RDS provisioning commonly takes several minutes. | Wait for Terraform to report completion. |
| Lifecycle `filter` warning | S3 lifecycle rules need an explicit scope. | The current module uses `filter {}` for the all-objects rule. |
| `no matches for kind ServiceMonitor` | Prometheus Operator CRDs are missing. | Complete [Install the monitoring prerequisite](#4-install-the-monitoring-prerequisite). |
| Helm times out with `Available: 0/1` | A Pod started but did not become ready. | Read its previous logs with `kubectl logs ... --previous`; do not fix this by only increasing Helm's timeout. |
| `JWT_SECRET` is too short | The auth service requires at least 32 bytes. | Generate a new value with `openssl rand -base64 48`, update `.env`, and redeploy. |
| Rails requests `admin_service_development` | The admin database setting was not wired to RDS. | Deploy the current script, which sets `DATABASE_NAME=otterworks`; the admin image runs migrations at startup. |
| Redis connection reset/handshake failure | ElastiCache requires TLS. | Keep `REDIS_TLS=true`; use the current service images, which configure TLS clients. |

## 9. Subsequent deployments

For later deployments in a new terminal:

```sh
source .env
aws sso login --profile "$AWS_PROFILE"   # SSO only; skip if you use static keys
make deploy-dev
```

If Terraform infrastructure already exists and you only need to rebuild and redeploy workloads, the script supports:

```sh
source .env
./scripts/deploy-dev.sh --skip-terraform
```

Terraform outputs and state must still be accessible because the script reads them to configure Kubernetes runtime settings.

## 10. Teardown

`make teardown-dev` destroys development resources. Review the Terraform destroy plan carefully before running it. Do not use teardown against an environment that contains data you need to preserve.
