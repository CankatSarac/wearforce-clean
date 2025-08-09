# Production Environment Terraform Configuration

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
  }

  backend "s3" {
    bucket         = "wearforce-clean-terraform-state"
    key            = "environments/production/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "wearforce-clean-terraform-locks"
  }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment   = var.environment
      Project       = "WearForce"
      ManagedBy     = "Terraform"
      Owner         = "Platform Team"
      CostCenter    = "Production"
      BackupPolicy  = "Required"
      Compliance    = "SOC2"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Local values
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  
  # VPC CIDR calculation
  vpc_cidr = "10.0.0.0/16"
  azs      = slice(data.aws_availability_zones.available.names, 0, 3)

  # Common tags
  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }

  # Node groups configuration
  node_groups = {
    system = {
      capacity_type               = "ON_DEMAND"
      instance_types             = ["m6i.large", "m6i.xlarge"]
      ami_type                   = "AL2_x86_64"
      disk_size                  = 100
      desired_size               = 3
      max_size                   = 6
      min_size                   = 3
      max_unavailable_percentage = 25
      labels = {
        role = "system"
        tier = "infrastructure"
      }
      taints = []
    }
    
    general = {
      capacity_type               = "SPOT"
      instance_types             = ["m6i.large", "m6i.xlarge", "m5.large", "m5.xlarge"]
      ami_type                   = "AL2_x86_64"
      disk_size                  = 100
      desired_size               = 5
      max_size                   = 20
      min_size                   = 5
      max_unavailable_percentage = 50
      labels = {
        role = "general"
        tier = "application"
      }
      taints = []
    }

    gpu = {
      capacity_type               = "ON_DEMAND"
      instance_types             = ["g5.xlarge", "g5.2xlarge"]
      ami_type                   = "AL2_x86_64_GPU"
      disk_size                  = 200
      desired_size               = 2
      max_size                   = 8
      min_size                   = 2
      max_unavailable_percentage = 25
      labels = {
        role = "gpu"
        tier = "ai-services"
        "nvidia.com/gpu" = "present"
      }
      taints = [
        {
          key    = "nvidia.com/gpu"
          value  = "present"
          effect = "NO_SCHEDULE"
        }
      ]
    }

    memory_optimized = {
      capacity_type               = "ON_DEMAND"
      instance_types             = ["r6i.xlarge", "r6i.2xlarge"]
      ami_type                   = "AL2_x86_64"
      disk_size                  = 100
      desired_size               = 2
      max_size                   = 6
      min_size                   = 2
      max_unavailable_percentage = 25
      labels = {
        role = "memory-optimized"
        tier = "database"
      }
      taints = [
        {
          key    = "database"
          value  = "memory-optimized"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }

  # Cluster addons
  cluster_addons = {
    coredns = {
      addon_version            = "v1.11.1-eksbuild.4"
      resolve_conflicts        = "OVERWRITE"
      service_account_role_arn = null
    }
    kube-proxy = {
      addon_version            = "v1.29.0-eksbuild.1"
      resolve_conflicts        = "OVERWRITE"
      service_account_role_arn = null
    }
    vpc-cni = {
      addon_version            = "v1.16.0-eksbuild.1"
      resolve_conflicts        = "OVERWRITE"
      service_account_role_arn = null
    }
    aws-ebs-csi-driver = {
      addon_version            = "v1.25.0-eksbuild.1"
      resolve_conflicts        = "OVERWRITE"
      service_account_role_arn = module.eks.ebs_csi_driver_role_arn
    }
  }
}

# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  name = local.name_prefix
  cidr = local.vpc_cidr

  azs              = local.azs
  private_subnets  = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k)]
  public_subnets   = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 10)]
  database_subnets = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 20)]

  enable_nat_gateway     = true
  single_nat_gateway     = false
  enable_vpn_gateway     = false
  enable_dns_hostnames   = true
  enable_dns_support     = true
  enable_flow_log        = true
  flow_log_destination_type = "cloud-watch-logs"

  # Kubernetes tags required for EKS
  public_subnet_tags = {
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${local.name_prefix}" = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${local.name_prefix}" = "shared"
  }

  database_subnet_tags = {
    "kubernetes.io/role/database" = "1"
  }

  tags = local.common_tags
}

# EKS Cluster
module "eks" {
  source = "../../modules/eks"

  cluster_name       = local.name_prefix
  kubernetes_version = var.kubernetes_version
  environment        = var.environment

  vpc_id                  = module.vpc.vpc_id
  subnet_ids              = module.vpc.private_subnets
  private_subnet_ids      = module.vpc.private_subnets
  endpoint_private_access = true
  endpoint_public_access  = true
  public_access_cidrs     = var.cluster_public_access_cidrs

  node_groups     = local.node_groups
  cluster_addons  = local.cluster_addons

  enable_irsa                          = true
  enable_aws_load_balancer_controller  = true
  enable_ebs_csi_driver               = true

  tags = local.common_tags
}

# RDS Database
module "database" {
  source = "../../modules/rds"

  identifier = "${local.name_prefix}-primary"
  
  engine         = "postgres"
  engine_version = "15.5"
  instance_class = "db.r6g.2xlarge"
  
  allocated_storage     = 1000
  max_allocated_storage = 5000
  storage_type         = "gp3"
  storage_encrypted    = true
  
  db_name  = "wearforce-clean"
  username = "wearforce-clean_admin"
  port     = 5432
  
  vpc_security_group_ids = [module.database_security_group.security_group_id]
  db_subnet_group_name   = module.vpc.database_subnet_group
  
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "Sun:04:00-Sun:05:00"
  
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn
  
  performance_insights_enabled = true
  performance_insights_retention_period = 7
  
  enabled_cloudwatch_logs_exports = ["postgresql"]
  
  # Read replicas
  create_read_replica = true
  read_replica_count  = 2
  
  tags = local.common_tags
}

# ElastiCache Redis
module "redis" {
  source = "../../modules/elasticache"

  cluster_id = "${local.name_prefix}-redis"
  
  engine         = "redis"
  engine_version = "7.0"
  node_type      = "cache.r7g.xlarge"
  
  num_cache_clusters = 3
  parameter_group_name = "default.redis7.cluster.on"
  
  port = 6379
  
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [module.redis_security_group.security_group_id]
  
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled         = true
  
  snapshot_retention_limit = 10
  snapshot_window         = "03:00-05:00"
  
  tags = local.common_tags
}

# S3 Buckets for application data
module "s3_buckets" {
  source = "../../modules/s3"

  buckets = {
    "${local.name_prefix}-artifacts" = {
      versioning_enabled = true
      encryption_enabled = true
      public_access_block = true
      lifecycle_rules = [
        {
          enabled = true
          id      = "cleanup_old_versions"
          noncurrent_version_expiration = {
            days = 90
          }
        }
      ]
    }
    
    "${local.name_prefix}-backups" = {
      versioning_enabled = true
      encryption_enabled = true
      public_access_block = true
      lifecycle_rules = [
        {
          enabled = true
          id      = "backup_retention"
          expiration = {
            days = 2555  # 7 years
          }
        }
      ]
    }
    
    "${local.name_prefix}-logs" = {
      versioning_enabled = false
      encryption_enabled = true
      public_access_block = true
      lifecycle_rules = [
        {
          enabled = true
          id      = "log_retention"
          expiration = {
            days = 365  # 1 year
          }
        }
      ]
    }
  }

  tags = local.common_tags
}

# Security Groups
module "database_security_group" {
  source = "../../modules/security_group"

  name        = "${local.name_prefix}-database"
  description = "Security group for RDS database"
  vpc_id      = module.vpc.vpc_id

  ingress_rules = [
    {
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      cidr_blocks = module.vpc.private_subnets_cidr_blocks
    }
  ]

  egress_rules = []

  tags = local.common_tags
}

module "redis_security_group" {
  source = "../../modules/security_group"

  name        = "${local.name_prefix}-redis"
  description = "Security group for ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id

  ingress_rules = [
    {
      from_port   = 6379
      to_port     = 6379
      protocol    = "tcp"
      cidr_blocks = module.vpc.private_subnets_cidr_blocks
    }
  ]

  egress_rules = []

  tags = local.common_tags
}

# ElastiCache subnet group
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name_prefix}-redis"
  subnet_ids = module.vpc.private_subnets

  tags = local.common_tags
}

# RDS Enhanced Monitoring Role
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${local.name_prefix}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "application_logs" {
  for_each = toset([
    "/aws/eks/${local.name_prefix}/cluster",
    "/wearforce-clean/gateway",
    "/wearforce-clean/ai-services",
    "/wearforce-clean/business-services",
    "/wearforce-clean/monitoring"
  ])

  name              = each.value
  retention_in_days = 30
  kms_key_id        = aws_kms_key.cloudwatch.arn

  tags = local.common_tags
}

# KMS Keys
resource "aws_kms_key" "cloudwatch" {
  description             = "KMS key for CloudWatch Logs encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Principal = {
          Service = "logs.us-west-2.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "cloudwatch" {
  name          = "alias/${local.name_prefix}-cloudwatch"
  target_key_id = aws_kms_key.cloudwatch.key_id
}