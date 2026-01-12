from __future__ import annotations

from typing import Any

from llm_loop_system.types import AnalysisReport, SimulationResult


class AnalysisLayer:
    def analyze(self, simulation_result: SimulationResult, risk_limits: dict[str, float]) -> AnalysisReport:
        metrics = simulation_result["metrics"]
        returns = metrics["returns_metrics"]
        risk = metrics["risk_metrics"]
        robustness = metrics["robustness_metrics"]

        analysis_summary = "收益与风险指标已计算。"
        optimization_signals: list[str] = []
        risk_alerts: list[str] = []
        info_requests: list[str] = []

        if returns["annualized_return"] < risk_limits.get("target_return", 0.12):
            optimization_signals.append("提升收益率")
            analysis_summary = "收益未达标，需要提升收益。"

        if risk["max_drawdown"] < -risk_limits.get("max_drawdown", 0.15):
            risk_alerts.append("最大回撤超限")
            optimization_signals.append("降低回撤")

        if risk["tail_risk_95"] < -risk_limits.get("tail_risk", 0.05):
            risk_alerts.append("尾部风险超限")

        if robustness["scenario_consistency"] < 0.7:
            optimization_signals.append("提升压力场景稳健性")

        if simulation_result["data_gaps"]:
            info_requests.extend(simulation_result["data_gaps"])

        return AnalysisReport(
            analysis_summary=analysis_summary,
            optimization_signals=optimization_signals,
            risk_alerts=risk_alerts,
            info_requests=info_requests,
        )
