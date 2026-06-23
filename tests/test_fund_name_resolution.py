# -*- coding: utf-8 -*-

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.base import DataFetcherManager
from src.analyzer import get_stock_name_multi_source


class TestFundNameResolution(unittest.TestCase):
    def test_data_fetcher_manager_uses_fund_name_fallback(self):
        manager = DataFetcherManager.__new__(DataFetcherManager)
        manager._fetchers = []

        with patch("data_provider.base.get_fund_name", return_value="易方达蓝筹精选混合"):
            name = manager.get_stock_name("005827", allow_realtime=False)

        self.assertEqual(name, "易方达蓝筹精选混合")

    def test_analyzer_name_resolver_uses_fund_name_fallback(self):
        with patch("src.analyzer.get_fund_name", return_value="中欧医疗健康混合A"):
            name = get_stock_name_multi_source("003095", data_manager=None)

        self.assertEqual(name, "中欧医疗健康混合A")


if __name__ == "__main__":
    unittest.main()
