#!/bin/bash
set -euo pipefail

LABEL="com.local.minikube-ingress-forward"
PLIST="/Library/LaunchDaemons/${LABEL}.plist"
CALLING_USER="${SUDO_USER:-$(id -un)}"
CALLING_HOME="${HOME}"
CONTEXT="${CONTEXT:-minikube}"
NAMESPACE="${NAMESPACE:-ingress-nginx}"
SERVICE="${SERVICE:-svc/ingress-nginx-controller}"
LOCAL_PORT="${LOCAL_PORT:-80}"
SERVICE_PORT="${SERVICE_PORT:-80}"
ADDRESS="${ADDRESS:-127.0.0.1,::1}"
STDOUT_LOG="${STDOUT_LOG:-/usr/local/var/log/minikube-ingress-forward.out.log}"
STDERR_LOG="${STDERR_LOG:-/usr/local/var/log/minikube-ingress-forward.err.log}"

if [ -z "${KUBECTL:-}" ]; then
  if command -v kubectl >/dev/null 2>&1; then
    KUBECTL="$(command -v kubectl)"
  elif [ -x /usr/local/bin/kubectl ]; then
    KUBECTL="/usr/local/bin/kubectl"
  elif [ -x /opt/homebrew/bin/kubectl ]; then
    KUBECTL="/opt/homebrew/bin/kubectl"
  else
    KUBECTL="kubectl"
  fi
fi

if [ "${CALLING_USER}" != "$(id -un)" ] && command -v dscl >/dev/null 2>&1; then
  dscl_home="$(dscl . -read "/Users/${CALLING_USER}" NFSHomeDirectory 2>/dev/null | awk '{print $2}' || true)"
  if [ -n "${dscl_home}" ]; then
    CALLING_HOME="${dscl_home}"
  fi
fi

KUBECONFIG_PATH="${KUBECONFIG:-${CALLING_HOME}/.kube/config}"

usage() {
  cat <<EOF
Usage: $0 install|uninstall|restart|status

Installs a macOS launchd daemon that keeps this command running:
  kubectl --kubeconfig ${KUBECONFIG_PATH} --context ${CONTEXT} port-forward --address ${ADDRESS} -n ${NAMESPACE} ${SERVICE} ${LOCAL_PORT}:${SERVICE_PORT}

Environment overrides:
  KUBECTL=${KUBECTL}
  KUBECONFIG=${KUBECONFIG_PATH}
  CONTEXT=${CONTEXT}
  NAMESPACE=${NAMESPACE}
  SERVICE=${SERVICE}
  LOCAL_PORT=${LOCAL_PORT}
  SERVICE_PORT=${SERVICE_PORT}
  ADDRESS=${ADDRESS}
EOF
}

require_macos() {
  if [ "$(uname -s)" != "Darwin" ]; then
    echo "[FAIL] This installer is only for macOS launchd." >&2
    exit 1
  fi
}

require_file() {
  local path="$1"
  local description="$2"

  if [ ! -e "$path" ]; then
    echo "[FAIL] Missing ${description}: ${path}" >&2
    exit 1
  fi
}

warn_if_port_busy() {
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"${LOCAL_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[WARN] Something is already listening on local TCP port ${LOCAL_PORT}:"
    lsof -nP -iTCP:"${LOCAL_PORT}" -sTCP:LISTEN
    echo
    echo "Stop the existing listener first, then rerun:"
    echo "  sudo $0 install"
    exit 1
  fi
}

ensure_log_paths() {
  sudo install -d -o root -g wheel -m 0755 "$(dirname "${STDOUT_LOG}")"
  sudo install -d -o root -g wheel -m 0755 "$(dirname "${STDERR_LOG}")"
  sudo touch "${STDOUT_LOG}" "${STDERR_LOG}"
  sudo chown root:wheel "${STDOUT_LOG}" "${STDERR_LOG}"
  sudo chmod 0644 "${STDOUT_LOG}" "${STDERR_LOG}"
}

write_plist() {
  local tmp_plist
  tmp_plist="$(mktemp)"

  cat >"${tmp_plist}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${KUBECTL}</string>
    <string>--kubeconfig</string>
    <string>${KUBECONFIG_PATH}</string>
    <string>--context</string>
    <string>${CONTEXT}</string>
    <string>port-forward</string>
    <string>--address</string>
    <string>${ADDRESS}</string>
    <string>-n</string>
    <string>${NAMESPACE}</string>
    <string>${SERVICE}</string>
    <string>${LOCAL_PORT}:${SERVICE_PORT}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>${STDOUT_LOG}</string>
  <key>StandardErrorPath</key>
  <string>${STDERR_LOG}</string>
</dict>
</plist>
EOF

  sudo install -o root -g wheel -m 0644 "${tmp_plist}" "${PLIST}"
  rm -f "${tmp_plist}"
}

install_daemon() {
  require_macos
  require_file "${KUBECTL}" "kubectl binary"
  require_file "${KUBECONFIG_PATH}" "kubeconfig"

  if sudo launchctl print "system/${LABEL}" >/dev/null 2>&1; then
    sudo launchctl bootout system "${PLIST}" || true
  fi

  warn_if_port_busy
  ensure_log_paths
  write_plist
  sudo launchctl bootstrap system "${PLIST}"
  sudo launchctl enable "system/${LABEL}"
  sudo launchctl kickstart -k "system/${LABEL}"

  echo "[OK] Installed launchd daemon: ${LABEL}"
  echo "[OK] Logs:"
  echo "  ${STDOUT_LOG}"
  echo "  ${STDERR_LOG}"
}

uninstall_daemon() {
  require_macos

  if sudo launchctl print "system/${LABEL}" >/dev/null 2>&1; then
    sudo launchctl bootout system "${PLIST}" || true
  fi

  sudo rm -f "${PLIST}"
  echo "[OK] Removed launchd daemon: ${LABEL}"
}

status_daemon() {
  require_macos

  if sudo launchctl print "system/${LABEL}"; then
    echo
    echo "[OK] ${LABEL} is installed."
    if command -v lsof >/dev/null 2>&1; then
      echo
      echo "[INFO] Current listener on local TCP port ${LOCAL_PORT}:"
      lsof -nP -iTCP:"${LOCAL_PORT}" -sTCP:LISTEN || true
    fi
  else
    echo "[WARN] ${LABEL} is not installed or not loaded."
    exit 1
  fi
}

case "${1:-}" in
  install)
    install_daemon
    ;;
  uninstall)
    uninstall_daemon
    ;;
  restart)
    uninstall_daemon
    install_daemon
    ;;
  status)
    status_daemon
    ;;
  -h|--help|"")
    usage
    ;;
  *)
    echo "[FAIL] Unknown command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
