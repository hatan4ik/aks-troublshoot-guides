#!/bin/bash
# GitOps health diagnostics (Argo CD / Flux)
set -euo pipefail

echo "📦 GitOps Diagnostics"
echo "Timestamp: $(date)"

# ── Context check ────────────────────────────────────────────────────────────
CURRENT_CTX="$(kubectl config current-context 2>/dev/null || echo "<none>")"
echo -e "\n🔧 Active kubectl context: ${CURRENT_CTX}"
if [[ "${CURRENT_CTX}" == "<none>" ]]; then
  echo "  ⚠️  No active context — kubectl commands will fail."
fi

# ── Argo CD ──────────────────────────────────────────────────────────────────
echo -e "\n🚀 Argo CD"

ARGOCD_NS="${ARGOCD_NAMESPACE:-argocd}"

# Check controller pods — ArgoCD uses app.kubernetes.io/name=argocd-*, no part-of label
ARGOCD_PODS="$(kubectl get pods -n "${ARGOCD_NS}" --no-headers 2>/dev/null)" || true

if [[ -n "${ARGOCD_PODS}" ]]; then
  RUNNING=$(echo "${ARGOCD_PODS}" | grep -c "Running" || true)
  TOTAL=$(echo "${ARGOCD_PODS}" | wc -l | tr -d ' ')
  echo "  Controllers (namespace: ${ARGOCD_NS}): ${RUNNING}/${TOTAL} Running"
  kubectl get pods -n "${ARGOCD_NS}" 2>/dev/null | sed 's/^/  /'
else
  if kubectl get namespace "${ARGOCD_NS}" >/dev/null 2>&1; then
    echo "  ❌ Namespace '${ARGOCD_NS}' is empty — install manifest was never applied."
    echo "     Fix: kubectl apply --server-side --force-conflicts -n ${ARGOCD_NS} -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"
  else
    echo "  ℹ️  ArgoCD namespace '${ARGOCD_NS}' not found — ArgoCD not installed."
    echo "     Fix: kubectl create namespace ${ARGOCD_NS} && kubectl apply --server-side --force-conflicts -n ${ARGOCD_NS} -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"
  fi
fi

# Check CRD and Application resources — direct lookup is faster and more reliable than api-resources pipe
if kubectl get crd applications.argoproj.io >/dev/null 2>&1; then
  echo "  CRD: argoproj.io/Application ✅"
  APP_COUNT="$(kubectl get applications -A --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${APP_COUNT}" -gt 0 ]]; then
    echo "  Applications (${APP_COUNT}):"
    kubectl get applications -A 2>/dev/null | sed 's/^/  /'
  else
    echo "  ℹ️  No Application resources found (controllers installed, nothing deployed yet)."
  fi
else
  echo "  ℹ️  ArgoCD CRDs not installed."
fi

# ── Flux CD ──────────────────────────────────────────────────────────────────
echo -e "\n🚀 Flux CD"

FLUX_NS="${FLUX_NAMESPACE:-flux-system}"

# Check controller pods
FLUX_PODS="$(kubectl get pods -n "${FLUX_NS}" --no-headers 2>/dev/null)" || true

if [[ -n "${FLUX_PODS}" ]]; then
  echo "  Controllers (namespace: ${FLUX_NS}):"
  kubectl get pods -n "${FLUX_NS}" -o wide 2>/dev/null | sed 's/^/  /'
else
  if kubectl get namespace "${FLUX_NS}" >/dev/null 2>&1; then
    echo "  ⚠️  Namespace '${FLUX_NS}' exists but no Flux pods found."
  else
    echo "  ℹ️  Flux namespace '${FLUX_NS}' not found — Flux may not be installed."
  fi
fi

# Kustomizations
if kubectl get crd kustomizations.kustomize.toolkit.fluxcd.io >/dev/null 2>&1; then
  echo "  CRD: kustomize.toolkit.fluxcd.io/Kustomization ✅"
  KS_COUNT="$(kubectl get kustomizations -A --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${KS_COUNT}" -gt 0 ]]; then
    echo "  Kustomizations (${KS_COUNT}):"
    kubectl get kustomizations -A 2>/dev/null | sed 's/^/  /'

    echo "  🔍 Checking for Not Ready Kustomizations:"
    kubectl get kustomizations -A --no-headers 2>/dev/null | grep -v "True" | awk '{print "    ⚠️  Kustomization " $2 " in " $1 " is not Ready."}' || true
  else
    echo "  ℹ️  No Kustomization resources found."
  fi
else
  echo "  ℹ️  Flux Kustomization CRDs not installed."
fi

# HelmReleases
if kubectl get crd helmreleases.helm.toolkit.fluxcd.io >/dev/null 2>&1; then
  echo "  CRD: helm.toolkit.fluxcd.io/HelmRelease ✅"
  HR_COUNT="$(kubectl get helmreleases -A --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${HR_COUNT}" -gt 0 ]]; then
    echo "  HelmReleases (${HR_COUNT}):"
    kubectl get helmreleases -A 2>/dev/null | sed 's/^/  /'
  else
    echo "  ℹ️  No HelmRelease resources found."
  fi
else
  echo "  ℹ️  Flux HelmRelease CRDs not installed."
fi

# GitRepositories (useful for Flux source detection)
if kubectl get crd gitrepositories.source.toolkit.fluxcd.io >/dev/null 2>&1; then
  GR_COUNT="$(kubectl get gitrepositories -A --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${GR_COUNT}" -gt 0 ]]; then
    echo "  GitRepositories (${GR_COUNT}):"
    kubectl get gitrepositories -A 2>/dev/null | sed 's/^/  /'
  fi
fi

if kubectl get crd helmrepositories.source.toolkit.fluxcd.io >/dev/null 2>&1; then
  HELM_REPO_COUNT="$(kubectl get helmrepositories -A --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${HELM_REPO_COUNT}" -gt 0 ]]; then
    echo "  HelmRepositories (${HELM_REPO_COUNT}):"
    kubectl get helmrepositories -A 2>/dev/null | sed 's/^/  /'
  fi
fi

echo -e "\n🖥 Flux UI (optional Weave GitOps)"
if kubectl get svc ww-gitops-weave-gitops -n "${FLUX_NS}" >/dev/null 2>&1; then
  kubectl get pods,svc -n "${FLUX_NS}" -l app.kubernetes.io/name=weave-gitops 2>/dev/null | sed 's/^/  /'
  echo "  Access: kubectl port-forward svc/ww-gitops-weave-gitops -n ${FLUX_NS} 9001:9001"
  echo "  URL: http://localhost:9001"
else
  echo "  ℹ️  Weave GitOps UI not installed. Flux itself has no built-in GUI."
  echo "     See docs/GITOPS-MINIKUBE-INSTALL.md for the optional dashboard install."
fi

# ── Recent GitOps Warning Events ─────────────────────────────────────────────
echo -e "\n📜 Recent GitOps Warning Events"
EVENTS="$(kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp 2>/dev/null \
  | grep -iE "sync|git|helm|kustomize|apply" | tail -30)" || true
if [[ -n "${EVENTS}" ]]; then
  echo "${EVENTS}"
else
  echo "  ℹ️  No matching warning events found."
fi

echo -e "\n🛠 Repo Remediation Preview Commands"
echo "  python3 ./k8s-diagnostics-cli.py suggest"
echo "  python3 ./k8s-diagnostics-cli.py heal --dry-run"

echo -e "\n✅ Complete"
�� Complete"
