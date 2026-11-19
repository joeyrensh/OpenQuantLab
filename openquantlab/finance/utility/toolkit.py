#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from datetime import datetime, timedelta
import re
from base64 import b64encode
from io import BytesIO
import matplotlib.pyplot as plt
import sys
import numpy as np
from matplotlib import colors as mcolors
import pandas as pd
import hashlib
import os
from finance import FINANCE_ROOT
import json
from typing import Any


class ToolKit:
    def __init__(self, val=None):
        self.val = val
        if val is not None:
            print(f"{val}...")

    """ 执行进度显示 """

    def progress_bar(self, var, i) -> None:
        # 清屏
        sys.stdout.write("\033[2J")
        sys.stdout.flush()

        # 移动光标到顶部
        sys.stdout.write("\033[H")
        sys.stdout.flush()
        print(
            "\r{}: {}%: ".format(self.val, int(i * 100 / var)),
            "▋" * (i * 100 // var),
            end="",
            flush=True,
        )

    """ 判断今日是否美股交易日 """

    @staticmethod
    def is_us_trade_date(trade_date) -> bool:
        """
        当前北京时间 UTC+8
        utc_loc = datetime.now()
        当前美国时间 UTC-4
        """
        # utc_us = datetime.now() - timedelta(hours=12)
        utc_us = datetime.strptime(trade_date, "%Y%m%d")
        """ 
        utc_us = datetime.fromisoformat('2021-01-18 01:00:00')
        美股休市日，https://www.nyse.com/markets/hours-calendars
        marketclosed.config 是2021和2022两年的美股法定休市配置文件 
        """
        f = open(FINANCE_ROOT / "usstockinfo" / "marketclosed.config").readlines()
        x = []
        for i in f:
            x.append(i.split(",")[0].strip())
        """ 周末正常休市 """
        if utc_us.isoweekday() in [1, 2, 3, 4, 5]:
            if str(utc_us)[0:10] in x:
                # print("今日非美国交易日")
                return False
            else:
                return True
        else:
            # print("今日非美国交易日")
            return False

    """ 获取美股最新交易日期 """

    @staticmethod
    def get_us_latest_trade_date(offset) -> str | None:
        """
        utc_us = datetime.fromisoformat('2021-01-18 01:00:00')
        美股休市日，https://www.nyse.com/markets/hours-calendars
        marketclosed.config 是2021和2022两年的美股法定休市配置文件
        """
        if offset == 0:
            trade_date = str(datetime.now() - timedelta(hours=12))[0:10].replace(
                "-", ""
            )
            print("trade date: ", trade_date)
            return trade_date
        f = open(FINANCE_ROOT / "usstockinfo" / "marketclosed.config").readlines()
        x = []
        for i in f:
            x.append(i.split(",")[0].strip())
        """ 循环遍历最近一个交易日期 """
        counter = 0
        for h in range(1, 365):
            """当前美国时间 UTC-4"""
            # utc_us = datetime.now() - timedelta(hours=12) - timedelta(days=h)
            utc_us = datetime.now() - timedelta(days=h)
            """ 周末正常休市 """
            if utc_us.isoweekday() in [1, 2, 3, 4, 5]:
                if str(utc_us)[0:10] in x:
                    continue
                else:
                    """返回日期字符串格式20200101"""
                    counter += 1
                    if counter == offset:  # 找到第 offset 个交易日
                        print("trade date: ", str(utc_us)[0:10].replace("-", ""))
                        return str(utc_us)[0:10].replace("-", "")
            else:
                continue

    @staticmethod
    def get_us_trade_date_by_delta(offset, trade_date) -> str | None:
        """
        utc_us = datetime.fromisoformat('2021-01-18 01:00:00')
        美股休市日，https://www.nyse.com/markets/hours-calendars
        marketclosed.config 是2021和2022两年的美股法定休市配置文件
        """
        if offset == 0:
            return trade_date
        f = open(FINANCE_ROOT / "usstockinfo" / "marketclosed.config").readlines()
        x = []
        for i in f:
            x.append(i.split(",")[0].strip())
        """ 循环遍历最近一个交易日期 """
        counter = 1
        if counter == offset:
            return trade_date
        for h in range(1, 365):
            """当前美国时间 UTC-4"""
            utc_us = datetime.strptime(str(trade_date), "%Y%m%d") - timedelta(days=h)
            """ 周末正常休市 """
            if utc_us.isoweekday() in [1, 2, 3, 4, 5]:
                if str(utc_us)[0:10] in x:
                    continue
                else:
                    """返回日期字符串格式20200101"""
                    counter += 1
                    if counter == offset:  # 找到第 offset 个交易日
                        print("trade date: ", str(utc_us)[0:10].replace("-", ""))
                        return str(utc_us)[0:10].replace("-", "")
            else:
                continue

    """ 获取美股两个日期间的交易天数 """

    @staticmethod
    def get_us_trade_off_days(cur, before) -> int | None:
        """
        取两个交易日起之间的交易天数，用来过滤塞选滞胀的股票
        cur, before都需是datetime类型
        """
        f = open(FINANCE_ROOT / "usstockinfo" / "marketclosed.config").readlines()
        x = []
        for i in f:
            x.append(i.split(",")[0].strip())
        """ 循环遍历最近一个交易日期 """
        timer = 0
        for h in range(0, 365):
            """周末正常休市"""
            utc_us = cur - timedelta(days=h)
            if utc_us.isoweekday() in [1, 2, 3, 4, 5] and str(utc_us)[0:10] not in x:
                timer = timer + 1
            else:
                continue
            """ 当前美国时间 UTC-4 """
            if utc_us == before:
                return timer

    """ 判断今日是否A股交易日 """

    @staticmethod
    def is_cn_trade_date(trade_date) -> bool:
        # utc_cn = datetime.now()
        utc_cn = datetime.strptime(trade_date, "%Y%m%d")
        """
        utc_cn = datetime.fromisoformat('2021-01-18 01:00:00')
        A股休市日
        marketclosed.config 是2021和2022两年的美股法定休市配置文件 
        """
        f = open(FINANCE_ROOT / "cnstockinfo" / "marketclosed.config").readlines()
        x = []
        for i in f:
            x.append(i.split(",")[0].strip())
        """ 周末正常休市 """
        if utc_cn.isoweekday() in [1, 2, 3, 4, 5]:
            if str(utc_cn)[0:10] in x:
                # print("今日非A股交易日")
                return False
            else:
                return True
        else:
            # print("今日非A股交易日")
            return False

    """ 获取A股最新交易日期 """

    @staticmethod
    def get_cn_latest_trade_date(offset) -> str | None:
        if offset == 0:
            trade_date = str(datetime.now())[0:10].replace("-", "")
            print("trade date: ", trade_date)
            return trade_date
        f = open(FINANCE_ROOT / "cnstockinfo" / "marketclosed.config").readlines()
        x = []
        for i in f:
            x.append(i.split(",")[0].strip())
        """ 循环遍历最近一个交易日期 """
        counter = 0
        for h in range(1, 365):
            """当前北京时间 UTC+8"""
            utc_cn = datetime.now() - timedelta(days=h)
            """ 周末正常休市 """
            if utc_cn.isoweekday() in [1, 2, 3, 4, 5]:
                if str(utc_cn)[0:10] in x:
                    continue
                else:
                    """返回日期字符串格式20200101"""
                    counter += 1
                    if counter == offset:  # 找到第 offset 个交易日
                        print("trade date: ", str(utc_cn)[0:10].replace("-", ""))
                        return str(utc_cn)[0:10].replace("-", "")
            else:
                continue

    @staticmethod
    def get_cn_trade_date_by_delta(offset, trade_date) -> str | None:
        if offset == 0:
            return trade_date
        f = open(FINANCE_ROOT / "cnstockinfo" / "marketclosed.config").readlines()
        x = []
        for i in f:
            x.append(i.split(",")[0].strip())
        """ 循环遍历最近一个交易日期 """
        counter = 1
        if counter == offset:
            return trade_date
        for h in range(1, 365):
            """当前北京时间 UTC+8"""
            utc_cn = datetime.strptime(str(trade_date), "%Y%m%d") - timedelta(days=h)
            """ 周末正常休市 """
            if utc_cn.isoweekday() in [1, 2, 3, 4, 5]:
                if str(utc_cn)[0:10] in x:
                    continue
                else:
                    """返回日期字符串格式20200101"""
                    counter += 1
                    if counter == offset:  # 找到第 offset 个交易日
                        print("trade date: ", str(utc_cn)[0:10].replace("-", ""))
                        return str(utc_cn)[0:10].replace("-", "")
            else:
                continue

    """ 获取A股两个日期间的交易天数 """

    @staticmethod
    def get_cn_trade_off_days(cur, before) -> int | None:
        """
        取两个交易日起之间的交易天数，用来过滤塞选滞胀的股票
        cur, before都需是datetime类型
        """
        f = open(FINANCE_ROOT / "cnstockinfo" / "marketclosed.config").readlines()
        x = []
        for i in f:
            x.append(i.split(",")[0].strip())
        """ 循环遍历最近一个交易日期 """
        timer = 0
        for h in range(0, 365):
            """周末正常休市"""
            utc_cn = cur - timedelta(days=h)
            if utc_cn.isoweekday() in [1, 2, 3, 4, 5] and str(utc_cn)[0:10] not in x:
                timer = timer + 1
            else:
                continue
            """ 当前美国时间 UTC-4 """
            if utc_cn == before:
                return timer

    # area chart按照时间渐变透明度填充
    # @staticmethod
    # def create_line(*args, second_plot_type="area"):
    #     """
    #     增强版绘图函数，支持单列与双列输入。
    #     双轴时左右 Y 轴独立缩放（不再强制统一刻度），但仍保证主轴线不会被右轴覆盖。
    #     对常数序列或极小幅度序列做最小跨度扩展以保证可见性。

    #     Args:
    #         *args: 数据序列，1个参数时绘制单线，2个参数时双轴
    #         second_plot_type: 第二组数据的绘制类型，"area"=面积图，"line"=折线图
    #     """
    #     set_matplotlib_formats("svg")

    #     # 配置参数
    #     config = {
    #         "up_color": "#ff4444",
    #         "down_color": "#0d876d",
    #         "line_width": 2,
    #         "secondary_line_width": (
    #             0.5 if second_plot_type == "area" else 1.5
    #         ),  # 根据类型调整线宽
    #         "secondary_line_alpha": (
    #             0.8 if second_plot_type == "area" else 1.0
    #         ),  # 根据类型调整透明度
    #         "gradient_steps": 100,
    #         "fill_alpha_range": (0.06, 0.25),
    #         # alpha_power >1 强调最近端（非线性映射）， =1 为线性
    #         "alpha_power": 1.5,
    #         # "fill_alpha_range": (0.06, 0.25),
    #         "marker_size": 3.5,
    #         "zero_line_alpha": 0,
    #     }

    #     # 解析输入
    #     if len(args) == 1:
    #         # 单列模式
    #         if isinstance(args[0], (list, tuple, np.ndarray)):
    #             data = list(args[0])
    #         else:
    #             data = [args[0]] if args[0] is not None else []
    #         datasets = [data]
    #         is_single_mode = True
    #         if len(data) >= 2:
    #             is_uptrend = data[-1] >= data[-2]
    #         else:
    #             is_uptrend = True
    #         colors = [config["up_color"] if is_uptrend else config["down_color"]]
    #         fill_colors = [colors[0]]
    #     elif len(args) >= 2:
    #         # 双列模式，只取前两列
    #         datasets = []
    #         for arg in args[:2]:
    #             if isinstance(arg, (list, tuple, np.ndarray)):
    #                 datasets.append(list(arg))
    #             else:
    #                 datasets.append([arg])
    #         is_single_mode = False
    #         if len(datasets[0]) >= 2:
    #             is_uptrend = datasets[0][-1] >= datasets[0][-2]
    #         else:
    #             is_uptrend = True
    #         first_color = config["up_color"] if is_uptrend else config["down_color"]
    #         if is_uptrend:
    #             secondary_line_color = "#ff6666"
    #             secondary_fill_color = "#ff4444"
    #         else:
    #             secondary_line_color = "#66b266"
    #             secondary_fill_color = "#00a859"
    #         colors = [first_color, secondary_line_color]
    #         fill_colors = [first_color, secondary_fill_color]
    #     else:
    #         datasets = [[]]
    #         is_single_mode = True
    #         colors = [config["up_color"]]
    #         fill_colors = [config["up_color"]]

    #     # 初始化画布
    #     fig, ax1 = plt.subplots(1, 1, figsize=(2.5, 1), facecolor="none")
    #     fig.patch.set_alpha(0.0)

    #     if not is_single_mode and len(datasets) >= 2:
    #         ax2 = ax1.twinx()

    #         # 主轴置顶并隐藏背景，防止右轴遮挡左轴线
    #         ax1.set_zorder(ax2.get_zorder() + 1)
    #         ax1.patch.set_visible(False)
    #         try:
    #             ax2.patch.set_alpha(0.0)
    #         except Exception:
    #             ax2.patch.set_visible(False)
    #         # 让右轴绘图位于更低层
    #         ax2.set_zorder(ax1.get_zorder() - 1)
    #         axes = [ax1, ax2]
    #     else:
    #         axes = [ax1]

    #     # 截断到相等长度（双列）
    #     if not is_single_mode and len(datasets) >= 2:
    #         min_length = min(len(datasets[0]), len(datasets[1]))
    #         datasets[0] = datasets[0][:min_length]
    #         datasets[1] = datasets[1][:min_length]

    #     # 清理并计算范围
    #     def clean_and_convert(arr):
    #         clean = []
    #         for x in arr:
    #             if isinstance(x, (int, float, np.number)):
    #                 clean.append(float(x))
    #             else:
    #                 try:
    #                     clean.append(float(x))
    #                 except (ValueError, TypeError):
    #                     clean.append(0.0)
    #         return clean

    #     clean_datasets = [clean_and_convert(ds) for ds in datasets]

    #     # 计算每组数据的 dmin/dmax，并为常数或极小跨度序列扩展最小跨度
    #     data_ranges = []
    #     for cd in clean_datasets:
    #         if cd:
    #             dmin, dmax = min(cd), max(cd)
    #             span = dmax - dmin
    #             # 最小视觉跨度：相对值(2%)或绝对最小值 1e-3
    #             rel_min_span = max((abs(dmax) + abs(dmin)) * 0.02, 1e-3)
    #             if span < rel_min_span:
    #                 mid = (dmax + dmin) / 2.0
    #                 dmin = mid - rel_min_span / 2.0
    #                 dmax = mid + rel_min_span / 2.0
    #             data_ranges.append((dmin, dmax))
    #         else:
    #             data_ranges.append((-1, 1))

    #     # 为左右轴分别设置独立 ylim（不再尝试强制对齐）
    #     if not is_single_mode and len(clean_datasets) >= 2:
    #         # 左轴（主轴）范围
    #         min1, max1 = data_ranges[0]
    #         span1 = max1 - min1 if (max1 - min1) > 0 else 1.0
    #         margin1 = max(span1 * 0.15, (abs(max1) + abs(min1)) * 0.02, 1e-3)
    #         ax1.set_ylim(min1 - margin1, max1 + margin1)

    #         # 右轴（第二组数据）范围
    #         min2, max2 = data_ranges[1]
    #         span2 = max2 - min2 if (max2 - min2) > 0 else 1.0
    #         margin2 = max(span2 * 0.12, (abs(max2) + abs(min2)) * 0.02, 1e-3)
    #         ax2.set_ylim(min2 - margin2, max2 + margin2)
    #     elif is_single_mode and clean_datasets[0]:
    #         min_val, max_val = data_ranges[0]
    #         range_val = max_val - min_val if (max_val - min_val) > 0 else 1.0
    #         margin = max(range_val * 0.15, (abs(max_val) + abs(min_val)) * 0.02, 1e-3)
    #         ax1.set_ylim(min_val - margin, max_val + margin)

    #     # 设置边距
    #     for ax in axes:
    #         ax.margins(x=0.02, y=0.0)

    #     # 绘制数据
    #     for i, (dataset, color) in enumerate(zip(clean_datasets, colors)):
    #         if not dataset:
    #             continue

    #         # 选择轴与样式
    #         if is_single_mode or i == 0:
    #             ax = ax1
    #             line_width = config["line_width"]
    #             line_alpha = 1.0
    #             fill_color = color
    #         else:
    #             ax = ax2
    #             line_width = config["secondary_line_width"]
    #             line_alpha = config["secondary_line_alpha"]
    #             fill_color = fill_colors[i] if i < len(fill_colors) else fill_colors[-1]

    #         x = np.arange(len(dataset))
    #         y = np.array(dataset)

    #         # 绘制折线（主轴 zorder 已确保在上层）
    #         ax.plot(x, y, color=color, lw=line_width, alpha=line_alpha, zorder=3)

    #         # 第二组数据的特殊处理
    #         if not is_single_mode and i == 1 and len(dataset) > 0:
    #             if second_plot_type == "area":
    #                 # 面积图模式：填充到0
    #                 alphas = np.linspace(
    #                     config["fill_alpha_range"][0],
    #                     config["fill_alpha_range"][1],
    #                     len(dataset),
    #                 )
    #                 for j in range(len(dataset) - 1):
    #                     x_segment = x[j : j + 2]
    #                     y_segment = y[j : j + 2]
    #                     local_alpha = float(np.mean(alphas[j : j + 2]))
    #                     ax.fill_between(
    #                         x_segment,
    #                         y_segment,
    #                         0,
    #                         color=fill_color,
    #                         alpha=local_alpha,
    #                         edgecolor="none",
    #                         zorder=2,
    #                     )
    #                 # 非线性 alpha 映射：对时间序列末端（最近）给予更高透明度（更显眼）
    #                 a_min, a_max = config.get("fill_alpha_range", (0.06, 0.25))
    #                 power = float(config.get("alpha_power", 1.0))
    #                 steps = len(dataset)
    #                 # 生成 0..1 基准并做幂映射（power>1 强调末端）
    #                 base = np.linspace(0.0, 1.0, steps)
    #                 mapped = np.power(base, power)
    #                 alphas = a_min + (a_max - a_min) * mapped
    #                 # 填充分段渲染
    #                 for j in range(len(dataset) - 1):
    #                     x_segment = x[j : j + 2]
    #                     y_segment = y[j : j + 2]
    #                     local_alpha = float(np.mean(alphas[j : j + 2]))
    #                     # cap alpha 防止过于不透明
    #                     local_alpha = min(max(local_alpha, 0.0), 0.6)
    #                     ax.fill_between(
    #                         x_segment,
    #                         y_segment,
    #                         0,
    #                         color=fill_color,
    #                         alpha=local_alpha,
    #                         edgecolor="none",
    #                         zorder=2,
    #                     )

    #             elif second_plot_type == "line":
    #                 # 折线图模式：不填充，但可以添加端点标记
    #                 ax.scatter(
    #                     len(dataset) - 1,
    #                     dataset[-1],
    #                     color=color,
    #                     s=config["marker_size"] ** 2,
    #                     edgecolor="white",
    #                     linewidth=0.4,
    #                     zorder=4,
    #                 )

    #         # 端点强化（第一组或单列显示，如果是第二组且为line模式已在上面处理）
    #         if (i == 0 or is_single_mode) and not (
    #             i == 1 and second_plot_type == "line"
    #         ):
    #             ax.scatter(
    #                 len(dataset) - 1,
    #                 dataset[-1],
    #                 color=color,
    #                 s=config["marker_size"] ** 2,
    #                 edgecolor="white" if (is_single_mode or i == 0) else "#2a2e39",
    #                 linewidth=0.4,
    #                 zorder=4,
    #             )

    #     # 左轴零线（仅装饰，左右轴独立刻度）
    #     zero_color = colors[0] if colors else config["up_color"]
    #     ax1.axhline(
    #         0, color=zero_color, alpha=config["zero_line_alpha"], lw=0.8, zorder=1
    #     )

    #     # 隐藏坐标轴（仅保留图形）
    #     ax1.axis("off")
    #     if not is_single_mode and len(datasets) >= 2:
    #         ax2.axis("off")

    #     # 统一X轴范围（x 轴共享）
    #     if not is_single_mode and len(clean_datasets) >= 2:
    #         xlen = max(1, len(clean_datasets[0]) - 1)
    #         ax1.set_xlim(0, xlen)
    #         ax2.set_xlim(0, xlen)
    #     else:
    #         xlen = max(1, len(clean_datasets[0]) - 1)
    #         ax1.set_xlim(0, xlen)

    #     # 布局与导出
    #     plt.tight_layout(pad=0)
    #     plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    #     img = BytesIO()
    #     fig.savefig(
    #         img,
    #         format="png",
    #         dpi=150,
    #         transparent=True,
    #         bbox_inches="tight",
    #         pad_inches=0,
    #         facecolor="none",
    #     )
    #     plt.close(fig)

    #     return (
    #         f'<img src="data:image/png;base64,{b64encode(img.getvalue()).decode()}" />'
    #     )

    # area chart按照y轴渐变透明度填充
    @staticmethod
    def create_line(*args, second_plot_type="area"):
        config = {
            "up_color": "#ff4444",
            "down_color": "#0d876d",
            "line_width": 3.6,
            "marker_radius": 4.8,
            "zero_axis_color": "#667085",
            "volume_color": "#667085",
            "volume_line_width": 2.1,
            "volume_fill_alpha": 0.1,
            "volume_band_height": 24.0,
            "volume_gap": 8.0,
            "right_margin": 7.0,
        }

        if len(args) == 1:
            datasets = [list(args[0])]
            is_single = True
        else:
            datasets = [list(args[0]), list(args[1])]
            is_single = False

        def clean(arr):
            out = []
            for v in arr:
                try:
                    out.append(float(v))
                except Exception:
                    out.append(0.0)
            return out

        datasets = [clean(d) for d in datasets]
        if not is_single:
            min_len = min(len(datasets[0]), len(datasets[1]))
            datasets = [d[:min_len] for d in datasets]

        if not datasets[0]:
            return ""

        # Keep the original compact sparkline canvas dimensions.
        width, height = 300, 120
        volume_bottom = height - 4.0
        volume_top = volume_bottom - config["volume_band_height"]
        plot_top = 4.0
        plot_bottom = volume_top - config["volume_gap"]
        plot_right = width - config["right_margin"]
        point_count = len(datasets[0])
        x_values = (
            [plot_right / 2]
            if point_count == 1
            else [i * plot_right / (point_count - 1) for i in range(point_count)]
        )

        pnl_values = datasets[0]
        pnl_low = min(min(pnl_values), 0.0)
        pnl_high = max(max(pnl_values), 0.0)
        pnl_span = max(pnl_high - pnl_low, 1e-3)
        pnl_lower = pnl_low - pnl_span * 0.08
        pnl_upper = pnl_high + pnl_span * 0.08

        def map_pnl_y(value):
            return plot_top + (pnl_upper - value) / (pnl_upper - pnl_lower) * (
                plot_bottom - plot_top
            )

        main_points = [(x, map_pnl_y(y)) for x, y in zip(x_values, pnl_values)]
        last_x, last_y = main_points[-1]
        last_value = pnl_values[-1]
        last_color = (
            config["up_color"]
            if last_value > 0
            else config["down_color"]
            if last_value < 0
            else config["zero_axis_color"]
        )

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            'preserveAspectRatio="xMidYMid meet">',
            '<defs><clipPath id="plot"><rect width="300" height="120"/></clipPath></defs>',
            '<g clip-path="url(#plot)">',
        ]

        # A volume line and faint area use their own lower band and square-root
        # scaling, so volume remains legible without bars dominating the PnL.
        if not is_single:
            volume = [max(value, 0.0) for value in datasets[1]]
            max_volume = max(volume, default=0.0)
            if max_volume > 0:
                volume_points = [
                    (
                        x,
                        volume_bottom
                        - (value / max_volume) ** 0.5 * (volume_bottom - volume_top),
                    )
                    for x, value in zip(x_values, volume)
                ]
                volume_points_attr = " ".join(
                    f"{x:.2f},{y:.2f}" for x, y in volume_points
                )
                volume_area_points = (
                    f"{x_values[0]:.2f},{volume_bottom:.2f} "
                    f"{volume_points_attr} "
                    f"{x_values[-1]:.2f},{volume_bottom:.2f}"
                )
                svg_parts.extend(
                    [
                        f'<polygon points="{volume_area_points}" '
                        f'fill="{config["volume_color"]}" '
                        f'fill-opacity="{config["volume_fill_alpha"]:.2f}"/>',
                        f'<polyline points="{volume_points_attr}" fill="none" '
                        f'stroke="{config["volume_color"]}" '
                        f'stroke-width="{config["volume_line_width"]:.2f}" '
                        'stroke-linejoin="round" stroke-linecap="round"/>',
                    ]
                )

        zero_y = map_pnl_y(0.0)
        svg_parts.append(
            f'<line x1="0" y1="{zero_y:.2f}" x2="{plot_right:.2f}" '
            f'y2="{zero_y:.2f}" stroke="{config["zero_axis_color"]}" '
            'stroke-width="1.1" stroke-opacity="0.58" stroke-dasharray="3 3"/>'
        )

        # Color each segment by the sign of its PnL. Split zero crossings so a
        # rising/falling segment never gets the wrong sign color.
        pnl_paths = {"positive": [], "negative": [], "zero": []}
        for index in range(len(pnl_values) - 1):
            x1, y1 = main_points[index]
            x2, y2 = main_points[index + 1]
            value1, value2 = pnl_values[index], pnl_values[index + 1]
            if value1 * value2 < 0:
                fraction = abs(value1) / (abs(value1) + abs(value2))
                cross_x = x1 + (x2 - x1) * fraction
                cross_y = zero_y
                first_key = "positive" if value1 > 0 else "negative"
                second_key = "positive" if value2 > 0 else "negative"
                pnl_paths[first_key].append(
                    f"M{x1:.2f},{y1:.2f} L{cross_x:.2f},{cross_y:.2f}"
                )
                pnl_paths[second_key].append(
                    f"M{cross_x:.2f},{cross_y:.2f} L{x2:.2f},{y2:.2f}"
                )
            else:
                midpoint = (value1 + value2) / 2
                key = (
                    "positive"
                    if midpoint > 0
                    else "negative"
                    if midpoint < 0
                    else "zero"
                )
                pnl_paths[key].append(f"M{x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f}")

        for key, color in (
            ("positive", config["up_color"]),
            ("negative", config["down_color"]),
            ("zero", config["zero_axis_color"]),
        ):
            if pnl_paths[key]:
                svg_parts.append(
                    f'<path d="{" ".join(pnl_paths[key])}" fill="none" '
                    f'stroke="{color}" stroke-width="{config["line_width"]:.2f}" '
                    'stroke-linejoin="round" stroke-linecap="round"/>'
                )

        svg_parts.extend(
            [
                f'<circle cx="{last_x:.2f}" cy="{last_y:.2f}" '
                f'r="{config["marker_radius"]:.2f}" fill="{last_color}" '
                f'stroke="{last_color}" stroke-width="{0.4 * 120 / 72:.2f}"/>',
                "</g></svg>",
            ]
        )
        svg = "".join(svg_parts)
        encoded_svg = b64encode(svg.encode("utf-8")).decode("ascii")
        return f'<img src="data:image/svg+xml;base64,{encoded_svg}" />'

    @staticmethod
    def get_config(path: str = None, default: Any = None) -> Any:
        try:
            config_path = FINANCE_ROOT / "utility" / "scoring_weights.json"

            if not config_path.exists():
                return default if path else {}

            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        except Exception as e:
            print(f"[ToolKit] 读取配置文件失败: {e}")
            return default if path else {}

        # 1. 不传 path，直接返回完整字典
        if not path:
            return cfg

        # 2. 按点号解析层级 key
        curr = cfg
        for k in path.split("."):
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                return default

        return curr

    @staticmethod
    def score_and_select_symbols(
        df: pd.DataFrame,
        column_map: dict,
        market: str,
        trade_date: str,
        *,
        quantile: float | None = None,
    ) -> set[str]:
        """
        执行打分逻辑 + 筛选 symbol
        返回：被选中的 symbol 集合
        """
        # 如果调用方没传 quantile（为 None），则优先从 UI 配置读取；配置没有则回退到 0.95
        if quantile is None:
            quantile = (
                ToolKit.get_config().get("stock_filter", {}).get("quantile", 0.95)
            )

        def extract_arrow_num(s):
            # 去除 HTML 标签
            clean_text = re.sub(r"<[^<]+?>", "", s)
            arrow_num = 0
            up_match = re.search(r"↑(\d+)", clean_text)
            if up_match:
                arrow_num = int(up_match.group(1))
            else:
                down_match = re.search(r"↓(\d+)", clean_text)
                if down_match:
                    arrow_num = -int(down_match.group(1))
            bracket_match = re.search(r"/(\d+)", clean_text)
            bracket_num = int(bracket_match.group(1)) if bracket_match else None
            return arrow_num, bracket_num

        def rank_score(
            s: pd.Series,
            *,
            higher_is_better: bool = True,
            mid: float | None = None,
        ) -> pd.Series:
            s_num = pd.to_numeric(s, errors="coerce")
            score = pd.Series(0.0, index=s.index)
            valid = s_num.dropna()
            if valid.empty:
                return score
            if mid is None:
                vals = valid.copy()
                if not higher_is_better:
                    vals = -vals
                rank_pct = vals.rank(pct=True)
                score.loc[valid.index] = rank_pct
                return score
            aligned = valid - mid
            pos = aligned[aligned > 0]
            neg = aligned[aligned < 0]
            eps = 0.001
            if not pos.empty:
                pos_rank = pos.rank(pct=True)
                pos_score = eps + (1 - eps) * pos_rank
                score.loc[pos.index] = pos_score
            if not neg.empty:
                neg_rank = neg.rank(pct=True)
                neg_score = -(eps + (1 - eps) * (1 - neg_rank))
                score.loc[neg.index] = neg_score
            return score

        df = df.copy()

        # -----读取权重配置-----#
        weights_cfg = ToolKit.get_config()
        w = weights_cfg["weights"]
        sw = weights_cfg["sub_weights"]

        # ===== 列映射 =====
        c = column_map
        sym_col = c["symbol"]

        # ===== 行业解析（保持不变） =====
        df[["IND_ARROW_NUM", "IND_BRACKET_NUM"]] = df[c["industry"]].apply(
            lambda x: pd.Series(extract_arrow_num(x))
        )
        df["industry_arrow_score"] = rank_score(df["IND_ARROW_NUM"], mid=0)
        df["industry_bracket_score"] = rank_score(
            df["IND_BRACKET_NUM"], higher_is_better=False
        )
        df["industry_score"] = (
            sw["industry"]["arrow"] * df["industry_arrow_score"]
            + sw["industry"]["bracket"] * df["industry_bracket_score"]
        )

        # ===== ERP（保持不变） =====
        df[c["erp"]] = pd.to_numeric(df[c["erp"]], errors="coerce")
        df[c["erp"]] = df[c["erp"]].fillna(-99999)
        ind_cnt = df.groupby(c["industry"])[sym_col].transform("count")
        invalid_ind = ind_cnt < 3
        df["erp_score"] = np.where(
            invalid_ind,
            rank_score(df[c["erp"]], mid=0),
            df.groupby(c["industry"])[c["erp"]].transform(
                lambda x: rank_score(x, mid=0)
            ),
        )

        # ===== PNL（保持不变） =====
        trade_dt = pd.to_datetime(trade_date)
        open_dt = pd.to_datetime(df[c["open_date"]], errors="coerce")
        days = (trade_dt - open_dt).dt.days.clip(lower=1)
        df["pnl_daily_score"] = rank_score(df[c["pnl_ratio"]] / days, mid=0)

        def weighted_avg_return(returns_list):
            if isinstance(returns_list, str):
                try:
                    import ast

                    returns_list = ast.literal_eval(returns_list)
                except Exception:
                    return np.nan
            if (
                not isinstance(returns_list, (list, np.ndarray))
                or len(returns_list) == 0
            ):
                return np.nan
            arr = np.asarray(returns_list, dtype=float)
            if len(arr) == 0:
                return np.nan
            weights = np.arange(1, len(arr) + 1)
            return np.average(arr, weights=weights)

        df["weighted_return"] = df[c["daily_return_array"]].apply(weighted_avg_return)
        df["weighted_return_score"] = rank_score(df["weighted_return"], mid=0)
        df["pnl_score"] = (
            sw["pnl"]["daily"] * df["pnl_daily_score"]
            + sw["pnl"]["weighted_return"] * df["weighted_return_score"]
        )

        # ===== 稳定性（保持不变） =====
        df["win_rate_score"] = rank_score(df[c["win_rate"]], mid=0.5)
        df["avg_trans_score"] = rank_score(df[c["avg_trans"]], higher_is_better=False)
        df["sortino_score"] = rank_score(df[c["sortino"]], mid=0.5)
        df["maxdd_score"] = rank_score(df[c["max_dd"]])
        df["stability_score"] = (
            sw["stability"]["win_rate"] * df["win_rate_score"]
            + sw["stability"]["avg_trans"] * df["avg_trans_score"]
            + sw["stability"]["sortino"] * df["sortino_score"]
            + sw["stability"]["maxdd"] * df["maxdd_score"]
        )

        # ===== 新增：策略因子（strategy_cnt + strategy） =====
        # 1. strategy_cnt（越高越好）
        df["strategy_cnt_score"] = rank_score(
            df[c["strategy_cnt"]], higher_is_better=True
        )

        # 2. strategy 有序映射
        strategy_level_map = {
            "多头排列": 3,
            "突破年线": 3,
            "均线金叉": 2,
            "突破半年线": 2,
            "均线收敛": 2,
            "成交量放大": 1,
            "红三兵": 1,
            "连续上涨": 1,
        }
        df["strategy_signal_num"] = (
            df[c["strategy"]].map(strategy_level_map).fillna(1)
        )  # 缺失或未知默认为最低级
        df["strategy_signal_score"] = rank_score(
            df["strategy_signal_num"], higher_is_better=True
        )

        # 策略综合得分（子权重需在配置中定义）
        df["strategy_score"] = (
            sw["strategy"]["cnt"] * df["strategy_cnt_score"]
            + sw["strategy"]["signal"] * df["strategy_signal_score"]
        )

        # ===== 总分 =====
        df["total_score"] = (
            w["industry"] * df["industry_score"]
            + w["pnl"] * df["pnl_score"]
            + w["stability"] * df["stability_score"]
            + w["erp"] * df["erp_score"]
            + w["strategy"] * df["strategy_score"]  # 新增主权重
        )

        # ===== 筛选 =====
        threshold = df["total_score"].quantile(quantile)
        selected = df.loc[df["total_score"] > threshold, sym_col]
        selected_symbols = set(selected.astype(str).str.strip().unique())

        # ===== 返回得分字典（包含新因子） =====
        score_fields = [
            "total_score",
            "industry_score",
            "erp_score",
            "pnl_score",
            "stability_score",
            "strategy_score",  # 新增综合得分
            "strategy_cnt_score",  # 新增子得分
            "strategy_signal_score",  # 新增子得分
        ]
        score_dict = {
            field: df.set_index(sym_col)[field].to_dict() for field in score_fields
        }
        rank_series = df["total_score"].rank(ascending=False, method="min").astype(int)
        score_dict["rank"] = rank_series.set_axis(df[sym_col]).to_dict()

        return selected_symbols, score_dict

    @staticmethod
    def export_if_changed(selected_symbols, market):
        """
        当命中的 symbol 列表发生变化时才写出 CSV
        CSV 格式：
            symbol
            AAPL
            MSFT
            ...
        """
        out_file = FINANCE_ROOT / f"{market}stockinfo" / "dynamic_list.csv"
        # 将 selected_symbols 转为已排序的字符串列表，保证顺序确定且可用于 pandas
        symbols_list = sorted([str(s).strip() for s in selected_symbols])
        # 当前内容 hash（使用排序后的列表以确保可复现的哈希）
        content = "\n".join(symbols_list).encode("utf-8")
        new_md5 = hashlib.md5(content).hexdigest()

        # 2️⃣ 如果文件已存在，计算旧文件的 hash
        if os.path.exists(out_file):
            old_df = pd.read_csv(out_file)

            if "symbol" in old_df.columns:
                old_symbols = sorted(
                    old_df["symbol"].astype(str).str.strip().unique().tolist()
                )

                old_content = "\n".join(old_symbols).encode("utf-8")
                old_md5 = hashlib.md5(old_content).hexdigest()

                if old_md5 == new_md5:
                    return  # 内容一致，不写文件

        # 3️⃣ 内容不同，写文件
        pd.DataFrame({"symbol": symbols_list}).to_csv(out_file, index=False)
