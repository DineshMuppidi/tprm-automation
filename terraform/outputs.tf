output "rds_endpoint" {
  value       = module.rds.db_instance_endpoint
  description = "Set as the host portion of DATABASE_URL in the app's secrets"
}

output "evidence_bucket_name" {
  value = aws_s3_bucket.evidence_storage.id
}

output "app_security_group_id" {
  value       = aws_security_group.app.id
  description = "Attach to the ECS task / EKS node group running the backend"
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "private_subnet_ids" {
  value = module.vpc.private_subnets
}
