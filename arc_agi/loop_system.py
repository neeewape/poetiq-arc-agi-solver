from __future__ import annotations

from typing import Optional, TypedDict

from arc_agi.io import build_kaggle_two_attempts
from arc_agi.scoring import score_task
from arc_agi.solve import solve
from arc_agi.types import ARCAGIResult


class LoopMetrics(TypedDict):
    score: Optional[float]


class LoopAnalysis(TypedDict):
    analysis_summary: str
    optimization_signals: list[str]
    risk_alerts: list[str]
    info_requests: list[str]


class LoopIteration(TypedDict):
    iteration_id: str
    metrics: LoopMetrics
    analysis: LoopAnalysis
    stop_decision: bool
    stop_reason: Optional[str]


class LoopResult(TypedDict):
    kaggle_preds: list[dict]
    tokens: dict[str, int]
    iterations: list[LoopIteration]
    best_score: Optional[float]


def _sum_tokens(results: list[ARCAGIResult]) -> dict[str, int]:
    prompt_tokens = sum(r["prompt_tokens"] or 0 for r in results if r)
    completion_tokens = sum(r["completion_tokens"] or 0 for r in results if r)
    return {
        "prompt": prompt_tokens,
        "completion": completion_tokens,
        "total": prompt_tokens + completion_tokens,
    }


def _analyze_metrics(score: Optional[float]) -> LoopAnalysis:
    if score is None:
        return {
            "analysis_summary": "缺少标准解或指标，无法评估当前结果。",
            "optimization_signals": [],
            "risk_alerts": [],
            "info_requests": ["缺少标准解或评测指标数据"],
        }

    if score >= 1.0:
        return {
            "analysis_summary": "已达到满分，当前解法足够好。",
            "optimization_signals": [],
            "risk_alerts": [],
            "info_requests": [],
        }

    return {
        "analysis_summary": "当前得分未达标，需要继续优化。",
        "optimization_signals": ["提升解题准确率", "改进候选解覆盖率"],
        "risk_alerts": [],
        "info_requests": [],
    }


def _should_stop(
    score: Optional[float],
    analysis: LoopAnalysis,
    improvements: list[float],
    improvement_threshold: float,
    improvement_window: int,
    iteration: int,
    max_iterations: int,
) -> tuple[bool, Optional[str]]:
    if analysis["info_requests"]:
        return True, "info_required"
    if score is not None and score >= 1.0:
        return True, "score_target_reached"
    if len(improvements) >= improvement_window and all(
        delta < improvement_threshold for delta in improvements[-improvement_window:]
    ):
        return True, "insufficient_improvement"
    if iteration >= max_iterations:
        return True, "max_iterations_reached"
    return False, None


async def run_closed_loop(
    train_in: list[list[list[int]]],
    train_out: list[list[list[int]]],
    test_in: list[list[list[int]]],
    problem_id: str | None = None,
    solutions_blob: Optional[dict[str, list]] = None,
    max_iterations: int = 3,
    improvement_threshold: float = 0.01,
    improvement_window: int = 3,
) -> LoopResult:
    iterations: list[LoopIteration] = []
    improvements: list[float] = []
    best_score: Optional[float] = None
    best_preds: list[dict] = []
    prev_score: Optional[float] = None
    tokens_total = {"prompt": 0, "completion": 0, "total": 0}

    for iteration in range(1, max_iterations + 1):
        results = await solve(
            train_in=train_in,
            train_out=train_out,
            test_in=test_in,
            problem_id=problem_id,
        )
        kaggle_preds = build_kaggle_two_attempts(results, test_in)
        tokens = _sum_tokens(results)
        tokens_total = {
            "prompt": tokens_total["prompt"] + tokens["prompt"],
            "completion": tokens_total["completion"] + tokens["completion"],
            "total": tokens_total["total"] + tokens["total"],
        }

        score = None
        if solutions_blob is not None and problem_id is not None and problem_id in solutions_blob:
            score = score_task(kaggle_preds, solutions_blob[problem_id])

        if score is not None:
            if best_score is None or score > best_score:
                best_score = score
                best_preds = kaggle_preds

        if prev_score is not None and score is not None:
            improvements.append(score - prev_score)

        analysis = _analyze_metrics(score)
        stop_decision, stop_reason = _should_stop(
            score=score,
            analysis=analysis,
            improvements=improvements,
            improvement_threshold=improvement_threshold,
            improvement_window=improvement_window,
            iteration=iteration,
            max_iterations=max_iterations,
        )

        iterations.append(
            {
                "iteration_id": f"{problem_id or 'unknown'}-iter-{iteration}",
                "metrics": {"score": score},
                "analysis": analysis,
                "stop_decision": stop_decision,
                "stop_reason": stop_reason,
            }
        )

        if stop_decision:
            if best_score is None:
                best_score = score
            if not best_preds:
                best_preds = kaggle_preds
            break

        prev_score = score

    return {
        "kaggle_preds": best_preds,
        "tokens": tokens_total,
        "iterations": iterations,
        "best_score": best_score,
    }
