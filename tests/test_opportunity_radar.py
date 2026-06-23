# -*- coding: utf-8 -*-
"""Unit tests for opportunity radar candidate selection."""

from types import SimpleNamespace
import sys
import unittest

from src.services.opportunity_radar import (
    OpportunityCandidate,
    build_open_fund_candidates,
    build_stock_candidates,
    format_opportunity_radar_report,
    parse_fund_candidate_specs,
)


def _analysis_result(**overrides):
    defaults = {
        "code": "600519",
        "name": "贵州茅台",
        "sentiment_score": 68,
        "decision_type": "buy",
        "operation_advice": "回踩买入",
        "confidence_level": "高",
        "current_price": 100.0,
        "change_pct": 1.2,
        "analysis_summary": "趋势向上，接近支撑位，适合等待回踩确认。",
        "risk_warning": "",
        "dashboard": {
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "99",
                    "stop_loss": "94",
                    "take_profit": "112",
                }
            },
            "intelligence": {"risk_alerts": []},
        },
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class OpportunityRadarTestCase(unittest.TestCase):
    def test_buy_candidate_near_sniper_point_is_selected(self):
        candidates = build_stock_candidates([_analysis_result()], min_score=60, top_n=3)

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.code, "600519")
        self.assertEqual(candidate.action, "重点跟踪")
        self.assertGreaterEqual(candidate.radar_score, 60)
        self.assertIn("接近买点", candidate.tags)
        self.assertEqual(candidate.ideal_buy, 99.0)

    def test_sell_or_low_score_candidate_is_filtered(self):
        candidates = build_stock_candidates([
            _analysis_result(
                code="300750",
                name="宁德时代",
                sentiment_score=58,
                decision_type="sell",
                operation_advice="减仓",
            )
        ], min_score=45, top_n=3)

        self.assertEqual(candidates, [])

    def test_fund_candidate_specs_parse_and_dedupe(self):
        specs = parse_fund_candidate_specs([
            "110011:易方达中小盘混合",
            "003096|中欧医疗健康混合A",
            "008888:示例主动基金:主动权益",
            "110011:重复",
            "  ",
        ])

        self.assertEqual([item.code for item in specs], ["110011", "003096", "008888"])
        self.assertEqual(specs[0].name, "易方达中小盘混合")
        self.assertEqual(specs[1].name, "中欧医疗健康混合A")
        self.assertEqual(specs[2].style, "主动权益")

    def test_open_fund_candidate_scores_with_fake_nav_data(self):
        class FakeFundFrame:
            columns = ["净值日期", "单位净值"]

            def __len__(self):
                return 80

            def __getitem__(self, key):
                if key == "单位净值":
                    return [1.0 + index * 0.002 for index in range(80)]
                raise KeyError(key)

        class FakeAkShare:
            @staticmethod
            def fund_open_fund_info_em(symbol, indicator):
                self.assertEqual(symbol, "008888")
                self.assertEqual(indicator, "单位净值走势")
                return FakeFundFrame()

        old_akshare = sys.modules.get("akshare")
        sys.modules["akshare"] = FakeAkShare
        try:
            candidates = build_open_fund_candidates(
                parse_fund_candidate_specs(["008888:示例主动基金:主动权益"]),
                top_n=1,
            )
        finally:
            if old_akshare is None:
                sys.modules.pop("akshare", None)
            else:
                sys.modules["akshare"] = old_akshare

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].code, "008888")
        self.assertIn("主动权益", candidates[0].tags)
        self.assertIn(candidates[0].action, {"重点跟踪", "定投观察", "等待"})

    def test_report_contains_disclaimer_and_fund_section(self):
        report = format_opportunity_radar_report(
            [
                OpportunityCandidate(
                    code="600519",
                    name="贵州茅台",
                    asset_type="A股",
                    radar_score=76,
                    action="重点跟踪",
                    reason="接近买点。",
                    risk="跌破止损退出。",
                )
            ],
            [
                OpportunityCandidate(
                    code="110011",
                    name="易方达中小盘混合",
                    asset_type="场外基金",
                    radar_score=70,
                    action="定投观察",
                    reason="近20日趋势改善。",
                    risk="分批控制。",
                )
            ],
        )

        self.assertIn("不构成收益承诺或下单指令", report)
        self.assertIn("## A股/ETF 候选", report)
        self.assertIn("## 场外基金候选", report)


if __name__ == "__main__":
    unittest.main()
