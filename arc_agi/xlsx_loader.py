import os
import re
import zipfile
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET


class XlsxLoadError(Exception):
    pass


@dataclass(frozen=True)
class XlsxSheet:
    name: str
    headers: list[str]
    rows: list[dict[str, Any]]


def load_xlsx(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        raise XlsxLoadError(f"XLSX file not found: {path}")

    with zipfile.ZipFile(path) as zf:
        shared_strings = _load_shared_strings(zf)
        sheets = _load_sheets(zf, shared_strings)

    return {
        "source_file": os.path.abspath(path),
        "sheets": {
            sheet.name: {
                "headers": sheet.headers,
                "rows": sheet.rows,
            }
            for sheet in sheets
        },
    }


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    with zf.open("xl/sharedStrings.xml") as f:
        tree = ET.parse(f)

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for si in tree.findall(".//m:si", ns):
        text_parts = [t.text or "" for t in si.findall(".//m:t", ns)]
        strings.append("".join(text_parts))
    return strings


def _load_sheets(zf: zipfile.ZipFile, shared_strings: list[str]) -> list[XlsxSheet]:
    workbook = _load_workbook(zf)
    rels = _load_workbook_rels(zf)
    sheets: list[XlsxSheet] = []
    for name, rel_id in workbook:
        target = rels.get(rel_id)
        if not target:
            continue
        normalized = target.lstrip("/")
        sheet_path = normalized if normalized.startswith("xl/") else os.path.join("xl", normalized)
        sheet_data = _parse_sheet(zf, sheet_path, shared_strings)
        sheets.append(XlsxSheet(name=name, headers=sheet_data.headers, rows=sheet_data.rows))
    return sheets


def _load_workbook(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    with zf.open("xl/workbook.xml") as f:
        tree = ET.parse(f)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    sheets = []
    for sheet in tree.findall(".//m:sheet", ns):
        name = sheet.get("name")
        rel_id = sheet.get(rel_attr)
        if name and rel_id:
            sheets.append((name, rel_id))
    return sheets


def _load_workbook_rels(zf: zipfile.ZipFile) -> dict[str, str]:
    with zf.open("xl/_rels/workbook.xml.rels") as f:
        tree = ET.parse(f)
    ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    rels = {}
    for rel in tree.findall(".//r:Relationship", ns):
        rel_id = rel.get("Id")
        target = rel.get("Target")
        if rel_id and target:
            rels[rel_id] = target
    return rels


@dataclass(frozen=True)
class _SheetData:
    headers: list[str]
    rows: list[dict[str, Any]]


def _parse_sheet(
    zf: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> _SheetData:
    with zf.open(sheet_path) as f:
        tree = ET.parse(f)

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows_by_index: dict[int, dict[str, Any]] = {}
    for row in tree.findall(".//m:row", ns):
        row_index = int(row.get("r", "0"))
        row_data: dict[str, Any] = {}
        for cell in row.findall("m:c", ns):
            cell_ref = cell.get("r", "")
            col = _column_letter(cell_ref)
            if not col:
                continue
            cell_value = _cell_value(cell, shared_strings, ns)
            row_data[col] = cell_value
        if row_data:
            rows_by_index[row_index] = row_data

    if not rows_by_index:
        return _SheetData(headers=[], rows=[])

    header_row_index = min(rows_by_index)
    header_row = rows_by_index.get(header_row_index, {})
    header_pairs = [
        (col, str(value).strip())
        for col, value in sorted(header_row.items(), key=lambda item: item[0])
        if str(value).strip()
    ]
    headers = [value for _, value in header_pairs]
    header_cols = [col for col, _ in header_pairs]

    data_rows = []
    for row_index in sorted(rows_by_index.keys()):
        if row_index == header_row_index:
            continue
        row = rows_by_index[row_index]
        row_values: dict[str, Any] = {}
        for col, header in zip(header_cols, headers, strict=False):
            row_values[header] = _normalize_value(row.get(col))
        if any(value not in (None, "") for value in row_values.values()):
            data_rows.append(row_values)

    return _SheetData(headers=headers, rows=data_rows)


def _cell_value(cell: ET.Element, shared_strings: list[str], ns: dict[str, str]) -> Any:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        inline = cell.find("m:is/m:t", ns)
        return inline.text if inline is not None else ""
    value = cell.find("m:v", ns)
    if value is None:
        return ""
    text = value.text or ""
    if cell_type == "s":
        if text.isdigit():
            index = int(text)
            if 0 <= index < len(shared_strings):
                return shared_strings[index]
        return ""
    return text


def _column_letter(cell_ref: str) -> str:
    match = re.match(r"([A-Z]+)", cell_ref)
    return match.group(1) if match else ""


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        if re.fullmatch(r"-?\\d+", stripped):
            return int(stripped)
        if re.fullmatch(r"-?\\d*\\.\\d+", stripped):
            return float(stripped)
        return stripped
    return value
