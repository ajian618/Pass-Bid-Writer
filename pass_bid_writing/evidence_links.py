from __future__ import annotations

import re
from typing import Any


REFERENCE_MARKER_RE = re.compile(r"(?:详见|参见|见|按|按照|以).{0,16}", re.IGNORECASE)
PAGE_REFERENCE_RE = re.compile(
    r"(?:第\s*(?P<page>\d{1,4})\s*页|[PＰpｐ]\s*[.．:：\-]?\s*(?P<p_page>\d{1,4}))",
    re.IGNORECASE,
)
TABLE_REFERENCE_RE = re.compile(
    r"(?P<table>"
    r"投标人须知前附表|评标办法前附表|合同条款前附表|专用合同条款前附表|"
    r"附表\s*[一二三四五六七八九十百\dA-Za-z.\-—]*|"
    r"表\s*\d+(?:[.．]\d+){0,4}"
    r")"
)
REFERENCE_TAIL_RE = re.compile(
    r"[（(]?\s*(?:详见|参见|见|按|按照).{0,100}?"
    r"(?:第\s*\d{1,4}\s*页|[PＰpｐ]\s*[.．:：\-]?\s*\d{1,4}|"
    r"投标人须知前附表|评标办法前附表|合同条款前附表|附表|表\s*\d)"
    r".*?[）)]?\s*$",
    re.IGNORECASE,
)


def parse_document_reference(text: str) -> dict[str, Any] | None:
    clean = re.sub(r"\s+", " ", text).strip()
    marker = REFERENCE_MARKER_RE.search(clean)
    page_match = PAGE_REFERENCE_RE.search(clean)
    table_match = TABLE_REFERENCE_RE.search(clean)
    if marker is None or (page_match is None and table_match is None):
        return None
    page = None
    if page_match is not None:
        raw_page = page_match.group("page") or page_match.group("p_page")
        page = int(raw_page) if raw_page else None
    table = ""
    if table_match is not None:
        table = re.sub(r"\s+", "", table_match.group("table")).replace("．", ".")
    return {
        "target_page": page,
        "target_table": table,
        "reference_text": clean,
        "marker": marker.group(0).strip(),
    }


def is_reference_only_value(text: str) -> bool:
    clean = re.sub(r"\s+", " ", text).strip(" ：:；;，,。")
    reference = parse_document_reference(clean)
    if reference is None:
        return False
    marker = REFERENCE_MARKER_RE.search(clean)
    if marker is None:
        return False
    prefix = clean[: marker.start()].strip(" ：:；;，,。")
    return not prefix or len(prefix) <= 12


def strip_reference_tail(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return REFERENCE_TAIL_RE.sub("", clean).strip(" ：:；;，,。")


def normalize_fact_value(key: str, value: str, unit: str = "") -> str:
    clean = strip_reference_tail(value)
    clean = clean.replace("（", "(").replace("）", ")")
    clean = re.sub(r"[《》〈〉“”\"'`]", "", clean)
    clean = re.sub(r"[\s:：,，。；;、_\-—–]+", "", clean)
    if key in {"项目名称", "建设地点", "质量目标"}:
        clean = re.sub(r"^(?:项目|工程)?(?:名称|地点|质量目标|质量标准)", "", clean)
    normalized_unit = re.sub(r"\s+", "", unit)
    return f"{clean}{normalized_unit}".casefold()
