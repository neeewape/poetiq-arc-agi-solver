from __future__ import annotations

from typing import Any

from llm_loop_system.types import LLMOutput, Strategy


class LLMLayer:
    def generate_strategy(self, payload: dict[str, Any]) -> LLMOutput:
        base_params = payload.get("strategy_params", {})
        strategy = Strategy(
            name="red-jujube-strangle-v1",
            parameters={
                "short_call_distance": base_params.get("short_call_distance", 0.06),
                "short_put_distance": base_params.get("short_put_distance", 0.06),
                "hedge_ratio": base_params.get("hedge_ratio", 0.9),
                "target_exposure": base_params.get("target_exposure", 0.1),
                "premium_buffer": base_params.get("premium_buffer", 0.003),
            },
            rules=[
                "在压力位附近卖出看涨期权",
                "在支撑位附近卖出看跌期权",
                "期货对冲后保持10%方向性敞口",
                "若卖出看跌被行权，触发现货接货与对冲流程",
            ],
        )
        return LLMOutput(
            strategy=strategy,
            change_rationale=["初始化双卖期权+期货对冲策略"],
            risk_expectation={"expected_max_drawdown": 0.18, "expected_sharpe": 0.8},
            stop_recommendation={"should_stop": False, "reason": "需要仿真验证"},
        )

    def revise_strategy(
        self,
        payload: dict[str, Any],
        analysis_report: dict[str, Any],
        current_strategy: Strategy,
    ) -> LLMOutput:
        params = dict(current_strategy["parameters"])
        risk_alerts = analysis_report.get("risk_alerts", [])
        optimization_signals = analysis_report.get("optimization_signals", [])

        if any("回撤" in alert for alert in risk_alerts):
            params["hedge_ratio"] = min(1.0, params.get("hedge_ratio", 0.9) + 0.05)
            params["target_exposure"] = max(0.05, params.get("target_exposure", 0.1) - 0.02)

        if any("稳健" in signal for signal in optimization_signals):
            params["short_call_distance"] = min(0.1, params.get("short_call_distance", 0.06) + 0.01)
            params["short_put_distance"] = min(0.1, params.get("short_put_distance", 0.06) + 0.01)

        strategy = Strategy(
            name=f"{current_strategy['name']}-rev",
            parameters=params,
            rules=current_strategy["rules"],
        )
        return LLMOutput(
            strategy=strategy,
            change_rationale=["提高对冲比例并扩大卖出期权距离以降低回撤"],
            risk_expectation={"expected_max_drawdown": 0.15, "expected_sharpe": 0.9},
            stop_recommendation={"should_stop": False, "reason": "需要再次验证"},
        )
