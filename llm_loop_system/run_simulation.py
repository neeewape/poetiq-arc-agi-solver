from __future__ import annotations

import json

from llm_loop_system.loop_controller import LoopConfig, LoopController


def main() -> None:
    payload = {
        "assumptions": [
            "短期为随机游走，长期由供需决定",
            "方向判断正确率约90%",
        ],
        "strategy_params": {
            "short_call_distance": 0.06,
            "short_put_distance": 0.06,
            "hedge_ratio": 0.9,
            "target_exposure": 0.1,
            "premium_buffer": 0.003,
        },
        "risk_limits": {
            "target_return": 0.12,
            "max_drawdown": 0.18,
            "tail_risk": 0.06,
        },
        "simulation_config": {
            "num_paths": 2000,
            "steps": 21,
            "spot_price": 100.0,
            "drift": 0.02,
            "volatility": 0.25,
            "long_term_trend": 0.01,
            "direction_accuracy": 0.9,
            "delivery_discount": 0.02,
        },
    }

    controller = LoopController()
    result = controller.run(payload, LoopConfig(max_iterations=5))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
