"""Bounded LangGraph workflow and structured investigation result."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Annotated, TypedDict

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from kubesleuth.agent.llm import get_llm
from kubesleuth.agent.prompts import REPORT_SYSTEM, SYSTEM_PROMPT
from kubesleuth.agent.report import IncidentReport
from kubesleuth.agent.tools import ALL_TOOLS
from kubesleuth.config import settings


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    namespace: str
    symptom: str
    steps: int
    report: IncidentReport | None


@dataclass
class InvestigationResult:
    report: IncidentReport | None
    tool_calls: list[dict] = field(default_factory=list)
    steps: int = 0
    duration_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None


def route_after_investigate(state: AgentState) -> str:
    last = state["messages"][-1]
    wants_tools = bool(getattr(last, "tool_calls", None))
    if wants_tools and state["steps"] < settings.max_steps:
        return "tools"
    return "report"


def build_graph():
    llm = get_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    report_llm = llm.with_structured_output(IncidentReport, method="function_calling")

    def triage(state: AgentState) -> dict:
        system = SystemMessage(content=SYSTEM_PROMPT.format(max_steps=settings.max_steps))
        request = HumanMessage(
            content=(
                f"Namespace: {state['namespace']}\n"
                f"Reported symptom: {state['symptom']}\n"
                "Investigate this incident and gather evidence."
            )
        )
        return {"messages": [system, request], "steps": 0}

    def investigate_node(state: AgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response], "steps": state["steps"] + 1}

    def report_node(state: AgentState) -> dict:
        evidence = "\n\n".join(
            f"### {message.name}\n{message.content}"
            for message in state["messages"]
            if isinstance(message, ToolMessage)
        )
        prompt = [
            SystemMessage(content=REPORT_SYSTEM),
            HumanMessage(
                content=(
                    f"Namespace: {state['namespace']}\n"
                    f"Reported symptom: {state['symptom']}\n\n"
                    "Evidence collected by read-only tools:\n"
                    f"{evidence or '(no evidence was collected)'}"
                )
            ),
        ]
        return {"report": report_llm.invoke(prompt)}

    graph = StateGraph(AgentState)
    graph.add_node("triage", triage)
    graph.add_node("investigate", investigate_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS))
    graph.add_node("report", report_node)
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "investigate")
    graph.add_conditional_edges(
        "investigate",
        route_after_investigate,
        {"tools": "tools", "report": "report"},
    )
    graph.add_edge("tools", "investigate")
    graph.add_edge("report", END)
    return graph.compile()


_GRAPH = None


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def investigate(namespace: str, symptom: str) -> InvestigationResult:
    """Run one bounded investigation; return errors in the result instead of raising."""
    started = time.monotonic()
    usage = UsageMetadataCallbackHandler()

    try:
        final = _graph().invoke(
            {
                "messages": [],
                "namespace": namespace,
                "symptom": symptom,
                "steps": 0,
                "report": None,
            },
            config={
                "callbacks": [usage],
                "recursion_limit": 2 * settings.max_steps + 6,
            },
        )
    except Exception as exc:  # return provider, graph, and tool errors to the caller
        return InvestigationResult(
            report=None,
            duration_s=time.monotonic() - started,
            error=f"{type(exc).__name__}: {exc}",
        )

    calls = [
        {"name": call["name"], "args": call["args"]}
        for message in final["messages"]
        if isinstance(message, AIMessage)
        for call in (message.tool_calls or [])
    ]
    tokens_in = sum(item.get("input_tokens", 0) for item in usage.usage_metadata.values())
    tokens_out = sum(item.get("output_tokens", 0) for item in usage.usage_metadata.values())

    return InvestigationResult(
        report=final["report"],
        tool_calls=calls,
        steps=final["steps"],
        duration_s=time.monotonic() - started,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
