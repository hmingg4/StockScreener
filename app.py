import streamlit as st
import requests
import json
import time
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ===================== 全局配置 =====================
st.set_page_config(page_title="Wyckoff+VCP 选股器（新浪财经版）", layout="wide")

# ===================== 新浪财经数据抓取（稳定免费）=====================
def get_sina_data(stock_code, days=180):
    """
    从新浪财经抓取日线数据（延迟15分钟，稳定免费）
    港股格式：hk00700，美股：usAAPL，A股：sh600519 / sz300750
    """
    try:
        # 适配新浪代码格式
        if ".HK" in stock_code:
            sina_code = f"hk{stock_code.replace('.HK', '').zfill(5)}"  # 0700.HK → hk00700
        elif ".SS" in stock_code:
            sina_code = f"sh{stock_code.replace('.SS', '')}"
        elif ".SZ" in stock_code:
            sina_code = f"sz{stock_code.replace('.SZ', '')}"
        else:
            sina_code = f"us{stock_code}"  # 美股
        
        # 新浪财经日线接口（公开免费）
        url = f"https://quotes.sina.cn/cgi-bin/jsonp/q.php?type=history&symbol={sina_code}&start=2024-01-01&end={datetime.now().strftime('%Y-%m-%d')}"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        
        # 解析JSONP数据
        text = response.text.strip().strip('()')
        data = json.loads(text)
        if not data:
            return None
        
        # 转换为DataFrame
        df = pd.DataFrame(data)
        df["datetime"] = pd.to_datetime(df["d"])
        df.rename(columns={
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume"
        }, inplace=True)
        df = df[["datetime", "high", "low", "close", "volume"]].drop_duplicates()
        df = df.fillna(method="ffill").fillna(method="bfill")
        
        # 只保留最近days天
        return df.tail(days)
    except Exception as e:
        st.warning(f"新浪抓取{stock_code}失败：{str(e)[:30]}")
        return None

# ===================== yfinance 兜底 =====================
def get_yfinance_data(stock_code, days=180):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 20)
        df = yf.download(
            stock_code,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1d",
            progress=False
        )
        if len(df) < days * 0.8:
            return None
        df = df.reset_index()
        df.rename(columns={
            "Date": "datetime",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        }, inplace=True)
        return df.tail(days)
    except Exception as e:
        st.warning(f"Yahoo抓取{stock_code}失败：{str(e)[:30]}")
        return None

# ===================== 统一数据入口 =====================
def get_stock_data(stock_code, days=180):
    # 优先新浪，失败用yfinance兜底
    df = get_sina_data(stock_code, days)
    if df is not None and len(df) >= days * 0.8:
        return df
    df = get_yfinance_data(stock_code, days)
    if df is not None and len(df) >= days * 0.8:
        return df
    st.error(f"{stock_code} 所有数据源抓取失败，跳过")
    return None

# ===================== Wyckoff+VCP 核心逻辑（不变）=====================
def calculate_atr(df, period=14):
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
    df['atr'] = df['tr'].rolling(window=period).mean()
    return df

def check_wyckoff_spring(df):
    if len(df) < 30:
        return False, 0, 0
    df['support_30d'] = df['low'].rolling(window=30).min()
    recent_data = df.iloc[-20:]
    for idx, row in recent_data.iterrows():
        if row['low'] <= row['support_30d'] * 1.05 and row['close'] > row['support_30d']:
            bounce_rate = (row['close'] - row['low']) / row['low'] * 100
            vol_ratio = row['volume'] / df['volume'].mean() if df['volume'].mean() > 0 else 0
            score = bounce_rate * 0.7 + vol_ratio * 0.3
            return True, row['support_30d'], round(score, 2)
    return False, 0, 0

def check_vcp_contraction(df):
    if len(df) < 60:
        return False, 0, 0
    df = calculate_atr(df)
    stage1_atr = df['atr'].iloc[-60:-40].mean()
    stage2_atr = df['atr'].iloc[-40:-20].mean()
    stage3_atr = df['atr'].iloc[-20:].mean()
    contraction_count = 0
    if stage2_atr < stage1_atr * 0.9:
        contraction_count += 1
    if stage3_atr < stage2_atr * 0.9:
        contraction_count += 1
    stage1_range = df['high'].iloc[-60:-40].max() - df['low'].iloc[-60:-40].min()
    stage3_range = df['high'].iloc[-20:].max() - df['low'].iloc[-20:].min()
    if stage3_range < stage1_range * 0.7:
        contraction_count += 1
    if contraction_count >= 2:
        score = (1 - stage3_atr/stage1_atr) * 100
        return True, contraction_count, round(score, 2)
    return False, 0, 0

def analyze_stock(stock_code, days=180):
    df = get_stock_data(stock_code, days)
    if df is None:
        return None
    current_price = df['close'].iloc[-1]
    wyck_spring, wyck_support, wyck_score = check_wyckoff_spring(df)
    vcp_contraction, vcp_count, vcp_score = check_vcp_contraction(df)
    if wyck_spring and vcp_contraction:
        stage = "✅ 吸筹末期+VCP收缩，临近突破"
    elif wyck_spring:
        stage = "⚠️ 仅Wyckoff弹簧，无VCP收缩"
    elif vcp_contraction:
        stage = "⚠️ 仅VCP收缩，无Wyckoff弹簧"
    else:
        stage = "❌ 无核心形态"
    support = round(wyck_support, 2) if wyck_support > 0 else current_price * 0.95
    resistance = df['high'].iloc[-20:].max()
    return {
        "股票代码": stock_code,
        "最新价": round(current_price, 2),
        "Wyckoff弹簧": wyck_spring,
        "VCP收缩": vcp_contraction,
        "形态阶段": stage,
        "核心支撑": round(support, 2),
        "核心压力": round(resistance, 2),
        "稳健进场位": round(support * 1.02, 2),
        "止损位": round(support * 0.98, 2),
        "第一目标位": round(current_price * 1.08, 2),
        "第二目标位": round(current_price * 1.15, 2)
    }

# ===================== Streamlit 界面 =====================
def main():
    st.title("🚀 Wyckoff+VCP 选股器（新浪财经 + Yahoo 双源兜底）")
    st.markdown("### 数据来源：新浪财经（优先）+ Yahoo Finance（兜底），延迟15-30分钟")
    with st.sidebar:
        st.header("⚙️ 筛选配置")
        market = st.selectbox("选择市场", ["港股", "美股", "A股"])
        days = st.slider("回看天数（日线）", 90, 180, 180)
        if market == "港股":
            stock_list = st.text_area("标的列表（每行一个）", 
                value="0700.HK\n01810.HK\n9988.HK\n3690.HK\n0005.HK")
        elif market == "美股":
            stock_list = st.text_area("标的列表（每行一个）", 
                value="AAPL\nMSFT\nNVDA\nTSLA\nMETA")
        else:
            stock_list = st.text_area("标的列表（每行一个）", 
                value="600519.SS\n300750.SZ\n002594.SZ")
        run_btn = st.button("开始筛选", type="primary")
    if run_btn:
        stock_codes = [s.strip() for s in stock_list.split("\n") if s.strip()]
        if not stock_codes:
            st.error("请输入至少一只股票代码！")
            return
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        for idx, stock in enumerate(stock_codes):
            status_text.text(f"正在分析 {stock} ({idx+1}/{len(stock_codes)})")
            progress_bar.progress((idx+1)/len(stock_codes))
            analysis = analyze_stock(stock, days)
            if analysis and (analysis['Wyckoff弹簧'] or analysis['VCP收缩']):
                results.append(analysis)
            time.sleep(0.3)
        if not results:
            st.info("📊 暂无符合Wyckoff+VCP形态的标的")
        else:
            st.success(f"🎉 共筛选出 {len(results)} 只符合条件的标的")
            df_result = pd.DataFrame(results)
            st.dataframe(df_result, use_container_width=True)
            csv_data = df_result.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📁 导出筛选结果（CSV）",
                data=csv_data,
                file_name=f"Wyckoff_VCP_{market}_{days}天.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
