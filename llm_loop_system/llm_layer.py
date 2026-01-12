from __future__ import annotations

import json
import os
from typing import Any

import litellm

from llm_loop_system.types import LLMOutput, Strategy


class LLMLayer:
    def generate_strategy(self, payload: dict[str, Any]) -> LLMOutput:
        base_params = payload.get("strategy_params", {})
        llm_config = payload.get("llm_config", {})
        model = llm_config.get("model") or os.getenv("LLM_MODEL", "gemini/gemini-3-pro-preview")
        temperature = float(llm_config.get("temperature", 0.2))

        prompt = self._build_generate_prompt(base_params)
        response_json = self._call_llm(model, prompt, temperature=temperature)
        if response_json is None:
            return self._default_strategy(base_params, note="LLM 输出解析失败，使用默认策略")
        return response_json

    def revise_strategy(
        self,
        payload: dict[str, Any],
        analysis_report: dict[str, Any],
        current_strategy: Strategy,
    ) -> LLMOutput:
        llm_config = payload.get("llm_config", {})
        model = llm_config.get("model") or os.getenv("LLM_MODEL", "gemini/gemini-3-pro-preview")
        temperature = float(llm_config.get("temperature", 0.2))

        prompt = self._build_revision_prompt(current_strategy, analysis_report)
        response_json = self._call_llm(model, prompt, temperature=temperature)
        if response_json is None:
            return self._default_revision(current_strategy, note="LLM 输出解析失败，回退规则修正")
        return response_json

    def _call_llm(self, model: str, prompt: str, temperature: float) -> LLMOutput | None:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": "你是量化策略分析助手，必须严格输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        content = response["choices"][0]["message"]["content"]
        payload = self._parse_json(content)
        if payload is None:
            return None
        return LLMOutput(**payload)

    def _parse_json(self, content: str) -> dict[str, Any] | None:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _build_generate_prompt(self, base_params: dict[str, Any]) -> str:
        return (
            "基于以下初始参数生成策略，必须输出 JSON。"
            "\nJSON 结构："
            "\n{"
            '\n  "strategy": {"name": "...", "parameters": {...}, "rules": ["..."]},'
            '\n  "change_rationale": ["..."],'
            '\n  "risk_expectation": {"expected_max_drawdown": 0.0, "expected_sharpe": 0.0},'
            '\n  "stop_recommendation": {"should_stop": false, "reason": "..."}'
            "\n}"
            "\n初始参数："
            f"\n{json.dumps(base_params, ensure_ascii=False)}"
        )

    def _build_revision_prompt(self, current_strategy: Strategy, analysis_report: dict[str, Any]) -> str:
        return (
            "根据当前策略与分析报告修正策略，必须输出 JSON。"
            "\nJSON 结构："
            "\n{"
            '\n  "strategy": {"name": "...", "parameters": {...}, "rules": ["..."]},'
            '\n  "change_rationale": ["..."],'
            '\n  "risk_expectation": {"expected_max_drawdown": 0.0, "expected_sharpe": 0.0},'
            '\n  "stop_recommendation": {"should_stop": false, "reason": "..."}'
            "\n}"
            "\n当前策略："
            f"\n{json.dumps(current_strategy, ensure_ascii=False)}"
            "\n分析报告："
            f"\n{json.dumps(analysis_report, ensure_ascii=False)}"
        )

    def _default_strategy(self, base_params: dict[str, Any], note: str) -> LLMOutput:
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
            change_rationale=[note],
            risk_expectation={"expected_max_drawdown": 0.18, "expected_sharpe": 0.8},
            stop_recommendation={"should_stop": False, "reason": "需要仿真验证"},
        )

    def _default_revision(self, current_strategy: Strategy, note: str) -> LLMOutput:
        params = dict(current_strategy["parameters"])
        params["hedge_ratio"] = min(1.0, params.get("hedge_ratio", 0.9) + 0.05)
        params["target_exposure"] = max(0.05, params.get("target_exposure", 0.1) - 0.02)
        strategy = Strategy(
            name=f"{current_strategy['name']}-rev",
            parameters=params,
            rules=current_strategy["rules"],
        )
        return LLMOutput(
            strategy=strategy,
            change_rationale=[note],
            risk_expectation={"expected_max_drawdown": 0.15, "expected_sharpe": 0.9},
            stop_recommendation={"should_stop": False, "reason": "需要再次验证"},
        )
