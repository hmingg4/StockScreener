import streamlit as st
import requests
import json
import time
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings  # 这里补上缺失的导入
warnings.filterwarnings("ignore")

# ===================== 全局配置 =====================
st.set_page_config(page_title="Wyckoff+VCP选股器", layout="wide")
# 阿斯达克请求头（防反爬）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.aastocks.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

# ===================== 多源数据抓取核心模块 =====================
def get_yfinance_data(stock_code, days=180):
    """优先从Yahoo Finance抓取日线数据"""
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
        
        # 数据清洗+标准化
        df = df.reset_index()
        df.rename(columns={
            "Date": "datetime",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        }, inplace=True)
        df = df[["datetime", "high", "low", "close", "volume"]].drop_duplicates()
        df = df.fillna(method="ffill").fillna(method="bfill")
        
        if len(df) >= days * 0.8:
            return df.tail(days)
        else:
            return None
    except Exception as e:
        st.warning(f"Yahoo抓取{stock_code}失败：{str(e)[:30]}")
        return None

def get_aastocks_data(stock_code, days=180):
    """备用：阿斯达克抓取港股/美股日线（延迟15-30分钟）"""
    try:
        if ".HK" in stock_code:
            aastock_code = f"0{stock_code.replace('.HK', '')}"
            market = "hk"
        else:
            aastock_code = stock_code
            market = "us"
        
        url = f"https://www.aastocks.com/tc/resources/data/getchartdata.aspx?symbol={aastock_code}&resolution=D&count={days}&period=1"
        time.sleep(0.5)
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = json.loads(response.text)
        if "data" not in data or len(data["data"]) == 0:
            return None
        
        df = pd.DataFrame(data["data"])
        df["datetime"] = pd.to_datetime(df["t"], unit="s")
        df.rename(columns={
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume"
        }, inplace=True)
        df = df[["datetime", "high", "low", "close", "volume"]].drop_duplicates()
        df = df.fillna(method="ffill").fillna(method="bfill")
        
        return df
    except Exception as e:
        st.warning(f"阿斯达克抓取{stock_code}失败：{str(e)[:30]}")
        return None

def get_stock_data(stock_code, days=180):
    """统一数据入口：Yahoo失败则用阿斯达克"""
    df = get_yfinance_data(stock_code, days)
    if df is not None and len(df) >= days * 0.8:
        return df
    df = get_aastocks_data(stock_code, days)
    if df is not None and len(df) >= days * 0.8:
        return df
    st.error(f"{stock_code} 所有数据源抓取失败，跳过")
    return None

# ===================== Wyckoff+VCP 核心筛选逻辑 =====================
def calculate_atr(df, period=14):
    """计算ATR（VCP核心指标）"""
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
    df['atr'] = df['tr'].rolling(window=period).mean()
    return df

def check_wyckoff_spring(df):
    """识别Wyckoff弹簧效应"""
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
    """识别VCP波动收缩"""
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
    """单只股票完整分析"""
    df = get_stock_data(stock_code, days)
    if df is None:
        return None
    
    current_price = df['close'].iloc[-1]
    wyck_spring, wyck_support, wyck_score = check_wyckoff_spring(df)
    vcp_contraction, vcp_count, vcp_score = check_vcp_contraction(df)
    
    # 阶段定位
    if wyck_spring and vcp_contraction:
        stage = "✅ 吸筹末期+VCP收缩，临近突破"
    elif wyck_spring:
        stage = "⚠️ 仅Wyckoff弹簧，无VCP收缩"
    elif vcp_contraction:
        stage = "⚠️ 仅VCP收缩，无Wyckoff弹簧"
    else:
        stage = "❌ 无核心形态"
    
    # 交易点位
    support = round(wyck_support, 2) if wyck_support > 0 else current_price * 0.95
    resistance = df['high'].iloc[-20:].max()
    
    result = {
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
    return result

# ===================== Streamlit网页交互 =====================
def main():
    st.title("🚀 Wyckoff+VCP 多源数据选股器（港/美/A股）")
    st.markdown("### 数据来源：Yahoo Finance + 阿斯达克（延迟15-30分钟，不影响日线分析）")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 筛选配置")
        market = st.selectbox("选择市场", ["港股", "美股", "A股"])
        days = st.slider("回看天数（日线）", 90, 180, 180)
        # 标的池（可直接修改）
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
    
    # 执行筛选
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
        
        # 显示结果
        if not results:
            st.info("📊 暂无符合Wyckoff+VCP形态的标的")
        else:
            st.success(f"🎉 共筛选出 {len(results)} 只符合条件的标的")
            # 表格展示
            df_result = pd.DataFrame(results)
            st.dataframe(df_result, use_container_width=True)
            # 导出Excel
            csv_data = df_result.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📁 导出筛选结果（CSV）",
                data=csv_data,
                file_name=f"Wyckoff_VCP_{market}_{days}天.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
