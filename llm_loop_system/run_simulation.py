from __future__ import annotations

import argparse
import json

from llm_loop_system.data_loader import load_market_data
from llm_loop_system.loop_controller import LoopConfig, LoopController


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM loop simulation.")
    parser.add_argument(
        "--data-path",
        default="红枣期货期权数据.xlsx",
        help="Excel file containing red-jujube futures/options data.",
    )
    args = parser.parse_args()

    data_summary = load_market_data(args.data_path)

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
            "spot_price": data_summary.spot_price,
            "drift": data_summary.drift,
            "volatility": data_summary.volatility,
            "long_term_trend": 0.01,
            "direction_accuracy": 0.9,
            "delivery_discount": 0.02,
        },
    }

    controller = LoopController()
    result = controller.run(payload, LoopConfig(max_iterations=5))
    result["data_notes"] = data_summary.notes
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
