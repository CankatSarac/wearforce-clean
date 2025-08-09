# WearForce-Clean Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the WearForce-Clean platform to production environments using our automated CI/CD pipeline, Infrastructure as Code (IaC), and container orchestration.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [CI/CD Pipeline](#cicd-pipeline)
4. [Deployment Strategies](#deployment-strategies)
5. [Monitoring and Observability](#monitoring-and-observability)
6. [Security and Compliance](#security-and-compliance)
7. [Disaster Recovery](#disaster-recovery)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- **AWS CLI v2** - AWS command line interface
- **kubectl v1.29+** - Kubernetes command line tool
- **Helm v3.14+** - Kubernetes package manager
- **Terraform v1.7+** - Infrastructure as Code tool
- **Docker 24+** - Container runtime
- **Git** - Version control system

### AWS Account Setup

1. **IAM Roles and Policies**
   ```bash
   # Create deployment service account
   aws iam create-role --role-name WearForce-Clean-DeploymentRole --assume-role-policy-document file://deployment-role-policy.json
   
   # Attach necessary policies
   aws iam attach-role-policy --role-name WearForce-Clean-DeploymentRole --policy-arn arn:aws:iam::aws:policy/AmazonEKSClusterPolicy
   aws iam attach-role-policy --role-name WearForce-Clean-DeploymentRole --policy-arn arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
   aws iam attach-role-policy --role-name WearForce-Clean-DeploymentRole --policy-arn arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
   ```

2. **S3 Buckets**
   - `wearforce-clean-terraform-state` - Terraform state storage
   - `wearforce-clean-production-backups` - Production backups
   - `wearforce-clean-dr-site-backups` - Disaster recovery backups
   - `wearforce-clean-app-storage` - Application file storage

3. **Secrets Management**
   ```bash
   # Store secrets in AWS Secrets Manager
   aws secretsmanager create-secret --name "wearforce-clean/production/database" --secret-string '{"username":"wearforce-clean","password":"SECURE_PASSWORD"}'
   aws secretsmanager create-secret --name "wearforce-clean/production/redis" --secret-string '{"password":"REDIS_PASSWORD"}'
   aws secretsmanager create-secret --name "wearforce-clean/production/api-keys" --secret-string '{"openai":"sk-...","huggingface":"hf_..."}'
   ```

### GitHub Repository Setup

1. **Repository Secrets**
   ```
   AWS_ACCESS_KEY_ID=<deployment-role-access-key>
   AWS_SECRET_ACCESS_KEY=<deployment-role-secret-key>
   DATABASE_URL_PROD=postgresql://username:password@hostname:5432/database
   CODECOV_TOKEN=<codecov-token>
   SLACK_WEBHOOK_URL=<slack-webhook-for-notifications>
   PAGERDUTY_SERVICE_KEY=<pagerduty-integration-key>
   ```

2. **Environment Protection Rules**
   - `production` environment requires manual approval
   - `staging` environment allows automatic deployment from develop branch
   - `infrastructure` environment requires manual approval for changes

## Infrastructure Setup

### 1. Network Infrastructure

Deploy the VPC, subnets, and networking components:

```bash
cd infrastructure/terraform/environments/production
terraform init
terraform plan -var-file="production.tfvars"
terraform apply -var-file="production.tfvars"
```

**Key Network Components:**
- VPC with public/private/database subnets across 3 AZs
- NAT Gateways for private subnet internet access
- VPC Endpoints for AWS services (S3, ECR, ELB)
- Network ACLs and Security Groups
- VPC Flow Logs for monitoring

### 2. EKS Cluster

Deploy the Kubernetes cluster:

```bash
cd infrastructure/terraform/modules/eks
terraform plan -var="cluster_name=wearforce-clean-production"
terraform apply
```

**Cluster Configuration:**
- Kubernetes v1.29
- Managed node groups with auto-scaling
- GPU node groups for AI services
- Fargate profiles for serverless workloads
- Add-ons: CoreDNS, kube-proxy, VPC CNI, EBS CSI

### 3. Database Infrastructure

Deploy RDS PostgreSQL and ElastiCache Redis:

```bash
# PostgreSQL with read replicas
terraform apply -target=module.rds

# Redis with clustering
terraform apply -target=module.elasticache
```

**Database Features:**
- Multi-AZ deployment for high availability
- Automated backups and point-in-time recovery
- Encryption at rest and in transit
- Performance monitoring with CloudWatch

## CI/CD Pipeline

### Pipeline Stages

1. **Code Quality & Testing**
   - Static code analysis (SonarQube, CodeQL)
   - Unit and integration tests
   - Security scanning (Semgrep, Bandit, Gosec)
   - Dependency vulnerability checks

2. **Build & Package**
   - Multi-architecture Docker builds (linux/amd64, linux/arm64)
   - Container vulnerability scanning (Trivy, Grype)
   - Image signing with Cosign
   - SBOM generation with Syft

3. **Infrastructure Provisioning**
   - Terraform plan and apply
   - Infrastructure security scanning (Checkov)
   - Resource tagging and cost optimization

4. **Database Migration**
   - Backup creation before migration
   - Migration testing on copy
   - Production migration with rollback capability

5. **Application Deployment**
   - Canary deployment (5% → 25% → 50% → 100%)
   - Health checks and monitoring
   - Automated rollback on failure

### Triggering Deployments

**Automatic Deployment:**
```bash
# Staging deployment
git push origin develop

# Production deployment
git tag v1.2.3
git push origin v1.2.3
```

**Manual Deployment:**
```bash
# Via GitHub Actions UI
# Navigate to Actions → Production Deployment Pipeline → Run workflow
```

### Pipeline Monitoring

Monitor pipeline execution:
- GitHub Actions UI for real-time logs
- Slack notifications for status updates
- PagerDuty alerts for failures
- Grafana dashboards for deployment metrics

## Deployment Strategies

### Canary Deployment (Recommended)

**Advantages:**
- Gradual traffic shift minimizes risk
- Real-time monitoring of new version
- Automatic rollback capability
- Zero-downtime deployment

**Process:**
1. Deploy new version alongside current (5% traffic)
2. Monitor metrics for 3 minutes
3. Gradually increase traffic (25% → 50% → 100%)
4. Complete rollout or rollback based on metrics

**Configuration:**
```yaml
# values-production.yaml
global:
  deployment:
    strategy: canary
    canary:
      enabled: true
      steps:
        - weight: 5
          pause: 180s
        - weight: 25
          pause: 180s
        - weight: 50
          pause: 300s
```

### Blue-Green Deployment

**Use Cases:**
- Database schema changes
- Major version upgrades
- Critical infrastructure updates

**Process:**
1. Deploy new version to "green" environment
2. Run comprehensive tests on green
3. Switch traffic from blue to green
4. Keep blue environment for quick rollback

### Rolling Update

**Use Cases:**
- Configuration changes
- Minor updates
- Non-critical services

**Configuration:**
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 25%
    maxUnavailable: 25%
```

## Monitoring and Observability

### Metrics Collection

**Prometheus Stack:**
- Application metrics (custom and standard)
- Infrastructure metrics (nodes, pods, containers)
- Business metrics (user activity, API usage)

**Key Metrics:**
- **SLIs (Service Level Indicators):**
  - Request rate: `wearforce-clean:http_requests_per_second`
  - Error rate: `wearforce-clean:http_error_rate`
  - Response time: `wearforce-clean:http_request_duration_99p`
  - Availability: `wearforce-clean:service_availability`

- **AI Service Metrics:**
  - Token generation rate: `wearforce-clean:llm_tokens_per_second`
  - GPU utilization: `wearforce-clean:gpu_utilization_avg`
  - Model inference time: `wearforce-clean:model_inference_duration`

### Logging

**Centralized Logging with ELK Stack:**
- Filebeat for log collection
- Elasticsearch for storage and indexing
- Kibana for visualization and search

**Log Levels:**
- `ERROR`: System errors and failures
- `WARN`: Potential issues and degraded performance
- `INFO`: Normal operation events
- `DEBUG`: Detailed diagnostic information

### Distributed Tracing

**Jaeger Integration:**
- End-to-end request tracing
- Performance bottleneck identification
- Service dependency mapping
- Error propagation tracking

### Alerting

**Alert Hierarchy:**
- **Critical**: Service down, high error rate (>5%)
- **Warning**: High response time (>5s), resource exhaustion
- **Info**: Deployment events, scaling activities

**Notification Channels:**
- Slack for team notifications
- PagerDuty for on-call escalation
- Email for non-urgent alerts

## Security and Compliance

### Security Scanning

**Automated Security Scans:**
- Daily code security analysis
- Container vulnerability scanning
- Infrastructure configuration validation
- Dependency vulnerability checks
- Secrets detection

**Compliance Frameworks:**
- SOC 2 Type II
- GDPR data protection
- PCI DSS (if handling payments)
- CIS Kubernetes Benchmarks

### Access Control

**RBAC Implementation:**
```yaml
# Production access roles
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: wearforce-clean-admin
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
---
# Developer read-only access
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: wearforce-clean-developer
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps"]
  verbs: ["get", "list", "watch"]
```

### Network Security

**Security Measures:**
- Network policies for pod-to-pod communication
- Service mesh (Istio) for encrypted inter-service communication
- WAF protection at ingress level
- VPC endpoints for AWS service communication

## Disaster Recovery

### Backup Strategy

**Automated Daily Backups:**
- PostgreSQL database dumps
- Redis snapshots
- Kubernetes resource definitions
- Application configuration
- File storage synchronization

**Retention Policy:**
- Daily backups: 30 days
- Weekly backups: 12 weeks
- Monthly backups: 12 months

### Recovery Procedures

**RTO/RPO Targets:**
- Recovery Time Objective (RTO): 4 hours
- Recovery Point Objective (RPO): 1 hour

**Recovery Steps:**
1. Assess the scope of the disaster
2. Deploy infrastructure in DR region
3. Restore database from latest backup
4. Deploy application services
5. Update DNS to point to DR site
6. Verify system functionality

### DR Testing

**Monthly DR Tests:**
- Automated infrastructure deployment
- Database restore verification
- Application deployment testing
- End-to-end functionality validation

## Troubleshooting

### Common Issues

#### Deployment Failures

**Pod CrashLoopBackOff:**
```bash
# Check pod logs
kubectl logs -f <pod-name> -n production

# Check pod events
kubectl describe pod <pod-name> -n production

# Check resource constraints
kubectl top pod <pod-name> -n production
```

**Image Pull Errors:**
```bash
# Check image registry access
kubectl get events -n production | grep Failed

# Verify image pull secrets
kubectl get secrets -n production | grep regcred

# Check image existence
docker manifest inspect <image-url>
```

#### Database Connectivity Issues

**Connection Pool Exhaustion:**
```bash
# Check active connections
kubectl exec -it <database-pod> -- psql -c "SELECT count(*) FROM pg_stat_activity;"

# Adjust connection pool settings
kubectl edit configmap database-config -n production
```

**High CPU/Memory Usage:**
```bash
# Check database metrics
kubectl top pod -l app=postgresql -n production

# Review slow queries
kubectl exec -it <database-pod> -- psql -c "SELECT query, calls, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

#### Performance Issues

**High Response Times:**
```bash
# Check service metrics in Grafana
# URL: https://grafana.wearforce-clean.io/d/wearforce-clean-services

# Analyze distributed traces
# URL: https://jaeger.wearforce-clean.io

# Check resource utilization
kubectl top nodes
kubectl top pods --all-namespaces
```

### Emergency Procedures

#### Service Rollback

**Quick Rollback:**
```bash
# Helm rollback
helm rollback wearforce-clean -n production

# Check rollback status
kubectl rollout status deployment/wearforce-clean-gateway -n production
```

**Database Rollback:**
```bash
# Stop application to prevent data corruption
kubectl scale deployment --replicas=0 -n production

# Restore from backup
aws s3 cp s3://wearforce-clean-production-backups/postgresql/latest.sql ./
pg_restore -h $DB_HOST -U $DB_USER -d wearforce-clean ./latest.sql

# Restart application
kubectl scale deployment --replicas=3 -n production
```

#### Scaling During High Load

**Horizontal Scaling:**
```bash
# Scale specific services
kubectl scale deployment wearforce-clean-gateway --replicas=10 -n production
kubectl scale deployment wearforce-clean-llm --replicas=5 -n production

# Enable cluster autoscaling
kubectl patch hpa wearforce-clean-gateway -n production -p '{"spec":{"maxReplicas":15}}'
```

**Vertical Scaling:**
```bash
# Update resource limits
kubectl patch deployment wearforce-clean-gateway -n production -p '{"spec":{"template":{"spec":{"containers":[{"name":"gateway","resources":{"limits":{"cpu":"4000m","memory":"8Gi"}}}]}}}}'
```

### Support Contacts

- **Platform Team**: platform-team@wearforce-clean.io
- **DevOps Team**: devops@wearforce-clean.io
- **On-Call Engineer**: +1-555-ONCALL (Slack: @oncall)
- **Security Team**: security@wearforce-clean.io

### Useful Links

- **Production Dashboard**: https://grafana.wearforce-clean.io/d/production-overview
- **Log Search**: https://kibana.wearforce-clean.io
- **Distributed Tracing**: https://jaeger.wearforce-clean.io
- **CI/CD Pipeline**: https://github.com/wearforce-clean/wearforce-clean/actions
- **Infrastructure Repository**: https://github.com/wearforce-clean/infrastructure
- **Runbooks**: https://github.com/wearforce-clean/wearforce-clean/tree/main/docs/runbooks

---

## Conclusion

This deployment guide provides a comprehensive overview of the WearForce-Clean production deployment process. For detailed service-specific information, refer to the individual service documentation in the `/docs` directory.

Regular updates to this guide ensure it remains current with platform changes and operational learnings.

**Last Updated**: 2025-01-07  
**Version**: 1.0.0  
**Maintainer**: Platform Engineering Team