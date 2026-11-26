import akshare as ak
import pandas as pd
import plotly.express as px

# 韭圈儿对应的指数名称
index_map = {
    "沪深300": "沪深300",
    "中证500": "中证500",
    "科创50": "科创50"
}

df_list = []
for name, funddb_name in index_map.items():
    # 获取PE-TTM历史
    df = ak.index_value_hist_funddb(
        symbol=funddb_name,
        indicator="市盈率"
    )
    df["指数名称"] = name
    df_list.append(df)

df_all = pd.concat(df_list, ignore_index=True)
df_all["日期"] = pd.to_datetime(df_all["日期"])

# 绘图
fig = px.line(
    df_all,
    x="日期",
    y="平均值",
    color="指数名称",
    title="沪深300 / 中证500 / 科创50 PE-TTM 历史走势（韭圈-funddb口径）",
    labels={"平均值": "PE-TTM", "日期": "日期"}
)
fig.update_layout(height=600)
fig.show()

# 导出csv
df_all.to_csv("index_pe_history.csv", index=False, encoding="utf-8-sig")
