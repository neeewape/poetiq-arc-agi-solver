from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class Strategy(TypedDict):
    name: str
    parameters: dict[str, Any]
    rules: list[str]


class StopRecommendation(TypedDict):
    should_stop: bool
    reason: str


class LLMOutput(TypedDict):
    strategy: Strategy
    change_rationale: list[str]
    risk_expectation: dict[str, float]
    stop_recommendation: StopRecommendation


class SimulationMetrics(TypedDict):
    returns_metrics: dict[str, float]
    risk_metrics: dict[str, Any]
    robustness_metrics: dict[str, Any]


class SimulationResult(TypedDict):
    metrics: SimulationMetrics
    scenario_metrics: dict[str, dict[str, float]]
    run_log: list[str]
    data_gaps: list[str]


class AnalysisReport(TypedDict):
    analysis_summary: str
    optimization_signals: list[str]
    risk_alerts: list[str]
    info_requests: list[str]


class TerminationDecision(TypedDict):
    stop_decision: bool
    stop_reason: str
    required_info: list[str]


@dataclass
class IterationState:
    iteration_id: str
    history_feedback: list[dict[str, Any]]
    history_improvements: list[float]
