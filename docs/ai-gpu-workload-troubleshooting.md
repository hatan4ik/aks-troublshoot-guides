# AI/GPU Workload Troubleshooting

## Scope

Use this guide when ML training, inference, vector search, or model-serving workloads fail on Kubernetes because of GPU scheduling, NVIDIA runtime, node pool, memory, or image/runtime mismatches.

This applies to AKS, EKS, GKE, and bare-metal clusters. Provider details differ, but the Kubernetes failure path is the same:

```text
Pod spec -> scheduler -> GPU node pool -> device plugin -> container runtime -> model process
```

Do not start by changing the model image or node pool. First prove which layer is failing.

## Fast Triage

```bash
kubectl get nodes -o wide
kubectl get nodes --show-labels | grep -Ei "gpu|nvidia|accelerator|instance-type"
kubectl describe node <gpu-node> | grep -A30 -E "Capacity|Allocatable|Taints"
kubectl get pods -A -o wide | grep -Ei "gpu|nvidia|cuda|triton|kserve|ray|vllm"
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -80
kubectl get daemonset -A | grep -Ei "nvidia|gpu|device"
kubectl get pods -A | grep -Ei "nvidia|gpu|device"
```

If the pod is `Pending`, inspect scheduling first:

```bash
kubectl describe pod <pod> -n <namespace>
kubectl get quota -n <namespace>
kubectl get limitrange -n <namespace>
```

If the pod starts and then fails, inspect runtime and model logs:

```bash
kubectl logs <pod> -n <namespace> --all-containers --tail=200
kubectl logs <pod> -n <namespace> --previous --all-containers --tail=200
kubectl describe pod <pod> -n <namespace>
```

If the NVIDIA device plugin exists, inspect it:

```bash
kubectl get pods -A -l app=nvidia-device-plugin-daemonset -o wide
kubectl logs -n kube-system daemonset/nvidia-device-plugin-daemonset --tail=200
```

Some clusters install the plugin under a different label or namespace:

```bash
kubectl get pods -A | grep -Ei "nvidia|device-plugin|gpu-operator"
```

## Failure Matrix

| Symptom | Likely cause | What to verify | Safe first action |
|---|---|---|---|
| Pod is `Pending` with `Insufficient nvidia.com/gpu` | No allocatable GPUs, wrong node pool, node taint, namespace quota | `kubectl describe pod`, `kubectl describe node`, `kubectl get quota` | Fix selector/toleration/quota, or scale GPU pool |
| GPU node exists but allocatable GPU is `0` | Device plugin not healthy, driver not loaded, runtime mismatch | Node capacity/allocatable, plugin pod logs | Fix plugin/driver/runtime before changing workload |
| NVIDIA plugin `CrashLoopBackOff` | Driver/kernel/runtime mismatch, unsupported node image, MIG misconfiguration | Device plugin logs, node OS image, runtime class | Restart plugin only after confirming driver path |
| Pod starts then exits with CUDA error | Image CUDA version incompatible with host driver | Application logs, image tag, node driver version | Use image compatible with driver, or upgrade GPU node image |
| Training pod OOMKilled | Kubernetes memory limit too low, data loader memory, checkpoint burst | `Last State`, cgroup memory, pod events | Increase memory request/limit or reduce batch/data loader pressure |
| Inference fails with GPU OOM | Model weights, KV cache, batch size, tensor parallelism | Model logs, GPU utilization, request concurrency | Reduce batch/concurrency, enable quantization, shard model |
| GPU pod scheduled on CPU node | Missing node selector, affinity, taint/toleration | Pod spec, node labels, scheduler event | Add explicit GPU node placement rules |
| Slow inference but no crash | CPU bottleneck, cold starts, storage pull latency, network path | CPU throttling, startup latency, image pull timing | Right-size CPU, pre-warm, cache model artifacts |

## Scheduling Checklist

GPU pods should usually be explicit:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
nodeSelector:
  accelerator: nvidia
tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
```

Cluster labels vary. Use the labels already present on your nodes:

```bash
kubectl get nodes --show-labels | grep -Ei "gpu|nvidia|accelerator"
```

Avoid relying only on node names. Node names change during upgrades and autoscaling.

## Runtime Checklist

Run these from a debug workload only if your platform allows it:

```bash
kubectl exec -n <namespace> <gpu-pod> -- nvidia-smi
kubectl exec -n <namespace> <gpu-pod> -- python -c "import torch; print(torch.cuda.is_available())"
```

If `nvidia-smi` is missing inside the application image, that does not always mean the GPU is unavailable. Prefer checking application framework detection and Kubernetes allocated resources:

```bash
kubectl get pod <pod> -n <namespace> -o jsonpath='{.spec.containers[*].resources}'
kubectl describe node <gpu-node> | grep -A20 "Allocated resources"
```

## Provider Notes

### AKS

- Use a dedicated GPU node pool. Validate node SKU, taints, and autoscaler state before changing workload YAML.
- GPU nodes can require the NVIDIA device plugin or GPU operator depending on node image and cluster setup.
- Check Azure CNI IP capacity when GPU pods are stuck `Pending` but GPU capacity exists.
- If model images pull from ACR, validate kubelet identity or workload identity for ACR access before blaming GPU scheduling.

### EKS

- GPU scheduling depends on GPU AMI support, NVIDIA device plugin, and AWS VPC CNI IP availability.
- IRSA is usually not involved in GPU device allocation, but it can break model artifact access from S3.
- If using Karpenter, validate provisioner/node pool requirements and instance family filters for GPU instance types.

### GKE

- Validate GPU node pool accelerator type, driver installation mode, node taints, and GKE version support.
- Workload Identity issues can look like model startup failures when the container cannot fetch artifacts from GCS.
- If using Autopilot, confirm the GPU resource class and platform limitations before applying standard node-pool assumptions.

### Bare Metal

- Confirm BIOS, PCIe visibility, driver installation, container runtime configuration, and device plugin health.
- Track GPU/node mapping in inventory. Kubernetes labels should reflect the physical hardware inventory.
- Treat driver upgrades like node maintenance, not normal application redeploys.

## Remediation Guardrails

- Do not force delete long-running training jobs unless checkpoint safety is confirmed.
- Do not remove node taints globally to "make it schedule"; that can move non-GPU workloads onto expensive GPU nodes.
- Do not mix unrelated fixes. Separate image pull/authentication issues from GPU allocation issues.
- Prefer canarying one GPU workload after driver/plugin changes before restarting every model-serving pod.

## Interview Signals

A strong answer should explain:

- The difference between Kubernetes memory OOM and GPU VRAM OOM.
- Why `limits.nvidia.com/gpu` is normally required and requests are not set separately for GPUs.
- How a healthy GPU node can still expose zero allocatable GPUs when the device plugin is broken.
- How cloud identity failures can look like model failures when artifacts are loaded at startup.
