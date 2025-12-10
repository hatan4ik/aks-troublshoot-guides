# Common Kubernetes Issues Playbook

## 🚨 Critical Issues (P0/P1)

### Pod Stuck in Pending State
**Symptoms**: Pods remain in Pending status indefinitely
**Common Causes**:
- Insufficient cluster resources
- Node selector/affinity constraints
- Persistent volume issues
- Image pull failures

**Diagnosis**:
```bash
kubectl describe pod <pod-name>
kubectl get events --sort-by=.metadata.creationTimestamp
kubectl top nodes
```

**Resolution**:
1. Check resource requests vs available capacity
2. Verify node labels match selectors
3. Ensure PVs are available and bound
4. Validate image registry access

---

### CrashLoopBackOff
**Symptoms**: Pods continuously restart
**Common Causes**:
- Application startup failures
- Misconfigured health checks
- Resource limits too low
- Missing dependencies

**Diagnosis**:
```bash
kubectl logs <pod-name> --previous
kubectl describe pod <pod-name>
kubectl get pod <pod-name> -o yaml
```

**Resolution**:
1. Review application logs for errors
2. Adjust resource limits/requests
3. Fix health check configurations
4. Verify environment variables and secrets

---

### ImagePullBackOff
**Symptoms**: Cannot pull container images
**Common Causes**:
- Registry authentication issues
- Network connectivity problems
- Image doesn't exist
- Registry rate limiting

**Diagnosis**:
```bash
kubectl describe pod <pod-name>
kubectl get events
docker pull <image-name>  # Test locally
```

**Resolution**:
1. Verify image registry credentials
2. Check network policies and firewall rules
3. Confirm image exists and tag is correct
4. Configure image pull secrets if needed

---

## 🔧 Infrastructure Issues (P2)

### Node NotReady
**Symptoms**: Nodes show NotReady status
**Common Causes**:
- kubelet issues
- Network connectivity problems
- Resource exhaustion
- Container runtime failures

**Diagnosis**:
```bash
kubectl get nodes -o wide
kubectl describe node <node-name>
# SSH to node and check:
systemctl status kubelet
journalctl -u kubelet -f
```

**Resolution**:
1. Restart kubelet service
2. Check disk space and memory
3. Verify network connectivity
4. Restart container runtime if needed

---

### DNS Resolution Failures
**Symptoms**: Services cannot resolve each other
**Common Causes**:
- CoreDNS pod failures
- Network policy blocking DNS
- Incorrect DNS configuration
- Service discovery issues

**Diagnosis**:
```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
nslookup kubernetes.default  # From inside pod
```

**Resolution**:
1. Restart CoreDNS pods
2. Check network policies
3. Verify DNS configuration
4. Test service endpoints

---

### Persistent Volume Issues
**Symptoms**: Pods cannot mount volumes
**Common Causes**:
- PV/PVC binding failures
- Storage class issues
- Node affinity constraints
- Storage backend problems

**Diagnosis**:
```bash
kubectl get pv,pvc
kubectl describe pvc <pvc-name>
kubectl get storageclass
```

**Resolution**:
1. Check PV availability and binding
2. Verify storage class configuration
3. Ensure node has access to storage
4. Check storage backend health

---

## 📊 Performance Issues (P3)

### High Resource Usage
**Symptoms**: Nodes or pods consuming excessive resources
**Common Causes**:
- Memory leaks in applications
- CPU-intensive workloads
- Insufficient resource limits
- Inefficient algorithms

**Diagnosis**:
```bash
kubectl top nodes
kubectl top pods -A
kubectl describe node <node-name>
```

**Resolution**:
1. Set appropriate resource limits
2. Optimize application code
3. Scale horizontally if needed
4. Consider node upgrades

---

### Slow Application Response
**Symptoms**: Applications responding slowly
**Common Causes**:
- Resource constraints
- Network latency
- Database performance
- Inefficient load balancing

**Diagnosis**:
```bash
kubectl top pods
kubectl get hpa
kubectl describe service <service-name>
```

**Resolution**:
1. Check resource utilization
2. Optimize database queries
3. Configure horizontal pod autoscaling
4. Review load balancer configuration

---

## 🔐 Security Issues (P2/P3)

### RBAC Permission Denied
**Symptoms**: Users/services cannot access resources
**Common Causes**:
- Insufficient RBAC permissions
- Incorrect service account binding
- Namespace restrictions
- API server authentication issues

**Diagnosis**:
```bash
kubectl auth can-i <verb> <resource> --as=<user>
kubectl get rolebindings,clusterrolebindings
kubectl describe serviceaccount <sa-name>
```

**Resolution**:
1. Review and update RBAC policies
2. Bind appropriate roles to users/SAs
3. Verify namespace access
4. Check authentication configuration

---

### Network Policy Blocking Traffic
**Symptoms**: Pods cannot communicate despite being in same cluster
**Common Causes**:
- Overly restrictive network policies
- Incorrect label selectors
- Missing ingress/egress rules
- Policy conflicts

**Diagnosis**:
```bash
kubectl get networkpolicies -A
kubectl describe networkpolicy <policy-name>
kubectl get pods --show-labels
```

**Resolution**:
1. Review network policy rules
2. Verify label selectors match pods
3. Add necessary ingress/egress rules
4. Test connectivity after changes

---

## 🔄 Deployment Issues (P2/P3)

### Rolling Update Stuck
**Symptoms**: Deployments not progressing during updates
**Common Causes**:
- Readiness probe failures
- Resource constraints
- Image pull issues
- Configuration errors

**Diagnosis**:
```bash
kubectl rollout status deployment/<deployment-name>
kubectl describe deployment <deployment-name>
kubectl get replicasets
```

**Resolution**:
1. Check pod readiness and health
2. Verify resource availability
3. Fix configuration issues
4. Rollback if necessary: `kubectl rollout undo deployment/<name>`

---

### Service Discovery Not Working
**Symptoms**: Services cannot find each other
**Common Causes**:
- Incorrect service configuration
- Endpoint issues
- DNS problems
- Network connectivity

**Diagnosis**:
```bash
kubectl get services,endpoints
kubectl describe service <service-name>
kubectl get pods -l <service-selector>
```

**Resolution**:
1. Verify service selector matches pod labels
2. Check endpoint configuration
3. Test DNS resolution
4. Validate network connectivity

---

## 📋 Quick Reference Commands

### Emergency Diagnostics
```bash
# Cluster overview
kubectl get nodes,pods,services -A

# Resource usage
kubectl top nodes
kubectl top pods -A

# Recent events
kubectl get events -A --sort-by=.metadata.creationTimestamp

# Failed pods
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
```

### Log Collection
```bash
# Pod logs
kubectl logs <pod-name> -f --previous

# System component logs
kubectl logs -n kube-system -l component=kube-apiserver

# All container logs in pod
kubectl logs <pod-name> --all-containers=true
```

### Network Troubleshooting
```bash
# DNS test
kubectl run dns-test --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default

# Network connectivity test
kubectl run netshoot --image=nicolaka/netshoot --rm -it --restart=Never -- bash
```