# -*- coding: utf-8 -*-
from __future__ import annotations

"""
场外基金代码与名称映射。

该模块是报告展示层的轻量依赖：即使某只基金未收录，也必须回退到
基金代码，避免因为名称映射缺失导致日报任务失败。
"""

from typing import Optional


FUND_NAME_MAP: dict[str, str] = {
    "008888": "场外基金008888",
    "003096": "中欧医疗健康混合A",
    "110011": "易方达中小盘混合",
    "161725": "招商中证白酒指数A",
    "005827": "易方达蓝筹精选混合",
    "001875": "前海开源沪港深优势精选混合A",
    "001594": "天弘中证银行ETF联接A",
    "000248": "汇添富中证主要消费ETF联接A",
    "000991": "工银战略转型股票A",
    "001475": "易方达国防军工混合A",
}


def normalize_fund_code(code: str | int | None) -> str:
    """Normalize an open fund code to a six-digit display key when possible."""
    if code is None:
        return ""

    text = str(code).strip()
    if not text:
        return ""

    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


def get_fund_name(code: str | int | None, fallback: Optional[str] = None) -> str:
    """Return the display name for a fund, falling back safely to code/fallback."""
    normalized_code = normalize_fund_code(code)
    if normalized_code in FUND_NAME_MAP:
        return FUND_NAME_MAP[normalized_code]

    if fallback:
        fallback_text = str(fallback).strip()
        if fallback_text:
            return fallback_text

    return normalized_code or "未知基金"


__all__ = ["FUND_NAME_MAP", "get_fund_name", "normalize_fund_code"]
