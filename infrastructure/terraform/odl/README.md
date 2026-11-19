# ODL ephemeral image repositories

Independent state; does not apply platform or application infrastructure. AWS
credentials must be supplied through the environment. Every repository inherits
`run_token=odl-1795112287`, `Expires=2027-02-17T00:00:00Z`, owner and demo tags.
ECR lifecycle policies inherit ownership through their repository (AWS does not
support tagging lifecycle policies separately).

```sh
terraform -chdir=infrastructure/terraform/odl init -input=false
terraform -chdir=infrastructure/terraform/odl plan -out=odl.tfplan
terraform -chdir=infrastructure/terraform/odl apply odl.tfplan
terraform -chdir=infrastructure/terraform/odl output repository_urls
# Only after all ODL image consumers have been removed:
terraform -chdir=infrastructure/terraform/odl destroy
```

`force_delete` removes images on destroy. Plans/state may contain sensitive
infrastructure data: do not commit them.
