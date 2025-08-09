# WearForce-Clean Incident Response Runbook

## Overview

This runbook provides step-by-step procedures for responding to incidents in the WearForce-Clean production environment. It covers identification, classification, response, and resolution of various types of incidents.

## Incident Classification

### Severity Levels

#### SEV 1 - Critical
- **Impact**: Complete service outage, data loss, security breach
- **Response Time**: 15 minutes
- **Resolution Target**: 4 hours
- **Escalation**: Immediate to senior engineers and management

#### SEV 2 - High
- **Impact**: Significant degradation, partial outage, critical feature unavailable
- **Response Time**: 30 minutes
- **Resolution Target**: 8 hours
- **Escalation**: Senior engineer within 1 hour

#### SEV 3 - Medium
- **Impact**: Minor degradation, non-critical feature impact
- **Response Time**: 2 hours
- **Resolution Target**: 24 hours
- **Escalation**: Team lead notification

#### SEV 4 - Low
- **Impact**: Cosmetic issues, minor bugs
- **Response Time**: 1 business day
- **Resolution Target**: 5 business days
- **Escalation**: Standard team process

## Incident Response Process

### 1. Detection and Alert

**Alert Sources:**
- Monitoring systems (Prometheus/Grafana)
- User reports
- Automated health checks
- Third-party service alerts

**Initial Response (First 5 minutes):**
1. Acknowledge the alert
2. Open incident channel in Slack: `#incident-<timestamp>`
3. Page the on-call engineer if SEV 1 or SEV 2
4. Create incident record in incident management system

### 2. Assessment and Classification

**Information Gathering:**
```bash
# Quick system health check
kubectl get pods --all-namespaces | grep -E "(Error|CrashLoopBackOff|Pending)"
kubectl top nodes
kubectl get events --sort-by='.lastTimestamp' | tail -20

# Check application logs
kubectl logs -f deployment/wearforce-clean-gateway -n production --tail=100
kubectl logs -f deployment/wearforce-clean-llm -n production --tail=100

# Review monitoring dashboards
# - Overall system health: https://grafana.wearforce-clean.io/d/system-overview
# - Application metrics: https://grafana.wearforce-clean.io/d/application-metrics
# - Infrastructure metrics: https://grafana.wearforce-clean.io/d/infrastructure-metrics
```

**Classification Criteria:**
- User impact assessment
- Service availability metrics
- Data integrity status
- Security implications

### 3. Response Team Assembly

**SEV 1 Response Team:**
- Incident Commander (Senior Engineer)
- Technical Lead
- Platform Engineer
- Security Engineer (if security-related)
- Communications Lead

**Team Roles:**
- **Incident Commander**: Overall incident coordination
- **Technical Lead**: Technical troubleshooting and resolution
- **Communications**: Internal/external communications
- **Scribe**: Document timeline and actions

## Common Incident Scenarios

### Service Outage

#### Symptoms
- Multiple 503/504 errors
- High response times (>10 seconds)
- Failed health checks
- User reports of unavailability

#### Investigation Steps
```bash
# 1. Check pod status
kubectl get pods -n production -o wide
kubectl describe pods -l app=wearforce-clean-gateway -n production

# 2. Check service endpoints
kubectl get endpoints -n production
kubectl get services -n production

# 3. Check ingress configuration
kubectl get ingress -n production
kubectl describe ingress wearforce-clean-ingress -n production

# 4. Check HPA status
kubectl get hpa -n production
kubectl describe hpa wearforce-clean-gateway -n production

# 5. Check resource utilization
kubectl top pods -n production
kubectl top nodes
```

#### Resolution Actions
1. **Scale up if resource constrained:**
   ```bash
   kubectl scale deployment wearforce-clean-gateway --replicas=10 -n production
   ```

2. **Restart failing pods:**
   ```bash
   kubectl rollout restart deployment/wearforce-clean-gateway -n production
   ```

3. **Check recent deployments:**
   ```bash
   kubectl rollout history deployment/wearforce-clean-gateway -n production
   # If recent deployment is causing issues:
   kubectl rollout undo deployment/wearforce-clean-gateway -n production
   ```

### Database Connectivity Issues

#### Symptoms
- Database connection timeouts
- Connection pool exhaustion errors
- Transaction rollback errors
- Slow query performance

#### Investigation Steps
```bash
# 1. Check database pod status
kubectl get pods -l app=postgresql -n production
kubectl logs -f deployment/postgresql -n production

# 2. Check connection metrics
kubectl exec -it postgresql-0 -n production -- psql -c "
SELECT count(*) as active_connections,
       max_conn,
       max_conn - count(*) as remaining_connections
FROM pg_stat_activity,
     (SELECT setting::int as max_conn FROM pg_settings WHERE name = 'max_connections') max_conn
GROUP BY max_conn;"

# 3. Check slow queries
kubectl exec -it postgresql-0 -n production -- psql -c "
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;"

# 4. Check database locks
kubectl exec -it postgresql-0 -n production -- psql -c "
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON (blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation)
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;"
```

#### Resolution Actions
1. **Kill long-running queries:**
   ```bash
   kubectl exec -it postgresql-0 -n production -- psql -c "
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes';"
   ```

2. **Scale database read replicas:**
   ```bash
   kubectl scale statefulset postgresql-read --replicas=3 -n production
   ```

3. **Restart application pods to reset connection pools:**
   ```bash
   kubectl rollout restart deployment/wearforce-clean-gateway -n production
   ```

### High Memory Usage

#### Symptoms
- OOMKilled pods
- High memory utilization metrics
- Slow application performance
- Memory leak alerts

#### Investigation Steps
```bash
# 1. Check pod memory usage
kubectl top pods -n production --sort-by=memory

# 2. Check node memory usage
kubectl top nodes

# 3. Describe nodes for memory pressure
kubectl describe nodes | grep -A 5 "Memory pressure"

# 4. Check pod resource limits
kubectl describe pod <high-memory-pod> -n production | grep -A 10 "Limits:"

# 5. Review memory metrics in Grafana
# Navigate to: https://grafana.wearforce-clean.io/d/memory-usage
```

#### Resolution Actions
1. **Immediate relief - restart high-memory pods:**
   ```bash
   kubectl delete pod <high-memory-pod> -n production
   ```

2. **Scale horizontally to distribute load:**
   ```bash
   kubectl scale deployment <app> --replicas=5 -n production
   ```

3. **Increase memory limits (temporary fix):**
   ```bash
   kubectl patch deployment <app> -n production -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
   ```

### AI Service Performance Issues

#### Symptoms
- High GPU utilization (>95%)
- Model inference timeouts
- Queue backlog in AI services
- Slow response times for AI features

#### Investigation Steps
```bash
# 1. Check GPU utilization
kubectl exec -it <llm-pod> -n production -- nvidia-smi

# 2. Check AI service metrics
curl -s http://<llm-service>:9090/metrics | grep -E "(gpu_utilization|model_inference|queue_length)"

# 3. Check model loading status
kubectl logs -f deployment/wearforce-clean-llm -n production | grep -E "(model|loading|error)"

# 4. Check resource requests vs limits
kubectl describe pod <llm-pod> -n production | grep -A 15 "Requests:"
```

#### Resolution Actions
1. **Scale AI services:**
   ```bash
   kubectl scale deployment wearforce-clean-llm --replicas=3 -n production
   ```

2. **Restart AI services to clear memory leaks:**
   ```bash
   kubectl rollout restart deployment/wearforce-clean-llm -n production
   ```

3. **Adjust batch size for better throughput:**
   ```bash
   kubectl patch configmap llm-config -n production -p '{"data":{"BATCH_SIZE":"16"}}'
   kubectl rollout restart deployment/wearforce-clean-llm -n production
   ```

### Security Incidents

#### Symptoms
- Suspicious login attempts
- Unusual API traffic patterns
- Security alerts from scanning tools
- Unauthorized access attempts

#### Investigation Steps
```bash
# 1. Check access logs
kubectl logs -f deployment/wearforce-clean-gateway -n production | grep -E "(401|403|suspicious|attack)"

# 2. Check authentication failures
kubectl exec -it postgresql-0 -n production -- psql -c "
SELECT username, COUNT(*) as failed_attempts, MAX(created_at) as last_attempt
FROM auth_logs
WHERE status = 'failed' AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY username
ORDER BY failed_attempts DESC;"

# 3. Review security scanning results
aws securityhub get-findings --region us-west-2 --filters '{"RecordState":[{"Value":"ACTIVE","Comparison":"EQUALS"}],"SeverityLabel":[{"Value":"HIGH","Comparison":"EQUALS"}]}' --max-results 20

# 4. Check network traffic
kubectl get networkpolicies -n production
```

#### Response Actions
1. **Block suspicious IPs:**
   ```bash
   kubectl apply -f - <<EOF
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: block-suspicious-ips
     namespace: production
   spec:
     podSelector: {}
     policyTypes:
     - Ingress
     ingress:
     - from:
       - ipBlock:
           cidr: 0.0.0.0/0
           except:
           - <suspicious-ip>/32
   EOF
   ```

2. **Force logout all users (if compromised):**
   ```bash
   kubectl exec -it redis-master-0 -n production -- redis-cli FLUSHDB
   ```

3. **Rotate secrets:**
   ```bash
   # Update database passwords
   aws secretsmanager put-secret-value --secret-id wearforce-clean/production/database --secret-string '{"username":"wearforce-clean","password":"NEW_SECURE_PASSWORD"}'
   
   # Restart applications to pick up new secrets
   kubectl rollout restart deployment/wearforce-clean-gateway -n production
   ```

## Communication Templates

### Internal Communication

**Incident Declaration (Slack):**
```
🚨 INCIDENT DECLARED - SEV [1/2/3/4]

**Summary:** Brief description of the issue
**Impact:** What's affected and how many users
**Started:** <timestamp>
**Incident Commander:** @username
**Slack Channel:** #incident-<timestamp>

Current status: Investigating...
```

**Status Updates:**
```
⏰ INCIDENT UPDATE - <timestamp>

**Current Status:** [Investigating/Identified/Implementing Fix/Resolved]
**Actions Taken:**
- Action 1
- Action 2

**Next Steps:**
- Next action with ETA

**ETA to Resolution:** [If known]
```

### External Communication

**Service Status Page Update:**
```
[INVESTIGATING] We are currently investigating reports of [issue description]. 
We will provide updates as more information becomes available.

Posted at: <timestamp>
```

**Resolution Announcement:**
```
[RESOLVED] The issue affecting [service/feature] has been resolved. 
All services are now operating normally.

Summary: [Brief explanation of what happened and what was done]
Posted at: <timestamp>
```

## Post-Incident Activities

### Incident Review

**Timeline Documentation:**
1. Incident detection and alert
2. Response team assembly
3. Investigation and diagnosis
4. Resolution implementation
5. Service restoration
6. Post-incident activities

**Impact Assessment:**
- User impact duration and scope
- Revenue/business impact
- SLA/SLO impact
- Customer communications sent

### Post-Mortem Process

**Post-Mortem Meeting (within 48 hours):**
1. Timeline review
2. Root cause analysis
3. Response effectiveness evaluation
4. Lessons learned identification
5. Action items assignment

**Post-Mortem Document Template:**
```markdown
# Post-Mortem: [Brief Description]

## Summary
- **Date:** [Incident date]
- **Duration:** [How long the incident lasted]
- **Impact:** [Who/what was affected]
- **Root Cause:** [What caused the incident]

## Timeline
[Detailed timeline of events]

## Root Cause Analysis
[Deep dive into why this happened]

## What Went Well
[Things that worked during the response]

## What Didn't Go Well
[Areas for improvement]

## Action Items
[Specific tasks to prevent recurrence]

## Lessons Learned
[Key takeaways for the team]
```

### Follow-up Actions

**Immediate (0-7 days):**
- Implement quick fixes
- Update monitoring/alerting
- Improve documentation

**Short-term (1-4 weeks):**
- Code changes to prevent recurrence
- Process improvements
- Tool enhancements

**Long-term (1-3 months):**
- Architectural changes
- Infrastructure improvements
- Team training and development

## Contacts and Escalation

### On-Call Rotation
- **Primary On-Call:** Platform Engineering team
- **Secondary On-Call:** Senior Engineering team
- **Escalation:** Engineering Manager → VP Engineering → CTO

### External Vendors
- **AWS Support:** Enterprise Support Case
- **Database Expert:** consultant@dbexpert.com
- **Security Consultant:** security@securityfirm.com

### Emergency Contacts
- **Platform Team Lead:** +1-555-PLATFORM
- **Engineering Manager:** +1-555-ENGMGR
- **CTO:** +1-555-CTO (SEV 1 only)

## Tools and Resources

### Monitoring and Alerting
- **Grafana:** https://grafana.wearforce-clean.io
- **Prometheus:** https://prometheus.wearforce-clean.io
- **Alertmanager:** https://alertmanager.wearforce-clean.io
- **PagerDuty:** https://wearforce-clean.pagerduty.com

### Logging and Tracing
- **Kibana:** https://kibana.wearforce-clean.io
- **Jaeger:** https://jaeger.wearforce-clean.io

### Infrastructure
- **AWS Console:** https://console.aws.amazon.com
- **Kubernetes Dashboard:** https://dashboard.k8s.wearforce-clean.io
- **GitHub Actions:** https://github.com/wearforce-clean/wearforce-clean/actions

### Documentation
- **Runbooks:** https://github.com/wearforce-clean/wearforce-clean/tree/main/docs/runbooks
- **Architecture Docs:** https://github.com/wearforce-clean/wearforce-clean/tree/main/docs/architecture
- **API Documentation:** https://api-docs.wearforce-clean.io

---

**Document Version:** 1.0.0  
**Last Updated:** 2025-01-07  
**Next Review Date:** 2025-04-07  
**Owner:** Platform Engineering Team