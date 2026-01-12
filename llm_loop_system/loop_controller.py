from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llm_loop_system.analysis_layer import AnalysisLayer
from llm_loop_system.llm_layer import LLMLayer
from llm_loop_system.simulation_layer import SimulationConfig, SimulationLayer
from llm_loop_system.termination import TerminationModule
from llm_loop_system.types import AnalysisReport, IterationState, LLMOutput, SimulationResult


@dataclass
class LoopConfig:
    max_iterations: int = 5
    improvement_threshold: float = 0.01
    max_no_improve_rounds: int = 3


class LoopController:
    def __init__(self) -> None:
        self.llm_layer = LLMLayer()
        self.sim_layer = SimulationLayer()
        self.analysis_layer = AnalysisLayer()
        self.termination = TerminationModule()

    def run(self, payload: dict[str, Any], loop_config: LoopConfig) -> dict[str, Any]:
        iteration_state = IterationState(
            iteration_id="iter-0001",
            history_feedback=[],
            history_improvements=[],
        )

        llm_output: LLMOutput = self.llm_layer.generate_strategy(payload)
        history: list[dict[str, Any]] = []

        for it in range(loop_config.max_iterations):
            sim_config = payload.get("simulation_config", {})
            scenarios = self._build_scenarios(sim_config)

            simulation_result: SimulationResult = self.sim_layer.simulate(
                llm_output["strategy"],
                simulation_config=scenarios["baseline"],
                scenarios=scenarios,
            )
            analysis_report: AnalysisReport = self.analysis_layer.analyze(
                simulation_result,
                risk_limits=payload.get("risk_limits", {}),
            )

            decision = self.termination.decide(
                simulation_result,
                analysis_report,
                iteration_state.__dict__,
                payload.get("risk_limits", {}),
                improvement_threshold=loop_config.improvement_threshold,
                max_no_improve_rounds=loop_config.max_no_improve_rounds,
            )

            history.append(
                {
                    "iteration": it + 1,
                    "strategy": llm_output["strategy"],
                    "metrics": simulation_result["metrics"],
                    "analysis": analysis_report,
                    "decision": decision,
                }
            )

            current_return = simulation_result["metrics"]["returns_metrics"]["annualized_return"]
            iteration_state.history_improvements.append(current_return)

            if decision["stop_decision"]:
                break

            llm_output = self.llm_layer.revise_strategy(payload, analysis_report, llm_output["strategy"])

        return {
            "history": history,
            "final_strategy": llm_output["strategy"],
        }

    def _build_scenarios(self, sim_config: dict[str, Any]) -> dict[str, SimulationConfig]:
        base = SimulationConfig(**sim_config)
        return {
            "baseline": base,
            "stress_downturn": SimulationConfig(**{**sim_config, "drift": base.drift - 0.03, "implied_vol_shift": 0.05}),
            "high_volatility": SimulationConfig(**{**sim_config, "volatility": base.volatility + 0.1}),
        }
