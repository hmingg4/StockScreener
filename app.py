import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ------------------------------
# 1. 扩展股票池（覆盖更多个股）
# ------------------------------
# 港股：扩展为恒生综合指数成分股（覆盖更全），后续会自动筛选≥5港元
HANG_SENG_EXTENDED = [
    "0700.HK", "9988.HK", "3690.HK", "0005.HK", "0941.HK", "1810.HK",
    "0016.HK", "0001.HK", "0857.HK", "0388.HK", "1211.HK", "2318.HK",
    "0027.HK", "1024.HK", "9618.HK", "9888.HK", "2015.HK", "0066.HK",
    "0175.HK", "0241.HK", "0267.HK", "0288.HK", "0332.HK", "0386.HK",
    "0688.HK", "0762.HK", "0823.HK", "0836.HK", "0868.HK", "0914.HK",
    "0960.HK", "0981.HK", "1038.HK", "1044.HK", "1088.HK", "1093.HK",
    "1109.HK", "1113.HK", "1177.HK", "1299.HK", "1398.HK", "1801.HK",
    "1818.HK", "1928.HK", "1929.HK", "2007.HK", "2020.HK", "2269.HK",
    "2313.HK", "2319.HK", "2331.HK", "2382.HK", "2601.HK", "2628.HK",
    "3328.HK", "3968.HK", "3988.HK", "6098.HK", "6862.HK", "9626.HK",
    "0012.HK", "0017.HK", "0027.HK", "0066.HK", "0101.HK", "0151.HK",
    "0175.HK", "0267.HK", "0288.HK", "0332.HK", "0386.HK", "0688.HK",
    "0762.HK", "0823.HK", "0836.HK", "0868.HK", "0914.HK", "0960.HK",
    "0981.HK", "1038.HK", "1044.HK", "1088.HK", "1093.HK", "1109.HK",
    "1113.HK", "1177.HK", "1299.HK", "1398.HK", "1801.HK", "1818.HK",
    "1928.HK", "1929.HK", "2007.HK", "2020.HK", "2269.HK", "2313.HK",
    "2319.HK", "2331.HK", "2382.HK", "2601.HK", "2628.HK", "3328.HK",
    "3968.HK", "3988.HK", "6098.HK", "6862.HK", "9626.HK", "9866.HK",
    "9898.HK", "9999.HK", "2013.HK", "2015.HK", "2020.HK", "2057.HK",
    "2158.HK", "2238.HK", "2269.HK", "2313.HK", "2319.HK", "2331.HK",
    "2382.HK", "2518.HK", "2601.HK", "2628.HK", "3328.HK", "3690.HK",
    "3968.HK", "3988.HK", "6098.HK", "6862.HK", "9618.HK", "9626.HK",
    "9866.HK", "9888.HK", "9898.HK", "9988.HK", "9999.HK"
]

# 美股：标普500+纳指100，后续会自动筛选≥5美元
SP500_PLUS_NASDAQ = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "BRK-B", "UNH", "JNJ", "JPM", "V", "WMT", "PG", "MA", "HD",
    "DIS", "NFLX", "PYPL", "BAC", "ADBE", "CRM", "INTC", "VZ",
    "KO", "PEP", "NKE", "MRK", "T", "PFE", "ABBV", "ABT", "CVX",
    "XOM", "COST", "MCD", "WFC", "CSCO", "ACN", "DHR", "TXN",
    "NEE", "LIN", "AMD", "HON", "QCOM", "LOW", "SPGI", "IBM",
    "GS", "CAT", "BLK", "RTX", "INTU", "AMAT", "GE", "NOW",
    "DE", "MS", "BKNG", "SCHW", "PLD", "AXP", "TMO", "LRCX",
    "ISRG", "EL", "MU", "ADP", "ZTS", "C", "MDLZ", "GILD",
    "CI", "SYK", "TMUS", "TJX", "MMM", "CB", "MO", "CL",
    "REGN", "BDX", "HUM", "AMGN", "SPG", "EW", "SO", "DUK",
    # 纳指100新增
    "AEP", "ALGN", "AMGN", "ADI", "ANSS", "AAPL", "AMAT", "ASML",
    "TEAM", "ADSK", "ADP", "AZN", "AVGO", "BIDU", "BIIB", "BMRN",
    "BKNG", "CDNS", "CDW", "CHTR", "CHKP", "CTAS", "CSCO", "CTSH",
    "CMCSA", "CEG", "CPRT", "CSGP", "COST", "CRWD", "DDOG", "DXCM",
    "FANG", "DLTR", "DASH", "EA", "EXC", "FAST", "GFS", "META",
    "FI", "FTNT", "GILD", "GOOG", "GOOGL", "HON", "ILMN", "INTC",
    "INTU", "ISRG", "JD", "KDP", "KLAC", "KHC", "LRCX", "LULU",
    "MAR", "MRVL", "MELI", "MCHP", "MU", "MSFT", "MRNA", "MDLZ",
    "MNST", "NFLX", "NVDA", "NXPI", "ORLY", "ODFL", "ON", "PCAR",
    "PANW", "PAYX", "PYPL", "PDD", "PEP", "QCOM", "REGN", "ROP",
    "ROST", "SIRI", "SBUX", "SNPS", "TSLA", "TXN", "TTD", "VRSK",
    "VRTX", "WBA", "WBD", "WDAY", "XEL", "ZM", "ZS"
]

# ------------------------------
# 2. 核心技术指标（不用改）
# ------------------------------
def calculate_atr(data, period=14):
    high = data['High']
    low = data['Low']
    close = data['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_rs(data, market_data, period=20):
    stock_return = data['Close'].pct_change(period).iloc[-1]
    market_return = market_data['Close'].pct_change(period).iloc[-1]
    return stock_return - market_return

def find_zigzag(data, deviation=0.05):
    zigzag = [np.nan] * len(data)
    last_pivot = 0
    for i in range(1, len(data)-1):
        if data['High'].iloc[i] > data['High'].iloc[i-1] * (1+deviation) and \
           data['High'].iloc[i] > data['High'].iloc[i+1] * (1+deviation):
            if last_pivot == 0 or data['High'].iloc[i] > data['High'].iloc[last_pivot]:
                zigzag[i] = data['High'].iloc[i]
                last_pivot = i
        elif data['Low'].iloc[i] < data['Low'].iloc[i-1] * (1-deviation) and \
             data['Low'].iloc[i] < data['Low'].iloc[i+1] * (1-deviation):
            if last_pivot == 0 or data['Low'].iloc[i] < data['Low'].iloc[last_pivot]:
                zigzag[i] = data['Low'].iloc[i]
                last_pivot = i
    return zigzag

# ------------------------------
# 3. 增强版 Wyckoff 策略（不用改）
# ------------------------------
def wyckoff_spring(data):
    if len(data) < 30: return False
    recent_lows = data['Low'].iloc[-20:].min()
    support = recent_lows * 1.01
    test_day = data.iloc[-3]
    bounce_day = data.iloc[-2]
    confirm_day = data.iloc[-1]
    avg_vol = data['Volume'].iloc[-8:-3].mean()
    is_vol_shrink = test_day['Volume'] < avg_vol * 0.8
    is_test_support = test_day['Low'] <= support
    is_bounce = bounce_day['Close'] > bounce_day['Open']
    is_confirm = confirm_day['Close'] > test_day['Close']
    return is_test_support and is_vol_shrink and is_bounce and is_confirm

def wyckoff_secondary_test(data):
    if len(data) < 40: return False
    spring_days = []
    for i in range(-30, -10):
        if data['Low'].iloc[i] <= data['Low'].iloc[i-5:i+5].min() * 1.01:
            spring_days.append(i)
    if len(spring_days) < 2: return False
    last_spring = spring_days[-1]
    test_vol = data['Volume'].iloc[last_spring]
    prev_spring_vol = data['Volume'].iloc[spring_days[-2]]
    return test_vol < prev_spring_vol * 0.85 and data['Close'].iloc[-1] > data['Close'].iloc[last_spring]

def wyckoff_upthrust(data):
    if len(data) < 30: return False
    recent_highs = data['High'].iloc[-20:].max()
    resistance = recent_highs * 0.99
    test_day = data.iloc[-3]
    drop_day = data.iloc[-2]
    confirm_day = data.iloc[-1]
    avg_vol = data['Volume'].iloc[-8:-3].mean()
    is_vol_spike = test_day['Volume'] > avg_vol * 1.5
    is_test_resistance = test_day['High'] >= resistance
    is_drop = drop_day['Close'] < drop_day['Open']
    is_confirm = confirm_day['Close'] < test_day['Close']
    return is_test_resistance and is_vol_spike and is_drop and is_confirm

# ------------------------------
# 4. 增强版 VCP 策略（不用改）
# ------------------------------
def vcp_volatility_contraction(data):
    if len(data) < 40: return False
    atr = calculate_atr(data)
    current_atr = atr.iloc[-14:].mean()
    historical_atr = atr.iloc[-30:-14].mean()
    return current_atr < historical_atr * 0.7

def vcp_multiple_contractions(data):
    if len(data) < 60: return False
    zigzag = find_zigzag(data, deviation=0.03)
    pivots = data[~pd.isna(zigzag)]
    if len(pivots) < 4: return False
    highs = pivots[pivots['High'] == pivots['zigzag']]['High']
    lows = pivots[pivots['Low'] == pivots['zigzag']]['Low']
    if len(highs) < 2 or len(lows) < 2: return False
    is_highs_lower = highs.iloc[-1] < highs.iloc[-2]
    is_lows_higher = lows.iloc[-1] > lows.iloc[-2]
    return is_highs_lower and is_lows_higher

def vcp_breakout_volume(data):
    if len(data) < 20: return False
    recent_high = data['High'].iloc[-10:-1].max()
    breakout = data['Close'].iloc[-1] >= recent_high
    avg_vol = data['Volume'].iloc[-6:-1].mean()
    vol_spike = data['Volume'].iloc[-1] > avg_vol * 1.5
    return breakout and vol_spike

def vcp_relative_strength(data, market_data):
    rs = calculate_rs(data, market_data)
    return rs > 0

# ------------------------------
# 5. 主选股逻辑（已添加价格筛选）
# ------------------------------
def run_screener(market, interval, lookback_days, strategies, min_price):
    if market == "港股":
        symbols = HANG_SENG_EXTENDED
        market_ticker = "^HSI"
    else:
        symbols = SP500_PLUS_NASDAQ
        market_ticker = "^GSPC"
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    
    market_data = yf.download(market_ticker, start=start_date, end=end_date, interval=interval)
    results = []
    
    progress_bar = st.progress(0)
    for idx, symbol in enumerate(symbols):
        try:
            data = yf.download(symbol, start=start_date, end=end_date, interval=interval)
            if len(data) < 30: continue
            
            # 【新增】价格筛选：只看≥min_price的股票
            current_price = data['Close'].iloc[-1]
            if current_price < min_price: continue
            
            data['zigzag'] = find_zigzag(data)
            signals = {}
            
            if "Wyckoff" in strategies:
                signals['弹簧效应'] = wyckoff_spring(data)
                signals['二次测试'] = wyckoff_secondary_test(data)
                signals['上冲下洗'] = wyckoff_upthrust(data)
            
            if "VCP" in strategies:
                signals['波动率收缩'] = vcp_volatility_contraction(data)
                signals['多次收缩'] = vcp_multiple_contractions(data)
                signals['突破放量'] = vcp_breakout_volume(data)
                signals['相对强势'] = vcp_relative_strength(data, market_data)
            
            total_signals = sum(signals.values())
            if total_signals >= 2:
                results.append({
                    "代码": symbol,
                    "最新价": round(current_price, 2),
                    "信号数": total_signals,
                    "具体信号": ", ".join([k for k, v in signals.items() if v]),
                    "数据": data
                })
        except:
            continue
        
        progress_bar.progress((idx + 1) / len(symbols))
    
    return sorted(results, key=lambda x: x['信号数'], reverse=True)

# ------------------------------
# 6. 超简单网页界面
# ------------------------------
st.set_page_config(page_title="Wyckoff+VCP 选股器", layout="wide")
st.title("🚀 Wyckoff + VCP 选股器")
st.markdown("左侧选参数，点「开始筛选」即可，不用懂编程")

# 侧边栏参数（更简单）
with st.sidebar:
    st.header("⚙️ 筛选参数")
    market = st.selectbox("1. 选市场", ["港股", "美股"], index=0)
    interval = st.selectbox("2. 选时间维度", ["1d", "1wk", "1h", "4h"], index=0)
    lookback_days = st.slider("3. 选回看天数", 30, 120, 60)
    min_price = st.number_input("4. 最低股价（港元/美元）", min_value=0.0, value=5.0, step=1.0)
    strategies = st.multiselect("5. 选策略（默认全选）", ["Wyckoff", "VCP"], default=["Wyckoff", "VCP"])
    run_button = st.button("🔍 开始筛选", type="primary")

# 主界面
if run_button:
    if not strategies:
        st.warning("请至少选一个策略！")
    else:
        st.subheader("📊 正在筛选，请稍候（约1-3分钟）...")
        results = run_screener(market, interval, lookback_days, strategies, min_price)
        
        if not results:
            st.info("暂无符合条件的个股，建议调整参数或稍后再试")
        else:
            st.subheader(f"✅ 找到 {len(results)} 只符合条件的个股（按信号数排序）")
            for res in results:
                with st.expander(f"📈 {res['代码']} - 信号数：{res['信号数']} - 最新价：{res['最新价']}"):
                    st.markdown(f"**具体信号**：{res['具体信号']}")
                    
                    # 画K线+成交量图
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(
                        x=res['数据'].index,
                        open=res['数据']['Open'],
                        high=res['数据']['High'],
                        low=res['数据']['Low'],
                        close=res['数据']['Close'],
                        name="K线"
                    ))
                    fig.add_trace(go.Bar(
                        x=res['数据'].index,
                        y=res['数据']['Volume'],
                        name="成交量",
                        yaxis="y2",
                        marker_color="rgba(0,0,255,0.3)"
                    ))
                    fig.update_layout(
                        title=f"{res['代码']} 价格与成交量",
                        yaxis_title="价格",
                        yaxis2=dict(title="成交量", overlaying="y", side="right"),
                        xaxis_rangeslider_visible=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
