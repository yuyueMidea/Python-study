#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
年度销售自动化报表生成脚本
依赖库: pandas, openpyxl, random, datetime
运行命令: python auto_report.py
输出文件: 2024年度销售自动化报表.xlsx
"""

import random
from datetime import datetime, timedelta

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils import get_column_letter

# ========== 全局样式常量 ==========
BLUE_DARK = "1F3864"
BLUE_MID = "2E75B6"
BLUE_LIGHT = "BDD7EE"
BLUE_PALE = "DEEAF1"
ORANGE = "ED7D31"
WHITE = "FFFFFF"
GRAY_LIGHT = "F2F2F2"
GRAY_MID = "D9D9D9"
GREEN = "70AD47"
RED = "FF0000"


def thin_border(top=True, bottom=True, left=True, right=True):
    s = Side(style="thin", color="BFFBFF")
    n = Side(style=None)
    return Border(top=s if top else n,
                  bottom=s if bottom else n,
                  left=s if left else n,
                  right=s if right else n)


def header_style(ws, row, col, value, bg=BLUE_DARK, fg=WHITE, bold=True, size=11, h_align="center"):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(name="Arial", bold=bold, color=fg, size=size)
    c.fill = PatternFill("solid", fgColor=bg)
    c.alignment = Alignment(horizontal=h_align, vertical="center", wrap_text=True)
    c.border = thin_border()
    return c


def data_style(ws, row, col, value, bg=WHITE, bold=False, h_align="center", num_format=None):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(name="Arial", bold=bold, color="000000", size=10)
    c.fill = PatternFill("solid", fgColor=bg)
    c.alignment = Alignment(horizontal=h_align, vertical="center")
    c.border = thin_border()
    if num_format:
        c.number_format = num_format
    return c


def set_col_width(ws, widths: dict):
    for col_letter, w in widths.items():
        ws.column_dimensions[col_letter].width = w


def freeze_and_filter(ws, freeze_cell, filter_range):
    ws.freeze_panes = freeze_cell
    ws.auto_filter.ref = filter_range


# ========== 1. 生成模拟销售原始数据 ==========
def generate_raw_data(n=500):
    start = datetime(2024, 1, 1)
    regions = ["东北", "华东", "华南", "华北", "西南"]
    products = ["产品A", "产品B", "产品C", "产品D"]
    channels = ["线上", "线下", "分销"]
    salesreps = ["张三", "李四", "王五", "赵六", "钱七", "孙八"]

    rows = []
    for i in range(1, n + 1):
        qty = random.randint(1, 200)
        price = random.choice([299, 499, 799, 1299])
        cost = round(price * random.uniform(0.4, 0.65), 2)
        rows.append({
            "订单ID": f"ORD-{i:04d}",
            "日期": start + timedelta(days=random.randint(0, 364)),
            "地区": random.choice(regions),
            "产品": random.choice(products),
            "渠道": random.choice(channels),
            "销售员": random.choice(salesreps),
            "数量": qty,
            "单价": price,
            "销售额": qty * price,
            "成本": round(qty * cost, 2),
            "利润": round(qty * (price - cost), 2),
        })
    df = pd.DataFrame(rows)
    df["利润率"] = (df["利润"] / df["销售额"] * 100).round(2)
    df["季度"] = df["日期"].apply(lambda d: f"Q{(d.month - 1) // 3 + 1}")
    df["月份"] = df["日期"].apply(lambda d: d.month)
    return df


# ========== 2. 工作表：封面 ==========
def build_cover(wb, report_date):
    ws = wb.active
    ws.title = "封面"
    ws.sheet_view.showGridLines = False

    # 深色背景
    for r in range(1, 40):
        for c in range(1, 15):
            ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=BLUE_DARK)

    # 标题
    ws.merge_cells("B4:M6")
    c = ws["B4"]
    c.value = "年度销售自动化报表"
    c.font = Font(name="Arial", bold=True, size=36, color=WHITE)
    c.alignment = Alignment(horizontal="center", vertical="center")

    # 副标题
    ws.merge_cells("B7:M8")
    c = ws["B7"]
    c.value = "Annual Sales Automated Report"
    c.font = Font(name="Arial", size=16, color=BLUE_LIGHT)
    c.alignment = Alignment(horizontal="center", vertical="center")

    # 橙色分割线
    for col in range(2, 14):
        ws.cell(row=9, column=col).fill = PatternFill("solid", fgColor=ORANGE)
    ws.row_dimensions[9].height = 4

    # 报告信息
    info = [
        ("报告期间", "2024年度（1月 - 12月）"),
        ("报告日期", report_date.strftime("%Y年%m月%d日")),
        ("数据来源", "销售管理系统"),
        ("编制单位", "销售分析部"),
    ]
    for i, (label, val) in enumerate(info, start=11):
        ws.merge_cells(f"D{i}:E{i}")
        ws.merge_cells(f"F{i}:K{i}")
        lc = ws[f"D{i}"]
        lc.value = label
        lc.font = Font(name="Arial", bold=True, color=ORANGE, size=12)
        lc.alignment = Alignment(horizontal="right", vertical="center")
        vc = ws[f"F{i}"]
        vc.value = val
        vc.font = Font(name="Arial", color=WHITE, size=12)
        vc.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[i].height = 22

    # 报告目录
    ws.merge_cells("B17:M17")
    c = ws["B17"]
    c.value = "报告目录"
    c.font = Font(name="Arial", bold=True, size=14, color=ORANGE)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[17].height = 28

    toc = [
        ("Sheet 1", "封面"),
        ("Sheet 2", "原始数据"),
        ("Sheet 3", "总体概览(KPI + 图表)"),
        ("Sheet 4", "地区分析"),
        ("Sheet 5", "产品分析"),
        ("Sheet 6", "月度趋势"),
        ("Sheet 7", "销售员排名"),
    ]
    for i, (sheet, desc) in enumerate(toc, start=19):
        ws.merge_cells(f"D{i}:E{i}")
        ws.merge_cells(f"F{i}:K{i}")
        ws[f"D{i}"].value = sheet
        ws[f"D{i}"].font = Font(name="Arial", color=ORANGE, size=11, bold=True)
        ws[f"F{i}"].value = desc
        ws[f"F{i}"].font = Font(name="Arial", color=WHITE, size=11)
        ws.row_dimensions[i].height = 20


# ========== 3. 工作表：原始数据 ==========
def build_raw_data(wb, df):
    ws = wb.create_sheet("原始数据")
    ws.sheet_view.showGridLines = False

    # 写入表头
    headers = list(df.columns)
    for j, h in enumerate(headers, 1):
        header_style(ws, 1, j, h, bg=BLUE_MID, size=10)

    # 写入数据行
    for i, row in df.iterrows():
        for j, val in enumerate(row, 1):
            bg = GRAY_LIGHT if i % 2 == 0 else WHITE
            data_style(ws, i + 2, j, val, bg=bg)

    # 冻结首行，自动筛选
    freeze_and_filter(ws, "A2", f"A1:{get_column_letter(len(headers))}{len(df)+2}")
    set_col_width(ws, {get_column_letter(c): 12 for c in range(1, len(headers) + 1)})


# ========== 4. 工作表：总体概览 ==========
def build_overview(wb, df):
    ws = wb.create_sheet("总体概览")
    ws.sheet_view.showGridLines = False

    # KPI 卡片 (4个)
    total_sales = df["销售额"].sum()
    total_profit = df["利润"].sum()
    avg_margin = (total_profit / total_sales * 100) if total_sales else 0
    total_orders = df["订单ID"].nunique()

    titles = ["总销售额", "总利润", "平均利润率", "总订单数"]
    values = [total_sales, total_profit, f"{avg_margin:.1f}%", total_orders]
    colors = [BLUE_MID, GREEN, ORANGE, BLUE_DARK]

    start_row = 2
    start_cols = [2, 5, 8, 11]
    for idx, (title, val, color) in enumerate(zip(titles, values, colors)):
        col = start_cols[idx]
        ws.merge_cells(start_row=start_row, start_column=col, end_row=start_row, end_column=col + 1)
        ws.cell(row=start_row, column=col, value=title).font = Font(bold=True, color=color, size=12)
        ws.merge_cells(start_row=start_row + 1, start_column=col, end_row=start_row + 2, end_column=col + 1)
        val_cell = ws.cell(row=start_row + 1, column=col, value=val)
        val_cell.font = Font(bold=True, size=18)
        val_cell.alignment = Alignment(horizontal="center", vertical="center")
        val_cell.fill = PatternFill("solid", fgColor=GRAY_LIGHT)

    # 季度汇总表
    q_data = df.groupby("季度").agg(
        销售额=("销售额", "sum"),
        利润=("利润", "sum"),
        订单数=("订单ID", "count")
    ).reset_index().sort_values("季度")
    r0 = 7
    header_style(ws, r0, 1, "季度销售汇总", bg=BLUE_MID, size=12)
    ws.merge_cells(f"A{r0}:D{r0}")
    headers = ["季度", "销售额(¥)", "利润(¥)", "订单数"]
    for j, h in enumerate(headers, 1):
        header_style(ws, r0 + 1, j, h, bg=BLUE_DARK)
    for i, row in enumerate(q_data.itertuples(index=False), r0 + 2):
        bg = BLUE_PALE if i % 2 == 0 else WHITE
        data_style(ws, i, 1, row.季度, bg=bg)
        data_style(ws, i, 2, row.销售额, bg=bg, num_format="#,##0")
        data_style(ws, i, 3, row.利润, bg=bg, num_format="#,##0")
        data_style(ws, i, 4, row.订单数, bg=bg)
    total_r = r0 + 2 + len(q_data)
    data_style(ws, total_r, 1, "合计", bg=BLUE_LIGHT, bold=True)
    for col in range(2, 5):
        cell = ws.cell(row=total_r, column=col, value=f"=SUM({chr(64+col)}{r0+2}:{chr(64+col)}{total_r-1})")
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor=BLUE_LIGHT)
        cell.number_format = "#,##0"

    # 柱状图：季度销售额 vs 利润
    chart = BarChart()
    chart.type = "col"
    chart.title = "季度销售额 vs 利润"
    chart.y_axis.title = "金额 (¥)"
    chart.x_axis.title = "季度"
    chart.style = 10
    chart.width = 16
    chart.height = 10
    data_ref = Reference(ws, min_col=2, max_col=3, min_row=r0 + 1, max_row=total_r)
    cats_ref = Reference(ws, min_col=1, min_row=r0 + 2, max_row=total_r - 1)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.series[0].graphicalProperties.solidFill = BLUE_MID
    chart.series[1].graphicalProperties.solidFill = GREEN
    ws.add_chart(chart, "F7")
    for col in range(1, 18):
        ws.column_dimensions[get_column_letter(col)].width = 13


# ========== 5. 工作表：地区分析 ==========
def build_region(wb, df):
    ws = wb.create_sheet("地区分析")
    ws.sheet_view.showGridLines = False

    region_df = df.groupby("地区").agg(
        销售额=("销售额", "sum"),
        利润=("利润", "sum"),
        订单数=("订单ID", "count"),
        平均利润率=("利润率", "mean")
    ).reset_index().sort_values("销售额", ascending=False)
    region_df["利润率pct"] = region_df["平均利润率"].round(1)

    ws.merge_cells("A1:F1")
    t = ws["A1"]
    t.value = "地区销售分析"
    t.font = Font(name="Arial", bold=True, size=14, color=BLUE_DARK)
    t.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 30

    headers = ["地区", "销售额(¥)", "利润(¥)", "订单数", "利润率(%)"]
    for j, h in enumerate(headers, 1):
        header_style(ws, 2, j, h, bg=BLUE_MID)

    for i, row in enumerate(region_df.itertuples(index=False), 3):
        bg = WHITE if i % 2 == 0 else GRAY_LIGHT
        data_style(ws, i, 1, row.地区, bg=bg, bold=True)
        data_style(ws, i, 2, row.销售额, bg=bg, num_format="#,##0")
        data_style(ws, i, 3, row.利润, bg=bg, num_format="#,##0")
        data_style(ws, i, 4, row.订单数, bg=bg)
        data_style(ws, i, 5, row.利润率pct, bg=bg, num_format="0.0")

    last_r = 2 + len(region_df)
    # 销售额热力图
    ws.conditional_formatting.add(
        f"B3:B{last_r}",
        ColorScaleRule(start_type="min", start_color="DEEAF1", end_type="max", end_color="1F3864")
    )
    # 饼图
    pie = PieChart()
    pie.title = "各地区销售额占比"
    pie.style = 10
    pie.width = 14
    pie.height = 10
    data_ref = Reference(ws, min_col=2, min_row=2, max_row=last_r)
    cats_ref = Reference(ws, min_col=1, min_row=3, max_row=last_r)
    pie.add_data(data_ref, titles_from_data=True)
    pie.set_categories(cats_ref)
    ws.add_chart(pie, "G2")
    set_col_width(ws, {"A": 10, "B": 14, "C": 14, "D": 10, "E": 14})


# ========== 6. 工作表：产品分析 ==========
def build_product(wb, df):
    ws = wb.create_sheet("产品分析")
    ws.sheet_view.showGridLines = False

    prod_df = df.groupby("产品").agg(
        销售额=("销售额", "sum"),
        利润=("利润", "sum"),
        数量=("数量", "sum"),
        订单数=("订单ID", "count")
    ).reset_index().sort_values("销售额", ascending=False)
    prod_df["利润率pct"] = (prod_df["利润"] / prod_df["销售额"] * 100).round(1)

    ws.merge_cells("A1:G1")
    t = ws["A1"]
    t.value = "产品销售分析"
    t.font = Font(name="Arial", bold=True, size=14, color=BLUE_DARK)
    t.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 30

    headers = ["产品", "销售额(¥)", "利润(¥)", "销量", "订单数", "利润率(%)"]
    for j, h in enumerate(headers, 1):
        header_style(ws, 2, j, h, bg=ORANGE)
    for i, row in enumerate(prod_df.itertuples(index=False), 3):
        bg = WHITE if i % 2 == 0 else GRAY_LIGHT
        data_style(ws, i, 1, row.产品, bg=bg, bold=True)
        data_style(ws, i, 2, row.销售额, bg=bg, num_format="#,##0")
        data_style(ws, i, 3, row.利润, bg=bg, num_format="#,##0")
        data_style(ws, i, 4, row.数量, bg=bg)
        data_style(ws, i, 5, row.订单数, bg=bg)
        data_style(ws, i, 6, row.利润率pct, bg=bg, num_format='0.0"%"')

    # 柱状图：产品销售额
    chart = BarChart()
    chart.type = "col"
    chart.title = "产品销售额对比"
    chart.style = 10
    chart.width = 14
    chart.height = 10
    last_r = 2 + len(prod_df)
    data_ref = Reference(ws, min_col=2, min_row=2, max_row=last_r)
    cats_ref = Reference(ws, min_col=1, min_row=3, max_row=last_r)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.series[0].graphicalProperties.solidFill = ORANGE
    ws.add_chart(chart, "H2")

    # 交叉表
    cross = df.pivot_table(index="渠道", columns="产品", values="销售额", aggfunc="sum").fillna(0)
    r0 = last_r + 2
    ws.merge_cells(f"A{r0}:E{r0}")
    header_style(ws, r0, 1, "渠道 × 产品销售额交叉分析", bg=BLUE_MID)
    header_style(ws, r0 + 1, 1, "渠道", bg=BLUE_DARK)
    for j, col_name in enumerate(cross.columns, 2):
        header_style(ws, r0 + 1, j, col_name, bg=BLUE_DARK)
    for i, (ch, row_data) in enumerate(cross.iterrows(), r0 + 2):
        bg = WHITE if i % 2 == 0 else GRAY_LIGHT
        data_style(ws, i, 1, ch, bg=bg, bold=True)
        for j, val in enumerate(row_data, 2):
            data_style(ws, i, j, val, bg=bg, num_format="#,##0")
    set_col_width(ws, {get_column_letter(c): 13 for c in range(1, 10)})


# ========== 7. 工作表：月度趋势 ==========
def build_monthly(wb, df):
    ws = wb.create_sheet("月度趋势")
    ws.sheet_view.showGridLines = False

    monthly = df.groupby("月份").agg(
        销售额=("销售额", "sum"),
        利润=("利润", "sum"),
        订单数=("订单ID", "count")
    ).reset_index().sort_values("月份")
    monthly["月份标签"] = monthly["月份"].apply(lambda m: f"{m}月")

    ws.merge_cells("A1:E1")
    t = ws["A1"]
    t.value = "月度销售趋势分析"
    t.font = Font(name="Arial", bold=True, size=14, color=BLUE_DARK)
    t.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 30

    headers = ["月份", "销售额(¥)", "利润(¥)", "订单数", "环比增长"]
    for j, h in enumerate(headers, 1):
        header_style(ws, 2, j, h, bg=BLUE_MID)

    for i, row in enumerate(monthly.itertuples(index=False), 3):
        bg = WHITE if i % 2 == 0 else GRAY_LIGHT
        data_style(ws, i, 1, row.月份标签, bg=bg)
        data_style(ws, i, 2, row.销售额, bg=bg, num_format="#,##0")
        data_style(ws, i, 3, row.利润, bg=bg, num_format="#,##0")
        data_style(ws, i, 4, row.订单数, bg=bg)
        if i > 3:
            ws.cell(row=i, column=5, value=f"=(B{i}-B{i-1})/B{i-1}").number_format = "0.0%"
        else:
            ws.cell(row=3, column=5, value="")
    last_r = 2 + len(monthly)

    # 折线图
    line = LineChart()
    line.title = "月度销售额 & 利润趋势"
    line.style = 10
    line.y_axis.title = "金额 (¥)"
    line.x_axis.title = "月份"
    line.width = 22
    line.height = 12
    data_ref = Reference(ws, min_col=2, max_col=3, min_row=2, max_row=last_r)
    cats_ref = Reference(ws, min_col=1, min_row=3, max_row=last_r)
    line.add_data(data_ref, titles_from_data=True)
    line.set_categories(cats_ref)
    line.series[0].graphicalProperties.line.solidFill = BLUE_MID
    line.series[1].graphicalProperties.line.solidFill = GREEN
    ws.add_chart(line, "G2")
    set_col_width(ws, {"A": 8, "B": 14, "C": 14, "D": 10, "E": 12})
    for col in range(7, 20):
        ws.column_dimensions[get_column_letter(col)].width = 10


# ========== 8. 工作表：销售员排名 ==========
def build_ranking(wb, df):
    ws = wb.create_sheet("销售员排名")
    ws.sheet_view.showGridLines = False

    rep_df = df.groupby("销售员").agg(
        销售额=("销售额", "sum"),
        利润=("利润", "sum"),
        订单数=("订单ID", "count"),
        平均利润率=("利润率", "mean")
    ).reset_index().sort_values("销售额", ascending=False)
    rep_df["利润率%"] = rep_df["平均利润率"].round(1)
    rep_df["排名"] = range(1, len(rep_df) + 1)
    rep_df["利润率_pct"] = rep_df["利润率%"]  # 创建无特殊字符的列

    ws.merge_cells("A1:G1")
    t = ws["A1"]
    t.value = "销售员绩效排名"
    t.font = Font(name="Arial", bold=True, size=14, color=BLUE_DARK)
    t.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 30

    headers = ["排名", "销售员", "销售额(¥)", "利润(¥)", "订单数", "利润率(%)", "奖牌"]
    for j, h in enumerate(headers, 1):
        header_style(ws, 2, j, h, bg=GREEN)
    for i, row in enumerate(rep_df.itertuples(index=False), 3):
        bg = WHITE if i % 2 == 0 else GRAY_LIGHT
        medal = "🥇" if row.排名 == 1 else "🥈" if row.排名 == 2 else "🥉" if row.排名 == 3 else ""
        data_style(ws, i, 1, row.排名, bg=bg)
        data_style(ws, i, 2, row.销售员, bg=bg, bold=True)
        data_style(ws, i, 3, row.销售额, bg=bg, num_format="#,##0")
        data_style(ws, i, 4, row.利润, bg=bg, num_format="#,##0")
        data_style(ws, i, 5, row.订单数, bg=bg)
        # data_style(ws, i, 6, row.利润率, bg=bg, num_format="0.0")
        data_style(ws, i, 6, row.利润率_pct, bg=bg, num_format="0.0")
        data_style(ws, i, 7, medal, bg=bg, h_align="center")
    last_row = 2 + len(rep_df)

    # 条形图（销售额）
    bar = BarChart()
    bar.type = "bar"
    bar.title = "销售员销售额排行"
    bar.style = 10
    bar.width = 15
    bar.height = 12
    data_ref = Reference(ws, min_col=3, min_row=2, max_row=last_row)
    cats_ref = Reference(ws, min_col=2, min_row=3, max_row=last_row)
    bar.add_data(data_ref, titles_from_data=True)
    bar.set_categories(cats_ref)
    bar.series[0].graphicalProperties.solidFill = ORANGE
    ws.add_chart(bar, "H2")
    set_col_width(ws, {"A": 6, "B": 12, "C": 14, "D": 14, "E": 10, "F": 10, "G": 8})


# ========== 9. 统一美化 ==========
def finalize_workbook(wb):
    TAB_COLORS = {
        "封面": "1F3864",
        "原始数据": "595959",
        "总体概览": "2E75B6",
        "地区分析": "70AD47",
        "产品分析": "ED7D31",
        "月度趋势": "4472C4",
        "销售员排名": "FFC000",
    }
    for ws in wb.worksheets:
        color = TAB_COLORS.get(ws.title, "000000")
        ws.sheet_properties.tabColor = color
        # 页眉页脚
        ws.oddHeader.center.text = f'&"Arial,Bold"&14 2024年度销售报表 - {ws.title}'
        ws.oddFooter.left.text = '&"Arial"&9 机密文件，请勿外传'
        ws.oddFooter.right.text = '&"Arial"&9 第 &P 页 / 共 &N 页'
        # 打印设置
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0


# ========== 10. 自检函数 ==========
def self_check(wb, df):
    expected_sheets = ["封面", "原始数据", "总体概览", "地区分析", "产品分析", "月度趋势", "销售员排名"]
    issues = []
    for sheet in expected_sheets:
        if sheet not in [ws.title for ws in wb.worksheets]:
            issues.append(f"缺少工作表: {sheet}")
    if df.isnull().values.any():
        issues.append("原始数据中存在空值")
    if df["销售额"].sum() <= 0:
        issues.append("总销售额为0，数据可能异常")
    if issues:
        for issue in issues:
            print(f"⚠️ {issue}")
        return False
    return True


# ========== 主函数 ==========
def main():
    print("=" * 55)
    print("年度销售自动化报表生成器")
    print("=" * 55)

    today = datetime.today()
    output_path = "2024年度销售自动化报表.xlsx"

    # 1. 生成数据
    print("[1/8] 生成模拟销售数据...")
    df = generate_raw_data(n=500)

    # 2. 创建 workbook 及封面
    print("[2/8] 创建工作簿 & 封面...")
    wb = Workbook()
    build_cover(wb, today)

    # 3. 原始数据
    print("[3/8] 写入原始数据...")
    build_raw_data(wb, df)

    # 4. 总体概览
    print("[4/8] 生成总体概览...")
    build_overview(wb, df)

    # 5. 地区分析
    print("[5/8] 生成地区分析...")
    build_region(wb, df)

    # 6. 产品分析
    print("[6/8] 生成产品分析...")
    build_product(wb, df)

    # 7. 月度趋势
    print("[7/8] 生成月度趋势...")
    build_monthly(wb, df)

    # 8. 销售员排名
    print("[8/8] 生成销售员排名...")
    build_ranking(wb, df)

    # 9. 美化
    print("统一美化（标签颜色 + 页眉页脚）...")
    finalize_workbook(wb)

    # 10. 自检
    print("执行自检...")
    ok = self_check(wb, df)

    # 11. 保存
    print(f"保存报表到：{output_path}")
    wb.save(output_path)

    print("\n" + "=" * 55)
    if ok:
        print("✅ 报表生成成功！")
    else:
        print("⚠️ 报表已生成，但存在上述问题，请检查。")
    print(f"文件路径：{output_path}")
    print("=" * 55)

    # 输出关键统计
    print("\n数据摘要：")
    print(f"总销售额：{df['销售额'].sum():>15,.0f}")
    print(f"总利润：{df['利润'].sum():>15,.0f}")
    print(f"平均利润率：{df['利润率'].mean():>10.1f}%")
    print(f"最佳地区：{df.groupby('地区')['销售额'].sum().idxmax()}")
    print(f"最佳产品：{df.groupby('产品')['销售额'].sum().idxmax()}")
    top_rep = df.groupby("销售员")["销售额"].sum().idxmax()
    print(f"销售冠军：{top_rep}")


if __name__ == "__main__":
    main()
