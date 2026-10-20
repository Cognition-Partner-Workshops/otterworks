# Wave 1: six VM-hosted applications, their VM stand-ins and the run-scoped
# cloud resources the pipeline uses.
#   make vm-up            start the stand-ins on the shared seed data
#   make vm-smoke         hit every stand-in once
#   make vm-down          stop them; make reset also drops their volumes
#   make ecr RUN=<token>  create the ECR repositories for a run
#   make ns RUN=<token> PR=<n>   create the PR namespace on otterworks-dev
#   make destroy RUN=<token>     delete everything tagged with the token and prove it
SHELL := /bin/bash
REGION ?= us-east-1
CLUSTER ?= otterworks-dev
TTL_HOURS ?= 72
APPS := statements-web rates-batch branch-locator notify-svc kyc-docs
COMPOSE := docker compose -f vm/compose.yaml
DAYS := 2026-10-14 2026-10-15 2026-10-16

.PHONY: vm-build vm-up vm-rates vm-smoke vm-down reset ecr ns destroy check-run

vm-build:
	DOCKER_BUILDKIT=0 $(COMPOSE) build

vm-up:
	$(COMPOSE) up -d
	$(MAKE) vm-rates

vm-rates:
	@for d in $(DAYS); do $(COMPOSE) exec -T rates-01 /opt/rates/bin/run-rates.sh $$d; done
	@$(COMPOSE) exec -T rates-01 tail -n 3 /var/log/rates/rates.log

vm-smoke:
	@for i in $$(seq 1 40); do curl -sf -o /dev/null http://localhost:8081/statements/accounts && break; sleep 3; done
	curl -sf -o /dev/null -w "statements-web %{http_code}\n" http://localhost:8081/statements/accounts
	curl -sf -o /dev/null -w "branch-locator %{http_code}\n" "http://localhost:8083/api/nearest?q=harbour"
	curl -sf -o /dev/null -w "notify-svc     %{http_code}\n" -H 'Content-Type: application/json' \
	  -d '{"account":"HG611000001","kind":"statement_ready","fields":{}}' http://localhost:8084/notify
	curl -skf -o /dev/null -w "kyc-docs       %{http_code}\n" https://localhost:8085/documents/HG611000001
	curl -sf -o /dev/null -w "fx-report      %{http_code}\n" "http://localhost:8086/fx/fx-report.cgi?day=2026-10-16"
	$(COMPOSE) exec -T rates-01 ls /var/spool/rates/out

vm-down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v --remove-orphans

check-run:
	@[[ "$(RUN)" =~ ^[a-z0-9]{3,12}$$ ]] || { echo "RUN=<token> is required (lowercase letters and digits)"; exit 2; }

ecr: check-run
	@exp=$$(date -u -d "+$(TTL_HOURS) hours" +%Y-%m-%dT%H:%M:%SZ); \
	for a in $(APPS); do \
	  r=otterworks/bank-$$a; \
	  aws ecr describe-repositories --region $(REGION) --repository-names $$r >/dev/null 2>&1 || \
	  aws ecr create-repository --region $(REGION) --repository-name $$r --image-scanning-configuration scanOnPush=true \
	    --tags Key=run_token,Value=$(RUN) Key=Expires,Value=$$exp Key=Project,Value=otterworks-bank-wave1 >/dev/null; \
	  aws ecr put-lifecycle-policy --region $(REGION) --repository-name $$r --lifecycle-policy-text \
	    '{"rules":[{"rulePriority":1,"description":"keep the last 10 images","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":10},"action":{"type":"expire"}}]}' >/dev/null; \
	  echo "ecr $$r run_token=$(RUN) Expires=$$exp"; \
	done

ns: check-run
	@[[ -n "$(PR)" ]] || { echo "PR=<number> is required"; exit 2; }
	@ns=bank-w1-$(RUN)-pr$(PR); epoch=$$(( $$(date -u +%s) + $(TTL_HOURS) * 3600 )); \
	kubectl create namespace $$ns --dry-run=client -o yaml | kubectl apply -f - >/dev/null; \
	kubectl label namespace $$ns --overwrite demo/run-token=$(RUN) platform.otterworks.dev/policy=enforced \
	  app.kubernetes.io/part-of=bank-wave1 >/dev/null; \
	kubectl annotate namespace $$ns --overwrite demo/expires-at=$$(date -u -d @$$epoch +%Y-%m-%dT%H:%M:%SZ) \
	  demo/expires-at-epoch=$$epoch >/dev/null; \
	echo "namespace $$ns expires $$(date -u -d @$$epoch +%Y-%m-%dT%H:%M:%SZ)"

destroy: check-run
	@echo "== namespaces labelled demo/run-token=$(RUN)"
	@for ns in $$(kubectl get ns -l demo/run-token=$(RUN) -o name 2>/dev/null); do \
	  for rel in $$(helm list -q -n $${ns#namespace/}); do helm uninstall $$rel -n $${ns#namespace/} --wait; done; \
	  kubectl delete $$ns --wait=true; done
	@echo "== ECR repositories tagged run_token=$(RUN)"
	@for arn in $$(aws resourcegroupstaggingapi get-resources --region $(REGION) --resource-type-filters ecr:repository \
	    --tag-filters Key=run_token,Values=$(RUN) --query 'ResourceTagMappingList[].ResourceARN' --output text); do \
	  r=$${arn#*:repository/}; aws ecr delete-repository --region $(REGION) --repository-name $$r --force >/dev/null && echo "deleted $$r"; done
	@echo "== what is left"
	@left_ns=$$(kubectl get ns -l demo/run-token=$(RUN) -o name 2>/dev/null); \
	left_ecr=$$(for a in $(APPS); do aws ecr describe-repositories --region $(REGION) --repository-names otterworks/bank-$$a \
	  --query 'repositories[].repositoryName' --output text 2>/dev/null; done); \
	left_tag=$$(aws resourcegroupstaggingapi get-resources --region $(REGION) --tag-filters Key=run_token,Values=$(RUN) \
	  --query 'ResourceTagMappingList[].ResourceARN' --output text); \
	echo "namespaces: $${left_ns:-none}"; echo "ecr: $${left_ecr:-none}"; echo "tagged resources: $${left_tag:-none}"; \
	[[ -z "$$left_ns$$left_ecr$$left_tag" ]]
