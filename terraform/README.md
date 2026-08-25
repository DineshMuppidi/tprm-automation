# Terraform — Supporting AWS Infrastructure

Phase 5 deliverable. Provisions what the Phase 0 architecture and tech
-stack docs actually named — VPC, RDS (PostgreSQL, encrypted, Multi-AZ in
production), S3 (evidence/contract storage, KMS-encrypted, versioned),
Secrets Manager, CloudWatch, and a WAF web ACL. Deliberately does not
provision compute (ECS/EKS workloads) — see `k8s/README.md` for that
layer.

**Not applied.** No `terraform` binary in this sandbox, and applying real
AWS infrastructure needs a live account, a reviewed `terraform plan`, and
explicit authorization in any case — not something to do from a sandbox
regardless of tooling availability. Written using the standard community
modules (`terraform-aws-modules/vpc`, `terraform-aws-modules/rds`) rather
than hand-rolled resources, so `terraform validate`/`plan` against a real
account would be checking well-trodden module code, not a bespoke VPC
implementation nobody has run before.

## Applying for real

```bash
terraform init
terraform plan -var="environment=staging" -var="db_password=$(openssl rand -base64 24)" \
  -var="allowed_admin_cidr=YOUR_OFFICE_CIDR/32"
terraform apply   # after reviewing the plan
```

`db_password` and `allowed_admin_cidr` have no defaults on purpose —
forces a conscious choice each time rather than silently reusing a
committed default.

## What's intentionally not here

- **Compute** (ECS services / EKS node groups): see `k8s/` — provisioning
  both a from-scratch ECS setup and Kubernetes manifests for the same
  workload would be redundant, and this repo's manifests already cover
  the Kubernetes path the Phase 0 doc names as the "beyond single-VM"
  option.
- **Route 53 / ACM**: DNS and certificate provisioning depend on a real
  registered domain, which doesn't exist for a portfolio project — the
  `aws_wafv2_web_acl` and ingress manifests assume these exist but don't
  create them.
- **CI/CD OIDC role for `aws_iam_role`**: the GitHub Actions workflows
  reference AWS credentials via repo secrets as a placeholder;
  a real deployment should use GitHub's OIDC federation instead of
  long-lived AWS keys in Actions secrets — noted here as the right next
  step, not implemented since it requires a real AWS account to wire up.
