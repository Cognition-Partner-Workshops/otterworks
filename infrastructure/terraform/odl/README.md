# ODL ephemeral image repositories

Independent state, shared by the ODL feature branches; never apply platform state
for these repositories. All repositories inherit `run_token=odl-1795112287`,
`Expires=2027-02-17T00:00:00Z`, owner and demo tags. Lifecycle policies keep ten
images and inherit ownership through their repository (AWS cannot tag them).

To add only Confluence to an existing run without touching repositories from
other feature branches:

```sh
terraform -chdir=infrastructure/terraform/odl init -input=false
terraform -chdir=infrastructure/terraform/odl apply \
  '-target=aws_ecr_repository.images["mock-confluence"]' \
  '-target=aws_ecr_lifecycle_policy.images["mock-confluence"]'
```

```sh
terraform -chdir=infrastructure/terraform/odl init -input=false
terraform -chdir=infrastructure/terraform/odl plan -out=odl.tfplan
terraform -chdir=infrastructure/terraform/odl apply odl.tfplan
# Only after all ODL consumers have been removed:
terraform -chdir=infrastructure/terraform/odl destroy
```

`force_delete` removes images on destroy. Do not commit state or plans. The mongo
repository mirrors the official `mongo:8.0.16` image to avoid Docker Hub limits.
