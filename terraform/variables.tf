variable "environment" {
  description = "Deployment environment name (staging, production)"
  type        = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class — small by default; this platform's data volume (a few hundred vendors, not millions) doesn't need much"
  type        = string
  default     = "db.t4g.small"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 50
}

variable "db_username" {
  type    = string
  default = "tprm"
}

variable "db_password" {
  description = "Set via TF_VAR_db_password or a CI secret — never commit a real value"
  type        = string
  sensitive   = true
}

variable "allowed_admin_cidr" {
  description = "CIDR allowed to reach the bastion/admin surface (e.g. your office VPN range) — never 0.0.0.0/0"
  type        = string
}
