from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class MarketDataSummary:
    spot_price: float
    drift: float
    volatility: float
    implied_vol: float | None
    notes: list[str]


def load_market_data(path: str | Path) -> MarketDataSummary:
    data_path = Path(path)
    if not data_path.exists():
        raise FileNotFoundError(f"找不到数据文件: {data_path}")

    df = pd.read_excel(data_path)
    if df.empty:
        raise ValueError("数据文件为空，无法估计参数")

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        raise ValueError("未找到数值列，无法估计价格序列")

    price_col = _find_column(numeric_cols, ["close", "settle", "price", "future", "spot"])
    if price_col is None:
        price_col = numeric_cols[0]

    price_series = df[price_col].dropna().astype(float)
    if len(price_series) < 5:
        raise ValueError("价格序列过短，无法估计参数")

    log_returns = np.log(price_series / price_series.shift(1)).dropna()
    daily_mean = float(log_returns.mean())
    daily_vol = float(log_returns.std())
    drift = daily_mean * 252
    volatility = max(0.01, daily_vol * np.sqrt(252))

    implied_col = _find_column(numeric_cols, ["iv", "implied", "vol"])
    implied_vol: float | None = None
    if implied_col is not None:
        implied_series = df[implied_col].dropna().astype(float)
        if not implied_series.empty:
            implied_vol = float(np.clip(implied_series.mean(), 0.01, 2.0))
            volatility = implied_vol

    notes = [f"使用列 {price_col} 估计漂移与波动", f"样本数 {len(price_series)}"]
    if implied_vol is not None:
        notes.append(f"使用列 {implied_col} 估计隐含波动率")

    return MarketDataSummary(
        spot_price=float(price_series.iloc[-1]),
        drift=drift,
        volatility=volatility,
        implied_vol=implied_vol,
        notes=notes,
    )


def _find_column(columns: list[str], keywords: list[str]) -> str | None:
    lowered = {col: col.lower() for col in columns}
    for key in keywords:
        for original, lower in lowered.items():
            if key in lower:
                return original
    return None
