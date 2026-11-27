#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""Build and email a scored daily report for CN/US dynamic strategy holdings."""

import html
import json
import os
import re
import time
from urllib.parse import urlparse

import pandas as pd
from ruamel.yaml import YAML

from finance import FINANCE_ROOT
from finance.utility.email_uti import MyEmail
from finance.utility.tickerinfo import TickerInfo


class DynamicMarketReport:
    def __init__(self, market, trade_date):
        self.market = market
        self.base_market = market.split("_")[0]
        self.trade_date = pd.to_datetime(trade_date).strftime("%Y-%m-%d")
        self.ticker_trade_date = pd.to_datetime(trade_date).strftime("%Y%m%d")
        yaml = YAML(typ="safe")
        conf_dir = FINANCE_ROOT / "conf"
        self.analysis = yaml.load((conf_dir / "market_report_analysis.yaml").read_text())
        self.format = yaml.load((conf_dir / "market_report_format.yaml").read_text())

    @staticmethod
    def _progress(message):
        print(f"[动态研判] {message}", flush=True)

    @staticmethod
    def _number(value):
        try:
            result = float(value)
            return result if pd.notna(result) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_industry(value):
        """Parse main-strategy IND such as Industry<span>↑3</span>/12."""
        raw = "" if value is None or pd.isna(value) else str(value)
        plain = html.unescape(re.sub(r"<[^>]*>", "", raw))
        arrow = re.search(r"([↑↓])\s*(\d+)", plain)
        rank = re.search(r"/\s*(\d+)\s*$", plain)
        industry = re.sub(r"[↑↓]\s*\d+", "", plain)
        industry = re.sub(r"/\s*\d+\s*$", "", industry).strip()
        change = None
        if arrow:
            magnitude = int(arrow.group(2))
            # IND arrows encode the 5-day ranking change relative to the 10-day rank.
            change = magnitude if arrow.group(1) == "↑" else -magnitude
        return {
            "industry": industry or None,
            "industry_rank_10d": int(rank.group(1)) if rank else None,
            "industry_rank_improvement_5d": change,
        }

    @staticmethod
    def _percentile_score(value, distribution, higher_is_better=True):
        valid = [item for item in distribution if item is not None and pd.notna(item)]
        if value is None or pd.isna(value) or not valid:
            return None
        count = len(valid)
        if count == 1:
            return 50.0
        less = sum(item < value for item in valid)
        equal = sum(item == value for item in valid)
        rank = less + (equal + 1) / 2
        score = 100 * (rank - 1) / (count - 1)
        return score if higher_is_better else 100 - score

    def _read_csv(self, filename):
        path = FINANCE_ROOT / "data" / filename
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path, low_memory=False)

    def _history_by_symbol(self, symbols):
        """Use TickerInfo's forward-adjusted daily feed and exclude its mock bar."""
        history = {}
        if not symbols:
            return history
        started = time.perf_counter()
        self._progress(f"开始读取 {len(symbols)} 只标的一年复权日线数据。")
        try:
            feeds = TickerInfo(self.ticker_trade_date, self.market).get_backtrader_data_feed()
        except Exception as exc:
            self._progress(
                f"一年日线数据读取失败，耗时 {time.perf_counter() - started:.1f}s：{exc}"
            )
            return history
        self._progress(
            f"一年日线数据读取完成：返回 {len(feeds)} 个标的，耗时 {time.perf_counter() - started:.1f}s；开始计算收益和回撤。"
        )

        window = int(self.analysis.get("history", {}).get("trading_days_per_year", 252))
        end_date = pd.Timestamp(self.trade_date)
        for frame in feeds:
            if frame.empty or "symbol" not in frame or "datetime" not in frame:
                continue
            symbol = str(frame["symbol"].iloc[0]).strip()
            if symbol not in symbols:
                continue
            prices = frame.copy()
            prices["datetime"] = pd.to_datetime(prices["datetime"], errors="coerce")
            prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
            prices = prices[
                prices["datetime"].le(end_date) & prices["close"].gt(0)
            ].dropna(subset=["datetime", "close"])
            prices = prices.sort_values("datetime").drop_duplicates("datetime")
            period = prices.tail(window + 1)
            if len(period) < 2:
                continue
            closes = period["close"]
            full_year = len(period) >= window + 1
            return_1y = closes.iloc[-1] / closes.iloc[0] - 1 if full_year else None
            drawdown = closes / closes.cummax() - 1
            history[symbol] = {
                "return_1y": float(return_1y) if return_1y is not None else None,
                "return_available": float(closes.iloc[-1] / closes.iloc[0] - 1),
                "max_drawdown_1y": float(drawdown.min()) if full_year else None,
                "max_drawdown_available": float(drawdown.min()),
                "history_sessions": len(period) - 1,
                "history_days": len(period),
                "full_year_available": full_year,
            }
        full_year_count = sum(item["full_year_available"] for item in history.values())
        self._progress(
            f"一年行情指标计算完成：有行情 {len(history)}/{len(symbols)} 只，其中完整一年 {full_year_count} 只，其余按可用区间计算回撤；耗时 {time.perf_counter() - started:.1f}s。"
        )
        return history

    def _load_candidates(self):
        started = time.perf_counter()
        self._progress("读取动态持仓、主策略行业排名和行业数据文件。")
        dynamic = self._read_csv(f"{self.market}_stockdetail.csv")
        main = self._read_csv(f"{self.base_market}_stockdetail.csv")
        category = self._read_csv(f"{self.base_market}_category.csv")
        if dynamic.empty or "SYMBOL" not in dynamic:
            self._progress("动态持仓明细为空或缺少 SYMBOL 列，没有候选标的。")
            return [], 0, []

        industry_by_symbol = {}
        category_change_by_industry = {}
        if not category.empty and {"industry_new", "index_diff"}.issubset(category.columns):
            for _, row in category.dropna(subset=["industry_new"]).iterrows():
                category_change_by_industry[str(row["industry_new"]).strip()] = self._number(
                    row.get("index_diff")
                )
        if not main.empty and {"SYMBOL", "IND"}.issubset(main.columns):
            for _, row in main.dropna(subset=["SYMBOL"]).iterrows():
                industry = self._parse_industry(row["IND"])
                if industry["industry_rank_improvement_5d"] is None:
                    industry["industry_rank_improvement_5d"] = category_change_by_industry.get(
                        industry["industry"]
                    )
                industry_by_symbol[str(row["SYMBOL"]).strip()] = industry

        industry_count = len(category) if not category.empty else 0
        category_trend = []
        if not category.empty and "index_diff" in category:
            category_trend = [
                self._number(value)
                for value in pd.to_numeric(category["index_diff"], errors="coerce")
            ]
            category_trend = [value for value in category_trend if value is not None]

        dynamic = dynamic.dropna(subset=["SYMBOL"]).drop_duplicates(
            subset=["SYMBOL"], keep="last"
        )
        symbols = [str(symbol).strip() for symbol in dynamic["SYMBOL"]]
        history_by_symbol = self._history_by_symbol(set(symbols))
        candidates = []
        strategy_column = self.analysis.get("categories", {}).get(
            "technical_source", "dynamic_stockdetail.STRATEGY"
        ).split(".")[-1]
        for _, row in dynamic.iterrows():
            symbol = str(row["SYMBOL"]).strip()
            main_industry = industry_by_symbol.get(symbol, {})
            history = history_by_symbol.get(symbol, {})
            pe = self._number(row.get("PE"))
            strategy = row.get(strategy_column)
            candidate = {
                "symbol": symbol,
                "name": str(row.get("NAME", "") or ""),
                "industry": main_industry.get("industry"),
                "industry_rank_10d": main_industry.get("industry_rank_10d"),
                "industry_rank_improvement_5d": main_industry.get(
                    "industry_rank_improvement_5d"
                ),
                "pe": pe if pe is not None and pe > 0 else None,
                "return_since_entry": self._number(row.get("PNL RATIO")),
                "sortino_since_entry": self._number(row.get("SORTINO RATIO")),
                "max_drawdown_since_entry": self._number(row.get("MAX DD")),
                "return_1y": history.get("return_1y"),
                "return_available": history.get("return_available"),
                "max_drawdown_1y": history.get("max_drawdown_1y"),
                "max_drawdown_available": history.get("max_drawdown_available"),
                "history_sessions": history.get("history_sessions", 0),
                "history_days": history.get("history_days", 0),
                "full_year_available": history.get("full_year_available", False),
                "main_industry_matched": bool(main_industry.get("industry")),
                "industry_factor_complete": (
                    main_industry.get("industry_rank_10d") is not None
                    and main_industry.get("industry_rank_improvement_5d") is not None
                ),
                "technical_tag": "" if strategy is None or pd.isna(strategy) else str(strategy).strip(),
            }
            candidates.append(candidate)

        if not industry_count:
            ranks = [item["industry_rank_10d"] for item in candidates if item["industry_rank_10d"] is not None]
            industry_count = max(ranks) + 1 if ranks else 1
        for candidate in candidates:
            rank = candidate["industry_rank_10d"]
            candidate["score_industry_rank_10d"] = (
                max(0.0, min(100.0, 100 * (industry_count - 1 - rank) / (industry_count - 1)))
                if rank is not None and industry_count > 1
                else None
            )
            candidate["score_industry_rank_improvement_5d"] = self._percentile_score(
                candidate["industry_rank_improvement_5d"], category_trend
            )

        factors = self.analysis["scoring"]["factors"]
        for factor, settings in factors.items():
            if factor in (
                "industry_rank_10d",
                "industry_rank_improvement_5d",
            ):
                continue
            values = [candidate.get(factor) for candidate in candidates]
            higher_is_better = settings["direction"] == "higher_is_better"
            for candidate in candidates:
                candidate[f"score_{factor}"] = self._percentile_score(
                    candidate.get(factor), values, higher_is_better
                )

        factor_weights = {
            factor: settings["weight"] for factor, settings in factors.items()
        }
        for candidate in candidates:
            weighted = [
                (candidate.get(f"score_{factor}"), weight)
                for factor, weight in factor_weights.items()
                if candidate.get(f"score_{factor}") is not None
            ]
            weight_sum = sum(weight for _, weight in weighted)
            candidate["quantitative_score"] = (
                sum(score * weight for score, weight in weighted) / weight_sum
                if weight_sum
                else 50.0
            )
        candidates.sort(key=lambda item: item["quantitative_score"], reverse=True)
        self._progress(
            f"候选数据及本地量化评分完成：{len(candidates)} 只标的，覆盖 {industry_count} 个行业，耗时 {time.perf_counter() - started:.1f}s。"
        )
        return candidates, industry_count, category_trend

    def _research_candidates(self, candidates):
        settings = self.analysis.get("llm", {})
        max_candidates = int(settings.get("max_candidates", 20))
        shortlist = sorted(candidates, key=lambda item: item["symbol"])
        if max_candidates > 0:
            shortlist = shortlist[:max_candidates]
        if not shortlist:
            self._progress("没有候选标的，跳过 LLM 财报/新闻研判。")
            return {}

        self._progress(
            f"准备调用 LLM 进行联网财报/新闻检索和摘要：{len(shortlist)} 只标的，模型 {settings.get('model', 'qwen3.7-max')}。"
        )

        try:
            from dotenv import load_dotenv
            import httpx
            from openai import OpenAI
        except Exception as exc:
            self._progress(f"LLM 依赖初始化失败：{exc}")
            return self._research_failure(exc, retries=0)

        try:
            load_dotenv()
        except Exception as exc:
            self._progress(f"读取 LLM 环境配置失败：{exc}")
            return self._research_failure(exc, retries=0)
        api_key = os.getenv("API_KEY")
        if not api_key:
            self._progress("LLM 研判跳过：未配置 API_KEY。")
            return self._research_failure(
                RuntimeError("缺少环境变量 API_KEY"), retries=0
            )

        try:
            prompt_path = FINANCE_ROOT / "conf" / "market_report_analysis.md"
            analysis_guide = prompt_path.read_text(encoding="utf-8")
            public_symbols = [
                {"symbol": item["symbol"], "name": item["name"]}
                for item in shortlist
            ]
            allowed_tags = self.analysis.get("categories", {}).get("fundamental_tags", [])
            prompt = (
                analysis_guide
                + "\n\nAllowed fundamental/event tags:\n"
                + json.dumps(allowed_tags, ensure_ascii=False)
                + "\n\nMarket: "
                + ("A-share" if self.base_market == "cn" else "US stocks")
                + f"\nReport date: {self.trade_date}\n"
                + "Research this entire symbol set in this single request.\n"
                + json.dumps(public_symbols, ensure_ascii=False)
            )
        except Exception as exc:
            self._progress(f"LLM 提示词准备失败：{exc}")
            return self._research_failure(exc, retries=0)

        # This API request performs both public news research and JSON summary
        # generation, so a malformed response or request failure retries both.
        retry_count = min(1, max(0, int(settings.get("retry_count", 1))))
        last_error = None
        for attempt in range(retry_count + 1):
            http_client = None
            request_started = time.perf_counter()
            self._progress(
                f"LLM 请求中（第 {attempt + 1}/{retry_count + 1} 次，最长等待 180 秒）。"
            )
            try:
                http_client = httpx.Client(timeout=180)
                client = OpenAI(
                    api_key=api_key,
                    base_url="https://token-plan.maas.qianwenaiapi.com/compatible-mode/v1",
                    http_client=http_client,
                )
                response = client.responses.create(
                    model=settings.get("model", "qwen3.7-max"),
                    input=prompt,
                    tools=[{"type": "web_search"}, {"type": "web_extractor"}],
                    max_output_tokens=int(settings.get("max_output_tokens", 6000)),
                    extra_body={"enable_thinking": True},
                )
                response_text = (response.output_text or "").strip()
                self._progress(
                    f"LLM 已返回内容：{len(response_text)} 个字符，耗时 {time.perf_counter() - request_started:.1f}s；正在校验结果。"
                )
                response_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text)
                try:
                    payload = json.loads(response_text)
                except json.JSONDecodeError:
                    start, end = response_text.find("{"), response_text.rfind("}")
                    if start < 0 or end <= start:
                        raise
                    payload = json.loads(response_text[start : end + 1])
                if not isinstance(payload, dict):
                    raise ValueError("LLM response JSON 顶层必须是对象")
                raw_candidates = payload.get("candidates")
                if not isinstance(raw_candidates, list):
                    raise ValueError("LLM response 缺少 candidates 列表")
                returned = {
                    str(item.get("symbol", "")).strip().upper(): item
                    for item in raw_candidates
                    if isinstance(item, dict) and str(item.get("symbol", "")).strip()
                }
                expected = {
                    item["symbol"].strip().upper(): item["symbol"]
                    for item in shortlist
                }
                missing = [symbol for symbol in expected if symbol not in returned]
                if missing:
                    preview = ", ".join(missing[:10])
                    more = "…" if len(missing) > 10 else ""
                    raise ValueError(
                        f"LLM response 缺少 {len(missing)} 个标的结果：{preview}{more}"
                    )
                researched = {
                    expected[symbol]: returned[symbol] for symbol in expected
                }
                invalid = [
                    symbol
                    for symbol, item in researched.items()
                    if self._number(item.get("fundamental_score")) is None
                    or not all(
                        isinstance(item.get(field), str) and item[field].strip()
                        for field in ("latest_financials", "outlook", "catalyst")
                    )
                    or not isinstance(item.get("risks"), list)
                    or not isinstance(item.get("sources"), list)
                ]
                if invalid:
                    preview = ", ".join(invalid[:10])
                    more = "…" if len(invalid) > 10 else ""
                    raise ValueError(
                        f"LLM response 中 {len(invalid)} 个标的缺少必需研判字段：{preview}{more}"
                    )
                if not researched:
                    raise ValueError("LLM response 未包含有效个股研判结果")
                market_summary = str(payload.get("market_summary", "")).strip()
                if not market_summary:
                    raise ValueError("LLM response 缺少 market_summary")
                self._progress(
                    f"LLM 研判完成并通过校验：{len(researched)} 只标的，重试 {attempt} 次。"
                )
                return {
                    "market_summary": market_summary,
                    "candidates": researched,
                    "error": None,
                    "retries": attempt,
                }
            except Exception as exc:
                last_error = exc
                self._progress(
                    f"LLM 第 {attempt + 1}/{retry_count + 1} 次请求失败，耗时 {time.perf_counter() - request_started:.1f}s：{exc}"
                )
                if attempt < retry_count:
                    self._progress("即将自动重试一次。")
            finally:
                if http_client:
                    try:
                        http_client.close()
                    except Exception as exc:
                        print(f"关闭 LLM HTTP 连接失败: {exc}")

        return self._research_failure(last_error, retries=retry_count, api_key=api_key)

    @staticmethod
    def _research_failure(exc, retries, api_key=None):
        message = f"{type(exc).__name__}: {exc}" if exc else "未知错误"
        if api_key:
            message = message.replace(api_key, "[redacted]")
        return {
            "market_summary": "",
            "candidates": {},
            "error": message[:1000],
            "retries": retries,
        }

    def _apply_research_and_score(self, candidates, research):
        scoring = self.analysis["scoring"]
        quant_weight = float(scoring.get("quantitative_weight", 0.8))
        fundamental_weight = float(self.analysis.get("llm", {}).get("fundamental_weight", 0.2))
        categories = self.analysis.get("categories", {})
        allowed_fundamental_tags = set(categories.get("fundamental_tags", []))
        for candidate in candidates:
            details = research.get("candidates", {}).get(candidate["symbol"], {})
            fundamental_score = self._number(details.get("fundamental_score"))
            if fundamental_score is not None:
                fundamental_score = max(0.0, min(100.0, fundamental_score))
                candidate["score"] = (
                    candidate["quantitative_score"] * quant_weight
                    + fundamental_score * fundamental_weight
                ) / (quant_weight + fundamental_weight)
            else:
                candidate["score"] = candidate["quantitative_score"]
            raw_fundamental_tags = details.get("fundamental_tags", [])
            candidate["fundamental_tags"] = [
                tag for tag in raw_fundamental_tags
                if isinstance(tag, str) and tag in allowed_fundamental_tags
            ] if isinstance(raw_fundamental_tags, list) else []
            industry_tags = []
            for rule in categories.get("industry_rules", []):
                conditions = rule.get("conditions", [])
                matches = bool(conditions)
                for condition in conditions:
                    actual = self._number(candidate.get(condition.get("field")))
                    expected = self._number(condition.get("value"))
                    operator = condition.get("operator")
                    if actual is None or expected is None:
                        matches = False
                    elif operator == "gte":
                        matches = matches and actual >= expected
                    elif operator == "lte":
                        matches = matches and actual <= expected
                    elif operator == "gt":
                        matches = matches and actual > expected
                    elif operator == "lt":
                        matches = matches and actual < expected
                    elif operator == "eq":
                        matches = matches and actual == expected
                    else:
                        matches = False
                if matches:
                    industry_tags.append(rule.get("label", rule.get("id", "")))
            candidate["industry_tags"] = industry_tags
            candidate["category"] = " · ".join(
                industry_tags + candidate["fundamental_tags"]
            ) or categories.get("fallback_tag", "暂无明确优势")
            candidate["fundamental_score"] = fundamental_score
            for field in ("latest_financials", "outlook", "catalyst", "confidence"):
                candidate[field] = str(details.get(field, "") or "")
            candidate["risks"] = details.get("risks", []) if isinstance(details.get("risks", []), list) else []
            candidate["sources"] = details.get("sources", []) if isinstance(details.get("sources", []), list) else []
            candidate["market_summary"] = research.get("market_summary", "")
        candidates.sort(key=lambda item: item["score"], reverse=True)

    def _save_scores(self, candidates):
        rows = []
        for item in candidates:
            rows.append(
                {
                    "REPORT DATE": self.trade_date,
                    "SYMBOL": item["symbol"],
                    "NAME": item["name"],
                    "INDUSTRY": item["industry"],
                    "INDUSTRY RANK 10D": item["industry_rank_10d"],
                    "INDUSTRY RANK IMPROVEMENT 5D": item["industry_rank_improvement_5d"],
                    "PE": item["pe"],
                    "RETURN SINCE ENTRY": item["return_since_entry"],
                    "SORTINO SINCE ENTRY": item["sortino_since_entry"],
                    "MAX DD SINCE ENTRY": item["max_drawdown_since_entry"],
                    "RETURN 1Y": item["return_1y"],
                    "MAX DD 1Y": item["max_drawdown_1y"],
                    "STRATEGY TAG": item["technical_tag"],
                    "INDUSTRY TAGS": ";".join(item["industry_tags"]),
                    "FUNDAMENTAL TAGS": ";".join(item["fundamental_tags"]),
                    "QUANTITATIVE SCORE": item["quantitative_score"],
                    "FUNDAMENTAL SCORE": item.get("fundamental_score"),
                    "SCORE": item["score"],
                    "CATEGORY": item["category"],
                }
            )
        output = FINANCE_ROOT / "data" / f"{self.market}_recommendation_scores.csv"
        pd.DataFrame(rows).to_csv(output, index=False)

    @staticmethod
    def _esc(value):
        return html.escape(str(value if value is not None else ""), quote=True)

    def _format_pct(self, value, digits=1):
        value = self._number(value)
        return self.format["email"]["text"]["missing"] if value is None else f"{value * 100:+.{digits}f}%"

    def _render(
        self, candidates, dynamic_count, research_count, industry_count,
        research_error=None, research_retries=0,
    ):
        email = self.format["email"]
        labels = email["labels"]
        text = email["text"]
        style = email["style"]
        limit = int(email.get("recommendation_limit", 3))
        recommendation_rules = self.analysis.get("recommendations", {})
        eligible = candidates
        if recommendation_rules.get("require_main_industry_match", True):
            eligible = [item for item in eligible if item["industry_factor_complete"]]
        if recommendation_rules.get("require_fundamental_assessment", True):
            eligible = [item for item in eligible if item.get("fundamental_score") is not None]
        picks = eligible[:limit]
        market_name = "A股" if self.base_market == "cn" else "美股"
        subject = email["subject"].format(market_name=market_name, trade_date=self.trade_date)

        def metric(item, key, suffix=""):
            value = item.get(key)
            if value is None or pd.isna(value):
                return text["missing"]
            digits = 1 if key == "pe" else 2
            return f"{value:.{digits}f}{suffix}" if isinstance(value, (int, float)) else f"{value}{suffix}"

        def source_links(sources):
            links = []
            for source in sources[:3]:
                if not isinstance(source, dict):
                    continue
                url = str(source.get("url", ""))
                if urlparse(url).scheme not in ("https", "http"):
                    continue
                title = self._esc(source.get("title") or url)
                links.append(f'<a href="{self._esc(url)}" style="color:{style["accent"]};">{title}</a>')
            return " · ".join(links) or text["missing"]

        card_html = []
        for index, item in enumerate(picks):
            rank_improvement = item.get("industry_rank_improvement_5d")
            if rank_improvement is None:
                industry_change = text["missing"]
            elif rank_improvement > 0:
                industry_change = email["rank_improved_template"].format(value=rank_improvement)
            elif rank_improvement < 0:
                industry_change = email["rank_deteriorated_template"].format(value=abs(rank_improvement))
            else:
                industry_change = email["rank_unchanged"]
            if item.get("full_year_available"):
                return_1y = self._format_pct(item.get("return_1y"))
                drawdown_1y = self._format_pct(item.get("max_drawdown_1y"))
                drawdown_label = labels["max_drawdown_1y"]
            else:
                available_return = self._format_pct(item.get("return_available"))
                return_1y = email["partial_history_template"].format_map(
                    {"sessions": item.get("history_sessions", 0), "return": available_return}
                )
                available_drawdown = item.get("max_drawdown_available")
                if available_drawdown is not None:
                    drawdown_label = labels.get(
                        "max_drawdown_available", labels["max_drawdown_1y"]
                    )
                    drawdown_1y = email["partial_drawdown_template"].format(
                        value=self._format_pct(available_drawdown),
                        days=item.get("history_days", 0),
                    )
                else:
                    drawdown_label = labels["max_drawdown_1y"]
                    drawdown_1y = text["missing"]
            rows = [
                (labels["industry"], item.get("industry") or text["missing"]),
                (labels["industry_rank"], f"#{item['industry_rank_10d'] + 1}" if item.get("industry_rank_10d") is not None else text["missing"]),
                (labels["industry_change"], industry_change),
                (labels["pe"], metric(item, "pe")),
                (labels["entry_return"], self._format_pct(item.get("return_since_entry"))),
                (labels["sortino"], metric(item, "sortino_since_entry")),
                (labels["max_drawdown"], self._format_pct(item.get("max_drawdown_since_entry"))),
                (labels["return_1y"], return_1y),
                (drawdown_label, drawdown_1y),
            ]
            risks = "；".join(str(risk) for risk in item.get("risks", [])) or text["missing"]
            heading = email["first_pick_label"] if index == 0 else f'{email["other_pick_label"]} {index}'
            metric_cells = [
                f'<td style="padding:7px 9px;border:1px solid {style["border"]};width:25%;">'
                f'<div style="font-size:11px;color:{style["muted"]};">{self._esc(label)}</div>'
                f'<div style="font-size:14px;font-weight:bold;color:{style["text"]};">{self._esc(value)}</div></td>'
                for label, value in rows
            ]
            rows_html = "".join(
                f'<tr>{"".join(metric_cells[i:i + 4])}</tr>'
                for i in range(0, len(metric_cells), 4)
            )
            score_text = f"{item['score']:.1f}{email['score_suffix']}"
            tag_groups = [
                (labels["technical_tags"], [item.get("technical_tag")] if item.get("technical_tag") else []),
                (labels["industry_tags"], item.get("industry_tags", [])),
                (labels["fundamental_tags"], item.get("fundamental_tags", [])),
            ]
            tag_rows = []
            for group_label, tags in tag_groups:
                if not tags:
                    continue
                pills = "".join(
                    f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:3px 8px;border:1px solid {style["border"]};border-radius:12px;background:{style["tag_background"]};font-size:11px;color:{style["text"]};">{self._esc(tag)}</span>'
                    for tag in tags
                )
                tag_rows.append(
                    f'<tr><td colspan="4" style="padding:4px 12px;"><b>{self._esc(group_label)}：</b>{pills}</td></tr>'
                )
            card_html.append(
                f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid {style["border"]};border-collapse:collapse;margin:0 0 14px;background:{style["surface"]};">'
                f'<tr><td colspan="4" style="padding:10px 14px;background:{style["accent"]};color:#ffffff;">'
                '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>'
                f'<td><div style="font-size:11px;">{self._esc(heading)}</div>'
                f'<strong style="font-size:18px;">{self._esc(item["name"])} ({self._esc(item["symbol"])})</strong></td>'
                f'<td align="right" style="font-size:16px;font-weight:bold;white-space:nowrap;">{self._esc(score_text)}</td>'
                '</tr></table></td></tr>'
                f'{rows_html}'
                + "".join(tag_rows)
                + f'<tr><td colspan="4" style="padding:10px 12px 4px;"><b>{self._esc(labels["latest_financials"])}：</b>{self._esc(item.get("latest_financials") or text["no_research"])}</td></tr>'
                + f'<tr><td colspan="4" style="padding:4px 12px;"><b>{self._esc(labels["catalyst"])}：</b>{self._esc(item.get("catalyst") or text["missing"])}</td></tr>'
                + f'<tr><td colspan="4" style="padding:4px 12px;"><b>{self._esc(labels["outlook"])}：</b>{self._esc(item.get("outlook") or text["no_research"])}</td></tr>'
                + f'<tr><td colspan="4" style="padding:4px 12px;"><b>{self._esc(labels["risks"])}：</b>{self._esc(risks)}</td></tr>'
                + f'<tr><td colspan="4" style="padding:4px 12px 11px;font-size:12px;"><b>{self._esc(labels["references"])}：</b>{source_links(item.get("sources", []))}</td></tr>'
                + '</table>'
            )

        overall = candidates[0].get("market_summary", "") if picks else ""
        if not picks:
            empty_message = text["no_candidates"] if not candidates else text["no_eligible_candidates"]
            card_html.append(f'<p style="color:{style["muted"]};">{self._esc(empty_message)}</p>')
        subtitle = email.get("subtitle", "").format(
            screened=dynamic_count,
            scored=len(candidates),
            researched=research_count,
            industry_count=industry_count,
        )
        failure_notice = ""
        if research_error:
            failure_message = text.get(
                "llm_failure", "LLM研判失败，报告中未包含可靠的基本面摘要。"
            ).format(retries=research_retries, error=research_error)
            failure_notice = (
                '<div style="margin:12px 0;padding:10px 12px;border:1px solid #d9822b;'
                'background:#fff7e8;color:#7a4b12;">'
                f'{self._esc(failure_message)}</div>'
            )
        body = (
            f'<div style="max-width:900px;margin:0 auto;padding:16px;background:{style["surface"]};color:{style["text"]};font-family:Arial,\'Microsoft YaHei\',sans-serif;line-height:1.55;">'
            f'<div style="padding:16px 18px;background:{style["accent"]};color:#ffffff;">'
            f'<div style="font-size:21px;font-weight:bold;">{self._esc(email["title"])}</div>'
            f'<div style="font-size:13px;margin-top:4px;">{self._esc(market_name)} · {self._esc(self.trade_date)}</div>'
            f'<div style="font-size:12px;margin-top:6px;">{self._esc(subtitle)}</div></div>'
            + failure_notice
            + f'<div style="padding:12px 2px 4px;">{self._esc(overall)}</div>'
            + f'<h3 style="margin:10px 0 8px;">{self._esc(email["recommendation_heading"])}</h3>'
            + "".join(card_html)
            + f'<div style="padding-top:10px;border-top:1px solid {style["border"]};font-size:11px;color:{style["muted"]};">'
            f'<b>{self._esc(labels["methodology"])}：</b>{self._esc(text["methodology"])}<br>{self._esc(text["source_note"])}'
            '</div></div>'
        )
        return subject, '<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;padding:12px;background:' + style["background"] + ';">' + body + '</body></html>'

    def send(self):
        if self.market not in ("cn_dynamic", "us_dynamic"):
            return
        started = time.perf_counter()
        self._progress(f"开始生成 {self.market} 研判报告，交易日 {self.trade_date}。")
        stage_started = time.perf_counter()
        candidates, industry_count, _ = self._load_candidates()
        self._progress(
            f"候选准备阶段结束，耗时 {time.perf_counter() - stage_started:.1f}s。"
        )
        stage_started = time.perf_counter()
        research = self._research_candidates(candidates)
        self._progress(
            f"LLM 研判阶段结束：成功 {len(research.get('candidates', {}))} 只，耗时 {time.perf_counter() - stage_started:.1f}s。"
        )
        stage_started = time.perf_counter()
        self._apply_research_and_score(candidates, research)
        self._save_scores(candidates)
        self._progress(
            f"综合评分和评分文件保存完成，耗时 {time.perf_counter() - stage_started:.1f}s。"
        )
        research_count = len(research.get("candidates", {}))
        self._progress("读取动态股票列表，用于报告候选数量统计。")
        try:
            dynamic_count = len(
                TickerInfo(self.ticker_trade_date, self.market).get_stock_list()
            )
        except Exception as exc:
            dynamic_count = len(candidates)
            self._progress(f"动态股票列表读取失败，改用候选明细数量：{exc}")
        self._progress(f"动态列表统计完成：{dynamic_count} 只。")
        subject, report_html = self._render(
            candidates,
            dynamic_count,
            research_count,
            industry_count,
            research_error=research.get("error"),
            research_retries=research.get("retries", 0),
        )
        self._progress("报告 HTML 已生成，正在发送邮件。")
        stage_started = time.perf_counter()
        MyEmail().send_email(subject, report_html)
        self._progress(
            f"报告邮件已发送：{subject}；发送耗时 {time.perf_counter() - stage_started:.1f}s，总耗时 {time.perf_counter() - started:.1f}s。"
        )

