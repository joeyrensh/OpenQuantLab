from dash import html
from dash import dcc
import re
from dash import dash_table
from datetime import datetime, timedelta
from dash.dash_table.Format import Format, Scheme, Trim
import pandas as pd
import numpy as np
import hashlib
import os
from finance.utility.toolkit import ToolKit
from finance import FINANCE_ROOT


def Header(app):
    return html.Div(
        [get_header(app), html.Br([]), get_menu()], className="header-menu-wrapper"
    )


def get_header(app):
    header = html.Div(
        [
            html.Div(
                [
                    # 左侧/中间：标题区域
                    html.Div(
                        [
                            html.Span(
                                # "Find Your Truth!",
                                id="header-title",
                                className="bubble-text",
                            ),
                        ],
                        className="seven columns main-title",
                    ),
                    # 右侧：仅保留 Source Code 按钮
                    html.Div(
                        [
                            html.A(
                                html.Button(
                                    [
                                        html.I(
                                            # className="fa-solid fa-code",
                                            className="fa-solid fa-magnifying-glass",
                                            style={"marginRight": "6px"},
                                        ),
                                        # "GitHub",
                                    ],
                                    id="learn-more-button",
                                ),
                                href="https://github.com/joeyrensh/OpenQuantLab/tree/master/openquantlab/finance",
                                target="_blank",
                                style={"textDecoration": "none"},
                            )
                        ],
                        className="header-right-action",
                    ),
                ],
                className="row",
            )
        ],
        className="background-header",
    )
    return header


def get_menu():
    menu = html.Div(
        [
            html.Div(
                [
                    dcc.Link(
                        html.Span("A-Share", className="menu-name"),
                        href="/dash-financial-report/a-share",
                        id="tab-a-share",
                        className="tab",
                    ),
                    dcc.Link(
                        html.Span("US-Stock", className="menu-name"),
                        href="/dash-financial-report/us-stock",
                        id="tab-us-stock",
                        className="tab",
                    ),
                    dcc.Link(
                        html.Span("A+", className="menu-name"),
                        href="/dash-financial-report/a-picks",
                        id="tab-a-picks",
                        className="tab",
                    ),
                    dcc.Link(
                        html.Span("US+", className="menu-name"),
                        href="/dash-financial-report/us-picks",
                        id="tab-us-picks",
                        className="tab",
                    ),
                    dcc.Link(
                        html.Span("Backtest", className="menu-name"),
                        href="/dash-financial-report/backtest",
                        id="tab-backtest",
                        className="tab",
                    ),
                    dcc.Link(
                        html.Span("Settings", className="menu-name"),
                        href="/dash-financial-report/settings",
                        id="tab-settings",
                        className="tab",
                    ),
                ],
                className="navbar",
            )
        ],
        className="row all-tabs",
    )
    return menu


def check_value_type(value):
    # 如果包含<img>标签，则提取<img>标签中的src属性值
    if re.search(r"<img\s+[^>]*>", value):
        match = re.search(r"<img\s+[^>]*src\s*=\s*\"([^\"]*)\"\s*\/?>", value)
        if match:
            return match.group(1), "img"
    # 如果包含<span>标签，则去除<span>标签但保留其内容
    elif re.search(r"<span\b[^>]*>(.*?)</span>", value):
        # return re.sub(r"<span\b[^>]*>(.*?)</span>", r"\1", value), "richtext"
        return value, "richtext"
    # 如果不是上述两种情况，则直接返回原字符串
    else:
        return value, "text"


def _numeric_label_width_em(values, value_format="ratio", precision=2):
    """Estimate the widest rendered numeric label for reserving cell space."""
    valid_values = pd.to_numeric(values, errors="coerce").dropna()

    def label_width(value):
        if value_format == "ratio":
            label = f"{float(value):.{precision}%}"
        elif value_format == "int":
            label = f"{float(value):.0f}"
        else:
            label = f"{float(value):.{precision}f}"
        return sum(
            0.62
            if char.isdigit()
            else 0.30
            if char == "."
            else 0.90
            if char == "%"
            else 0.42
            if char in ("-", "−")
            else 0.62
            for char in label
        )

    return max((label_width(value) for value in valid_values), default=4.4)


_RATIO_BAR_STYLE = {
    "label_gap": "var(--ratio-progress-label-gap)",
    "cell_padding_inline": "var(--ratio-progress-cell-padding-inline)",
    "cell_padding_block": "var(--ratio-progress-cell-padding-block)",
    "track_height_px": "var(--track-height-px)",
    "track_start": "var(--ratio-progress-track-start)",
    "min_track_width": "var(--ratio-progress-min-track-width)",
}


def _ratio_bar_min_width(label_width_em):
    """Return a CSS-sized minimum width while keeping visual tuning in CSS."""
    style = _RATIO_BAR_STYLE
    return (
        "max(var(--progress-bar-length), calc({label_width:.3f}em + "
        "{track_start} + {min_track_width} + {label_gap} + "
        "{cell_padding_inline}))"
    ).format(
        label_width=label_width_em,
        track_start=style["track_start"],
        min_track_width=style["min_track_width"],
        label_gap=style["label_gap"],
        cell_padding_inline=style["cell_padding_inline"],
    )


def _css_length(value):
    """Allow internal style helpers to accept either pixels or a CSS variable."""
    return value if isinstance(value, str) else f"{value:g}px"


def data_bars(df, column, source_values=None):
    label_gap = _RATIO_BAR_STYLE["label_gap"]
    cell_padding_inline = _RATIO_BAR_STYLE["cell_padding_inline"]
    cell_padding_block = _RATIO_BAR_STYLE["cell_padding_block"]
    track_height_px = _RATIO_BAR_STYLE["track_height_px"]
    track_start = _RATIO_BAR_STYLE["track_start"]

    values = pd.to_numeric(
        df[column] if source_values is None else source_values, errors="coerce"
    )

    # 获取值的范围
    min_val = values.min()
    max_val = values.max()

    styles = []
    style_cache = {}  # 缓存样式，避免重复计算

    # The data-dependent label width stays in Python; spacing and track geometry
    # are CSS variables so they can be tuned without rebuilding per-column rules.
    label_width_em = _numeric_label_width_em(values, "ratio")

    def progress_style(value, percentage, fill_color):
        percentage = max(0.0, min(100.0, float(percentage)))
        # DataTable compares values from its serialized row data. Use a tiny
        # interval instead of exact float equality so harmless JSON/JS precision
        # differences do not make the bar disappear for individual rows.
        numeric_value = float(value)
        tolerance = max(abs(numeric_value) * 1e-12, 1e-12)
        value_filter = (
            "{{{column}}} >= {lower:.17g} && {{{column}}} < {upper:.17g}"
        ).format(
            column=column,
            lower=numeric_value - tolerance,
            upper=numeric_value + tolerance,
        )
        # The background is clipped to the content box. Its left padding creates
        # the track inset; the percentage then scales within the remaining track.
        gradient = """
            linear-gradient(90deg,
                {fill_color} 0%,
                {fill_color} {percentage:.4f}%,
                transparent {percentage:.4f}%,
                transparent 100%)
        """.format(
            fill_color=fill_color,
            percentage=percentage,
        )
        # Put size, position, and repeat in the same shorthand. Dash's table
        # conditional styles can otherwise reset background-size after the
        # separate longhand is applied.
        background = (
            "{gradient} left center / calc(100% - {label_width:.3f}em - "
            "{gap}) {height} no-repeat"
        ).format(
            gradient=gradient.strip(),
            label_width=label_width_em,
            gap=label_gap,
            height=track_height_px,
        )
        return {
            "if": {
                "filter_query": value_filter,
                "column_id": column,
            },
            "background": background,
            "backgroundOrigin": "content-box",
            "backgroundClip": "content-box",
            "minWidth": _ratio_bar_min_width(label_width_em),
            "borderRadius": "0",
            "textAlign": "right",
            "paddingLeft": track_start,
            "paddingRight": cell_padding_inline,
            "paddingBottom": cell_padding_block,
            "paddingTop": cell_padding_block,
        }

    for value in values:
        if pd.isna(value) or value in style_cache:
            continue

        if value > 0:
            # 正值百分比 - 相对于最大值
            percentage = (value / max_val) * 100 if max_val > 0 else 0
            style = progress_style(value, percentage, "var(--positive-databar-color)")
        elif value < 0:
            # 负值百分比 - 相对于最小值的绝对值
            percentage = (abs(value) / abs(min_val)) * 100 if min_val < 0 else 0
            style = progress_style(value, percentage, "var(--negative-databar-color)")
        else:  # 零值
            style = progress_style(value, 0, "transparent")

        styles.append(style)
        style_cache[value] = True

    return styles


def _discrete_background_color_bins_with_style(
    df,
    column,
    n_bins=10,
    positive_is_red=False,
    mid=0,
    source_values=None,
    *,
    visual="heatmap",
    stripe_width_px="var(--value-left-stripe-width)",
    min_mix_pct=10,
    max_mix_pct=58,
    cell_padding_px=2,
    line_width_px=2,
    line_width_pct=80,
):
    """
    按数值区间生成主题自适应热力色、左侧色带或底部细色线。
    正负值区间分别围绕 mid 计算；heatmap 模式使用 min_mix_pct 到
    max_mix_pct 的透明度范围，减少整格色块过重的问题。
    mid: 渐变中心值，默认0，可设置为1或其它。
    """
    if column not in df.columns:
        return []

    vals = pd.to_numeric(
        df[column] if source_values is None else source_values, errors="coerce"
    ).dropna()
    if vals.empty:
        return []

    vmin = float(vals.min())
    vmax = float(vals.max())

    styles = []

    # 零值或 mid 值透明；指标线模式下数值左对齐。
    mid_style = {
        "if": {
            "filter_query": "{{{}}} = {}".format(column, mid),
            "column_id": column,
        },
        "background": "transparent",
    }
    if visual == "left-stripe":
        mid_style.update(
            {
                "textAlign": "right",
                "paddingRight": _css_length(cell_padding_px),
            }
        )
    elif visual == "bottom-line":
        mid_style.update(
            {
                "textAlign": "left",
                "paddingLeft": _css_length(cell_padding_px),
            }
        )
    styles.append(mid_style)

    # 根据参数决定正/负的基础颜色（使用 CSS 变量，保留可覆盖性）
    if positive_is_red:
        pos_base = "var(--positive-int-bg-color, red)"
        neg_base = "var(--negative-int-bg-color, green)"
    else:
        pos_base = "var(--negative-int-bg-color, green)"
        neg_base = "var(--positive-int-bg-color, red)"

    # 使用CSS变量定义颜色，让CSS处理暗黑模式适配
    def get_color_style(value_range, is_positive=True):
        low, high = value_range
        mid_val = (low + high) / 2.0

        if is_positive:
            intensity = min(
                max(abs(mid_val - mid) / max(abs(vmax - mid), 1e-10), 0.1), 1.0
            )
            base_color = pos_base
        else:
            intensity = min(
                max(abs(mid_val - mid) / max(abs(vmin - mid), 1e-10), 0.1), 1.0
            )
            base_color = neg_base

        style = {
            "if": {
                "filter_query": "{{{col}}} >= {low} && {{{col}}} <= {high} && {{{col}}} != {mid}".format(
                    col=column, low=repr(low), high=repr(high), mid=repr(mid)
                ),
                "column_id": column,
            },
        }
        # The final mix percentage depends on each data bin's intensity, so this
        # interpolation remains data-driven in Python. CSS controls the rendered
        # line/stripe geometry and the theme-aware base colors.
        mix_pct = min_mix_pct + (max_mix_pct - min_mix_pct) * intensity
        mixed_color = f"color-mix(in srgb, {base_color} {mix_pct:.1f}%, transparent)"
        if visual == "left-stripe":
            style.update(
                {
                    # An inset shadow produces a fixed-width, full-cell-height
                    # strip without a proportional fill or a spatial gradient.
                    "boxShadow": (
                        f"inset {_css_length(stripe_width_px)} 0 0 0 {mixed_color}"
                    ),
                    "textAlign": "right",
                    "paddingRight": _css_length(cell_padding_px),
                }
            )
        elif visual == "bottom-line":
            style.update(
                {
                    # Draw a centered, solid-color underline narrower than
                    # the cell so adjacent cells remain visually separated.
                    "background": (
                        "linear-gradient(90deg, {color} 0, {color} 100%) "
                        "left bottom / {width_pct} {line_width} no-repeat"
                    ).format(
                        color=mixed_color,
                        width_pct=(
                            line_width_pct
                            if isinstance(line_width_pct, str)
                            else f"{line_width_pct:g}%"
                        ),
                        line_width=_css_length(line_width_px),
                    ),
                    "textAlign": "left",
                    "paddingLeft": _css_length(cell_padding_px),
                }
            )
        elif visual == "heatmap":
            style["backgroundColor"] = mixed_color
        else:
            raise ValueError(
                "visual must be 'heatmap', 'left-stripe', or 'bottom-line'"
            )
        return style

    # 负值区间：从vmin到mid
    if vmin < mid:
        neg_edges = [vmin + (mid - vmin) * (i / n_bins) for i in range(n_bins + 1)]
        for i in range(n_bins):
            styles.append(get_color_style((neg_edges[i], neg_edges[i + 1]), False))

    # 正值区间：从mid到vmax
    if vmax > mid:
        pos_edges = [mid + (vmax - mid) * (i / n_bins) for i in range(n_bins + 1)]
        for i in range(n_bins):
            styles.append(get_color_style((pos_edges[i], pos_edges[i + 1]), True))

    return styles


def discrete_background_color_bins(
    df, column, n_bins=10, positive_is_red=False, mid=0, source_values=None
):
    """Generate the default heatmap styles with the original public API."""
    return _discrete_background_color_bins_with_style(
        df,
        column,
        n_bins=n_bins,
        positive_is_red=positive_is_red,
        mid=mid,
        source_values=source_values,
    )


def make_dash_format_table(df, cols_format, market, trade_date, table_name):
    """Return a dash_table.DataTable for a Pandas dataframe"""
    # 创建一个新的 DataFrame 来存储原始列的副本
    original_df = df.copy()
    required_cols = [
        "IND",
        "SYMBOL",
        "NAME",
        "ERP",
        "OPEN DATE",
        "DAILY RETURN",
        "PNL RATIO",
        "AVG TRANS",
        "WIN RATE",
        "SORTINO RATIO",
        "MAX DD",
        "STRATEGY CNT",
        "STRATEGY",
    ]
    has_all_required_cols = all(col in df.columns for col in required_cols)
    if market in ("us", "us_special", "us_dynamic"):
        trade_date_l5 = get_us_specific_trade_date(4)
    elif market in ("cn", "cn_dynamic"):
        trade_date_l5 = get_cn_specific_trade_date(4)

    date_threshold_l5 = datetime.strptime(trade_date_l5, "%Y%m%d").strftime("%Y-%m-%d")
    # 如果有IND列，先生成辅助列
    if "ERP" in df.columns:
        df["ERP"] = pd.to_numeric(df["ERP"], errors="coerce")
        df["ERP"] = df["ERP"].fillna(-99999)

    tooltip_data = []
    if has_all_required_cols:
        column_map_default = {
            "symbol": "SYMBOL",
            "name": "NAME",
            "industry": "IND",
            "erp": "ERP",
            "open_date": "OPEN DATE",
            "daily_return_array": "DAILY RETURN",
            "pnl_ratio": "PNL RATIO",
            "win_rate": "WIN RATE",
            "avg_trans": "AVG TRANS",
            "sortino": "SORTINO RATIO",
            "max_dd": "MAX DD",
            "strategy_cnt": "STRATEGY CNT",
            "strategy": "STRATEGY",
        }
        selected_symbols, score_dict = ToolKit.score_and_select_symbols(
            df,
            column_map_default,
            market,
            trade_date,
        )

        if market in ("us", "cn", "us_special"):
            mask = df["SYMBOL"].isin(selected_symbols)
            df.loc[mask, "NAME"] = "88+" + df.loc[mask, "NAME"].astype(str)
            # 构建 tooltip_data：为每一行添加 symbol 列上的 score 提示
            score_fields = [
                "total_score",
                "industry_score",
                "erp_score",
                "pnl_score",
                "stability_score",
                "strategy_score",
                "rank",
            ]

            for idx, row in df.iterrows():
                symbol = row["SYMBOL"]  # 注意列名与实际一致
                values = [score_dict[field].get(symbol) for field in score_fields]

                if values[0] is not None:  # 至少总分存在
                    tooltip_text = (
                        f"总分: {values[0]:.4f}\n"
                        f"行业: {values[1]:.4f}\n"
                        f"ERP: {values[2]:.4f}\n"
                        f"收益: {values[3]:.4f}\n"
                        f"稳定性: {values[4]:.4f}\n"
                        f"策略: {values[5]:.4f}\n"
                        f"排名: {values[6]:.0f}"
                    )
                else:
                    tooltip_text = ""

                tooltip_data.append(
                    {"IDX": {"value": tooltip_text, "type": "markdown"}}
                )

    def create_link(symbol, market):
        if market in ("cn", "cn_dynamic") and symbol.startswith(("SH", "SZ")):
            url = f"https://quote.eastmoney.com/{symbol}.html"
        elif market == "cn" and symbol.startswith("ETF"):
            url = f"https://quote.eastmoney.com/{symbol[3:]}.html"
        else:
            url = f"https://quote.eastmoney.com/us/{symbol}.html"
        # 使用 inline style 让链接继承单元格颜色，并去掉下划线
        return f'<a href="{url}" target="_blank" style="color:inherit;text-decoration:underline;">{symbol}</a>'

    if "SYMBOL" in df.columns:
        df["SYMBOL"] = df["SYMBOL"].apply(lambda symbol: create_link(symbol, market))

    # 1. 初始化条件样式列表
    highlight_conditional = []

    # 获取表格当前所有的列名
    existing_cols = list(df.columns) if hasattr(df, "columns") else []

    # 2. 【独立逻辑一】：处理 IDX 列的交互样式（指针手势 + 内置选中高亮）
    if "NAME" in existing_cols:
        highlight_conditional.extend(
            [
                # 基础样式：只要存在 IDX 列，悬停即显示点击手势指针
                {
                    "if": {"column_id": "NAME"},
                    "cursor": "pointer",
                },
            ]
        )

    # 3. 【独立逻辑二】：根据外部条件 selected_symbols 触发的特定列高亮
    highlight_cols = ["SYMBOL", "NAME"]

    if (
        has_all_required_cols
        and selected_symbols
        and market in ("us", "cn", "us_special")
    ):
        # 构造过滤查询语句
        filter_query = " || ".join(
            ['({{{}}} = "{}")'.format("SYMBOL_o", sym) for sym in selected_symbols]
        )

        # 动态过滤：仅对表格中实际存在的列添加外部条件高亮
        target_cols = [col for col in highlight_cols if col in existing_cols]

        highlight_conditional.extend(
            [
                {
                    "if": {
                        "filter_query": filter_query,
                        "column_id": col,
                    },
                    "color": "var(--highlight-symbol-color)",
                    "fontWeight": "bold",
                }
                for col in target_cols
            ]
        )

    HEADER_NAME_MAP = {
        # --- 基础标识 & 分类 ---
        "IDX": "Idx",
        "SYMBOL": "Symbol",
        "NAME": "Name",
        "IND": "Industry",
        "INDUSTRY": "Industry",
        "STRATEGY": "Strat",
        "STRATEGY CNT": "Strat Count",
        # --- 价格 & 资产价值 ---
        "TOTAL VALUE": "Mkt Cap",
        "BASE": "Cost",
        "PRICE": "Cost",
        "ADJBASE": "Last",
        "OPEN": "Open Pos",
        "L5 OPEN": "5d Opens",
        "L5 CLOSE": "5d Closes",
        "TYPE": "Type",
        "VOLUME": "Volume",
        # --- 估值 & 风险指标 ---
        "PE": "P/E",
        "ERP": "ERP",
        "SHARPE RATIO": "Sharpe",
        "SORTINO RATIO": "Sortino",
        "MAX DD": "Max DD (%)",
        # --- 收益 & 盈亏指标 ---
        "PNL": "Pnl",
        "PROFIT": "Pnl",
        "PNL RATIO": "Pnl (%)",
        "TOTAL PNL RATIO": "Cum Pnl (%)",
        "DAILY RETURN": "1d Ret (%)",
        "PROFIT TREND": "Trend",
        # --- 交易统计 & 胜率 ---
        "WIN RATE": "Win Rate (%)",
        "LRATIO": "Ind Ratio (%)",
        "AVG TRANS": "Trades",
        "AVG DAYS": "Hold Days",
        "HIS DAYS": "Hist Days",
        # --- 日期 ---
        "DATE": "Date",
        "OPEN DATE": "Open Date",
        "CLOSE DATE": "Close Date",
    }

    columns = [
        {
            "name": HEADER_NAME_MAP.get(col, col),
            "id": col,
            "type": (
                "numeric"
                if col in cols_format
                and cols_format[col][0] in ("ratio", "float", "int")
                else "text"
            ),
            "format": (
                Format(
                    precision=2,
                    scheme=Scheme.percentage,
                )
                if col in cols_format and cols_format[col][0] == "ratio"
                else (
                    Format(
                        precision=2,
                        scheme=Scheme.fixed,
                    )
                    if col in cols_format and cols_format[col][0] == "float"
                    else (
                        Format(
                            precision=0,
                            scheme=Scheme.fixed,
                        )
                        if col in cols_format and cols_format[col][0] == "int"
                        else None
                    )
                )
            ),
            "presentation": (
                None
                if col in cols_format
                and cols_format[col][0] in ("ratio", "float", "int", "text")
                else "markdown"
            ),
        }
        for col in df.columns
        if col
        not in [
            "DAILY RETURN",
            "STRATEGY CNT",
        ]
    ]
    # Keep case-insensitive text search at table level, but use case-sensitive
    # filtering for numeric columns so relational operators compare numbers.
    for column in columns:
        if column["type"] == "numeric":
            column["filter_options"] = {
                "placeholder_text": "Search",
                "case": "sensitive",
            }
    # Preserve original values only for columns whose displayed content changes
    # and is still needed by callbacks/highlighting.
    for col in ("SYMBOL", "NAME"):
        if col in original_df.columns:
            df[f"{col}_o"] = original_df[col]

    # These columns are used above for scoring but are not displayed or needed
    # by table callbacks, so keep them out of the DataTable row payload.
    payload_excluded_cols = [
        col for col in ("DAILY RETURN", "STRATEGY CNT") if col in df.columns
    ]
    data = df.drop(columns=payload_excluded_cols).to_dict("records")

    def format_value(value, value_type):
        if value_type == "img":
            img_style = "max-width: 150px; max-height: 40px;"
            return f'<img src="{value}" style="{img_style}" />'
        elif value_type == "richtext":
            return f"{value}"
        elif value_type == "float":
            return f"{value:.2f}"
        else:
            return value

    for row in data:
        for key in list(row.keys()):
            if key.endswith("_o"):
                continue  # 跳过副本列

            if key in cols_format and cols_format[key][0] in ("ratio", "float", "int"):
                try:
                    # 若原始是字符串数字，尝试转换为 float；保留 None/空值
                    val = row[key]
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        row[key] = None
                    else:
                        row[key] = float(val)
                except Exception:
                    # 若不能转换，保留原值（不会破坏 markdown/html 列）
                    row[key] = row[key]
                continue

            # 非数值列：检查是否包含 img/span 等并按 markdown/html 处理
            value = str(row[key])
            new_value, value_type = check_value_type(value)

            if value_type == "img":
                img_style = "max-width: 150px; max-height: 40px;"
                row[key] = f'<img src="{new_value}" style="{img_style}" />'
            elif value_type == "richtext":
                row[key] = f"{new_value}"
            else:
                row[key] = new_value

    style_data_conditional = (
        [
            {
                "if": {
                    "column_id": col,
                },
                "background": "none",
                # "color": "var(--text-color)",
            }
            for col in original_df.columns
            if col in cols_format and len(cols_format[col]) == 1
        ]
        + [
            {
                "if": {
                    "column_id": col,
                },
                "background": "none",
                # "color": "var(--text-color)",
            }
            for col in original_df.columns
            if col not in cols_format
        ]
        + [
            {
                "if": {
                    "filter_query": "{{{column}}} >= {value} and {{{column}}} != 'nan'".format(
                        column=col, value=date_threshold_l5
                    ),
                    "column_id": col,
                },
                # "backgroundColor": "RebeccaPurple",
                # "backgroundColor": "coral",
                "backgroundColor": ("""var(--date-bg-color)"""),
                # "color": "var(--text-color)",
            }
            for col in original_df.columns
            if col in cols_format
            and len(cols_format[col]) > 1
            and cols_format[col][0] == "date"
            and cols_format[col][1] == "format"
        ]
        + [
            {
                "if": {
                    "filter_query": "{{{column}}} = {value} and {{{column}}} != 'nan'".format(
                        column=col, value="Buy"
                    ),
                    "column_id": col,
                },
                "backgroundColor": ("""var(--positive-databar-color)"""),
            }
            for col in original_df.columns
            if col in cols_format
            and len(cols_format[col]) > 1
            and cols_format[col][0] == "text"
            and cols_format[col][1] == "format"
        ]
        + [
            {
                "if": {
                    "filter_query": "{{{}}} < 0".format(col),
                    "column_id": col,
                },
                "color": "var(--negative-int-bg-color)",
            }
            for col in original_df.columns
            if col in cols_format
            and len(cols_format[col]) > 1
            and cols_format[col][0] in ("float", "int")
            and cols_format[col][1] == "format"
        ]
        + [
            {
                "if": {
                    "filter_query": "{{{}}} > 0".format(col),
                    "column_id": col,
                },
                "color": "var(--positive-int-bg-color)",
            }
            for col in original_df.columns
            if col in cols_format
            and len(cols_format[col]) > 1
            and cols_format[col][0] in ("float", "int")
            and cols_format[col][1] == "format"
        ]
        + highlight_conditional
    )

    ratio_progress_columns = {
        "LRATIO",
        "PNL RATIO",
        "WIN RATE",
        "TOTAL PNL RATIO",
    }
    style_header_conditional = []

    for col in original_df.columns:
        if (
            col in cols_format
            and len(cols_format[col]) > 1
            and cols_format[col][0] == "ratio"
            and cols_format[col][1] == "format"
            and col in ratio_progress_columns
        ):
            label_width_em = _numeric_label_width_em(original_df.get(col), "ratio")
            style_header_conditional.append(
                {
                    "if": {"column_id": col},
                    "minWidth": _ratio_bar_min_width(label_width_em),
                }
            )
            style_data_conditional.extend(
                data_bars(
                    df,
                    col,
                    original_df.get(col),
                )
            )

    bottom_line_options = {
        "visual": "bottom-line",
        "line_width_px": "var(--value-bottom-line-height)",
        "line_width_pct": "var(--value-bottom-line-width)",
        "min_mix_pct": 24,
        "max_mix_pct": 88,
        "cell_padding_px": "var(--value-cell-inline-padding)",
    }

    # 在这里把按值分段着色应用到需要的列
    gradient_target_cols = ["ERP"]

    for col in gradient_target_cols:
        style_data_conditional.extend(
            _discrete_background_color_bins_with_style(
                df,
                col,
                n_bins=10,
                positive_is_red=True,
                source_values=original_df.get(col),
                **bottom_line_options,
            )
        )

    # 在这里把按值分段着色应用到需要的列
    gradient_target_cols = ["SHARPE RATIO", "SORTINO RATIO"]

    for col in gradient_target_cols:
        style_data_conditional.extend(
            _discrete_background_color_bins_with_style(
                df,
                col,
                n_bins=10,
                positive_is_red=True,
                mid=1,
                source_values=original_df.get(col),
                **bottom_line_options,
            )
        )

    gradient_target_cols = ["MAX DD"]

    for col in gradient_target_cols:
        style_data_conditional.extend(
            _discrete_background_color_bins_with_style(
                df,
                col,
                n_bins=10,
                positive_is_red=True,
                mid=0,
                source_values=original_df.get(col),
                **bottom_line_options,
            )
        )

    gradient_target_cols = ["L5 OPEN"]

    for col in gradient_target_cols:
        style_data_conditional.extend(
            _discrete_background_color_bins_with_style(
                df,
                col,
                n_bins=10,
                positive_is_red=True,
                source_values=original_df.get(col),
                **bottom_line_options,
            )
        )

    gradient_target_cols = ["L5 CLOSE"]

    for col in gradient_target_cols:
        style_data_conditional.extend(
            _discrete_background_color_bins_with_style(
                df,
                col,
                n_bins=10,
                positive_is_red=False,
                source_values=original_df.get(col),
                **bottom_line_options,
            )
        )

    table_id = {
        "type": "auto-table",
        "page": market,
        "table": table_name,
    }

    count_id = {
        "type": "auto-table-count",
        "page": market,
        "table": table_name,
    }
    is_checkbox_enabled = market in ("cn", "us") and table_name in ("detail", "cn_etf")

    # 1. 关键：为每一行数据注入 'id' 键，值为 IDX 的值（前端 UI 不会多显一列）
    for row in data:
        row["id"] = str(row.get("IDX", "SYMBOL_o"))

    return html.Div(
        children=[
            # 行数 overlay
            html.Div(
                id=count_id,
                style={
                    "position": "absolute",
                    "right": 0,
                    "top": "-15px",
                    "zIndex": 200,
                    "pointerEvents": "none",
                    "whiteSpace": "nowrap",
                },
            ),
            html.Div(
                children=[
                    dash_table.DataTable(
                        id=table_id,
                        data=data,
                        page_size=50,
                        columns=columns,
                        tooltip_data=tooltip_data,
                        tooltip_delay=0,
                        tooltip_duration=None,
                        filter_action="native",
                        sort_action="native",
                        sort_mode="single",
                        filter_options={
                            "placeholder_text": "Search",
                            "case": "insensitive",
                        },
                        markdown_options={"html": True, "link_target": "_blank"},
                        fill_width=True,
                        editable=False,
                        cell_selectable=True,
                        row_selectable="multi" if is_checkbox_enabled else False,
                        selected_row_ids=[],
                        # selected_rows=[],
                        style_header={
                            "position": "sticky",
                            "top": "0",
                            "backgroundColor": "transparent",
                            "zIndex": 10,
                            "fontWeight": "bold",
                            "white-space": "normal",
                        },
                        style_header_conditional=style_header_conditional,
                        style_cell={
                            "textAlign": "left",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "backgroundColor": "transparent",
                            "margin": "0px",
                            "padding": "0px 2px",
                        },
                        style_data={
                            "backgroundColor": "transparent",
                        },
                        style_table={
                            "paddingBottom": (
                                "2px"
                                if (table_name == "trade" or not data or len(data) < 10)
                                else "20px"
                            ),
                            "position": "relative",
                            "width": "100%",
                            "maxWidth": "100%",
                            "overflow": "auto",
                            "maxHeight": (
                                "300px"
                                if table_name in ("detail_short", "cn_etf")
                                else "400px"
                            ),
                        },
                        style_data_conditional=style_data_conditional,
                    ),
                ],
                style={
                    "overflow": "auto",
                    "maxHeight": (
                        "300px" if table_name in ("detail_short", "cn_etf") else "400px"
                    ),
                    "width": "100%",
                },
            ),
        ],
        className="default-table",
        style={
            "position": "relative",
            "width": "100%",
        },
    )


def get_us_specific_trade_date(offset) -> str | None:
    """
    utc_us = datetime.fromisoformat('2021-01-18 01:00:00')
    美股休市日，https://www.nyse.com/markets/hours-calendars
    marketclosed.config 是2021和2022两年的美股法定休市配置文件
    """
    f = open(FINANCE_ROOT / "usstockinfo" / "marketclosed.config").readlines()
    x = []
    for i in f:
        x.append(i.split(",")[0].strip())
    """ 循环遍历最近一个交易日期 """
    counter = 0
    # 收益率曲线
    DATA_PATH = FINANCE_ROOT / "data"
    df_overall = pd.read_csv(
        DATA_PATH / "us_df_result.csv",
        usecols=[i for i in range(1, 5)],
    )
    utc_us = datetime.strptime(df_overall["end_date"].iloc[0], "%Y-%m-%d")
    for h in range(0, 365):
        # 当前美国时间 UTC-4
        current_date = utc_us - timedelta(days=h)
        # 周末正常休市
        if current_date.isoweekday() in [1, 2, 3, 4, 5]:
            if str(current_date)[0:10] in x:
                continue
            else:
                """返回日期字符串格式20200101"""
                counter += 1
                if counter == offset + 1:  # 找到第 offset 个交易日
                    print("trade date: ", str(current_date)[0:10].replace("-", ""))
                    return str(current_date)[0:10].replace("-", "")
        else:
            continue


def get_cn_specific_trade_date(offset) -> str | None:
    f = open(FINANCE_ROOT / "cnstockinfo" / "marketclosed.config").readlines()
    x = []
    for i in f:
        x.append(i.split(",")[0].strip())
    """ 循环遍历最近一个交易日期 """
    counter = 0
    # 收益率曲线
    DATA_PATH = FINANCE_ROOT / "data"
    df_overall = pd.read_csv(
        DATA_PATH / "cn_df_result.csv",
        usecols=[i for i in range(1, 5)],
    )
    utc_cn = datetime.strptime(df_overall["end_date"].iloc[0], "%Y-%m-%d")
    for h in range(0, 365):
        # 当前北京时间 UTC+8
        current_date = utc_cn - timedelta(days=h)
        # 周末正常休市
        if current_date.isoweekday() in [1, 2, 3, 4, 5]:
            if str(current_date)[0:10] in x:
                continue
            else:
                """返回日期字符串格式20200101"""
                counter += 1
                if counter == offset + 1:  # 找到第 offset 个交易日
                    print("trade date: ", str(current_date)[0:10].replace("-", ""))
                    return str(current_date)[0:10].replace("-", "")
        else:
            continue
