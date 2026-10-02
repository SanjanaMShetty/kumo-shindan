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
        "node_selector": pod.spec.node_selector or {},
        "persistent_volume_claims": [
            {
                "volume": volume.name,
                "claim": volume.persistent_volume_claim.claim_name,
            }
            for volume in pod.spec.volumes or []
            if volume.persistent_volume_claim
        ],
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


def get_pvc_status(namespace: str, pvc_name: str) -> dict:
    """Get a PVC's binding state, storage class, and related events."""
    core = _api()
    pvc = core.read_namespaced_persistent_volume_claim(
        name=pvc_name,
        namespace=namespace,
    )
    events = core.list_namespaced_event(
        namespace=namespace,
        field_selector=f"involvedObject.name={pvc_name}",
    ).items

    return {
        "name": pvc.metadata.name,
        "namespace": pvc.metadata.namespace,
        "phase": pvc.status.phase,
        "storage_class": pvc.spec.storage_class_name,
        "volume_name": pvc.spec.volume_name,
        "access_modes": pvc.spec.access_modes or [],
        "requested_storage": (
            pvc.spec.resources.requests.get("storage")
            if pvc.spec.resources and pvc.spec.resources.requests
            else None
        ),
        "capacity": pvc.status.capacity or {},
        "conditions": [
            {
                "type": condition.type,
                "status": condition.status,
                "reason": condition.reason,
                "message": condition.message,
            }
            for condition in pvc.status.conditions or []
        ],
        "events": [
            {
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "count": event.count,
            }
            for event in events
        ],
    }


def get_service_endpoints(namespace: str, service_name: str) -> dict:
    """Get a Service's selector, ports, and ready or unready endpoint addresses."""
    core = _api()
    service = core.read_namespaced_service(name=service_name, namespace=namespace)
    endpoints = core.read_namespaced_endpoints(name=service_name, namespace=namespace)

    return {
        "name": service.metadata.name,
        "namespace": service.metadata.namespace,
        "selector": service.spec.selector or {},
        "service_ports": [
            {
                "name": port.name,
                "port": port.port,
                "target_port": str(port.target_port),
                "protocol": port.protocol,
            }
            for port in service.spec.ports or []
        ],
        "ready_endpoints": [
            {
                "ip": address.ip,
                "pod": address.target_ref.name if address.target_ref else None,
            }
            for subset in endpoints.subsets or []
            for address in subset.addresses or []
        ],
        "not_ready_endpoints": [
            {
                "ip": address.ip,
                "pod": address.target_ref.name if address.target_ref else None,
            }
            for subset in endpoints.subsets or []
            for address in subset.not_ready_addresses or []
        ],
    }
