from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np


_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass(frozen=True)
class MarketDataSummary:
    spot_price: float
    drift: float
    volatility: float
    implied_vol: float | None
    data_version: str


def load_jujube_dataset(path: str) -> tuple[MarketDataSummary | None, list[str]]:
    data_gaps: list[str] = []
    xlsx_path = Path(path)
    if not xlsx_path.exists():
        return None, [f"数据文件不存在: {path}"]

    try:
        sheet1 = _read_sheet(xlsx_path, "红枣期货OHLC")
        sheet2 = _read_sheet(xlsx_path, "红枣期权隐含波动率")
    except Exception as exc:  # noqa: BLE001 - surface failure in data_gaps
        return None, [f"读取数据失败: {exc}"]

    closes = _extract_close_prices(sheet1, data_gaps)
    if len(closes) < 2:
        return None, data_gaps + ["期货OHLC数据不足，无法计算收益率"]

    log_returns = np.diff(np.log(np.array(closes, dtype=float)))
    drift = float(np.mean(log_returns) * 252)
    volatility = float(np.std(log_returns, ddof=1) * np.sqrt(252))
    spot_price = float(closes[-1])

    implied_vol = _extract_implied_vol(sheet2, data_gaps)

    data_version = _hash_file(xlsx_path)

    summary = MarketDataSummary(
        spot_price=spot_price,
        drift=drift,
        volatility=volatility,
        implied_vol=implied_vol,
        data_version=data_version,
    )
    return summary, data_gaps


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _extract_close_prices(rows: list[list[Any]], data_gaps: list[str]) -> list[float]:
    if not rows:
        data_gaps.append("期货OHLC表为空")
        return []
    header = rows[0]
    try:
        close_idx = header.index("收盘价(元/吨)")
    except ValueError:
        data_gaps.append("期货OHLC表缺少收盘价列")
        return []

    closes: list[float] = []
    for row in rows[1:]:
        if close_idx >= len(row):
            continue
        value = row[close_idx]
        if value is None:
            continue
        try:
            closes.append(float(value))
        except ValueError:
            data_gaps.append(f"无法解析收盘价: {value}")
    return closes


def _extract_implied_vol(rows: list[list[Any]], data_gaps: list[str]) -> float | None:
    if not rows:
        data_gaps.append("隐含波动率表为空")
        return None
    header = rows[0]
    try:
        iv_idx = header.index("日均隐含波动率(%)")
    except ValueError:
        data_gaps.append("隐含波动率表缺少日均隐含波动率列")
        return None

    vols: list[float] = []
    for row in rows[1:]:
        if iv_idx >= len(row):
            continue
        value = row[iv_idx]
        if value is None:
            continue
        try:
            vols.append(float(value) / 100.0)
        except ValueError:
            data_gaps.append(f"无法解析隐含波动率: {value}")

    if not vols:
        return None
    return float(np.mean(vols))


def _read_sheet(path: Path, sheet_name: str) -> list[list[Any]]:
    with zipfile.ZipFile(path) as zf:
        sheet_id = _sheet_id_for_name(zf, sheet_name)
        sheet_xml = zf.read(f"xl/worksheets/sheet{sheet_id}.xml")
    root = ET.fromstring(sheet_xml)
    sheet_rows: list[list[Any]] = []
    for row in root.findall("main:sheetData/main:row", _NS):
        row_values: list[Any] = []
        for cell in row.findall("main:c", _NS):
            value = _read_cell_value(cell)
            col = cell.attrib.get("r", "")
            col_index = _column_index(col)
            while len(row_values) <= col_index:
                row_values.append(None)
            row_values[col_index] = value
        sheet_rows.append(row_values)
    return _trim_empty_rows(sheet_rows)


def _sheet_id_for_name(zf: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_xml = zf.read("xl/workbook.xml")
    root = ET.fromstring(workbook_xml)
    for sheet in root.findall("main:sheets/main:sheet", _NS):
        if sheet.attrib.get("name") == sheet_name:
            return sheet.attrib["sheetId"]
    raise ValueError(f"未找到工作表: {sheet_name}")


def _read_cell_value(cell: ET.Element) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text = cell.find("main:is/main:t", _NS)
        return text.text if text is not None else None
    value = cell.find("main:v", _NS)
    if value is None:
        return None
    if cell_type == "s":
        return value.text
    return value.text


def _column_index(cell_ref: str) -> int:
    col = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for ch in col:
        index = index * 26 + (ord(ch.upper()) - ord("A") + 1)
    return max(0, index - 1)


def _trim_empty_rows(rows: list[list[Any]]) -> list[list[Any]]:
    trimmed: list[list[Any]] = []
    for row in rows:
        if any(value not in (None, "") for value in row):
            trimmed.append(row)
    return trimmed
