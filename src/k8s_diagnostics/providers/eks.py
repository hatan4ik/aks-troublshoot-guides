"""EKS-specific (AWS) provider checks.

Requires: boto3 botocore

All checks degrade gracefully if:
  - boto3 is not installed
  - AWS credentials are not configured (no ~/.aws/credentials, no IRSA, no instance profile)
  - Required IAM permissions are missing (returns partial results)

How AWS metadata is resolved:
  Node spec.providerID format:
      aws:///<az>/<instance-id>
  Cluster name and region are read from the node label:
      eks.amazonaws.com/nodegroup  (node group label)
      topology.kubernetes.io/region
  The EKS cluster name is taken from the kube-system configmap 'aws-auth'
  or derived from node labels / instance tags.
"""

from typing import Dict, List, Optional
from .base import BaseProviderChecker, ProviderIssue


class EKSChecker(BaseProviderChecker):
    """Runs AWS-layer checks for EKS clusters."""

    @property
    def provider_name(self) -> str:
        return "eks"

    def run_all_checks(self, k8s_client) -> List[ProviderIssue]:
        meta = self._get_cluster_metadata(k8s_client)
        if meta is None:
            return [ProviderIssue(
                "eks_metadata_unavailable", "low",
                "Could not derive AWS metadata from node providerIDs — "
                "ensure nodes have aws:// providerID set",
                "Run: kubectl get nodes -o jsonpath='{.items[*].spec.providerID}'",
            )]

        issues: List[ProviderIssue] = []
        issues.extend(self._check_vpc_cni_ip_exhaustion(meta, k8s_client))
        issues.extend(self._check_node_iam_role(meta))
        issues.extend(self._check_ecr_pull_permission(meta))
        issues.extend(self._check_security_groups(meta, k8s_client))
        issues.extend(self._check_target_group_health(meta, k8s_client))
        issues.extend(self._check_irsa_token_volume(k8s_client))
        issues.extend(self._check_fargate_profiles(meta, k8s_client))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Metadata extraction
    # ─────────────────────────────────────────────────────────────

    def _get_cluster_metadata(self, k8s_client) -> Optional[Dict]:
        try:
            nodes = k8s_client.v1.list_node().items
            if not nodes:
                return None

            provider_id = nodes[0].spec.provider_id or ""
            if not provider_id.startswith("aws://"):
                return None

            # aws:///<az>/<instance-id>  or  aws://<az>/<instance-id>
            parts = provider_id.lstrip("aws:///").split("/")
            az = parts[0] if parts else ""
            region = az[:-1] if az else ""  # us-east-1a → us-east-1
            instance_ids = [
                (p.lstrip("aws:///").split("/") + [""])[1]
                for p in [n.spec.provider_id or "" for n in nodes]
                if p.startswith("aws://")
            ]

            # Try to get cluster name from node labels
            labels = nodes[0].metadata.labels or {}
            cluster_name = (
                labels.get("eks.amazonaws.com/cluster-name") or
                labels.get("alpha.eksctl.io/cluster-name") or
                "unknown"
            )

            # Get account ID from instance profile if possible
            account_id = self._get_account_id()

            return {
                "region": region,
                "availability_zone": az,
                "cluster_name": cluster_name,
                "instance_ids": instance_ids[:10],  # cap to avoid huge API calls
                "account_id": account_id,
                "node_count": len(nodes),
            }
        except Exception:
            return None

    def _get_boto3_client(self, service: str, region: str):
        """Return a boto3 client or None if unavailable."""
        try:
            import boto3
            return boto3.client(service, region_name=region)
        except ImportError:
            return None
        except Exception:
            return None

    def _get_account_id(self) -> Optional[str]:
        try:
            import boto3
            sts = boto3.client("sts")
            return sts.get_caller_identity()["Account"]
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────
    # Check 1: VPC CNI IP exhaustion
    # ─────────────────────────────────────────────────────────────

    def _check_vpc_cni_ip_exhaustion(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Detect aws-node (VPC CNI) running out of IPs in node subnets."""
        ec2 = self._get_boto3_client("ec2", meta["region"])
        if ec2 is None:
            return [self._sdk_not_available("eks_vpc_cni_ip_exhaustion",
                "pip install boto3")]

        issues = []
        try:
            if not meta["instance_ids"]:
                return []

            # Get subnet IDs used by nodes
            resp = ec2.describe_instances(InstanceIds=meta["instance_ids"])
            subnet_ids = list({
                i["SubnetId"]
                for r in resp.get("Reservations", [])
                for i in r.get("Instances", [])
                if "SubnetId" in i
            })

            if not subnet_ids:
                return []

            subnets_resp = ec2.describe_subnets(SubnetIds=subnet_ids)
            for subnet in subnets_resp.get("Subnets", []):
                available = subnet.get("AvailableIpAddressCount", 9999)
                if available < 10:
                    issues.append(ProviderIssue(
                        "eks_vpc_cni_ip_exhaustion", "high",
                        f"Subnet '{subnet['SubnetId']}' (AZ: {subnet.get('AvailabilityZone')}) "
                        f"has only {available} IPs remaining. "
                        "New pods will fail to get an IP and stay in ContainerCreating.",
                        "Expand the subnet CIDR or enable VPC CNI prefix delegation: "
                        "kubectl set env daemonset aws-node -n kube-system "
                        "ENABLE_PREFIX_DELEGATION=true",
                    ))
        except Exception as e:
            issues.append(self._check_error("eks_vpc_cni_ip_exhaustion", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 2: Node IAM role policies
    # ─────────────────────────────────────────────────────────────

    def _check_node_iam_role(self, meta: Dict) -> List[ProviderIssue]:
        """Verify node instance profile has required EKS managed policies."""
        ec2 = self._get_boto3_client("ec2", meta["region"])
        iam = self._get_boto3_client("iam", meta["region"])
        if ec2 is None or iam is None:
            return [self._sdk_not_available("eks_node_iam_missing",
                "pip install boto3")]

        REQUIRED_POLICIES = {
            "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
            "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
            "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        }

        issues = []
        try:
            if not meta["instance_ids"]:
                return []

            resp = ec2.describe_instances(InstanceIds=meta["instance_ids"][:1])
            instance = (resp.get("Reservations", [{}])[0]
                           .get("Instances", [{}])[0])
            profile_arn = (instance.get("IamInstanceProfile") or {}).get("Arn")
            if not profile_arn:
                issues.append(ProviderIssue(
                    "eks_node_iam_missing", "high",
                    "Node instance has no IAM instance profile attached. "
                    "Worker nodes cannot authenticate with the EKS cluster.",
                    "Attach the node IAM role to the instance profile: "
                    "aws ec2 associate-iam-instance-profile --instance-id <id> "
                    "--iam-instance-profile Name=<profile-name>",
                ))
                return issues

            profile_name = profile_arn.split("/")[-1]
            profile = iam.get_instance_profile(InstanceProfileName=profile_name)
            roles = profile["InstanceProfile"].get("Roles", [])
            if not roles:
                return issues

            role_name = roles[0]["RoleName"]
            attached = iam.list_attached_role_policies(RoleName=role_name)
            attached_arns = {p["PolicyArn"] for p in
                             attached.get("AttachedPolicies", [])}

            missing = REQUIRED_POLICIES - attached_arns
            if missing:
                issues.append(ProviderIssue(
                    "eks_node_iam_missing", "high",
                    f"Node role '{role_name}' is missing required policies: "
                    + ", ".join(p.split("/")[-1] for p in missing),
                    "aws iam attach-role-policy --role-name "
                    f"{role_name} --policy-arn <policy-arn> (repeat for each missing policy)",
                ))
        except Exception as e:
            issues.append(self._check_error("eks_node_iam_missing", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 3: ECR pull permission
    # ─────────────────────────────────────────────────────────────

    def _check_ecr_pull_permission(self, meta: Dict) -> List[ProviderIssue]:
        """Verify the node role can pull from ECR (AmazonEC2ContainerRegistryReadOnly)."""
        # This is partially covered by node IAM check; here we test ECR auth directly.
        ecr = self._get_boto3_client("ecr", meta["region"])
        if ecr is None:
            return [self._sdk_not_available("eks_ecr_pull_denied",
                "pip install boto3")]

        issues = []
        try:
            # If we can call get_authorization_token, the role has ECR access
            ecr.get_authorization_token()
        except Exception as e:
            err = str(e)
            if "AccessDenied" in err or "not authorized" in err.lower():
                issues.append(ProviderIssue(
                    "eks_ecr_pull_denied", "high",
                    "ECR authorization token request denied — node role lacks "
                    "AmazonEC2ContainerRegistryReadOnly or equivalent policy. "
                    "Pods pulling from ECR will get ImagePullBackOff.",
                    "aws iam attach-role-policy --role-name <node-role> "
                    "--policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
                ))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 4: Security group blocking pod traffic
    # ─────────────────────────────────────────────────────────────

    def _check_security_groups(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Detect security groups that block required inter-node and API server ports."""
        ec2 = self._get_boto3_client("ec2", meta["region"])
        if ec2 is None:
            return [self._sdk_not_available("eks_sg_blocking",
                "pip install boto3")]

        REQUIRED_INBOUND = [
            (443, "API server to kubelet"),
            (10250, "kubelet API"),
            (53, "DNS UDP/TCP"),
        ]

        issues = []
        try:
            if not meta["instance_ids"]:
                return []

            resp = ec2.describe_instances(InstanceIds=meta["instance_ids"][:3])
            sg_ids = list({
                sg["GroupId"]
                for r in resp.get("Reservations", [])
                for i in r.get("Instances", [])
                for sg in i.get("SecurityGroups", [])
            })

            if not sg_ids:
                return []

            sgs_resp = ec2.describe_security_groups(GroupIds=sg_ids)
            for sg in sgs_resp.get("SecurityGroups", []):
                inbound_ports = set()
                for rule in sg.get("IpPermissions", []):
                    from_port = rule.get("FromPort", 0)
                    to_port = rule.get("ToPort", 65535)
                    if from_port == -1:  # all traffic
                        inbound_ports.update(range(0, 65536))
                        break
                    inbound_ports.update(range(from_port, to_port + 1))

                blocked = [
                    f"port {port} ({desc})"
                    for port, desc in REQUIRED_INBOUND
                    if port not in inbound_ports
                ]
                if blocked:
                    issues.append(ProviderIssue(
                        "eks_sg_blocking", "high",
                        f"Security group '{sg['GroupId']}' ({sg.get('GroupName')}) "
                        f"does not allow inbound traffic on: {', '.join(blocked)}. "
                        "Cluster communication and kubectl exec/logs will fail.",
                        "aws ec2 authorize-security-group-ingress --group-id "
                        f"{sg['GroupId']} --protocol tcp --port <port> --cidr <node-cidr>",
                    ))
        except Exception as e:
            issues.append(self._check_error("eks_sg_blocking", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 5: ALB/NLB target group health
    # ─────────────────────────────────────────────────────────────

    def _check_target_group_health(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Find ELB/ALB target groups where all targets are unhealthy."""
        elbv2 = self._get_boto3_client("elbv2", meta["region"])
        if elbv2 is None:
            return [self._sdk_not_available("eks_target_group_unhealthy",
                "pip install boto3")]

        issues = []
        try:
            tgs = elbv2.describe_target_groups().get("TargetGroups", [])
            for tg in tgs:
                health = elbv2.describe_target_health(
                    TargetGroupArn=tg["TargetGroupArn"]
                ).get("TargetHealthDescriptions", [])
                if not health:
                    continue
                all_unhealthy = all(
                    h.get("TargetHealth", {}).get("State") != "healthy"
                    for h in health
                )
                if all_unhealthy:
                    states = list({
                        h.get("TargetHealth", {}).get("State", "unknown")
                        for h in health
                    })
                    issues.append(ProviderIssue(
                        "eks_target_group_unhealthy", "high",
                        f"Target group '{tg['TargetGroupName']}' has all targets unhealthy "
                        f"(states: {states}). LoadBalancer traffic is being dropped.",
                        "aws elbv2 describe-target-health --target-group-arn "
                        f"{tg['TargetGroupArn']} — "
                        "verify NodePort is reachable on nodes and security groups allow health probe port",
                    ))
        except Exception as e:
            issues.append(self._check_error("eks_target_group_unhealthy", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 6: IRSA token volume not mounting
    # ─────────────────────────────────────────────────────────────

    def _check_irsa_token_volume(self, k8s_client) -> List[ProviderIssue]:
        """Detect pods that reference an IRSA ServiceAccount but lack the token volume.

        IRSA works by projecting a service account token into the pod via a volume.
        If the OIDC provider is misconfigured, the token projection still happens
        but the token will be rejected by AWS STS. We detect pods with the IRSA
        annotation on their ServiceAccount but missing the projected token volume.
        """
        issues = []
        try:
            pods = k8s_client.v1.list_pod_for_all_namespaces().items
            # Cache service account annotations per namespace
            sa_cache: Dict[str, Dict[str, str]] = {}

            def _get_sa_annotations(ns: str, sa_name: str) -> Dict[str, str]:
                key = f"{ns}/{sa_name}"
                if key not in sa_cache:
                    try:
                        sa = k8s_client.v1.read_namespaced_service_account(sa_name, ns)
                        sa_cache[key] = sa.metadata.annotations or {}
                    except Exception:
                        sa_cache[key] = {}
                return sa_cache[key]

            for pod in pods:
                sa_name = pod.spec.service_account_name or "default"
                annotations = _get_sa_annotations(pod.metadata.namespace, sa_name)
                irsa_role = annotations.get("eks.amazonaws.com/role-arn")
                if not irsa_role:
                    continue

                # Check for projected token volume
                has_token_volume = any(
                    vol.projected and any(
                        src.service_account_token
                        for src in (vol.projected.sources or [])
                    )
                    for vol in (pod.spec.volumes or [])
                )
                if not has_token_volume:
                    issues.append(ProviderIssue(
                        "eks_irsa_token_missing", "medium",
                        f"Pod '{pod.metadata.namespace}/{pod.metadata.name}' uses "
                        f"ServiceAccount '{sa_name}' with IRSA role '{irsa_role}' "
                        "but has no projected service account token volume. "
                        "AWS SDK calls will fail with credential errors.",
                        "Ensure the EKS OIDC provider is configured and the pod spec "
                        "does not override automountServiceAccountToken=false. "
                        "Check: kubectl describe pod <pod> | grep -A5 Volumes",
                    ))
        except Exception as e:
            issues.append(self._check_error("eks_irsa_token_missing", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 7: Fargate profile coverage
    # ─────────────────────────────────────────────────────────────

    def _check_fargate_profiles(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Find Pending pods in namespaces with no matching Fargate profile."""
        if meta["cluster_name"] == "unknown":
            return []

        eks = self._get_boto3_client("eks", meta["region"])
        if eks is None:
            return [self._sdk_not_available("eks_fargate_no_profile",
                "pip install boto3")]

        issues = []
        try:
            profiles_resp = eks.list_fargate_profiles(clusterName=meta["cluster_name"])
            profile_names = profiles_resp.get("fargateProfileNames", [])
            if not profile_names:
                return []

            # Get all Fargate profile selectors
            covered_namespaces = set()
            for name in profile_names:
                profile = eks.describe_fargate_profile(
                    clusterName=meta["cluster_name"], fargateProfileName=name
                )
                for sel in profile.get("fargateProfile", {}).get("selectors", []):
                    covered_namespaces.add(sel.get("namespace"))

            # Check for Pending pods in namespaces not covered by any profile
            pods = k8s_client.v1.list_pod_for_all_namespaces().items
            pending = [
                f"{p.metadata.namespace}/{p.metadata.name}"
                for p in pods
                if p.status.phase == "Pending"
                and p.metadata.namespace not in covered_namespaces
                and not p.spec.node_name  # truly unscheduled
            ]
            if pending:
                issues.append(ProviderIssue(
                    "eks_fargate_no_profile", "high",
                    f"{len(pending)} Pending pod(s) in namespaces with no Fargate profile: "
                    + ", ".join(pending[:5]),
                    "Create a Fargate profile covering the namespace: "
                    "aws eks create-fargate-profile --cluster-name "
                    f"{meta['cluster_name']} --fargate-profile-name <name> "
                    "--selectors namespace=<ns>",
                ))
        except Exception as e:
            issues.append(self._check_error("eks_fargate_no_profile", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _sdk_not_available(issue_type: str, install_hint: str) -> ProviderIssue:
        return ProviderIssue(
            issue_type, "info",
            "AWS SDK (boto3) not installed or credentials not configured — check skipped",
            f"To enable: {install_hint} && aws configure (or configure instance profile/IRSA)",
        )

    @staticmethod
    def _check_error(issue_type: str, error: str) -> ProviderIssue:
        return ProviderIssue(
            issue_type, "info",
            f"Check could not complete: {error[:200]}",
            "Ensure AWS credentials are configured: aws configure or instance profile",
        )
