# -*- coding: utf-8 -*-
"""Unit tests for open fund display name mapping."""

import unittest

from src.data.fund_mapping import get_fund_name, normalize_fund_code


class FundMappingTestCase(unittest.TestCase):
    def test_fund_mapping_falls_back_safely(self):
        self.assertEqual(normalize_fund_code(8888), "008888")
        self.assertEqual(get_fund_name("008888"), "场外基金008888")
        self.assertEqual(get_fund_name("999999"), "999999")
        self.assertEqual(get_fund_name(None), "未知基金")

    def test_get_fund_name_accepts_network_compat_flag(self):
        self.assertEqual(get_fund_name("999999", allow_network=False), "999999")


if __name__ == "__main__":
    unittest.main()
