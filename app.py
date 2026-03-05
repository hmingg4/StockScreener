import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ------------------------------
# 全局配置
# ------------------------------
st.set_page_config(page_title="Wyckoff+VCP 核心选股器", layout="wide")
st.title("🚀 Wyckoff + VCP 核心形态选股（已放宽条件）")

# ------------------------------
# 得分规则（只保留最核心）
# ------------------------------
SCORE_RULES = {
    "Wyckoff弹簧效应": 5.0,
    "VCP波动收缩": 3.0,
    "VCP接近突破": 2.0,
    "放量确认": 1.0,
}

# ------------------------------
# 强化备用股票池（港股 + 美股）
# ------------------------------
@st.cache_data(ttl=86400)
def get_stock_pool(market, min_price):
    if market == "港股":
        pool = [
            "0001.HK","0002.HK","0003.HK","0005.HK","0006.HK","0011.HK","0012.HK","0016.HK",
            "0017.HK","0019.HK","0027.HK","0066.HK","0083.HK","0101.HK","0144.HK","0151.HK",
            "0168.HK","0175.HK","0200.HK","0241.HK","0267.HK","0288.HK","0291.HK","0332.HK",
            "0358.HK","0386.HK","0388.HK","0688.HK","0700.HK","0762.HK","0823.HK","0857.HK",
            "0883.HK","0939.HK","0941.HK","0960.HK","0992.HK","1038.HK","1044.HK","1088.HK",
            "1093.HK","1109.HK","1113.HK","1177.HK","1211.HK","1299.HK","1398.HK","1810.HK",
            "1928.HK","2015.HK","2318.HK","2382.HK","2601.HK","3690.HK","3988.HK","6098.HK",
            "9618.HK","9868.HK","9888.HK","9988.HK"
        ]
    else:
        pool = [
            "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","JPM","V","MA","PG","WMT","JNJ",
            "UNH","HD","CVX","XOM","PFE","ABBV","MRK","ACN","CSCO","WFC","BAC","NFLX","ADBE",
            "CRM","INTC","TXN","AMD","QCOM","LRCX","AMAT","HON","IBM","MS","GS","BLK","SPGI",
            "PLD","C","ADP","ITW","MMM","GE","CAT","DE","LOW","TGT","COST","MCD","NKE","SBUX"
        ]
    return pool

# ------------------------------
# 技术指标
# ------------------------------
def calculate_atr(data, period=10):
    tr = np.maximum(
        data['High'] - data['Low'],
        abs(data['High'] - data['Close'].shift(1)),
        abs(data['Low'] - data['Close'].shift(1))
    )
    return tr.rolling(period).mean()

# ------------------------------
# 【核心】Wyckoff 弹簧效应（大幅放宽）
# ------------------------------
def check_wyckoff_spring(data):
    if len(data) < 20:
        return False
    low20 = data['Low'].rolling(20).min().iloc[-5]
    last_low = data['Low'].iloc[-3]
    last_close = data['Close'].iloc[-1]
    return (last_low <= low20 * 1.02) and (last_close > last_low)

# ------------------------------
# 【核心】VCP 波动收缩（大幅放宽）
# ------------------------------
def check_vcp_contraction(data):
    if len(data) < 30:
        return False
    atr = calculate_atr(data, 10)
    recent_atr = atr.iloc[-5:].mean()
    past_atr = atr.iloc[-20:-10].mean()
    if past_atr == 0:
        return False
    return recent_atr < past_atr * 0.85

# ------------------------------
# VCP 接近突破
# ------------------------------
def check_near_breakout(data):
    if len(data) < 20:
        return False
    high20 = data['High'].rolling(20).max().iloc[-1]
    close = data['Close'].iloc[-1]
    return close >= high20 * 0.95

# ------------------------------
# 放量
# ------------------------------
def check_volume_confirm(data):
    if len(data) < 10:
        return False
    vol_avg = data['Volume'].iloc[-10:-3].mean()
    last_vol = data['Volume'].iloc[-1]
    return last_vol > vol_avg * 1.2

# ------------------------------
# 选股主逻辑（只抓核心）
# ------------------------------
def run_screener(market, min_price):
    symbols = get_stock_pool(market, min_price)
    end = datetime.now()
    start = end - timedelta(days=90)
    results = []

    progress = st.progress(0)
    status = st.empty()

    for i, sym in enumerate(symbols):
        status.text(f"正在分析 {sym}")
        progress.progress((i+1)/len(symbols))
        try:
            df = yf.download(sym, start=start, end=end, interval="1d", progress=False)
            if len(df) < 20:
                continue

            close = df['Close'].iloc[-1]
            if close < min_price:
                continue

            # 信号
            spring = check_wyckoff_spring(df)
            vcp_con = check_vcp_contraction(df)
            near_break = check_near_breakout(df)
            vol_ok = check_volume_confirm(df)

            # 打分
            score = 0.0
            desc = []
            if spring:
                score += SCORE_RULES["Wyckoff弹簧效应"]
                desc.append("Wyckoff弹簧")
            if vcp_con:
                score += SCORE_RULES["VCP波动收缩"]
                desc.append("VCP收缩")
            if near_break:
                score += SCORE_RULES["VCP接近突破"]
                desc.append("近突破")
            if vol_ok:
                score += SCORE_RULES["放量确认"]
                desc.append("放量")

            # 只要有核心形态就入选（不再苛刻）
            if spring or vcp_con:
                results.append({
                    "代码": sym,
                    "价格": round(close, 2),
                    "得分": round(score, 1),
                    "信号": " | ".join(desc),
                    "数据": df
                })
        except:
            continue

    status.empty()
    return sorted(results, key=lambda x: x["得分"], reverse=True)

# ------------------------------
# 界面
# ------------------------------
with st.sidebar:
    st.header("参数")
    market = st.selectbox("市场", ["港股", "美股"])
    min_price = st.number_input("最低价格", min_value=0.0, value=5.0)
    run = st.button("🔍 开始筛选")

if run:
    res = run_screener(market, min_price)
    if not res:
        st.info("暂无符合，可把价格调到 3 元再试")
    else:
        st.success(f"找到 {len(res)} 只标的（按接近买入点排序）")
        for item in res:
            col = "green" if item["得分"] >= 5 else "orange" if item["得分"] >= 3 else "gray"
            with st.expander(f"📈 {item['代码']}  得分:{col}[{item['得分']}]  价格:{item['价格']}"):
                st.write(f"**信号**: {item['信号']}")
                df = item["数据"]
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close
                ))
                fig.update_layout(xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
