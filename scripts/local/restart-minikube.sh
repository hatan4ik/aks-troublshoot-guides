#!/bin/bash
set -euo pipefail

PROFILE="minikube"
DRIVER="docker"
KUBERNETES_VERSION=""
RECREATE=0

usage() {
  cat <<EOF
Usage: $0 [--profile NAME] [--driver DRIVER] [--kubernetes-version VERSION] [--recreate]

Examples:
  $0
  $0 --profile minikube
  $0 --kubernetes-version v1.35.1
  $0 --recreate

Notes:
  --recreate deletes the local Minikube profile before starting it again.
  This is destructive to the local cluster state.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --driver)
      DRIVER="$2"
      shift 2
      ;;
    --kubernetes-version)
      KUBERNETES_VERSION="$2"
      shift 2
      ;;
    --recreate)
      RECREATE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

for cmd in docker minikube kubectl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[FAIL] Missing required command: $cmd" >&2
    exit 1
  fi
done

echo "== Docker =="
if ! docker version >/dev/null 2>&1; then
  echo "[FAIL] Docker daemon is not reachable." >&2
  if [ "$(uname -s)" = "Darwin" ] && [ -d "/Applications/Docker.app" ]; then
    echo "Start Docker Desktop first: open -a Docker" >&2
  fi
  exit 1
fi
echo "[OK] Docker daemon is reachable"

echo
echo "== Current Minikube Status =="
minikube status -p "$PROFILE" || true

if [ "$RECREATE" -eq 1 ]; then
  echo
  echo "== Recreate Profile =="
  echo "[WARN] Deleting Minikube profile '$PROFILE'"
  minikube delete -p "$PROFILE"
fi

start_args=(start -p "$PROFILE" --driver="$DRIVER")
if [ -n "$KUBERNETES_VERSION" ]; then
  start_args+=(--kubernetes-version="$KUBERNETES_VERSION")
fi

echo
echo "== Start Minikube =="
minikube "${start_args[@]}"

echo
echo "== Verify =="
minikube status -p "$PROFILE" --output=json
kubectl get nodes -o wide
kubectl get pods -A

echo
echo "[OK] Minikube recovery completed"
