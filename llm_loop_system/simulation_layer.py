from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from llm_loop_system.types import SimulationResult, Strategy


@dataclass
class SimulationConfig:
    num_paths: int = 2000
    steps: int = 21
    spot_price: float = 100.0
    drift: float = 0.02
    volatility: float = 0.2
    long_term_trend: float = 0.01
    implied_vol_shift: float = 0.0
    direction_accuracy: float = 0.9
    risk_free_rate: float = 0.0
    delivery_discount: float = 0.02
    data_path: str | None = None
    data_version: str | None = None


class SimulationLayer:
    def simulate(
        self,
        strategy: Strategy,
        simulation_config: SimulationConfig,
        scenarios: dict[str, SimulationConfig],
        data_gaps: list[str] | None = None,
    ) -> SimulationResult:
        run_log: list[str] = []
        data_gaps = list(data_gaps or [])
        scenario_metrics: dict[str, dict[str, float]] = {}

        if simulation_config.data_version:
            run_log.append(f"使用数据版本: {simulation_config.data_version}")

        for name, config in scenarios.items():
            metrics = self._run_single_scenario(strategy, config, run_log)
            scenario_metrics[name] = metrics

        aggregated = self._aggregate_metrics(scenario_metrics)
        return SimulationResult(
            metrics=aggregated,
            scenario_metrics=scenario_metrics,
            run_log=run_log,
            data_gaps=data_gaps,
        )

    def _run_single_scenario(
        self,
        strategy: Strategy,
        config: SimulationConfig,
        run_log: list[str],
    ) -> dict[str, float]:
        rng = np.random.default_rng(42)
        params = strategy["parameters"]
        s0 = config.spot_price
        steps = config.steps
        dt = 1 / 252
        drift = config.drift + config.long_term_trend
        vol = max(0.01, config.volatility + config.implied_vol_shift)

        shocks = rng.normal(loc=(drift - 0.5 * vol**2) * dt, scale=vol * np.sqrt(dt), size=(config.num_paths, steps))
        log_paths = np.cumsum(shocks, axis=1)
        prices = s0 * np.exp(log_paths)
        terminal = prices[:, -1]

        short_call_distance = params.get("short_call_distance", 0.06)
        short_put_distance = params.get("short_put_distance", 0.06)
        hedge_ratio = params.get("hedge_ratio", 0.9)
        target_exposure = params.get("target_exposure", 0.1)
        premium_buffer = params.get("premium_buffer", 0.003)

        strike_call = s0 * (1 + short_call_distance)
        strike_put = s0 * (1 - short_put_distance)

        time_to_expiry = steps / 252
        premium_scale = 0.4 * vol * np.sqrt(time_to_expiry)
        call_premium = s0 * premium_scale + premium_buffer * s0
        put_premium = s0 * premium_scale + premium_buffer * s0

        call_payoff = -np.maximum(terminal - strike_call, 0.0) + call_premium
        put_payoff = -np.maximum(strike_put - terminal, 0.0) + put_premium

        delivery_bonus = np.where(terminal < strike_put, config.delivery_discount * s0, 0.0)
        option_pnl = call_payoff + put_payoff + delivery_bonus

        direction_signal = rng.random(config.num_paths) < config.direction_accuracy
        directional_bias = np.where(direction_signal, 1.0, -1.0)
        hedge_pnl = hedge_ratio * (terminal - s0) * directional_bias
        exposure_pnl = target_exposure * (terminal - s0) * directional_bias

        total_pnl = option_pnl + hedge_pnl + exposure_pnl
        monthly_returns = total_pnl / s0
        avg_return = float(np.mean(monthly_returns))
        std_return = float(np.std(monthly_returns))
        sharpe = float(avg_return / std_return * np.sqrt(12)) if std_return > 0 else 0.0
        tail_risk_95 = float(np.quantile(monthly_returns, 0.05))

        run_log.append(
            f"Scenario {config}: avg_return={avg_return:.4f}, sharpe={sharpe:.2f}, tail={tail_risk_95:.4f}"
        )

        return {
            "monthly_return_avg": avg_return,
            "annualized_return": avg_return * 12,
            "sharpe_ratio": sharpe,
            "tail_risk_95": tail_risk_95,
        }

    def _aggregate_metrics(self, scenario_metrics: dict[str, dict[str, float]]) -> dict[str, Any]:
        annualized = [m["annualized_return"] for m in scenario_metrics.values()]
        monthly = [m["monthly_return_avg"] for m in scenario_metrics.values()]
        sharpes = [m["sharpe_ratio"] for m in scenario_metrics.values()]
        tails = [m["tail_risk_95"] for m in scenario_metrics.values()]

        scenario_consistency = 1.0 - (np.std(sharpes) / (np.mean(sharpes) + 1e-6))
        scenario_consistency = float(np.clip(scenario_consistency, 0.0, 1.0))

        return {
            "returns_metrics": {
                "annualized_return": float(np.mean(annualized)),
                "monthly_return_avg": float(np.mean(monthly)),
                "sharpe_ratio": float(np.mean(sharpes)),
            },
            "risk_metrics": {
                "max_drawdown": float(min(0.0, np.min(tails))),
                "tail_risk_95": float(np.mean(tails)),
                "loss_distribution": {
                    "p10": float(np.quantile(monthly, 0.1)),
                    "p50": float(np.quantile(monthly, 0.5)),
                    "p90": float(np.quantile(monthly, 0.9)),
                },
            },
            "robustness_metrics": {
                "scenario_consistency": scenario_consistency,
                "scenario_results": scenario_metrics,
            },
        }
