# ganggang0516 Actions 配置清单

这份清单用于 `ganggang0516/daily_stock_analysis` 的 GitHub Actions 自动日报、盘中买卖点提醒和机会雷达。

## 已在 workflow 默认启用

无需额外配置时，工作流会默认分析：

```env
STOCK_LIST=002827,300502
OPPORTUNITY_FUND_LIST=008888:场外基金008888:主动权益
OPPORTUNITY_RADAR_ENABLED=true
NEWS_STRATEGY_PROFILE=short
NEWS_MAX_AGE_DAYS=3
REPORT_INTEGRITY_ENABLED=true
BACKTEST_ENABLED=true
ENABLE_REALTIME_QUOTE=true
ENABLE_REALTIME_TECHNICAL_INDICATORS=true
FUNDAMENTAL_CACHE_TTL_SECONDS=180
FUNDAMENTAL_CACHE_MAX_ENTRIES=512
```

`002827` 是高争民爆，`300502` 是新易盛。以后如果要改自选股，在 GitHub Repository Variables 里设置 `STOCK_LIST` 即可覆盖默认值。

## 必须手动配置的 Secrets

进入 `Settings -> Secrets and variables -> Actions -> Secrets`，至少配置一个 AI Key 和一个通知渠道。

推荐：

```env
GEMINI_API_KEY=你的 Gemini Key
TELEGRAM_BOT_TOKEN=你的 Telegram Bot Token
TELEGRAM_CHAT_ID=你的 Telegram Chat ID
```

如果你使用 AIHubMix 或 Anspire，也可以配置：

```env
AIHUBMIX_KEY=你的 AIHubMix Key
ANSPIRE_API_KEYS=你的 Anspire Key
```

## 可选 Variables

进入 `Settings -> Secrets and variables -> Actions -> Variables`，按需要覆盖默认值：

```env
STOCK_LIST=002827,300502
OPPORTUNITY_FUND_LIST=008888:你的基金名称:主动权益
OPPORTUNITY_RADAR_MIN_SCORE=60
OPPORTUNITY_RADAR_TOP_N=6
OPPORTUNITY_RADAR_FUND_TOP_N=4
ENABLE_CHIP_DISTRIBUTION=false
REALTIME_SOURCE_PRIORITY=tencent,akshare_sina,efinance,akshare_em
```

如果某个免费接口不稳定，优先保持 `ENABLE_CHIP_DISTRIBUTION=false`，避免影响主流程。

## 手动测试

合并 PR 后：

1. 进入 `Actions -> 每日股票分析`。
2. 点击 `Run workflow`。
3. `mode` 选择 `full`。
4. 跑完后查看日志，确认出现：
   - `机会雷达: true`
   - `场外基金候选: ✅ 已配置`
   - `自动回测: true`
   - `新闻增强: ✅ 已开启`
   - `实时行情: quote=true technical=true`

