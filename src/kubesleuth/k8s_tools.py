from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

_core_v1 = None


def _api():
    global _core_v1

    if _core_v1 is None:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()

        _core_v1 = client.CoreV1Api()

    return _core_v1


def _container_statuses(statuses):
    result = []

    for item in statuses or []:
        state = item.state
        if state and state.waiting:
            current_state = {
                "state": "waiting",
                "reason": state.waiting.reason,
                "message": state.waiting.message,
            }
        elif state and state.terminated:
            current_state = {
                "state": "terminated",
                "reason": state.terminated.reason,
                "exit_code": state.terminated.exit_code,
            }
        else:
            current_state = {"state": "running"}

        result.append(
            {
                "name": item.name,
                "ready": item.ready,
                "restart_count": item.restart_count,
                **current_state,
            }
        )

    return result


def list_pods(namespace: str) -> list[dict]:
    """List pod health and container states in a namespace."""
    pods = _api().list_namespaced_pod(namespace=namespace).items
    return [
        {
            "name": pod.metadata.name,
            "phase": pod.status.phase,
            "node": pod.spec.node_name,
            "pod_ip": pod.status.pod_ip,
            "containers": _container_statuses(pod.status.container_statuses),
        }
        for pod in pods
    ]


def get_pod_status(namespace: str, pod_name: str) -> dict:
    """Get a pod's phase, conditions, and container states."""
    pod = _api().read_namespaced_pod(name=pod_name, namespace=namespace)
    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "phase": pod.status.phase,
        "node": pod.spec.node_name,
        "conditions": [
            {"type": condition.type, "status": condition.status, "reason": condition.reason}
            for condition in pod.status.conditions or []
        ],
        "containers": _container_statuses(pod.status.container_statuses),
    }


def get_pod_events(namespace: str, pod_name: str) -> list[dict]:
    """Get recent Kubernetes events for a pod."""
    events = (
        _api()
        .list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}",
        )
        .items
    )

    return [
        {
            "type": event.type,
            "reason": event.reason,
            "message": event.message,
            "count": event.count,
            "last_seen": (
                event.event_time or event.last_timestamp or event.first_timestamp
            ).isoformat()
            if event.event_time or event.last_timestamp or event.first_timestamp
            else None,
        }
        for event in events
    ]


def get_pod_logs(
    namespace: str,
    pod_name: str,
    container: str | None = None,
    previous: bool = False,
    tail_lines: int = 100,
) -> str:
    """Read up to 500 lines of current or previous container logs."""
    response = _api().read_namespaced_pod_log(
        name=pod_name,
        namespace=namespace,
        container=container,
        previous=previous,
        tail_lines=max(1, min(tail_lines, 500)),
        timestamps=True,
        _preload_content=False,
    )

    try:
        raw_logs = response.read()
        logs = (
            raw_logs.decode("utf-8", errors="replace")
            if isinstance(raw_logs, bytes)
            else str(raw_logs)
        )
    finally:
        response.release_conn()

    if logs.startswith("unable to retrieve container logs for "):
        return f"[log retrieval error] {logs}"

    return logs
