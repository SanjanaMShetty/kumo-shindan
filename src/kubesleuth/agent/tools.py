"""LangChain wrappers around the read-only Kubernetes client functions."""

import json

from kubernetes.client.exceptions import ApiException
from langchain_core.tools import tool

from kubesleuth import k8s_tools
from kubesleuth.config import settings


def _check_namespace(namespace: str) -> None:
    if namespace not in settings.namespaces:
        raise ValueError(
            f"Namespace {namespace!r} is not allowed. Allowed namespaces: {settings.namespaces}"
        )


def _format_output(value) -> str:
    output = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
    limit = settings.max_tool_output_chars
    if len(output) > limit:
        return output[:limit] + "\n[output truncated]"
    return output


def _run_read_tool(function, namespace: str, *args, **kwargs) -> str:
    try:
        _check_namespace(namespace)
        return _format_output(function(namespace, *args, **kwargs))
    except ApiException as exc:
        if exc.status == 404:
            return (
                "Resource not found. Call list_pods for this namespace and use the exact "
                "Pod name, including its generated suffix. A Deployment name is not a Pod name."
            )
        if exc.status == 403:
            return "Kubernetes denied this read request; check the ServiceAccount RBAC."
        return f"Kubernetes API error {exc.status}: {exc.reason}"
    except ValueError as exc:
        return f"Tool input rejected: {exc}"


@tool
def list_pods(namespace: str) -> str:
    """List pods and their health in an allowed Kubernetes namespace."""
    return _run_read_tool(k8s_tools.list_pods, namespace)


@tool
def get_pod_status(namespace: str, pod_name: str) -> str:
    """Get a pod's phase, conditions, container states, and restart counts."""
    return _run_read_tool(k8s_tools.get_pod_status, namespace, pod_name)


@tool
def get_pod_events(namespace: str, pod_name: str) -> str:
    """Get recent Kubernetes events associated with a pod."""
    return _run_read_tool(k8s_tools.get_pod_events, namespace, pod_name)


@tool
def get_pod_logs(
    namespace: str,
    pod_name: str,
    container: str | None = None,
    previous: bool = False,
) -> str:
    """Read current or previous container logs for a pod."""
    return _run_read_tool(
        k8s_tools.get_pod_logs,
        namespace,
        pod_name,
        container=container,
        previous=previous,
        tail_lines=settings.log_tail_lines,
    )


ALL_TOOLS = [list_pods, get_pod_status, get_pod_events, get_pod_logs]
