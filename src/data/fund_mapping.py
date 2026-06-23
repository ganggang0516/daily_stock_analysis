# -*- coding: utf-8 -*-
"""场外基金代码到中文名称的轻量解析。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


FUND_NAME_MAP: Dict[str, str] = {}

_fund_name_cache: Optional[tuple[float, Dict[str, str]]] = None
_FUND_NAME_CACHE_TTL = 6 * 60 * 60


def _normalize_fund_code(code: Any) -> str:
    text = str(code or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    return text.zfill(6) if text.isdigit() and len(text) <= 6 else text


def _is_valid_fund_name(name: Any, code: str) -> bool:
    text = str(name or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered in {"n/a", "na", "none", "null", "unknown", "-", "--"}:
        return False
    if text.upper() == code.upper() or text.startswith("股票"):
        return False
    return True


def _extract_fund_name_table(df: Any) -> Dict[str, str]:
    if df is None or getattr(df, "empty", True):
        return {}

    columns = list(getattr(df, "columns", []))
    code_column = next(
        (
            column
            for column in columns
            if str(column).strip() in {"基金代码", "代码", "fund_code", "code"}
        ),
        None,
    )
    name_column = next(
        (
            column
            for column in columns
            if str(column).strip() in {"基金简称", "基金名称", "简称", "名称", "name"}
        ),
        None,
    )
    if code_column is None or name_column is None:
        logger.debug("[基金名称] 未识别基金名称表列: %s", columns)
        return {}

    result: Dict[str, str] = {}
    for _, row in df.iterrows():
        code = _normalize_fund_code(row.get(code_column))
        name = str(row.get(name_column) or "").strip()
        if code and _is_valid_fund_name(name, code):
            result[code] = name
    return result


def _load_akshare_fund_names() -> Dict[str, str]:
    global _fund_name_cache
    now = time.time()
    if _fund_name_cache is not None and now - _fund_name_cache[0] < _FUND_NAME_CACHE_TTL:
        return _fund_name_cache[1]

    try:
        import akshare as ak

        df = ak.fund_name_em()
        names = _extract_fund_name_table(df)
        _fund_name_cache = (now, names)
        logger.info("[基金名称] AkShare 场外基金名称缓存加载完成: %d 条", len(names))
        return names
    except Exception as exc:
        logger.warning("[基金名称] AkShare fund_name_em 获取失败: %s", exc)
        _fund_name_cache = (now, {})
        return {}


def get_fund_name(fund_code: Any, *, allow_network: bool = True) -> Optional[str]:
    """Return Chinese fund name for off-exchange fund code when available."""
    code = _normalize_fund_code(fund_code)
    if not code or not (code.isdigit() and len(code) == 6):
        return None

    static_name = FUND_NAME_MAP.get(code)
    if _is_valid_fund_name(static_name, code):
        return static_name

    if not allow_network:
        return None

    name = _load_akshare_fund_names().get(code)
    if _is_valid_fund_name(name, code):
        FUND_NAME_MAP[code] = name
        return name
    return None
