# AgentOS Terraform Variables
# Define all configurable parameters for the infrastructure

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (production, staging, development)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging", "development"], var.environment)
    error_message = "Environment must be one of: production, staging, development."
  }
}

variable "domain" {
  description = "Base domain name for the application"
  type        = string
  default     = "agentos.io"
}

# Database Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.xlarge"

  validation {
    condition = can(regex("^db\\.", var.db_instance_class))
    error_message = "DB instance class must start with 'db.'"
  }
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for RDS (GB)"
  type        = number
  default     = 100

  validation {
    condition     = var.db_allocated_storage >= 20 && var.db_allocated_storage <= 65536
    error_message = "DB allocated storage must be between 20 and 65536 GB."
  }
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS autoscaling (GB)"
  type        = number
  default     = 1000

  validation {
    condition     = var.db_max_allocated_storage >= 100
    error_message = "DB max allocated storage must be at least 100 GB."
  }
}

variable "db_iops" {
  description = "IOPS for RDS storage"
  type        = number
  default     = 3000

  validation {
    condition     = var.db_iops >= 1000 && var.db_iops <= 256000
    error_message = "DB IOPS must be between 1000 and 256000."
  }
}

variable "db_backup_retention_period" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 30

  validation {
    condition     = var.db_backup_retention_period >= 7 && var.db_backup_retention_period <= 35
    error_message = "Backup retention period must be between 7 and 35 days."
  }
}

variable "db_username" {
  description = "Master username for RDS instance"
  type        = string
  default     = "agentos_admin"
  sensitive   = true

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]*$", var.db_username))
    error_message = "DB username must start with a letter and contain only alphanumeric characters and underscores."
  }
}

variable "db_password" {
  description = "Master password for RDS instance"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8 && length(var.db_password) <= 128
    error_message = "DB password must be between 8 and 128 characters."
  }
}

# Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.r6g.large"

  validation {
    condition = can(regex("^cache\\.", var.redis_node_type))
    error_message = "Redis node type must start with 'cache.'"
  }
}

variable "redis_num_replicas" {
  description = "Number of Redis replicas"
  type        = number
  default     = 2

  validation {
    condition     = var.redis_num_replicas >= 1 && var.redis_num_replicas <= 5
    error_message = "Redis replicas must be between 1 and 5."
  }
}

variable "redis_auth_token" {
  description = "Auth token for Redis cluster"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.redis_auth_token) >= 16 && length(var.redis_auth_token) <= 128
    error_message = "Redis auth token must be between 16 and 128 characters."
  }
}

# EKS Configuration
variable "eks_min_size" {
  description = "Minimum number of EKS worker nodes"
  type        = number
  default     = 2

  validation {
    condition     = var.eks_min_size >= 1
    error_message = "EKS minimum size must be at least 1."
  }
}

variable "eks_max_size" {
  description = "Maximum number of EKS worker nodes"
  type        = number
  default     = 20

  validation {
    condition     = var.eks_max_size >= var.eks_min_size
    error_message = "EKS maximum size must be greater than or equal to minimum size."
  }
}

variable "eks_desired_size" {
  description = "Desired number of EKS worker nodes"
  type        = number
  default     = 3

  validation {
    condition     = var.eks_desired_size >= var.eks_min_size && var.eks_desired_size <= var.eks_max_size
    error_message = "EKS desired size must be between minimum and maximum size."
  }
}

variable "eks_instance_types" {
  description = "List of EC2 instance types for EKS worker nodes"
  type        = list(string)
  default     = ["t3a.large", "t3a.xlarge"]

  validation {
    condition     = length(var.eks_instance_types) > 0
    error_message = "At least one instance type must be specified."
  }
}

# CloudFlare Configuration
variable "cloudflare_api_token" {
  description = "CloudFlare API token for DNS management"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "CloudFlare Zone ID for the domain"
  type        = string
  sensitive   = true
}

# Monitoring Configuration
variable "enable_monitoring" {
  description = "Enable CloudWatch monitoring and logging"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30

  validation {
    condition = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

# Backup Configuration
variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 90

  validation {
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 365
    error_message = "Backup retention must be between 7 and 365 days."
  }
}

# Security Configuration
variable "enable_encryption" {
  description = "Enable encryption at rest for all services"
  type        = bool
  default     = true
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for critical resources"
  type        = bool
  default     = true
}

# SSL/TLS Configuration
variable "ssl_certificate_arn" {
  description = "ARN of the SSL certificate for HTTPS"
  type        = string
  default     = ""
}

# Cost Optimization
variable "use_spot_instances" {
  description = "Use Spot instances for cost optimization"
  type        = bool
  default     = false
}

variable "enable_autoscaling" {
  description = "Enable auto-scaling for EKS nodes"
  type        = bool
  default     = true
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid IPv4 CIDR block."
  }
}

variable "availability_zones_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 3

  validation {
    condition     = var.availability_zones_count >= 2 && var.availability_zones_count <= 6
    error_message = "Availability zones count must be between 2 and 6."
  }
}

# Application Configuration
variable "app_replicas" {
  description = "Number of application replicas to run"
  type        = number
  default     = 3

  validation {
    condition     = var.app_replicas >= 1 && var.app_replicas <= 50
    error_message = "App replicas must be between 1 and 50."
  }
}

variable "app_cpu_request" {
  description = "CPU request for application pods"
  type        = string
  default     = "500m"
}

variable "app_memory_request" {
  description = "Memory request for application pods"
  type        = string
  default     = "512Mi"
}

variable "app_cpu_limit" {
  description = "CPU limit for application pods"
  type        = string
  default     = "2000m"
}

variable "app_memory_limit" {
  description = "Memory limit for application pods"
  type        = string
  default     = "2Gi"
}

# Feature Flags
variable "enable_redis_cluster" {
  description = "Enable Redis cluster mode"
  type        = bool
  default     = true
}

variable "enable_multi_az" {
  description = "Enable Multi-AZ deployment for RDS"
  type        = bool
  default     = true
}

variable "enable_performance_insights" {
  description = "Enable Performance Insights for RDS"
  type        = bool
  default     = true
}

variable "enable_enhanced_monitoring" {
  description = "Enable Enhanced Monitoring for RDS"
  type        = bool
  default     = true
}

# Tags
variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "AgentOS"
}

variable "team_name" {
  description = "Name of the team responsible for this infrastructure"
  type        = string
  default     = "AgentOS-Platform"
}

variable "cost_center" {
  description = "Cost center for billing"
  type        = string
  default     = "Engineering"
}

# External Dependencies
variable "external_secrets" {
  description = "Map of external secrets to create"
  type = map(object({
    description = string
    value       = string
  }))
  default = {}
  sensitive = true
}

# Disaster Recovery
variable "enable_cross_region_backup" {
  description = "Enable cross-region backup replication"
  type        = bool
  default     = false
}

variable "backup_region" {
  description = "Region for cross-region backup replication"
  type        = string
  default     = "us-west-2"
}

# Compliance
variable "enable_compliance_monitoring" {
  description = "Enable AWS Config for compliance monitoring"
  type        = bool
  default     = true
}

variable "enable_cloudtrail" {
  description = "Enable CloudTrail for audit logging"
  type        = bool
  default     = true
}