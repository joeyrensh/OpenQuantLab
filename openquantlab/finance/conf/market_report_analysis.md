# Dynamic market report analysis instructions

Research the supplied public symbol/name list as one peer set for the requested market and report date. Do not invent or infer user-specific portfolio data.

For each supplied symbol, research current public information in this consolidated request. Prefer dated primary sources: for A-shares, company announcements, CNINFO, and the Shanghai/Shenzhen/Beijing exchanges; for US stocks, company investor relations and SEC filings. Distinguish publication date from fiscal period. Summarize the latest reported revenue, operating profit/net income, year-over-year direction, cash flow or margins when disclosed, and management guidance. Then give an evidence-based 6–12 month fundamental outlook, one material catalyst, and one material risk. Use analyst estimates only when a dated public source is available. Do not invent facts, target prices, or stock-price forecasts. If a figure or event cannot be verified, say so explicitly and lower confidence.

The local report generator separately analyzes the strategy's industry ranking, recent strategy PnL snapshots, holding metrics, valuation fields, corporate-action history, and adjusted price data. These per-position fields are not included in this API request. Do not claim to have reviewed them, do not infer the assigned strategy industry from the company name, and do not use them to fabricate public facts. The final report combines your sourced public-company research with those local facts after this request.

Choose zero or more company/fundamental/event labels from the configured `fundamental_tags` list. Every label needs dated evidence in the cited sources and must describe this company's fundamentals or a confirmed event. Apply `政策/行业利好` only when sources show direct business exposure for this company; do not attach a broad sector headline to a company without evidence. Distinguish `业绩高增` from one-off or low-base comparisons; use `基本面反转` only when prior weakness and recovery are both documented; use `估值修复` only when valuation and operating evidence are both verifiable. Treat dividends and stock splits as corporate actions, not automatically as bullish catalysts. Do not emit local technical or strategy-industry labels; those are calculated separately.

The report generator calculates the final cross-sectional score locally. Your `fundamental_score` should reflect source quality, earnings/guidance trajectory, and company-specific catalysts/risks; it is not a probability of return and must not be based on the backtest's open PnL, win rate, or trading strategy. The external research request contains only public symbol and company name. The `STRATEGY` tag is an existing backtest signal such as `多头排列` and is added locally, separate from fundamental/event labels.

Return JSON only, with this structure:

```json
{
  "market_summary": "one concise paragraph",
  "candidates": [
    {
      "symbol": "exact input symbol",
      "fundamental_score": 0,
      "fundamental_tags": ["values from configured fundamental_tags only"],
      "latest_financials": "key reported results, publication date and fiscal period",
      "outlook": "evidence-based 6–12 month fundamental outlook and assumptions",
      "catalyst": "one concise item",
      "risks": ["concise risk"],
      "confidence": "high, medium, or low",
      "sources": [{"title": "source title", "url": "https://...", "date": "YYYY-MM-DD"}]
    }
  ]
}
```

`fundamental_score` is a comparative, source-backed view of fundamentals and outlook from 0 to 100, not a probability of return. Return exactly one object for each supplied symbol, preserving its symbol spelling. Keep each field brief and factual so the final report can show only the highest-ranked candidates. If no reliable company-specific source is found, return a low score, explain the verification gap, use no unsupported tags, and provide an empty sources list.

