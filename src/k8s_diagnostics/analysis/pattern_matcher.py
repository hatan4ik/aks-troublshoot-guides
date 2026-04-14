"""5-Layer error pattern matcher.

Maps raw error text (from pod events, container logs, kubectl describe output)
to a structured diagnosis: layer, root cause, decisive signal, next investigation
command, and the smallest safe fix command.

Pattern library is organized by the 5-layer AKS debugging model taught in
course/01-foundations.md through course/05-aks-platform.md.

Layer map:
  layer1 — Pod Lifecycle       (scheduling, image pull, config, probes, entrypoint)
  layer2 — Container Runtime   (OOM, cgroups, exit codes, containerd)
  layer3 — Service Networking  (selector, endpoints, ports, DNS, Ingress)
  layer4 — Cluster Infra       (nodes, CNI, CoreDNS, NetworkPolicy, etcd)
  layer5 — Azure/Cloud Infra   (NSG, LB, VNet, ACR auth, storage, DNS zone)
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PatternMatch:
    """Result of matching one error pattern."""
    layer: str                    # layer1 … layer5
    error_class: str              # short slug, e.g. "image_pull_backoff"
    severity: str                 # high / medium / low
    signal: str                   # the exact phrase / field that proved it
    root_cause: str               # human explanation
    next_command: str             # first kubectl/az command to run
    fix_command: str              # smallest safe fix command
    fix_description: str          # what the fix does
    confidence: str = "high"      # high / medium — medium if pattern is broad
    matched_text: str = ""        # the substring that triggered this match


@dataclass
class _Pattern:
    """Internal: one regex pattern → diagnosis."""
    regex: str
    layer: str
    error_class: str
    severity: str
    root_cause: str
    next_command: str
    fix_command: str
    fix_description: str
    confidence: str = "high"
    flags: int = re.IGNORECASE


# ─────────────────────────────────────────────────────────────────────────────
# Pattern library — ordered from most specific to most general within each layer
# ─────────────────────────────────────────────────────────────────────────────

_PATTERNS: List[_Pattern] = [

    # ── Layer 1: Image Pull ──────────────────────────────────────────────────

    _Pattern(
        regex=r"manifest unknown|tag does not exist|not found.*repository",
        layer="layer1", error_class="bad_image_tag", severity="high",
        root_cause="Image tag does not exist in the registry — typo or image was never pushed",
        next_command="kubectl describe pod <pod> -n <ns>  # check Events for exact image+tag",
        fix_command="kubectl set image deployment/<name> <container>=<registry>/<image>:<correct-tag>",
        fix_description="Update the image tag to one that exists in the registry",
    ),
    _Pattern(
        regex=r"401 unauthorized|unauthorized.*registry|authentication required",
        layer="layer1", error_class="image_pull_auth", severity="high",
        root_cause="Registry authentication failed — missing or invalid imagePullSecret",
        next_command="kubectl describe pod <pod> -n <ns>  # check Events for 'unauthorized'",
        fix_command=(
            "kubectl create secret docker-registry regcred "
            "--docker-server=<registry> --docker-username=<user> "
            "--docker-password=<token> -n <ns> && "
            "kubectl patch deployment <name> -n <ns> "
            "-p '{\"spec\":{\"template\":{\"spec\":{\"imagePullSecrets\":"
            "[{\"name\":\"regcred\"}]}}}}'  "
        ),
        fix_description="Create imagePullSecret and attach it to the deployment",
    ),
    _Pattern(
        regex=r"connection timed out.*pull|failed to pull.*timeout|dial tcp.*443.*timeout",
        layer="layer5", error_class="image_pull_network", severity="high",
        root_cause="Network timeout pulling image — NSG blocking egress port 443 to registry",
        next_command=(
            "kubectl run nettest --image=nicolaka/netshoot --rm -it --restart=Never -- "
            "curl -v https://<registry>/v2/  # 'connection timed out' = NSG block"
        ),
        fix_command=(
            "az network nsg rule create -g <node-rg> --nsg-name <nsg> "
            "-n AllowAcrEgress --priority 100 --direction Outbound "
            "--destination-port-ranges 443 --access Allow --protocol Tcp"
        ),
        fix_description="Add NSG outbound allow rule for port 443 to registry",
    ),
    _Pattern(
        regex=r"ErrImageNeverPull|ImageNeverPull",
        layer="layer1", error_class="image_never_pull", severity="high",
        root_cause="imagePullPolicy=Never but image is not present in the node's local cache",
        next_command="kubectl get pod <pod> -n <ns> -o jsonpath='{.spec.containers[*].imagePullPolicy}'",
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "-p '{\"spec\":{\"template\":{\"spec\":{\"containers\":"
            "[{\"name\":\"<container>\",\"imagePullPolicy\":\"IfNotPresent\"}]}}}}'  "
        ),
        fix_description="Change imagePullPolicy to IfNotPresent or Always",
    ),
    _Pattern(
        regex=r"Back-off pulling image|backoff pulling",
        layer="layer1", error_class="image_pull_backoff", severity="high",
        root_cause="Repeated image pull failures — check the previous Failed event for root cause",
        next_command="kubectl describe pod <pod> -n <ns>  # read ALL Events, not just latest",
        fix_command="# Fix depends on preceding event: auth error → imagePullSecret, timeout → NSG, tag → correct tag",
        fix_description="Root cause is in the preceding event — this is the backoff state, not the cause",
    ),

    # ── Layer 1: Entrypoint / Command ────────────────────────────────────────

    _Pattern(
        regex=r"executable file not found|exec.*no such file|exec.*not found in \$PATH",
        layer="layer1", error_class="bad_entrypoint", severity="high",
        root_cause="Container command binary does not exist in the image (exit code 127)",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # check LastState.ExitCode (should be 127)\n"
            "kubectl run debug --image=<same-image> --rm -it --restart=Never -- which <binary>"
        ),
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "--type=json -p='[{\"op\":\"replace\",\"path\":"
            "\"/spec/template/spec/containers/0/command\",\"value\":[\"/correct/binary\"]}]'"
        ),
        fix_description="Fix the command/entrypoint to a binary that exists in the image",
    ),
    _Pattern(
        regex=r"permission denied.*exec|exec.*permission denied",
        layer="layer1", error_class="entrypoint_permission", severity="high",
        root_cause="Entrypoint binary exists but is not executable (exit code 126)",
        next_command="kubectl run debug --image=<same-image> --rm -it --restart=Never -- ls -la <binary>",
        fix_command="# Fix in Dockerfile: RUN chmod +x /entrypoint.sh — rebuild and push image",
        fix_description="Add executable permission to the binary in the image build",
    ),

    # ── Layer 1: Config / Secret / ConfigMap ─────────────────────────────────

    _Pattern(
        regex=r"couldn't find key (\S+) in ConfigMap|key.+not found.+configmap",
        layer="layer1", error_class="configmap_key_missing", severity="high",
        root_cause="Pod references a ConfigMap key that does not exist in that ConfigMap",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # shows CreateContainerConfigError\n"
            "kubectl get configmap <cm-name> -n <ns> -o yaml  # see actual keys"
        ),
        fix_command=(
            "kubectl patch configmap <cm-name> -n <ns> "
            "--type=merge -p '{\"data\":{\"MISSING_KEY\":\"value\"}}'  "
            "# OR fix the env.valueFrom.configMapKeyRef.key in the deployment"
        ),
        fix_description="Add the missing key to the ConfigMap or correct the key name in the pod spec",
    ),
    _Pattern(
        regex=r'secret[" ]+(\S+)[" ]+ not found|failed to get secret|secret.*not exist',
        layer="layer1", error_class="secret_missing", severity="high",
        root_cause="Pod references a Secret that does not exist in the namespace",
        next_command=(
            "kubectl get secret <secret-name> -n <ns>  # confirm missing\n"
            "kubectl describe pod <pod> -n <ns>  # CreateContainerConfigError event"
        ),
        fix_command=(
            "kubectl create secret generic <secret-name> -n <ns> "
            "--from-literal=<KEY>=<value>"
        ),
        fix_description="Create the missing Secret with the required keys",
    ),
    _Pattern(
        regex=(
            r"failed to sync configmap cache|"
            r"MountVolume\.SetUp failed.*configmap cache|"
            r"timed out waiting for the condition.*configmap"
        ),
        layer="layer4", error_class="configmap_cache_sync_timeout", severity="medium",
        root_cause=(
            "Kubelet timed out syncing its ConfigMap cache. This is often a transient API/kubelet "
            "signal and does not by itself prove the ConfigMap is missing."
        ),
        next_command=(
            "kubectl get configmap <cm-name> -n <ns>\n"
            "kubectl describe pod <pod> -n <ns>\n"
            "kubectl get events -n <ns> --sort-by=.metadata.creationTimestamp | tail -50"
        ),
        fix_command=(
            "# If the ConfigMap exists and the pod is stuck in Init, inspect init logs first:\n"
            "kubectl logs <pod> -n <ns> -c <init-container>\n"
            "# If cache timeouts continue across pods, check kubelet/node/API server health."
        ),
        fix_description="Verify whether this is a stale secondary event before changing ConfigMaps",
        confidence="medium",
    ),
    _Pattern(
        regex=r'configmap[" ]+(\S+)[" ]+ not found|failed to get configmap',
        layer="layer1", error_class="configmap_missing", severity="high",
        root_cause="Pod references a ConfigMap that does not exist in the namespace",
        next_command="kubectl get configmap <cm-name> -n <ns>",
        fix_command="kubectl create configmap <cm-name> -n <ns> --from-literal=<KEY>=<value>",
        fix_description="Create the missing ConfigMap",
    ),

    # ── Layer 1: Probes ───────────────────────────────────────────────────────

    _Pattern(
        regex=r"Readiness probe failed.*HTTP probe failed.*status.*404",
        layer="layer1", error_class="probe_path_404", severity="medium",
        root_cause="Readiness probe HTTP path returns 404 — path does not exist in the app",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # check readinessProbe.httpGet.path\n"
            "kubectl exec <pod> -n <ns> -- wget -qO- http://localhost:<port>/<path>"
        ),
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "--type=json -p='[{\"op\":\"replace\",\"path\":"
            "\"/spec/template/spec/containers/0/readinessProbe/httpGet/path\","
            "\"value\":\"/healthz\"}]'"
        ),
        fix_description="Fix readiness probe path to one the app actually serves",
    ),
    _Pattern(
        regex=r"Readiness probe failed.*connection refused|readiness.*dial.*connection refused",
        layer="layer1", error_class="probe_port_refused", severity="medium",
        root_cause="Readiness probe connects to wrong port — app not listening on probe port",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # compare readinessProbe.httpGet.port vs containerPort\n"
            "kubectl exec <pod> -n <ns> -- ss -tlnp"
        ),
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "--type=json -p='[{\"op\":\"replace\",\"path\":"
            "\"/spec/template/spec/containers/0/readinessProbe/httpGet/port\","
            "\"value\":<correct-port>}]'"
        ),
        fix_description="Fix readiness probe port to match the port the app listens on",
    ),
    _Pattern(
        regex=r"Liveness probe failed|liveness.*killing container|liveness.*BackOff",
        layer="layer1", error_class="liveness_killing_pod", severity="high",
        root_cause="Liveness probe is terminating a healthy container — initialDelaySeconds too low or probe too aggressive",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # check livenessProbe config and Events\n"
            "kubectl logs <pod> -n <ns> --previous  # was the app actually ready?"
        ),
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "--type=json -p='[{\"op\":\"replace\",\"path\":"
            "\"/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds\","
            "\"value\":30}]'"
        ),
        fix_description="Increase livenessProbe.initialDelaySeconds to give the app time to start",
    ),
    _Pattern(
        regex=r"Startup probe failed",
        layer="layer1", error_class="startup_probe_failed", severity="high",
        root_cause="Startup probe failed — app took longer than failureThreshold × periodSeconds to start",
        next_command="kubectl describe pod <pod> -n <ns>  # check startupProbe thresholds",
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "--type=json -p='[{\"op\":\"replace\",\"path\":"
            "\"/spec/template/spec/containers/0/startupProbe/failureThreshold\","
            "\"value\":30}]'"
        ),
        fix_description="Increase startupProbe.failureThreshold to allow more startup time",
    ),

    # ── Layer 2: OOM / Runtime ───────────────────────────────────────────────

    _Pattern(
        regex=r"OOMKilled|oom.kill|out of memory|memory limit exceeded|Killed process",
        layer="layer2", error_class="oomkilled", severity="high",
        root_cause="Container was killed by the kernel OOM killer (exit code 137) — memory limit too low",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # LastState.Reason: OOMKilled\n"
            "kubectl top pod <pod> -n <ns>  # actual memory usage"
        ),
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "--type=json -p='[{\"op\":\"replace\",\"path\":"
            "\"/spec/template/spec/containers/0/resources/limits/memory\","
            "\"value\":\"512Mi\"}]'"
        ),
        fix_description="Raise the container memory limit (measure actual usage first with kubectl top)",
    ),
    _Pattern(
        regex=r"failed to create containerd task|containerd.*failed|runc.*failed to create",
        layer="layer2", error_class="containerd_error", severity="high",
        root_cause="containerd failed to create the container — possible node-level issue",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # check Events for containerd error\n"
            "# On the node: journalctl -u containerd --no-pager | tail -50"
        ),
        fix_command="kubectl delete pod <pod> -n <ns>  # force reschedule to healthy node",
        fix_description="Delete pod to trigger reschedule; if persistent, drain and cordon the node",
    ),

    # ── Layer 1: Scheduling ───────────────────────────────────────────────────

    _Pattern(
        regex=r"0/\d+ nodes are available.*Insufficient (cpu|memory)",
        layer="layer1", error_class="insufficient_resources", severity="high",
        root_cause="No node has enough allocatable CPU or memory to satisfy the pod's requests",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # FailedScheduling event\n"
            "kubectl describe nodes | grep -A5 'Allocated resources'"
        ),
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "--type=json -p='[{\"op\":\"replace\",\"path\":"
            "\"/spec/template/spec/containers/0/resources/requests/cpu\","
            "\"value\":\"100m\"}]'"
            "  # OR add a node / scale node pool"
        ),
        fix_description="Lower resource requests to fit available nodes, or scale out the node pool",
    ),
    _Pattern(
        regex=r"node\(s\) had untolerated taint|untolerated taint",
        layer="layer1", error_class="taint_no_toleration", severity="high",
        root_cause="All nodes have a taint the pod does not tolerate — pod cannot be scheduled",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # shows taint key:value:effect\n"
            "kubectl describe nodes | grep Taint"
        ),
        fix_command=(
            "kubectl patch deployment <name> -n <ns> "
            "--type=json -p='[{\"op\":\"add\",\"path\":"
            "\"/spec/template/spec/tolerations\","
            "\"value\":[{\"key\":\"<key>\",\"operator\":\"Equal\","
            "\"value\":\"<value>\",\"effect\":\"NoSchedule\"}]}]'"
        ),
        fix_description="Add a matching toleration to the pod spec",
    ),
    _Pattern(
        regex=r"node selector.*not match|didn't match.*nodeSelector|MatchNodeSelector",
        layer="layer1", error_class="node_selector_mismatch", severity="high",
        root_cause="Pod nodeSelector labels do not match any node's labels",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # shows nodeSelector\n"
            "kubectl get nodes --show-labels"
        ),
        fix_command=(
            "kubectl label node <node> <key>=<value>  "
            "# OR fix the nodeSelector in the deployment spec"
        ),
        fix_description="Label a node to match the pod's nodeSelector, or remove the incorrect selector",
    ),
    _Pattern(
        regex=r"unbound immediate PersistentVolumeClaims|PVC.*not found|persistentvolumeclaim.*pending",
        layer="layer1", error_class="pvc_unbound_scheduling", severity="high",
        root_cause="Pod cannot schedule because its PVC is not bound — StorageClass or provisioner issue",
        next_command=(
            "kubectl describe pvc <pvc-name> -n <ns>  # check Events\n"
            "kubectl get storageclass  # confirm StorageClass exists"
        ),
        fix_command="# Check StorageClass and provisioner; ensure the PVC matches an available StorageClass",
        fix_description="Fix StorageClass name in PVC spec or create the StorageClass",
    ),

    # ── Layer 3: Service Networking ───────────────────────────────────────────

    _Pattern(
        regex=(
            r"(?:config-service|postgres-service|[a-z0-9-]+-service)\s+not ready(?:, retrying)?|"
            r"services? [\"'][a-z0-9-]+-service[\"'] not found|"
            r"bad address [\"']?[a-z0-9-]+-service[\"']?|"
            r"init[- ]?container.*(?:service|dependency).*(?:not ready|not found)"
        ),
        layer="layer3", error_class="init_dependency_service_missing", severity="high",
        root_cause=(
            "An init container is waiting for a Service/dependency that is missing or has no ready endpoints, "
            "so the main container never starts."
        ),
        next_command=(
            "kubectl logs <pod> -n <ns> -c <init-container>\n"
            "kubectl get svc,endpoints,endpointslice -n <ns> | grep <service-name>\n"
            "kubectl get pods -n <ns> --show-labels"
        ),
        fix_command=(
            "# Preferred: create/fix the dependency Service and backing pods.\n"
            "# Lab-only workaround: remove the init gate from the Deployment:\n"
            "kubectl patch deployment <deploy> -n <ns> --type=json "
            "-p='[{\"op\":\"remove\",\"path\":\"/spec/template/spec/initContainers\"}]'"
        ),
        fix_description="Restore the missing dependency Service/endpoints or remove the init gate only as a lab workaround",
    ),

    _Pattern(
        regex=r"dial tcp.*:(\d+).*connection refused|connect.*ECONNREFUSED",
        layer="layer3", error_class="connection_refused", severity="high",
        root_cause="'Connection refused' = app not listening on that port — wrong targetPort or app crashed",
        next_command=(
            "kubectl get endpoints <svc> -n <ns>  # populated?\n"
            "kubectl describe svc <svc> -n <ns>  # compare targetPort vs containerPort\n"
            "kubectl exec <pod> -n <ns> -- ss -tlnp  # what port is actually open?"
        ),
        fix_command=(
            "kubectl patch svc <svc> -n <ns> "
            "--type=json -p='[{\"op\":\"replace\",\"path\":"
            "\"/spec/ports/0/targetPort\",\"value\":<correct-port>}]'"
        ),
        fix_description="Fix Service targetPort to match the port the app actually listens on",
    ),
    _Pattern(
        regex=r"dial tcp.*i/o timeout|connection timed out|context deadline exceeded.*dial",
        layer="layer4", error_class="connection_timeout", severity="high",
        root_cause="'Timeout' = packet dropped silently — NetworkPolicy deny-all or NSG/firewall blocking",
        next_command=(
            "kubectl get networkpolicy -n <ns>  # deny-all present?\n"
            "kubectl run nettest --image=nicolaka/netshoot --rm -it --restart=Never -- "
            "nc -zv <pod-ip> <port>  # test directly"
        ),
        fix_command=(
            "# If NetworkPolicy: add ingress allow rule\n"
            "kubectl apply -f - <<EOF\napiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\n"
            "metadata:\n  name: allow-ingress\n  namespace: <ns>\nspec:\n  podSelector: {}\n"
            "  ingress:\n  - {}\nEOF"
        ),
        fix_description="Add NetworkPolicy ingress rule; if NSG: add inbound allow rule in Azure",
        confidence="medium",
    ),
    _Pattern(
        regex=r"no such host|NXDOMAIN|Name or service not known",
        layer="layer3", error_class="dns_nxdomain", severity="high",
        root_cause="DNS lookup returned NXDOMAIN — service name wrong, wrong namespace, or CoreDNS issue",
        next_command=(
            "kubectl run dns-test --image=busybox --rm -it --restart=Never -- "
            "nslookup <service-name>.<namespace>.svc.cluster.local\n"
            "kubectl get svc -A | grep <service-name>"
        ),
        fix_command=(
            "# If service name wrong: fix the DNS name used by the app\n"
            "# Format: <svc>.<namespace>.svc.cluster.local\n"
            "kubectl get svc -n <ns>  # verify correct service name"
        ),
        fix_description="Fix the DNS name — use <svc>.<namespace>.svc.cluster.local format",
    ),
    _Pattern(
        regex=r"SERVFAIL|upstream.*SERVFAIL|coredns.*SERVFAIL",
        layer="layer4", error_class="coredns_servfail", severity="high",
        root_cause="CoreDNS returned SERVFAIL — CoreDNS pod unhealthy or upstream DNS misconfigured",
        next_command=(
            "kubectl get pods -n kube-system -l k8s-app=kube-dns\n"
            "kubectl logs -n kube-system -l k8s-app=kube-dns --tail=30"
        ),
        fix_command="kubectl rollout restart deployment/coredns -n kube-system",
        fix_description="Restart CoreDNS; if persistent check ConfigMap: kubectl get cm coredns -n kube-system -o yaml",
    ),
    _Pattern(
        regex=r"5-second.*DNS|DNS.*5.*second|conntrack.*race|UDP.*timeout",
        layer="layer4", error_class="dns_conntrack_race", severity="medium",
        root_cause="5-second DNS timeouts — conntrack race condition on UDP DNS (common in Linux kernels < 5.4)",
        next_command="kubectl logs -n kube-system -l k8s-app=kube-dns | grep -i timeout",
        fix_command=(
            "kubectl apply -f https://raw.githubusercontent.com/kubernetes/kubernetes/"
            "master/cluster/addons/dns/nodelocaldns/nodelocaldns.yaml  "
            "# NodeLocal DNSCache resolves the conntrack race"
        ),
        fix_description="Deploy NodeLocal DNSCache to bypass conntrack for DNS",
    ),
    _Pattern(
        regex=r"503 Service Unavailable|no endpoints available for service",
        layer="layer3", error_class="no_endpoints", severity="high",
        root_cause="No healthy endpoints — selector mismatch, all pods not Ready, or zero replicas",
        next_command=(
            "kubectl get endpoints <svc> -n <ns>  # empty = selector or readiness problem\n"
            "kubectl get pods -n <ns> --show-labels\n"
            "kubectl get svc <svc> -n <ns> -o yaml | grep -A3 selector"
        ),
        fix_command=(
            "# If selector mismatch: fix labels in deployment or selector in service\n"
            "kubectl label pod <pod> -n <ns> <key>=<value>  # add matching label"
        ),
        fix_description="Fix selector/label mismatch or investigate why pods are not Ready",
    ),
    _Pattern(
        regex=r"502 Bad Gateway|upstream connect error|upstream.*failed",
        layer="layer3", error_class="upstream_502", severity="high",
        root_cause="Ingress reached the Service but the backend pod returned an error or closed connection",
        next_command=(
            "kubectl describe ingress <ing> -n <ns>  # backend service name correct?\n"
            "kubectl get endpoints <backend-svc> -n <ns>  # endpoints populated?"
        ),
        fix_command=(
            "# Verify backend service name/port in Ingress spec matches actual Service\n"
            "kubectl describe svc <backend-svc> -n <ns>"
        ),
        fix_description="Fix Ingress backend service name or port, or fix the app returning 5xx",
    ),

    # ── Layer 4: Cluster Infrastructure ──────────────────────────────────────

    _Pattern(
        regex=r"etcdserver: request timed out|etcd.*no leader|etcd.*timeout",
        layer="layer4", error_class="etcd_timeout", severity="high",
        root_cause="etcd is overloaded or has lost quorum — API server requests timing out cluster-wide",
        next_command=(
            "kubectl get componentstatuses\n"
            "# On control plane: etcdctl endpoint health --cluster"
        ),
        fix_command=(
            "# etcdctl defrag --cluster  (on control plane)\n"
            "# etcdctl compact $(etcdctl endpoint status --write-out=table | grep -v ID | awk '{print $7}')"
        ),
        fix_description="Defrag and compact etcd; on managed clusters (AKS/EKS/GKE) contact support",
    ),
    _Pattern(
        regex=r"failed to call webhook|webhook.*timeout|admission webhook.*failure",
        layer="layer4", error_class="admission_webhook_timeout", severity="high",
        root_cause="Admission webhook is unavailable or timing out — blocks all resource changes in affected namespaces",
        next_command=(
            "kubectl get validatingwebhookconfigurations\n"
            "kubectl get mutatingwebhookconfigurations\n"
            "kubectl get pods -A | grep -i webhook"
        ),
        fix_command=(
            "# Temporary: delete or disable the webhook\n"
            "kubectl delete validatingwebhookconfiguration <name>  "
            "# Permanent: fix the webhook service/pod"
        ),
        fix_description="Fix or temporarily remove the failing webhook configuration",
    ),
    _Pattern(
        regex=r"Failed to allocate IP|No IP address available|ipam.*exhausted",
        layer="layer4", error_class="cni_ip_exhaustion", severity="high",
        root_cause="CNI IPAM has no IPs left — subnet exhaustion (Azure CNI) or aws-node pool depleted (VPC CNI)",
        next_command=(
            "kubectl logs -n kube-system -l k8s-app=azure-cni --tail=30\n"
            "# AKS: az network vnet subnet show -g <node-rg> --vnet-name <vnet> "
            "--name <subnet> --query availableIpAddressCount"
        ),
        fix_command=(
            "# AKS: expand subnet in Azure Portal or add node pool in larger subnet\n"
            "# EKS: kubectl set env ds aws-node -n kube-system ENABLE_PREFIX_DELEGATION=true"
        ),
        fix_description="Expand subnet CIDR or enable IP prefix delegation",
    ),
    _Pattern(
        regex=r"network plugin.*failed|cni plugin.*failed|failed to set up sandbox network",
        layer="layer4", error_class="cni_plugin_error", severity="high",
        root_cause="CNI plugin failed to configure pod networking — node-level CNI issue",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # NetworkPlugin error in Events\n"
            "kubectl get pods -n kube-system  # CNI daemonset pods healthy?"
        ),
        fix_command="kubectl delete pod <pod> -n <ns>  # reschedule; if CNI pod failing: kubectl rollout restart ds/<cni-ds> -n kube-system",
        fix_description="Restart the CNI daemonset pod on the affected node",
    ),
    _Pattern(
        regex=r"x509: certificate has expired|x509.*certificate.*expired|tls.*certificate.*expired",
        layer="layer4", error_class="tls_cert_expired", severity="high",
        root_cause="TLS certificate has expired — affects API server communication or ingress",
        next_command=(
            "kubectl get secret -A | grep tls\n"
            "# Check cert expiry: kubectl get secret <name> -n <ns> -o jsonpath='{.data.tls\\.crt}' "
            "| base64 -d | openssl x509 -noout -dates"
        ),
        fix_command=(
            "# cert-manager: kubectl annotate certificate <name> -n <ns> "
            "cert-manager.io/renewal-reason=manual-$(date +%s)\n"
            "# Manual: replace tls.crt and tls.key in the Secret"
        ),
        fix_description="Renew the expired TLS certificate",
    ),

    # ── Layer 5: Azure / Cloud ────────────────────────────────────────────────

    _Pattern(
        regex=r"Error creating load balancer|failed to ensure load balancer|cloud controller.*error",
        layer="layer5", error_class="lb_provisioning_failed", severity="high",
        root_cause="Azure cloud controller manager failed to provision the Load Balancer — quota or permission issue",
        next_command=(
            "kubectl describe svc <svc> -n <ns>  # Events\n"
            "kubectl logs -n kube-system -l component=cloud-controller-manager --tail=30"
        ),
        fix_command=(
            "az quota list --provider Microsoft.Network --location <region>  "
            "# Check PublicIPAddresses quota\n"
            "az aks show -g <rg> -n <cluster> --query 'provisioningState'"
        ),
        fix_description="Check Azure quota and cloud-controller-manager permissions",
    ),
    _Pattern(
        regex=r"acr.*unauthorized|could not authenticate.*azure container registry|acrpull",
        layer="layer5", error_class="acr_auth_failed", severity="high",
        root_cause="AKS kubelet identity lacks AcrPull role on the Azure Container Registry",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # '401 Unauthorized' in image pull event\n"
            "az role assignment list --assignee <kubelet-object-id> --all -o table"
        ),
        fix_command=(
            "az role assignment create --assignee <kubelet-object-id> "
            "--role AcrPull "
            "--scope /subscriptions/<sub>/resourceGroups/<acr-rg>"
            "/providers/Microsoft.ContainerRegistry/registries/<acr-name>"
        ),
        fix_description="Assign AcrPull role to the AKS kubelet managed identity",
    ),
    _Pattern(
        regex=r"vmss.*provisioning.*failed|ScaleError|node.*not join",
        layer="layer5", error_class="vmss_failed", severity="high",
        root_cause="Azure VMSS instance failed to provision — node will not join the cluster",
        next_command=(
            "az vmss list-instances -g <node-rg> --name <vmss> -o table\n"
            "az aks nodepool list -g <rg> --cluster-name <cluster>"
        ),
        fix_command="az aks nodepool upgrade -g <rg> --cluster-name <cluster> --name <nodepool> --node-image-only",
        fix_description="Upgrade node image or delete/recreate the failing VMSS instance",
    ),
    _Pattern(
        regex=r"privatelink.*not resolve|private.*dns.*fail|api.*server.*not.*reachable.*private",
        layer="layer5", error_class="private_cluster_dns", severity="high",
        root_cause="Private cluster API server FQDN not resolving — private DNS zone not linked to VNet",
        next_command=(
            "nslookup <cluster-fqdn>  # should return 10.x.x.x private IP\n"
            "az network private-dns link vnet list -g <rg> --zone-name privatelink.<region>.azmk8s.io -o table"
        ),
        fix_command=(
            "# Emergency access without DNS: \n"
            "az aks command invoke -g <rg> -n <cluster> --command 'kubectl get pods -A'"
        ),
        fix_description="Fix private DNS zone VNet link or use az aks command invoke as emergency access",
    ),

    # ── Layer 1: StatefulSet / Job specifics ─────────────────────────────────

    _Pattern(
        regex=r"service.*not found.*headless|clusterIP.*None.*not found|statefulset.*service.*missing",
        layer="layer1", error_class="statefulset_headless_svc_missing", severity="high",
        root_cause="StatefulSet's governing headless Service does not exist — pod identity and DNS will fail",
        next_command=(
            "kubectl describe statefulset <name> -n <ns>  # check serviceName\n"
            "kubectl get svc <serviceName> -n <ns>  # does it exist with clusterIP: None?"
        ),
        fix_command=(
            "kubectl apply -f - <<EOF\napiVersion: v1\nkind: Service\nmetadata:\n"
            "  name: <serviceName>\n  namespace: <ns>\nspec:\n  clusterIP: None\n"
            "  selector:\n    app: <label>\nEOF"
        ),
        fix_description="Create the headless Service (clusterIP: None) matching the StatefulSet serviceName",
    ),
    _Pattern(
        regex=r"job.*backoff.*limit.*exceeded|backoffLimitExceeded",
        layer="layer1", error_class="job_backoff_exceeded", severity="medium",
        root_cause="Job's backoffLimit exhausted — all pod attempts failed",
        next_command=(
            "kubectl describe job <name> -n <ns>  # how many attempts\n"
            "kubectl logs -n <ns> -l job-name=<name> --previous  # last failure reason"
        ),
        fix_command=(
            "kubectl delete job <name> -n <ns>  # Jobs are immutable — must delete and recreate\n"
            "# Fix the job spec/command before recreating"
        ),
        fix_description="Jobs are immutable — delete and recreate with the corrected command",
    ),
    _Pattern(
        regex=r"persistentvolume.*multi.*attach|Multi-Attach error|volume.*already.*used.*by.*pod",
        layer="layer1", error_class="pv_multi_attach", severity="high",
        root_cause="ReadWriteOnce (Azure Disk) volume attached to one node, pod scheduled on another",
        next_command=(
            "kubectl describe pod <pod> -n <ns>  # Multi-Attach error in Events\n"
            "kubectl get pv <pv-name> -o yaml | grep -A5 nodeAffinity"
        ),
        fix_command=(
            "# Option 1: Add nodeAffinity to schedule pod on same node as disk\n"
            "# Option 2: Switch to Azure Files (RWX) for multi-node access\n"
            "kubectl delete pod <old-pod> -n <ns>  # release the volume from old node first"
        ),
        fix_description="Delete the old pod to release the RWO volume, then let the new pod attach",
    ),

    # ── RBAC ─────────────────────────────────────────────────────────────────

    _Pattern(
        regex=r"is forbidden.*cannot.*verbs|RBAC.*forbidden|User.*cannot.*resource",
        layer="layer1", error_class="rbac_forbidden", severity="medium",
        root_cause="RBAC: ServiceAccount or user lacks permission for this operation",
        next_command=(
            "kubectl auth can-i <verb> <resource> -n <ns> "
            "--as=system:serviceaccount:<ns>:<sa-name>\n"
            "kubectl describe rolebinding -n <ns>  # what role is bound?"
        ),
        fix_command=(
            "kubectl create rolebinding <name> -n <ns> "
            "--clusterrole=<role> --serviceaccount=<ns>:<sa-name>"
        ),
        fix_description="Create a RoleBinding granting the required permissions to the ServiceAccount",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

# Compile all patterns once at import time
_COMPILED: List[tuple] = [
    (re.compile(p.regex, p.flags), p) for p in _PATTERNS
]

# Layer label map for human output
LAYER_LABELS = {
    "layer1": "Layer 1 — Pod Lifecycle",
    "layer2": "Layer 2 — Container Runtime",
    "layer3": "Layer 3 — Service Networking",
    "layer4": "Layer 4 — Cluster Infrastructure",
    "layer5": "Layer 5 — Cloud Infrastructure (Azure/AWS/GCP)",
}


def match(text: str) -> List[PatternMatch]:
    """Match all patterns against a text string.

    Args:
        text: Any error string — from an Event message, kubectl describe output,
              container log line, or raw error returned by the API.

    Returns:
        List of PatternMatch objects, most specific first (preserves pattern order).
        Empty list if no pattern matched.
    """
    results = []
    seen_classes = set()
    for compiled, pattern in _COMPILED:
        m = compiled.search(text)
        if m and pattern.error_class not in seen_classes:
            seen_classes.add(pattern.error_class)
            results.append(PatternMatch(
                layer=pattern.layer,
                error_class=pattern.error_class,
                severity=pattern.severity,
                signal=m.group(0),
                root_cause=pattern.root_cause,
                next_command=pattern.next_command,
                fix_command=pattern.fix_command,
                fix_description=pattern.fix_description,
                confidence=pattern.confidence,
                matched_text=text[:200],
            ))
    return results


def match_events(events: list) -> List[PatternMatch]:
    """Match patterns against a list of Kubernetes Event objects or event dicts.

    Accepts either kubernetes-client V1Event objects or dicts with 'message' key.
    Returns deduplicated list of PatternMatch, one per error class.
    """
    results = []
    seen_classes = set()
    for event in events:
        if hasattr(event, "message"):
            text = (event.message or "") + " " + (event.reason or "")
        elif isinstance(event, dict):
            text = (event.get("message") or "") + " " + (event.get("reason") or "")
        else:
            continue
        for pm in match(text):
            if pm.error_class not in seen_classes:
                seen_classes.add(pm.error_class)
                results.append(pm)
    return results


def match_log_lines(log_text: str) -> List[PatternMatch]:
    """Match patterns against multi-line container log output.

    Splits on newlines and runs match() on each line, deduplicating by error_class.
    """
    results = []
    seen_classes = set()
    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        for pm in match(line):
            if pm.error_class not in seen_classes:
                seen_classes.add(pm.error_class)
                results.append(pm)
    return results


def format_match(pm: PatternMatch, verbose: bool = False) -> dict:
    """Convert a PatternMatch to a dict suitable for JSON output."""
    out = {
        "layer": pm.layer,
        "layer_label": LAYER_LABELS.get(pm.layer, pm.layer),
        "error_class": pm.error_class,
        "severity": pm.severity,
        "confidence": pm.confidence,
        "signal": pm.signal,
        "root_cause": pm.root_cause,
        "next_command": pm.next_command,
        "fix": {
            "command": pm.fix_command,
            "description": pm.fix_description,
        },
    }
    if verbose:
        out["matched_text"] = pm.matched_text
    return out
