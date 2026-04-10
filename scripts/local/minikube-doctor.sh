#!/bin/bash
set -u -o pipefail

PROFILE="${1:-minikube}"

ok() {
  printf '[OK] %s\n' "$1"
}

warn() {
  printf '[WARN] %s\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1"
}

section() {
  printf '\n== %s ==\n' "$1"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

run_or_warn() {
  local description="$1"
  shift
  printf '$ %s\n' "$*"
  if ! "$@"; then
    warn "$description"
  fi
}

section "Tooling"
for cmd in docker minikube kubectl; do
  if has_cmd "$cmd"; then
    ok "$cmd found at $(command -v "$cmd")"
  else
    fail "$cmd is not installed or not on PATH"
  fi
done

section "Docker"
if has_cmd docker; then
  run_or_warn "Unable to show Docker context" docker context show
  run_or_warn "Unable to list Docker contexts" docker context ls
  if docker version >/dev/null 2>&1; then
    ok "Docker daemon is reachable"
    run_or_warn "Unable to inspect Docker containers" docker ps -a --filter "name=^${PROFILE}$" --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
  else
    fail "Docker daemon is not reachable"
  fi
fi

section "Minikube"
if has_cmd minikube; then
  run_or_warn "Unable to print Minikube version" minikube version
  run_or_warn "Unable to list Minikube profiles" minikube profile list
  if minikube status -p "$PROFILE" --output=json >/dev/null 2>&1; then
    ok "Minikube status is available for profile '$PROFILE'"
    minikube status -p "$PROFILE" --output=json
  else
    warn "Unable to get JSON status for profile '$PROFILE'; falling back to plain status"
    run_or_warn "Unable to inspect Minikube status" minikube status -p "$PROFILE"
  fi
fi

section "Kubeconfig"
if has_cmd kubectl; then
  current_context="$(kubectl config current-context 2>/dev/null || true)"
  if [ -n "$current_context" ]; then
    ok "Current kubectl context: $current_context"
  else
    warn "kubectl has no current context"
  fi

  run_or_warn "Unable to show effective kubeconfig" kubectl config view --minify

  if kubectl get nodes --request-timeout=5s >/dev/null 2>&1; then
    ok "kubectl can reach the current cluster"
    kubectl get nodes -o wide
  else
    warn "kubectl cannot reach the current cluster"
  fi
fi

section "Next Steps"
cat <<EOF
- If Docker is unhealthy, fix Docker Desktop first.
- If Docker is healthy but Minikube is down, run: ./scripts/local/restart-minikube.sh
- If the profile is badly corrupted and cluster state is disposable, run: ./scripts/local/restart-minikube.sh --recreate
EOF
