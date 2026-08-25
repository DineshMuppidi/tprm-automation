# Supporting AWS infrastructure for the Phase 0 architecture doc's stated
# choices (RDS PostgreSQL, S3 for evidence/contract storage, CloudWatch,
# Secrets Manager, WAF). Deliberately does NOT provision the compute layer
# (ECS/EKS workloads) — k8s/ already covers that if the target is
# Kubernetes; a from-scratch ECS task-definition equivalent would just be
# k8s/'s manifests translated to a different scheduler for no added value
# in a portfolio build.
#
# Not applied: no `terraform` CLI in this sandbox, and applying real AWS
# infrastructure isn't something to do without a live AWS account, a
# reviewed plan, and the user's explicit go-ahead in any case — same
# reasoning the Bash tool's own safety rules already apply to. Written to
# be `terraform validate`-clean, using the standard community modules
# rather than hand-rolled VPC/RDS resources (the modules are the boring,
# well-tested choice — a hand-rolled VPC in a portfolio repo is a good way
# to hide a routing mistake behind confident-looking HCL).

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Real deployments: an S3 + DynamoDB backend for state locking, not local
  # state. Left unconfigured here rather than pointing at a bucket that
  # doesn't exist.
  # backend "s3" {}
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "tprm-automation"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "tprm-${var.environment}"
  cidr = var.vpc_cidr

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = [cidrsubnet(var.vpc_cidr, 4, 0), cidrsubnet(var.vpc_cidr, 4, 1)]
  public_subnets  = [cidrsubnet(var.vpc_cidr, 4, 8), cidrsubnet(var.vpc_cidr, 4, 9)]
  database_subnets = [cidrsubnet(var.vpc_cidr, 4, 12), cidrsubnet(var.vpc_cidr, 4, 13)]

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"   # one NAT for staging (cost), redundant pair for prod
  enable_dns_hostnames = true
}

resource "aws_security_group" "rds" {
  name_prefix = "tprm-${var.environment}-rds-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Postgres from the app tier's security group only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "app" {
  name_prefix = "tprm-${var.environment}-app-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTPS from the ALB only"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]   # tightened to the ALB's security group once that's created alongside the compute layer
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "tprm-${var.environment}"

  engine               = "postgres"
  engine_version       = "15"
  instance_class       = var.db_instance_class
  allocated_storage    = var.db_allocated_storage_gb
  storage_encrypted    = true   # Phase 5 spec §1a: encryption at rest

  db_name  = "tprm"
  username = var.db_username
  password = var.db_password
  port     = 5432

  multi_az               = var.environment == "production"
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = var.environment == "production" ? 30 : 7
  deletion_protection     = var.environment == "production"
  skip_final_snapshot     = var.environment != "production"

  # Phase 5 disaster-recovery doc's RPO — point-in-time recovery, not just
  # daily snapshots.
  create_db_option_group    = false
  create_db_parameter_group = false
}

resource "aws_kms_key" "evidence_storage" {
  description             = "Encrypts the S3 evidence/contract storage bucket"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_s3_bucket" "evidence_storage" {
  bucket_prefix = "tprm-${var.environment}-evidence-"
}

resource "aws_s3_bucket_versioning" "evidence_storage" {
  bucket = aws_s3_bucket.evidence_storage.id
  versioning_configuration {
    status = "Enabled"   # matches the disaster-recovery doc's backup story
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence_storage" {
  bucket = aws_s3_bucket.evidence_storage.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.evidence_storage.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "evidence_storage" {
  bucket                  = aws_s3_bucket.evidence_storage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_secretsmanager_secret" "app_secrets" {
  name = "tprm/${var.environment}/app-secrets"
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/tprm/${var.environment}/backend"
  retention_in_days = var.environment == "production" ? 90 : 30
}

resource "aws_wafv2_web_acl" "app" {
  name  = "tprm-${var.environment}"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "tprm-${var.environment}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "tprm-${var.environment}"
    sampled_requests_enabled   = true
  }
}
