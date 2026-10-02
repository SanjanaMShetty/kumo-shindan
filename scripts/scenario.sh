#!/usr/bin/env bash
set -euo pipefail

namespace="kubesleuth-lab"
command="${1:-}"
scenario="${2:-}"

cleanup_scenarios() {
  kubectl delete deployment \
    checkout-api payments-web report-worker batch-processor analytics-ui \
    uploads-service web-frontend inventory-api session-store notifications-svc \
    broken-image crash-loop-demo \
    -n "$namespace" --ignore-not-found --wait=true

  kubectl delete service web-frontend \
    -n "$namespace" --ignore-not-found --wait=true

  kubectl delete persistentvolumeclaim uploads-data \
    -n "$namespace" --ignore-not-found --wait=true
}

case "$command" in
  apply)
    if [[ -z "$scenario" || ! -f "deploy/scenarios/$scenario/manifest.yaml" ]]; then
      echo "Usage: scripts/scenario.sh apply <scenario-name>" >&2
      exit 2
    fi
    cleanup_scenarios
    kubectl apply -f "deploy/scenarios/$scenario/manifest.yaml"
    ;;
  delete)
    cleanup_scenarios
    ;;
  status)
    kubectl get pods,services,persistentvolumeclaims -n "$namespace"
    ;;
  *)
    echo "Usage: scripts/scenario.sh apply <scenario-name> | delete | status" >&2
    exit 2
    ;;
esac
