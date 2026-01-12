from __future__ import annotations

import os
import sys

_SCRIPT_DIR = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import json  # noqa: E402

from llm_loop_system.loop_controller import LoopConfig, LoopController  # noqa: E402


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
            "long_term_trend": 0.01,
            "direction_accuracy": 0.9,
            "delivery_discount": 0.02,
            "data_path": "红枣期货期权数据.xlsx",
        },
    }

    controller = LoopController()
    result = controller.run(payload, LoopConfig(max_iterations=5))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
