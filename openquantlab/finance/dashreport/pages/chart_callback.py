"""
修正版：单个通用回调 + DataLoader 驱动 (支持动态 Style / AspectRatio 返回)
"""

from dash import (
    ALL,
    MATCH,
    Input,
    Output,
    Patch,
    State,
    callback,
    ctx,
    html,
    no_update,
)
import plotly.graph_objects as go
from finance.dashreport.data_loader import ReportDataLoader
from finance.utility.toolkit import ToolKit
import time


class ChartCallback:
    """
    图表回调管理器 - 单个通用回调
    """

    _instance = None
    # industry_pnl_trend adds five consecutive traces for each industry:
    # history, interval lower, interval upper, forecast, and summary.
    _PNL_TREND_TRACES_PER_INDUSTRY = 5

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._charts = {}
            self._callback_registered = False
            self._initialized = True

    @staticmethod
    def _get_scale(
        base_fig_width=1440,
        client_width=None,
        min_scale=0.6,
        max_scale=1.05,
    ):
        """计算缩放比例"""
        if client_width is None:
            return 1.0
        if client_width < 550:
            scale = client_width / base_fig_width
        else:
            scale = 1.0
        return max(min_scale, min(scale, max_scale))

    @staticmethod
    def _get_font_sizes(client_width, base_font=12, min_scale=0.9, max_scale=1.05):
        """获取字体大小"""
        scale = ChartCallback._get_scale(1440, client_width, min_scale, max_scale)
        font_size = int(base_font * scale)
        return scale, font_size

    @staticmethod
    def _get_chart_style(chart_type: str, client_width: int):
        """
        根据图表类型与客户端宽度动态生成 style 字典
        """
        base_style = {
            "margin": 0,
            "padding": 0,
            "width": "100%",
            "height": "auto",
        }

        # Annual Return's ratio belongs to its chart-plus-metrics wrapper.
        if chart_type == "annual_return":
            base_style["height"] = "100%"
            return base_style

        base_style["aspectRatio"] = "1.6 / 1"
        return base_style

    @staticmethod
    def _placeholder_figure(
        text: str = "Run Backtest", theme: str = "light", client_width: int = 1440
    ):
        """生成一个显示文本的占位图表"""
        bg_color = "rgba(255, 255, 255, 0)"
        _, font_size = ChartCallback._get_font_sizes(
            client_width, base_font=12, min_scale=0.9, max_scale=1.05
        )
        fig = go.Figure()
        fig.add_annotation(
            text=text,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=font_size, color="#999"),
        )
        fig.update_layout(
            template="plotly_white" if theme == "light" else "plotly_dark",
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            xaxis=dict(showgrid=False, showticklabels=False, visible=False),
            yaxis=dict(showgrid=False, showticklabels=False, visible=False),
        )
        return fig

    # =========================
    # 注册图表（不传 DataFrame）
    # =========================
    def register_chart(
        self,
        chart_type: str,
        page_prefix: str,
        chart_builder,
        datasets,
        index: int = 0,
        industry_color_maps=None,
    ):
        """
        datasets: tuple[str, ...]
        """
        key = f"{chart_type}_{page_prefix}_{index}"
        self._charts[key] = {
            "builder": chart_builder,
            "datasets": tuple(datasets),
            "chart_type": chart_type,
            "page": page_prefix,
            "index": index,
            "industry_color_maps": industry_color_maps or {},
        }
        return key

    def get_chart_id(self, chart_type, page_prefix, index=0):
        return {
            "type": "dynamic-chart",
            "page": page_prefix,
            "chart": chart_type,
            "index": index,
        }

    @staticmethod
    def build_industry_selection_summary(
        selected_industries, page, chart_type, index, industry_colors=None
    ):
        if not selected_industries:
            return "Select industries"
        industry_colors = industry_colors or {}
        return [
            html.Span(
                [
                    html.Button(
                        "",
                        id={
                            "type": "industry-trend-remove",
                            "page": page,
                            "chart": chart_type,
                            "index": index,
                            "industry": str(industry),
                        },
                        n_clicks=0,
                        type="button",
                        title=f"Remove {industry}",
                        style={
                            "color": industry_colors.get(
                                str(industry), "var(--text-color)"
                            )
                        },                        
                        **{"aria-label": f"Remove {industry}"},
                    ),
                    html.Span(str(industry)),
                ],
                key=str(industry),
            )
            for industry in selected_industries
        ]

    @staticmethod
    def build_annual_return_metrics(year_groups):
        """Render annual performance metrics as compact, responsive chips."""
        if not year_groups:
            return []

        metric_labels = {
            "Ann.R": ("AnnR", "Annual Return"),
            "Cum.R": ("CumR", "Cumulative Return"),
            "Max.DD": ("MDD", "Max Drawdown"),
            "Daily 5%": ("P5", "Daily Return P5"),
        }
        latest_year = str(year_groups[0].get("year", ""))
        rows = []
        for group in year_groups:
            year = str(group.get("year", ""))
            chips = []
            for metric in group.get("metrics", []):
                value = str(metric.get("value", ""))
                label = str(metric.get("label", ""))
                short_label, full_label = metric_labels.get(label, (label, label))
                tone = "neutral"
                if year == latest_year:
                    try:
                        numeric_value = float(value.replace("%", ""))
                        if numeric_value > 0:
                            tone = "positive"
                        elif numeric_value < 0:
                            tone = "negative"
                    except (TypeError, ValueError):
                        pass

                chips.append(
                    html.Span(
                        [
                            html.Span(
                                [
                                    html.Abbr(short_label, title=full_label),
                                    html.Span(full_label),
                                ],
                                className="annual-return-metric-label",
                            ),
                            html.Strong(
                                value,
                                className="annual-return-metric-value",
                            ),
                        ],
                        className=f"annual-return-chip annual-return-chip--{tone}",
                    )
                )

            rows.append(
                html.Div(
                    [
                        html.Span(year, className="annual-return-year-label"),
                        html.Div(chips, className="annual-return-chip-list"),
                    ],
                    className="annual-return-year-row",
                )
            )
        return rows

    # =========================
    # 全局唯一回调
    # =========================
    def setup_callback(self, app):
        if self._callback_registered:
            return

        @callback(
            Output(
                {
                    "type": "industry-trend-selector",
                    "page": MATCH,
                    "chart": MATCH,
                    "index": MATCH,
                },
                "value",
            ),
            Input(
                {
                    "type": "industry-trend-remove",
                    "page": MATCH,
                    "chart": MATCH,
                    "index": MATCH,
                    "industry": ALL,
                },
                "n_clicks",
            ),
            State(
                {
                    "type": "industry-trend-selector",
                    "page": MATCH,
                    "chart": MATCH,
                    "index": MATCH,
                },
                "value",
            ),
            prevent_initial_call=True,
        )
        def remove_selected_industry(clicks, selected_industries):
            triggered_id = ctx.triggered_id
            if (
                not isinstance(triggered_id, dict)
                or triggered_id.get("type") != "industry-trend-remove"
            ):
                return no_update
            industry_to_remove = triggered_id.get("industry")
            selected_industries = selected_industries or []
            if industry_to_remove not in selected_industries:
                return no_update

            # Dash 3.4 reports ctx.triggered[0].value as None for an ALL input.
            # The ALL values follow the same order as the rendered summary
            # buttons, so use the matching selected industry's click count.
            selected_index = selected_industries.index(industry_to_remove)
            click_counts = clicks if isinstance(clicks, (list, tuple)) else [clicks]
            if selected_index >= len(click_counts) or not click_counts[selected_index]:
                return no_update

            return [
                industry
                for industry in selected_industries
                if industry != industry_to_remove
            ]

        @callback(
            [
                Output(
                    {
                        "type": "dynamic-chart",
                        "page": MATCH,
                        "chart": MATCH,
                        "index": MATCH,
                    },
                    "figure",
                ),
                Output(
                    {
                        "type": "dynamic-chart",
                        "page": MATCH,
                        "chart": MATCH,
                        "index": MATCH,
                    },
                    "style",
                ),
                Output(
                    {
                        "type": "industry-trend-summary",
                        "page": MATCH,
                        "chart": MATCH,
                        "index": MATCH,
                    },
                    "children",
                ),
                Output(
                    {
                        "type": "initial-chart-loading",
                        "page": MATCH,
                        "chart": MATCH,
                        "index": MATCH,
                    },
                    "display",
                ),
                Output(
                    {
                        "type": "industry-trend-selector-container",
                        "page": MATCH,
                        "chart": MATCH,
                        "index": MATCH,
                    },
                    "style",
                ),
                Output(
                    {
                        "type": "annual-return-metrics",
                        "page": MATCH,
                        "chart": MATCH,
                        "index": MATCH,
                    },
                    "children",
                ),
            ],
            Input("current-theme", "data"),
            Input("client-width", "data"),
            Input(
                {
                    "type": "industry-trend-selector",
                    "page": MATCH,
                    "chart": MATCH,
                    "index": MATCH,
                },
                "value",
            ),
            Input(
                {
                    "type": "dynamic-chart",
                    "page": MATCH,
                    "chart": MATCH,
                    "index": MATCH,
                },
                "id",
            ),
            prevent_initial_call=False,  # ⚠️ 允许首次渲染
        )
        def universal_chart_callback(
            theme, client_width, selected_industries, component_id
        ):
            page = component_id["page"]
            chart_type = component_id["chart"]
            index = component_id["index"]

            theme = theme or "light"
            client_width = client_width or 1440
            selected_industries = selected_industries or []
            key = f"{chart_type}_{page}_{index}"
            info = self._charts.get(key)
            industry_color_maps = (info or {}).get("industry_color_maps", {})
            selection_summary = self.build_industry_selection_summary(
                selected_industries,
                page,
                chart_type,
                index,
                industry_color_maps.get(theme, {}),
            )

            # 动态计算对应的 style
            chart_style = self._get_chart_style(chart_type, client_width)
            is_initial_trend_load = chart_type == "pnl_trend"
            initial_loading_display = "hide" if is_initial_trend_load else no_update
            selector_style = {"display": "block"} if is_initial_trend_load else no_update

            if key not in self._charts:
                return (
                    no_update,
                    no_update,
                    selection_summary,
                    initial_loading_display,
                    selector_style,
                    no_update,
                )

            info = self._charts[key]

            # A selector change only needs to toggle the existing industry's
            # traces. Avoid loading data, recalculating forecasts, sleeping for
            # the loading indicator, and sending the full figure back to Dash.
            triggered_props = ctx.triggered_prop_ids
            triggered_id = ctx.triggered_id
            selector_only = (
                len(triggered_props) == 1
                and isinstance(triggered_id, dict)
                and triggered_id.get("type") == "industry-trend-selector"
            )
            if selector_only and chart_type == "pnl_trend":
                industry_order = list(
                    next(iter(info["industry_color_maps"].values()), {}).keys()
                )
                if industry_order:
                    selected_set = {str(industry) for industry in selected_industries}
                    figure_patch = Patch()
                    traces_per_industry = self._PNL_TREND_TRACES_PER_INDUSTRY
                    for industry_index, industry in enumerate(industry_order):
                        is_visible = str(industry) in selected_set
                        first_trace = industry_index * traces_per_industry
                        for trace_index in range(
                            first_trace, first_trace + traces_per_industry
                        ):
                            figure_patch["data"][trace_index]["visible"] = is_visible
                    return (
                        figure_patch,
                        no_update,
                        selection_summary,
                        no_update,
                        no_update,
                        no_update,
                    )

            builder = info["builder"]
            datasets = info["datasets"]

            try:
                # 核心：真正命中 mtime-aware LRU
                data_bundle = ReportDataLoader.load(
                    prefix=page,
                    datasets=datasets,
                )

                # time.sleep(0.1)  # 100ms延迟，确保loading有显示时间

                # ===== 图表分发 =====
                if chart_type == "annual_return":
                    annual_data = data_bundle.get("annual_return")
                    if annual_data is None:
                        return (
                            self._placeholder_figure(
                                "Run Backtest", theme, client_width
                            ),
                            chart_style,
                            selection_summary,
                            initial_loading_display,
                            selector_style,
                            [],
                        )
                    pnl, cash, total_value = data_bundle["annual_return"]
                    fig = builder.annual_return(
                        page=page,
                        pnl=pnl,
                        theme=theme,
                        client_width=client_width,
                        chart_time_range=ToolKit.get_config(
                            "chart_display.chart_time_range", default=120
                        ),
                    )
                elif chart_type == "heatmap":
                    df = data_bundle.get("heatmap")
                    if df is None or df.empty:
                        return (
                            self._placeholder_figure(
                                "Run Backtest", theme, client_width
                            ),
                            chart_style,
                            selection_summary,
                            initial_loading_display,
                            selector_style,
                            no_update,
                        )
                    fig = builder.calendar_heatmap(
                        page=page,
                        df=df,
                        theme=theme,
                        client_width=client_width,
                    )
                elif chart_type == "industry_strength":
                    df = data_bundle.get("industry_strength")
                    if df is None or df.empty:
                        return (
                            self._placeholder_figure(
                                "Run Backtest", theme, client_width
                            ),
                            chart_style,
                            selection_summary,
                            initial_loading_display,
                            selector_style,
                            no_update,
                        )
                    fig = builder.industry_strength_chart(
                        page=page,
                        df=df,
                        theme=theme,
                        client_width=client_width,
                    )
                elif chart_type == "strategy":
                    df = data_bundle.get("strategy")
                    if df is None or df.empty:
                        return (
                            self._placeholder_figure(
                                "Run Backtest", theme, client_width
                            ),
                            chart_style,
                            selection_summary,
                            initial_loading_display,
                            selector_style,
                            no_update,
                        )
                    fig = builder.strategy_chart(
                        page=page,
                        df=df,
                        theme=theme,
                        client_width=client_width,
                    )

                elif chart_type == "trade":
                    df = data_bundle.get("trade")
                    if df is None or df.empty:
                        return (
                            self._placeholder_figure(
                                "Run Backtest", theme, client_width
                            ),
                            chart_style,
                            selection_summary,
                            initial_loading_display,
                            selector_style,
                            no_update,
                        )
                    fig = builder.trade_info_chart(
                        page=page,
                        df=df,
                        theme=theme,
                        client_width=client_width,
                    )

                elif chart_type == "pnl_trend":
                    df = data_bundle.get("pnl_trend")
                    if df is None or df.empty:
                        return (
                            self._placeholder_figure(
                                "Run Backtest", theme, client_width
                            ),
                            chart_style,
                            selection_summary,
                            initial_loading_display,
                            selector_style,
                            no_update,
                        )
                    fig = builder.industry_pnl_trend(
                        page=page,
                        df=df,
                        theme=theme,
                        client_width=client_width,
                        selected_industries=selected_industries,
                    )

                elif chart_type == "industry_position":
                    df = data_bundle.get("industry_position")
                    if df is None or df.empty:
                        return (
                            self._placeholder_figure(
                                "Run Backtest", theme, client_width
                            ),
                            chart_style,
                            selection_summary,
                            initial_loading_display,
                            selector_style,
                            no_update,
                        )
                    fig = builder.industry_position_treemap(
                        page=page,
                        df=df,
                        theme=theme,
                        client_width=client_width,
                    )

                elif chart_type == "industry_profit":
                    df = data_bundle.get("industry_profit")
                    if df is None or df.empty:
                        return (
                            self._placeholder_figure(
                                "Run Backtest", theme, client_width
                            ),
                            chart_style,
                            selection_summary,
                            initial_loading_display,
                            selector_style,
                            no_update,
                        )
                    fig = builder.industry_profit_treemap(
                        page=page,
                        df=df,
                        theme=theme,
                        client_width=client_width,
                    )

                else:
                    return (
                        no_update,
                        no_update,
                        selection_summary,
                        initial_loading_display,
                        selector_style,
                        no_update,
                    )

                annual_metrics = (
                    self.build_annual_return_metrics(
                        (fig.layout.meta or {}).get("annual_metrics", [])
                    )
                    if chart_type == "annual_return"
                    else no_update
                )
                return (
                    fig,
                    chart_style,
                    selection_summary,
                    initial_loading_display,
                    selector_style,
                    annual_metrics,
                )

            except Exception as e:
                print(f"⚠️ Chart generation failed. {key}: {e}")
                return (
                    no_update,
                    no_update,
                    selection_summary,
                    initial_loading_display,
                    selector_style,
                    no_update,
                )

        self._callback_registered = True

