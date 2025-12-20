# Security Control Framework (SCF) & Troubleshooting in Kubernetes

## Overview
In high-compliance environments (FAANG, Finance, Healthcare), security isn't just "good practice"—it's a rigid framework (NIST 800-53, SOC2, PCI-DSS, CIS Benchmarks). This guide focuses on **how to troubleshoot and debug** the components that enforce these frameworks.

---

## 1. The Components of a K8s SCF

| Layer | Control Type | Common Tools | Failure Scenarios |
| :--- | :--- | :--- | :--- |
| **Admission** | Preventive | OPA Gatekeeper, Kyverno | Deployment blocked, Policy sync failure |
| **Runtime** | Detective | Falco, Tetragon, Sysdig | False positives, Performance overhead |
| **Identity** | Authentication | OIDC (Dex, Keycloak), AWS IRSA, Azure Workload Identity | Token expiry, Audience mismatch |
| **Network** | Segmentation | NetworkPolicies (Cilium, Calico), Service Mesh (Istio) | Traffic drops, Sidecar injection failure |

---

## 2. Troubleshooting Policy-as-Code (Admission Controllers)

### Scenario: "My Deployment is Blocked but I Don't Know Why"
**Symptoms:** `kubectl apply` fails with a generic error or a webhook timeout.

**Debugging Steps:**

1.  **Check the Webhook Configuration:**
    *   Is the webhook server reachable?
    *   `kubectl get validatingwebhookconfigurations`
    *   **Expert Move:** Check the `timeoutSeconds` and `failurePolicy`. If `failurePolicy: Fail` and the OPA pod is down, the *entire cluster* stops accepting changes.

2.  **Inspect Controller Logs:**
    *   **OPA Gatekeeper:** `kubectl logs -n gatekeeper-system -l control-plane=controller-manager`
    *   **Kyverno:** `kubectl logs -n kyverno -l app=kyverno`
    *   Look for "rego parse error" or "constraint template violation".

3.  **Trace the Request:**
    *   Check `kubectl get events` in the target namespace.
    *   Review the specific constraint: `kubectl get k8srequiredlabels -o yaml` (example).

4.  **Bypass (Emergency Only):**
    *   Delete the `ValidatingWebhookConfiguration` (Risky!).
    *   Better: Exclude the namespace in the webhook config (`namespaceSelector`).

### Scenario: "The Policy is Valid but Syncing Failed"
**Symptoms:** You updated a constraint, but it's not applying to new resources.
*   **Cause:** The controller is stuck or OOMing due to caching too many K8s objects (common in large clusters).
*   **Fix:** Check memory usage of the policy controller. Tune `resource` limits.

---

## 3. Troubleshooting Identity & Access (IAM/OIDC)

### Scenario: "IRSA (IAM Roles for Service Accounts) Fails"
**Symptoms:** Pod cannot access S3/DynamoDB. "Access Denied".

**The Expert Path:**
1.  **Check the Token Projection:**
    *   `kubectl exec <pod> -- cat /var/run/secrets/kubernetes.io/serviceaccount/token`
    *   Is the file there? If not, `serviceAccountName` might be wrong.

2.  **Verify Trust Relationship (The Hardest Part):**
    *   Decode the token (jwt.io). Check the `iss` (Issuer) and `sub` (Subject).
    *   Does the AWS IAM Role Trust Policy match this EXACT `iss` and `sub`?
    *   *Common Bug:* Missing `https://` in the issuer URL in IAM policy.

3.  **Check Webhook Injection:**
    *   EKS uses a mutating webhook to inject `AWS_ROLE_ARN` and `AWS_WEB_IDENTITY_TOKEN_FILE` env vars.
    *   `kubectl get pod <pod> -o yaml | grep AWS_`
    *   If missing, is the pod's namespace labeled correctly? Is the webhook pod running?

---

## 4. Troubleshooting Runtime Security (Falco/Tetragon)

### Scenario: "Falco is killing valid pods (False Positives)"
**Symptoms:** Pods die randomly. Logs show "Falco specific rule triggered".

**Debugging:**
1.  **Identify the Rule:**
    *   Check Falco logs/events (often sent to stdout or a sidecar).
    *   Identify the syscall: e.g., "Write below /etc".

2.  **Profile the App:**
    *   Does the app *legitimately* write to /etc? (e.g., Nginx generating config on startup).
    *   **Action:** Create a strict exception. Do NOT disable the rule globally.
    *   *Bad:* `enabled: false`
    *   *Good:* `condition: ... and not (proc.name = nginx and fd.name startswith /etc/nginx)`

3.  **Kernel Module Issues:**
    *   Falco uses eBPF or a Kernel Module. On node OS upgrades, these can break.
    *   Check `dmesg` on the node for generic kernel faults related to `falco`.

---

## 5. Security Control Framework Checklist (NIST/CIS)

Use this to audit your cluster:

1.  **CIS Benchmark:**
    *   [ ] Master Node configuration (audit logs enabled?)
    *   [ ] Worker Node configuration (kubelet permissions?)
    *   [ ] RBAC (no `admin` usage?)
2.  **Network Segmentation:**
    *   [ ] All namespaces have a "Default Deny" NetworkPolicy?
    *   [ ] Egress allowed only to known CIDRs/DNS?
3.  **Supply Chain:**
    *   [ ] Image signature verification enabled?
    *   [ ] Image vulnerability scanning in pipeline?
4.  **Secrets Management:**
    *   [ ] Encryption at Rest enabled for etcd?
    *   [ ] Secrets externalized (Vault/ASM/AKV)?

---

## 6. Advanced Interview Questions (FAANG Level)

**Q1: How do you handle a "Break Glass" scenario where OPA is broken and preventing all updates?**
*   **A:** "Break Glass" means restoring availability ASAP.
    1.  **Identify:** Verify OPA is the blocker (timeout errors in API server logs).
    2.  **Bypass:** `kubectl delete validatingwebhookconfiguration <opa-config>`.
    3.  **Remediate:** Fix the OPA pod/policy.
    4.  **Restore:** Re-apply the Webhook Configuration.
    5.  **Audit:** Who broke the glass? (RBAC logs).

**Q2: A developer says "I need `privileged` mode for my build container". How do you respond securely?**
*   **A:** "No." Privileged mode breaks container isolation (access to host devices, ability to load kernel modules).
*   **Alternatives:**
    *   **Kaniko/Buildah:** Build images in userspace without root daemon.
    *   **Isolated Node:** Taint a node specifically for unsafe builds and use `tolerations`.
    *   **Capabilities:** Grant only `CAP_SETUID` or `CAP_SYS_ADMIN` (still risky, but better) instead of full privileged.

**Q3: We implemented a "Default Deny" Network Policy, and now DNS is broken. Why?**
*   **A:** You blocked Egress traffic to UDP port 53.
*   **Fix:** Add a NetworkPolicy allowing Egress to the `kube-system` namespace (where CoreDNS lives) on port 53 (UDP/TCP).

**Q4: An attacker gained access to a pod. How do you prevent them from pivoting to the cloud provider API (e.g., stealing AWS credentials)?**
*   **A:**
    1.  **Block Metadata Service:** NetworkPolicy denying egress to `169.254.169.254`.
    2.  **IMDSv2:** Enforce Instance Metadata Service Version 2 (requires session token, harder to spoof/SSRF).
    3.  **Least Privilege:** Ensure the Node's IAM role has minimal permissions. Pods should use IRSA (Pod Identity), not Node Identity.

**Q5: How do you debug a Certificate Authority (CA) rotation failure?**
*   **A:**
    1.  **Symptom:** API Server stops trusting Kubelets, or ServiceAccount tokens become invalid.
    2.  **Check:** Did you update the CA bundle in the `kube-root-ca.crt` ConfigMap in every namespace?
    3.  **Check:** Did you restart components to pick up the new CA?
    4.  **Rollback:** Keep the old CA in the bundle as "trusted" until the rotation is 100% complete.