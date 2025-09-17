# AgentOS Production Configuration
# Terraform variables for production deployment

# Environment Configuration
environment = "production"
aws_region  = "us-east-1"
domain      = "agentos.io"

# Network Configuration
vpc_cidr                  = "10.0.0.0/16"
availability_zones_count  = 3

# Database Configuration
db_instance_class          = "db.r6g.xlarge"
db_allocated_storage       = 100
db_max_allocated_storage   = 1000
db_iops                   = 3000
db_backup_retention_period = 30
db_username               = "agentos_admin"
# db_password is set via environment variable TF_VAR_db_password

# Redis Configuration
redis_node_type    = "cache.r6g.large"
redis_num_replicas = 2
# redis_auth_token is set via environment variable TF_VAR_redis_auth_token

# EKS Configuration
eks_min_size      = 2
eks_max_size      = 20
eks_desired_size  = 3
eks_instance_types = ["t3a.large", "t3a.xlarge"]

# Application Configuration
app_replicas      = 3
app_cpu_request   = "500m"
app_memory_request = "512Mi"
app_cpu_limit     = "2000m"
app_memory_limit  = "2Gi"

# CloudFlare Configuration
# cloudflare_api_token is set via environment variable TF_VAR_cloudflare_api_token
# cloudflare_zone_id is set via environment variable TF_VAR_cloudflare_zone_id

# Monitoring and Logging
enable_monitoring   = true
log_retention_days  = 30

# Backup Configuration
backup_retention_days = 90

# Security Configuration
enable_encryption          = true
enable_deletion_protection = true

# Feature Flags
enable_redis_cluster           = true
enable_multi_az               = true
enable_performance_insights   = true
enable_enhanced_monitoring    = true
enable_autoscaling            = true
enable_compliance_monitoring  = true
enable_cloudtrail            = true

# Cost Optimization
use_spot_instances = false  # Keep false for production stability

# Disaster Recovery
enable_cross_region_backup = true
backup_region             = "us-west-2"

# Tags
project_name = "AgentOS"
team_name    = "AgentOS-Platform"
cost_center  = "Engineering"

additional_tags = {
  "Deployment"    = "terraform"
  "Application"   = "agentos"
  "CriticalLevel" = "high"
  "Backup"        = "required"
  "Monitoring"    = "24x7"
  "Compliance"    = "required"
}