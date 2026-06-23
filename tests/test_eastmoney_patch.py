# -*- coding: utf-8 -*-
"""Regression tests for Eastmoney request patch resilience."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from src.patches import eastmoney_patch


class TestEastmoneyPatch(unittest.TestCase):
    def setUp(self) -> None:
        eastmoney_patch._cache.data = None
        eastmoney_patch._cache.expire_at = 0
        eastmoney_patch._cache.failure_logged_at = 0

    def test_get_nid_backs_off_after_403(self):
        response = MagicMock()
        response.status_code = 403
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "403 Client Error: Forbidden",
            response=response,
        )

        with patch("src.patches.eastmoney_patch.time.time", return_value=1000.0), patch(
            "src.patches.eastmoney_patch.requests.request",
            return_value=response,
        ) as mock_request:
            self.assertIsNone(eastmoney_patch._get_nid("ua-1"))
            self.assertIsNone(eastmoney_patch._get_nid("ua-2"))

        self.assertEqual(mock_request.call_count, 1)
        self.assertGreaterEqual(eastmoney_patch._cache.expire_at, 1000.0 + 30 * 60)


if __name__ == "__main__":
    unittest.main()
