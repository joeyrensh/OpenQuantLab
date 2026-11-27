# Dynamic market report analysis instructions

Research the supplied public symbol/name list as one peer set. Do not invent or infer user-specific portfolio data.

For each supplied symbol, research current public information in one consolidated request. Prefer company investor relations pages, exchange or regulator filings, and dated earnings releases. Distinguish the filing/publication date from the fiscal period. Include a concise summary of the latest financial results and guidance, business outlook over the next 6–12 months, one material catalyst, and one material risk. Use analyst forecasts only when a dated public source can be identified. Do not invent facts, target prices, or forecasts. If information is unavailable, state that it could not be verified.

Industry ranking, technical strategy signals, valuation, holding-period risk, and adjusted one-year performance are calculated locally and are not included in this API request. Do not claim to have reviewed those private fields. Do not infer industry rank from public news; the report generator combines those local factors with your public-company research after this request.

Choose zero or more fundamental/event labels from the configured `fundamental_tags` list. A tag must have dated, verifiable evidence. Useful distinctions include: `基本面反转` for a documented recovery after weakness; `业绩高增` for strong reported comparable growth; `估值修复` only when both valuation and fundamentals support it; `现金流改善` for disclosed cash-flow improvement; `财报催化` for a recent/near-term report event; `政策/行业利好`, `新品/订单落地`, and `并购重组` for confirmed developments; `减持/解禁压力`, `监管/舆情风险`, and `业绩承压` for documented risks. Do not apply labels from technical strategy data; that field is added locally from the dynamic stock detail.

The report generator calculates quantitative scores locally from main-strategy industry ranks, dynamic holding metrics, and one-year adjusted-price performance. The external research request contains only public symbol and company name; do not assume or request portfolio-specific data. The `STRATEGY` tag is an existing backtest signal such as `多头排列` and is added locally, separate from fundamental/event labels.

Return JSON only, with this structure:

```json
{
  "market_summary": "one concise paragraph",
  "candidates": [
    {
      "symbol": "exact input symbol",
      "fundamental_score": 0,
      "fundamental_tags": ["values from configured fundamental_tags only"],
      "latest_financials": "include publication date and fiscal period when verifiable",
      "outlook": "evidence-based 6–12 month fundamental outlook, not a price target",
      "catalyst": "one concise item",
      "risks": ["concise risk"],
      "confidence": "high, medium, or low",
      "sources": [{"title": "source title", "url": "https://...", "date": "YYYY-MM-DD"}]
    }
  ]
}
```

`fundamental_score` is a comparative evidence-quality and outlook score from 0 to 100, not a probability of return. Return one object for each supplied symbol. Keep each text field brief so the final report can show only the best-ranked candidates.

