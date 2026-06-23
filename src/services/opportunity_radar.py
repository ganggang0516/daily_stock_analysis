# -*- coding: utf-8 -*-
"""Opportunity radar for disciplined stock and fund watchlists.

The radar is intentionally conservative: it ranks candidates that are already
in the analysis universe and reports watch actions, not guaranteed profits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Iterable, List, Mapping, Optional, Sequence

from src.utils.sniper_points import extract_sniper_points


@dataclass
class OpportunityCandidate:
    code: str
    name: str
    asset_type: str
    radar_score: int
    action: str
    reason: str
    risk: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
    ideal_buy: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class FundCandidateSpec:
    code: str
    name: str = ""
    style: str = ""


def parse_fund_candidate_specs(raw_items: Iterable[str]) -> List[FundCandidateSpec]:
    specs: List[FundCandidateSpec] = []
    seen = set()
    for raw in raw_items or []:
        text = str(raw or "").strip()
        if not text:
            continue
        if ":" in text:
            parts = [part.strip() for part in text.split(":", 2)]
            code = parts[0] if parts else ""
            name = parts[1] if len(parts) > 1 else ""
            style = parts[2] if len(parts) > 2 else ""
        elif "|" in text:
            parts = [part.strip() for part in text.split("|", 2)]
            code = parts[0] if parts else ""
            name = parts[1] if len(parts) > 1 else ""
            style = parts[2] if len(parts) > 2 else ""
        else:
            code, name, style = text, "", ""
        code = code.strip()
        name = name.strip()
        if not code or code in seen:
            continue
        seen.add(code)
        specs.append(FundCandidateSpec(code=code, name=name, style=style.strip()))
    return specs


def build_stock_candidates(
    results: Sequence[Any],
    *,
    min_score: int = 60,
    top_n: int = 6,
) -> List[OpportunityCandidate]:
    candidates = [_score_analysis_result(result) for result in results or []]
    eligible = [
        item for item in candidates
        if item.radar_score >= min_score and item.action != "回避"
    ]
    eligible.sort(key=lambda item: (-item.radar_score, item.code))
    return eligible[: max(0, top_n)]


def build_open_fund_candidates(
    specs: Sequence[FundCandidateSpec],
    *,
    top_n: int = 4,
) -> List[OpportunityCandidate]:
    if not specs or top_n <= 0:
        return []
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:
        return [
            OpportunityCandidate(
                code="FUND",
                name="场外基金候选池",
                asset_type="场外基金",
                radar_score=0,
                action="数据不可用",
                reason="AkShare 未安装或不可用，暂无法拉取基金净值走势。",
                risk=str(exc)[:120],
            )
        ]

    candidates: List[OpportunityCandidate] = []
    for spec in specs:
        try:
            candidates.append(_score_open_fund(spec, ak))
        except Exception as exc:
            candidates.append(
                OpportunityCandidate(
                    code=spec.code,
                    name=spec.name or spec.code,
                    asset_type="场外基金",
                    radar_score=0,
                    action="数据不可用",
                    reason="基金净值走势拉取失败。",
                    risk=str(exc)[:120],
                )
            )
    candidates.sort(key=lambda item: (-item.radar_score, item.code))
    return candidates[: max(0, top_n)]


def format_opportunity_radar_report(
    stock_candidates: Sequence[OpportunityCandidate],
    fund_candidates: Sequence[OpportunityCandidate] = (),
    *,
    min_score: int = 60,
) -> str:
    now_cn = datetime.now(timezone(timedelta(hours=8)))
    lines = [
        "# 机会雷达",
        "",
        f"时间: {now_cn.strftime('%Y-%m-%d %H:%M')} 北京时间",
        f"入选阈值: {min_score}",
        "",
        "说明: 这是基于已有分析结果和基金净值走势的候选雷达，不构成收益承诺或下单指令；最终操作仍需结合仓位、止损和个人风险承受能力。",
        "",
    ]

    if stock_candidates:
        lines.extend(["## A股/ETF 候选", ""])
        for item in stock_candidates:
            lines.extend(_format_candidate_lines(item))
    else:
        lines.extend(["## A股/ETF 候选", "", "本轮没有达到阈值的 A股/ETF 候选。", ""])

    if fund_candidates:
        lines.extend(["## 场外基金候选", ""])
        for item in fund_candidates:
            lines.extend(_format_candidate_lines(item))

    lines.extend([
        "## 风控纪律",
        "",
        "- 不追高：涨幅过大或偏离买点时等待回踩。",
        "- 分批：候选只代表观察优先级，不建议一次性满仓。",
        "- 退出：跌破止损或风险提示增多时优先控制回撤。",
    ])
    return "\n".join(lines)


def build_opportunity_radar_report(
    results: Sequence[Any],
    *,
    fund_specs: Sequence[FundCandidateSpec] = (),
    min_score: int = 60,
    top_n: int = 6,
    fund_top_n: int = 4,
) -> str:
    stocks = build_stock_candidates(results, min_score=min_score, top_n=top_n)
    funds = build_open_fund_candidates(fund_specs, top_n=fund_top_n)
    return format_opportunity_radar_report(stocks, funds, min_score=min_score)


def _score_analysis_result(result: Any) -> OpportunityCandidate:
    code = str(getattr(result, "code", "") or "").strip()
    name = str(getattr(result, "name", "") or code).strip()
    base_score = _to_int(getattr(result, "sentiment_score", 50), 50)
    decision_type = str(getattr(result, "decision_type", "") or "").lower()
    action_text = str(getattr(result, "operation_advice", "") or "").strip()
    confidence = str(getattr(result, "confidence_level", "") or "").lower()
    risk_alerts = _extract_risk_alerts(result)
    risk_warning = str(getattr(result, "risk_warning", "") or "").strip()
    price = _to_float(getattr(result, "current_price", None))
    change_pct = _to_float(getattr(result, "change_pct", None))
    sniper = extract_sniper_points(result)
    ideal_buy = sniper.get("ideal_buy")
    stop_loss = sniper.get("stop_loss")
    take_profit = sniper.get("take_profit")

    score = base_score
    tags: List[str] = []
    if decision_type in {"buy", "strong_buy"}:
        score += 8
        tags.append("AI买点")
    elif decision_type in {"sell", "strong_sell"}:
        score -= 28
        tags.append("卖出/风控")
    if confidence in {"高", "high"}:
        score += 4
        tags.append("高置信")
    if change_pct is not None and change_pct >= 7:
        score -= 8
        tags.append("涨幅过大")
    if risk_alerts:
        score -= min(24, len(risk_alerts) * 8)
        tags.append("有风险提示")
    if risk_warning:
        score -= 5

    near_buy = _near_buy_zone(price, ideal_buy)
    if near_buy:
        score += 6
        tags.append("接近买点")
    if stop_loss and price and stop_loss < price:
        stop_gap = (price - stop_loss) / price * 100
        if stop_gap <= 8:
            score += 3
            tags.append("止损清晰")

    action = _stock_action(score, decision_type, near_buy, bool(risk_alerts))
    reason = _compact_reason(
        getattr(result, "analysis_summary", None)
        or getattr(result, "buy_reason", None)
        or action_text
        or "综合评分靠前，进入观察池。"
    )
    risk = _compact_reason(
        risk_alerts[0] if risk_alerts else risk_warning or "按买点/止损纪律执行，避免追高。"
    )
    asset_type = "基金/ETF" if _looks_like_fund_or_etf(code, name) else "A股"
    return OpportunityCandidate(
        code=code,
        name=name,
        asset_type=asset_type,
        radar_score=_clamp_int(score),
        action=action,
        reason=reason,
        risk=risk,
        price=price,
        change_pct=change_pct,
        ideal_buy=ideal_buy,
        stop_loss=stop_loss,
        take_profit=take_profit,
        tags=tags,
    )


def _score_open_fund(spec: FundCandidateSpec, ak: Any) -> OpportunityCandidate:
    df = ak.fund_open_fund_info_em(symbol=spec.code, indicator="单位净值走势")
    if df is None or len(df) < 30:
        raise ValueError("基金净值样本不足")
    value_col = _find_column(df, ("单位净值", "净值", "累计净值"))
    if not value_col:
        raise ValueError("基金净值列缺失")
    values = [
        _to_float(value)
        for value in list(df[value_col])
    ]
    nav = [value for value in values if value and value > 0]
    if len(nav) < 30:
        raise ValueError("有效净值样本不足")

    ret20 = _window_return(nav, 20)
    ret60 = _window_return(nav, min(60, len(nav) - 1))
    drawdown = _max_drawdown(nav[-120:])
    volatility = _annualized_volatility(nav[-60:])
    style = _normalize_fund_style(spec.style or spec.name)
    score = 60 + ret20 * 0.9 + ret60 * 0.35 - drawdown * 0.7 - volatility * 0.25
    if style in {"债券", "货币"}:
        score -= volatility * 0.15
        score -= drawdown * 0.2
    elif style in {"QDII", "海外"}:
        score -= volatility * 0.1
    action = "重点跟踪" if score >= 72 and drawdown <= 15 else "定投观察" if score >= 60 else "等待"
    name = spec.name or spec.code
    reason = f"近20日 {ret20:+.1f}%，近60日 {ret60:+.1f}%，回撤 {drawdown:.1f}%"
    risk = _fund_risk_message(style, drawdown, volatility)
    tags = ["场外基金", "净值趋势"]
    if style:
        tags.append(style)
    if ret20 > 0 and ret60 > 0:
        tags.append("趋势向上")
    if drawdown <= 8:
        tags.append("回撤较低")
    return OpportunityCandidate(
        code=spec.code,
        name=name,
        asset_type="场外基金",
        radar_score=_clamp_int(score),
        action=action,
        reason=reason,
        risk=risk,
        tags=tags,
    )


def _format_candidate_lines(item: OpportunityCandidate) -> List[str]:
    tags = f" | 标签: {', '.join(item.tags[:4])}" if item.tags else ""
    price_bits = []
    if item.price is not None:
        text = f"现价 {item.price:.2f}"
        if item.change_pct is not None:
            text += f" ({item.change_pct:+.2f}%)"
        price_bits.append(text)
    if item.ideal_buy is not None:
        price_bits.append(f"理想买点 {item.ideal_buy:.2f}")
    if item.stop_loss is not None:
        price_bits.append(f"止损 {item.stop_loss:.2f}")
    if item.take_profit is not None:
        price_bits.append(f"止盈 {item.take_profit:.2f}")
    price_line = f"- 点位: {'；'.join(price_bits)}" if price_bits else ""
    lines = [
        f"### {item.action}: {item.name}({item.code})",
        f"- 类型: {item.asset_type} | 雷达分: {item.radar_score}{tags}",
        f"- 理由: {item.reason}",
        f"- 风险: {item.risk}",
    ]
    if price_line:
        lines.append(price_line)
    lines.append("")
    return lines


def _extract_risk_alerts(result: Any) -> List[str]:
    if hasattr(result, "get_risk_alerts"):
        try:
            alerts = result.get_risk_alerts()
            if isinstance(alerts, list):
                return [str(item).strip() for item in alerts if str(item or "").strip()]
        except Exception:
            pass
    dashboard = getattr(result, "dashboard", None)
    if isinstance(dashboard, Mapping):
        intel = dashboard.get("intelligence")
        if isinstance(intel, Mapping):
            alerts = intel.get("risk_alerts")
            if isinstance(alerts, list):
                return [str(item).strip() for item in alerts if str(item or "").strip()]
    return []


def _stock_action(score: float, decision_type: str, near_buy: bool, has_risk: bool) -> str:
    if decision_type in {"sell", "strong_sell"} or score < 45:
        return "回避"
    if has_risk and score < 70:
        return "谨慎观察"
    if score >= 72 and near_buy:
        return "重点跟踪"
    if score >= 64:
        return "等待买点"
    return "观察"


def _near_buy_zone(price: Optional[float], ideal_buy: Optional[float]) -> bool:
    if not price or not ideal_buy:
        return False
    gap = (price - ideal_buy) / ideal_buy * 100
    return -4 <= gap <= 3


def _looks_like_fund_or_etf(code: str, name: str) -> bool:
    text = f"{code} {name}".lower()
    return any(token in text for token in ("etf", "lof", "基金", "指数"))


def _normalize_fund_style(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    style_aliases = (
        ("QDII", ("qdii", "海外", "纳斯达克", "标普", "全球", "越南", "印度", "港股")),
        ("指数", ("指数", "index", "沪深300", "中证", "创业板", "科创", "宽基")),
        ("债券", ("债", "bond", "固收", "纯债", "二级债")),
        ("货币", ("货币", "现金", "money")),
        ("医药", ("医药", "医疗", "生物", "创新药")),
        ("科技", ("科技", "芯片", "半导体", "ai", "人工智能", "数字")),
        ("消费", ("消费", "白酒", "食品", "家电")),
        ("主动权益", ("主动", "混合", "股票", "成长", "价值")),
    )
    for style, aliases in style_aliases:
        if any(alias in text for alias in aliases):
            return style
    return str(value).strip()[:12]


def _fund_risk_message(style: str, drawdown: float, volatility: float) -> str:
    if drawdown >= 15:
        return "回撤偏大，控制单笔投入，等趋势确认后再分批。"
    if style in {"债券", "货币"}:
        return "低波动品种更看重回撤和信用风险，异常波动时降低仓位。"
    if style in {"QDII", "海外"}:
        return "注意汇率、海外市场时差和溢价风险，适合分批观察。"
    if volatility >= 28:
        return "波动偏高，避免一次性追高，优先按定投或分批纪律执行。"
    return "基金适合分批/定投纪律，避免一次性追高。"


def _compact_reason(value: Any, max_length: int = 110) -> str:
    text = str(value or "").replace("\n", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text[:max_length] + ("..." if len(text) > max_length else "")


def _to_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _clamp_int(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def _find_column(df: Any, candidates: Sequence[str]) -> Optional[str]:
    columns = [str(col) for col in getattr(df, "columns", [])]
    for candidate in candidates:
        for column in columns:
            if candidate in column:
                return column
    return None


def _window_return(values: Sequence[float], days: int) -> float:
    if len(values) <= days or not values[-days - 1]:
        return 0.0
    return (values[-1] / values[-days - 1] - 1) * 100


def _max_drawdown(values: Sequence[float]) -> float:
    peak = None
    max_dd = 0.0
    for value in values:
        if peak is None or value > peak:
            peak = value
        if peak:
            max_dd = max(max_dd, (peak - value) / peak * 100)
    return max_dd


def _annualized_volatility(values: Sequence[float]) -> float:
    returns = []
    for prev, current in zip(values, values[1:]):
        if prev:
            returns.append(current / prev - 1)
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252) * 100
