from types import SimpleNamespace

from src.data_sources import MarketDataRouter, NewsDataRouter
from src.services.analysis_context_builder import AnalysisContextBuilder, PipelineAnalysisArtifacts


class _FakeQuote:
    code = "600519"
    name = "测试股票"
    source = SimpleNamespace(value="akshare_sina")
    price = 12.3
    change_pct = 1.2
    provider_timestamp = None

    def has_basic_data(self):
        return True


class _FailingFetcherManager:
    def get_realtime_quote(self, stock_code, *, log_final_failure=True):
        raise RuntimeError("provider timeout")


class _QuoteFetcherManager:
    def get_realtime_quote(self, stock_code, *, log_final_failure=True):
        return _FakeQuote()


class _ChipFetcherManager:
    def get_chip_distribution(self, stock_code):
        return SimpleNamespace(
            code=stock_code,
            date="2026-06-22",
            source="akshare",
            profit_ratio=0.52,
            avg_cost=101.2,
            concentration_90=0.13,
        )


class _EmptyChipFetcherManager:
    def get_chip_distribution(self, stock_code):
        return None


def test_market_data_router_returns_insufficient_bundle_on_realtime_failure():
    router = MarketDataRouter(_FailingFetcherManager())

    bundle = router.get_realtime_quote("600519")

    assert bundle.realtime_quote is None
    assert bundle.status.value == "failed"
    assert "数据不足" in (bundle.insufficient_reason or "")
    assert bundle.attempts[0].error_message == "provider timeout"


def test_market_data_router_marks_quote_source_and_timestamp():
    router = MarketDataRouter(_QuoteFetcherManager())

    bundle = router.get_realtime_quote("600519")

    assert bundle.realtime_quote is not None
    assert bundle.source_name == "akshare_sina"
    assert bundle.status.value == "ok"
    assert bundle.to_context_metadata()["source_name"] == "akshare_sina"


def test_market_data_router_marks_chip_source_and_timestamp():
    router = MarketDataRouter(_ChipFetcherManager())

    bundle = router.get_chip_distribution("600519")

    assert bundle.chip_distribution is not None
    assert bundle.source_name == "akshare"
    assert bundle.status.value == "ok"
    assert bundle.to_context_metadata()["data_timestamp"] == "2026-06-22"


def test_analysis_context_pack_preserves_chip_unavailable_reason():
    router = MarketDataRouter(_EmptyChipFetcherManager())
    bundle = router.get_chip_distribution("159915")

    pack = AnalysisContextBuilder.build(
        PipelineAnalysisArtifacts(
            code="159915",
            stock_name="ETF测试",
            market="cn",
            phase=None,
            base_context={"today": {}, "yesterday": {}},
            enhanced_context={"data_source_meta": {"chip": bundle.to_context_metadata()}},
            realtime_quote=None,
            trend_result=None,
            chip_data=None,
            fundamental_context=None,
            news_context=None,
            news_result_count=None,
            metadata={},
        )
    )

    chip_item = pack.blocks["chip"].items["chip_distribution"]
    assert pack.blocks["chip"].metadata["status"] == "empty"
    assert "AkShare" in chip_item.missing_reason


class _SearchService:
    is_available = True

    def search_comprehensive_intel(self, stock_code, stock_name, max_searches=5):
        return {
            "latest_news": SimpleNamespace(
                success=True,
                provider="Anspire",
                results=[SimpleNamespace(title="新闻1"), SimpleNamespace(title="新闻2")],
            ),
            "announcements": SimpleNamespace(
                success=True,
                provider="SerpAPI",
                results=[SimpleNamespace(title="公告1")],
            ),
        }

    def format_intel_report(self, responses, stock_name):
        return f"【{stock_name} 情报搜索结果】\n1. 新闻1"


def test_news_data_router_records_sources_and_result_count():
    router = NewsDataRouter(_SearchService(), max_items_per_stock=8)

    bundle = router.search_stock_intel(stock_code="600519", stock_name="贵州茅台")

    assert bundle.status.value == "ok"
    assert bundle.result_count == 3
    assert bundle.source_name == "Anspire, SerpAPI"
    assert "贵州茅台" in bundle.context_text


def test_news_data_router_disabled_is_explicit():
    router = NewsDataRouter(_SearchService(), enabled=False)

    bundle = router.search_stock_intel(stock_code="600519", stock_name="贵州茅台")

    assert bundle.status.value == "disabled"
    assert bundle.context_text == ""
    assert "新闻增强已关闭" in (bundle.insufficient_reason or "")
