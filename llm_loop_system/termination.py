from __future__ import annotations

from typing import Any

from llm_loop_system.types import AnalysisReport, SimulationResult, TerminationDecision


class TerminationModule:
    def decide(
        self,
        simulation_result: SimulationResult,
        analysis_report: AnalysisReport,
        iteration_state: dict[str, Any],
        risk_limits: dict[str, float],
        improvement_threshold: float = 0.01,
        max_no_improve_rounds: int = 3,
    ) -> TerminationDecision:
        metrics = simulation_result["metrics"]
        returns = metrics["returns_metrics"]
        risk = metrics["risk_metrics"]

        target_return = risk_limits.get("target_return", 0.12)
        max_drawdown = risk_limits.get("max_drawdown", 0.15)
        tail_risk = risk_limits.get("tail_risk", 0.05)

        if analysis_report["info_requests"]:
            return TerminationDecision(
                stop_decision=False,
                stop_reason="信息不足，需要补充数据",
                required_info=analysis_report["info_requests"],
            )

        if (
            returns["annualized_return"] >= target_return
            and abs(risk["max_drawdown"]) <= max_drawdown
            and abs(risk["tail_risk_95"]) <= tail_risk
        ):
            return TerminationDecision(
                stop_decision=True,
                stop_reason="收益与风险达到目标",
                required_info=[],
            )

        improvements = iteration_state.get("history_improvements", [])
        if len(improvements) >= max_no_improve_rounds and all(
            imp < improvement_threshold for imp in improvements[-max_no_improve_rounds:]
        ):
            return TerminationDecision(
                stop_decision=True,
                stop_reason="边际改进不足，停止迭代",
                required_info=[],
            )

        return TerminationDecision(
            stop_decision=False,
            stop_reason="继续迭代",
            required_info=[],
        )
