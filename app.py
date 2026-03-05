import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ------------------------------
# 全局配置
# ------------------------------
st.set_page_config(page_title="港美A Wyckoff+VCP 宽周期选股器", layout="wide")
st.title("🚀 港美A三市场 Wyckoff + VCP 宽周期选股器")
st.markdown("**核心优化**：回看3个月-半年内的形态 | 先图形筛选，成交量仅做加分项 | 近期信号标红置顶")

# ------------------------------
# 三市场全量股票池（多层兜底）
# ------------------------------
@st.cache_data(ttl=86400)  # 缓存1天，加快筛选速度
def get_full_stock_pool(market):
    """
    三市场全量标的池，覆盖绝大多数活跃个股
    market: A股/港股/美股
    """
    # ========== A股：沪深全市场（主板+创业板+科创板）==========
    if market == "A股":
        sh_prefix = ["600", "601", "603", "688"]  # 上交所
        sz_prefix = ["000", "001", "002", "300", "301"]  # 深交所
        pool = []
        
        # 生成标的代码
        for prefix in sh_prefix:
            for i in range(1, 1000):
                pool.append(f"{prefix}{i:03d}.SS")
        for prefix in sz_prefix:
            for i in range(1, 1000):
                pool.append(f"{prefix}{i:03d}.SZ")
        
        # 核心权重股兜底
        core_a_stocks = [
            "600519.SS", "601318.SS", "601899.SS", "601398.SS", "601988.SS",
            "600036.SS", "600276.SS", "600887.SS", "600030.SS", "601628.SS",
            "300750.SZ", "002594.SZ", "000858.SZ", "000568.SZ", "000333.SZ",
            "002415.SZ", "002475.SZ", "300059.SZ", "300124.SZ", "300760.SZ",
            "600000.SS", "600016.SS", "600019.SS", "600028.SS", "600048.SS",
            "000001.SZ", "000002.SZ", "000063.SZ", "000069.SZ", "000100.SZ"
        ]
        pool += core_a_stocks
        return list(set(pool))

    # ========== 港股：全市场主板标的 ==========
    elif market == "港股":
        pool = []
        # 港股主板代码全量生成
        for i in range(1, 10000):
            pool.append(f"{i:04d}.HK")
        # 核心权重股兜底
        core_hk_stocks = [
            "0700.HK", "9988.HK", "3690.HK", "0005.HK", "0941.HK", "1810.HK",
            "0016.HK", "0001.HK", "0857.HK", "0388.HK", "1211.HK", "2318.HK",
            "1024.HK", "9618.HK", "9888.HK", "2015.HK", "0066.HK", "0175.HK",
            "0267.HK", "0288.HK", "0332.HK", "0386.HK", "0688.HK", "0762.HK",
            "0823.HK", "0836.HK", "0868.HK", "0914.HK", "0960.HK", "0981.HK"
        ]
        pool += core_hk_stocks
        return list(set(pool))

    # ========== 美股：全市场核心标的 ==========
    else:
        core_us_stocks = [
            "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","JPM","V","MA","PG","WMT","JNJ",
            "UNH","HD","CVX","XOM","PFE","ABBV","MRK","ACN","CSCO","WFC","BAC","NFLX","ADBE",
            "CRM","INTC","TXN","AMD","QCOM","LRCX","AMAT","HON","IBM","MS","GS","BLK","SPGI",
            "PLD","C","ADP","ITW","MMM","GE","CAT","DE","LOW","TGT","COST","MCD","NKE","SBUX",
            "DIS","PYPL","VZ","KO","PEP","T","MO","CL","REGN","BDX","HUM","AMGN","SPG","EW",
            "SO","DUK","AEP","ALGN","ADI","ANSS","ASML","TEAM","ADSK","AZN","AVGO","BIDU","BIIB",
            "CDNS","CDW","CHTR","CHKP","CTAS","CTSH","CMCSA","CPRT","CRWD","DDOG","DXCM","FANG",
            "DLTR","DASH","EA","EXC","FAST","FTNT","JD","KDP","KLAC","KHC","LULU","MAR","MRVL",
            "MELI","MCHP","MRNA","MNST","NXPI","ORLY","ODFL","ON","PCAR","PANW","PAYX","PDD",
            "ROP","ROST","SIRI","SNPS","TTD","VRSK","VRTX","WBA","WBD","WDAY","XEL","ZM","ZS",
            "RIVN","LCID","SNAP","UBER","LYFT","PINS","DOCU","ROKU","SPOT","SQ","SHOP","TWLO",
            "OKTA","MDB","NET","CYBR","PLTR","F","GM","RCL","CCL","NCLH","MAR","HLT","MGM"
        ]
        # 扩展标的池
        for i in range(1, 5000):
            core_us_stocks.append(f"{i:04d}")
        return list(set(core_us_stocks))

# ------------------------------
# 技术指标计算（适配长周期）
# ------------------------------
def calculate_atr(data, period=14):
    """计算ATR（平均真实波幅，VCP核心指标，适配长周期）"""
    tr = np.maximum(
        data['High'] - data['Low'],
        abs(data['High'] - data['Close'].shift(1)),
        abs(data['Low'] - data['Close'].shift(1))
    )
    return tr.rolling(period).mean()

# ------------------------------
# 【核心优化】宽周期Wyckoff弹簧效应识别
# ------------------------------
def find_wyckoff_spring_in_window(data, max_lookback_days=180):
    """
    回看max_lookback_days天内的Wyckoff弹簧效应（核心买入形态）
    放宽阈值，优先抓核心形态：测试支撑位+快速收回
    返回：(是否找到, 出现的天数前, 形态强度得分)
    """
    if len(data) < max_lookback_days + 30:
        return (False, 9999, 0)
    
    # 适配长周期的支撑位计算（30天滚动最低值，更贴合半年周期）
    support_roll = data['Low'].rolling(30).min()
    valid_signals = []
    
    # 遍历回看周期内的每一天，找符合的形态
    for i in range(-max_lookback_days, 0):
        try:
            # 核心形态：价格测试前期支撑位 + 3天内快速收回（弹簧效应核心逻辑）
            test_low = data['Low'].iloc[i]
            support_level = support_roll.iloc[i-10]  # 测试前10天的支撑位
            close_after = data['Close'].iloc[i:i+5].max()  # 测试后5天内的收盘价高点
            
            # 大幅放宽阈值，只要符合核心形态就触发
            if test_low <= support_level * 1.05 and close_after > test_low:
                # 强度得分：越新得分越高，反弹幅度越大得分越高
                recency_score = (max_lookback_days + i)  # 越近数值越大，最高179
                bounce_score = (close_after - test_low) / test_low * 100  # 反弹幅度加分
                total_score = recency_score + bounce_score * 3
                valid_signals.append((True, abs(i), total_score))
        except:
            continue
    
    if valid_signals:
        # 返回最新、最强的信号
        return max(valid_signals, key=lambda x: x[2])
    return (False, 9999, 0)

# ------------------------------
# 【核心优化】宽周期VCP波动收缩识别
# ------------------------------
def find_vcp_contraction_in_window(data, max_lookback_days=180):
    """
    回看max_lookback_days天内的VCP波动收缩（核心前提形态）
    放宽阈值，优先抓核心形态：波动率持续收缩
    返回：(是否找到, 出现的天数前, 形态强度得分)
    """
    if len(data) < max_lookback_days + 30:
        return (False, 9999, 0)
    
    atr = calculate_atr(data, 14)
    valid_signals = []
    
    # 遍历回看周期内的每一天，找符合的收缩形态
    for i in range(-max_lookback_days, 0):
        try:
            # 核心形态：当前10天ATR 比 前期20天ATR 明显收缩（VCP核心逻辑）
            recent_atr = atr.iloc[i-10:i].mean()
            historical_atr = atr.iloc[i-30:i-10].mean()
            if historical_atr == 0:
                continue
            
            contraction_ratio = recent_atr / historical_atr
            # 放宽收缩阈值，只要波动率下降就触发
            if contraction_ratio < 0.92:
                # 强度得分：越新得分越高，收缩幅度越大得分越高
                recency_score = (max_lookback_days + i)
                contraction_score = (1 - contraction_ratio) * 60
                total_score = recency_score + contraction_score * 3
                valid_signals.append((True, abs(i), total_score))
        except:
            continue
    
    if valid_signals:
        return max(valid_signals, key=lambda x: x[2])
    return (False, 9999, 0)

# ------------------------------
# 成交量加分项（永远不做否决项，仅加分）
# ------------------------------
def get_volume_bonus_score(data):
    """成交量仅做加分，不做筛选门槛，适配长周期"""
    if len(data) < 20:
        return 0
    avg_vol = data['Volume'].iloc[-20:-5].mean()
    last_vol = data['Volume'].iloc[-1]
    # 放量加2分，缩量不扣分
    return 2.0 if last_vol > avg_vol * 1.2 else 0

# ------------------------------
# 主选股逻辑（宽周期适配）
# ------------------------------
def run_screener(market, min_price, lookback_days):
    # 1. 获取对应市场的全量标的池
    st.info(f"正在加载{market}全市场标的池...")
    symbols = get_full_stock_pool(market)
    st.success(f"成功加载{market}标的池，共{len(symbols)}只，开始宽周期形态筛选...")
    
    # 2. 拉取K线数据的时间范围（比回看周期多2个月，保证指标计算有足够数据）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + 60)
    results = []

    # 进度条
    progress_bar = st.progress(0)
    status_text = st.empty()
    max_scan_count = 3000  # 单次最多扫描3000只，避免超时

    # 3. 遍历标的筛选
    for idx, symbol in enumerate(symbols):
        if idx >= max_scan_count:
            break
        status_text.text(f"正在回看分析 {symbol} ({idx+1}/{min(len(symbols), max_scan_count)})")
        progress_bar.progress((idx+1) / min(len(symbols), max_scan_count))
        
        try:
            # 拉取日线数据
            df = yf.download(symbol, start=start_date, end=end_date, interval="1d", progress=False)
            if len(df) < lookback_days + 30:
                continue

            # 价格过滤（自动适配对应市场货币单位）
            latest_close = df['Close'].iloc[-1]
            if latest_close < min_price:
                continue

            # 核心：宽周期形态识别
            spring_found, spring_days_ago, spring_score = find_wyckoff_spring_in_window(df, lookback_days)
            vcp_found, vcp_days_ago, vcp_score = find_vcp_contraction_in_window(df, lookback_days)

            # 只要出现任意一个核心形态，就入选（零苛刻门槛）
            if spring_found or vcp_found:
                # 成交量加分
                vol_bonus = get_volume_bonus_score(df)
                # 综合得分
                total_score = spring_score + vcp_score + vol_bonus
                # 信号新鲜度
                days_ago = min(spring_days_ago, vcp_days_ago)
                # 信号分级
                is_recent = days_ago <= 7  # 一周内的信号标红
                is_medium = 7 < days_ago <= 30  # 一个月内的标橙

                # 信号描述
                signal_desc = []
                if spring_found:
                    signal_desc.append(f"Wyckoff弹簧效应({spring_days_ago}天前)")
                if vcp_found:
                    signal_desc.append(f"VCP波动收缩({vcp_days_ago}天前)")
                if vol_bonus > 0:
                    signal_desc.append("放量确认(+2分)")

                results.append({
                    "代码": symbol,
                    "最新价": round(latest_close, 2),
                    "综合得分": round(total_score, 1),
                    "几天前出现信号": days_ago,
                    "是否近期信号": is_recent,
                    "是否中期信号": is_medium,
                    "信号详情": " | ".join(signal_desc),
                    "K线数据": df
                })
        except:
            continue

    # 清理进度显示
    status_text.empty()
    progress_bar.empty()

    # 排序规则：近期信号置顶 → 中期信号 → 远期信号，同级别按综合得分从高到低
    results.sort(key=lambda x: (
        not x["是否近期信号"],
        not x["是否中期信号"],
        -x["综合得分"]
    ))
    return results

# ------------------------------
# 网页界面（新增回看天数可调）
# ------------------------------
with st.sidebar:
    st.header("⚙️ 筛选参数")
    market = st.selectbox("1. 选择市场", ["A股", "港股", "美股"], index=0)
    lookback_days = st.slider("2. 形态回看最大天数", 
                               min_value=90, max_value=180, value=180, step=30,
                               help="90天=3个月，180天=半年，数值越大，选出的标的越多")
    min_price = st.number_input("3. 最低股价", min_value=0.0, value=5.0, step=1.0,
                                help="A股对应人民币，港股对应港元，美股对应美元")
    run_button = st.button("🔍 开始宽周期筛选", type="primary")

# 执行筛选
if run_button:
    if not market:
        st.warning("请先选择市场！")
    else:
        st.subheader(f"📊 正在回看{market}过去{lookback_days}天的核心形态，请稍候...")
        st.markdown("⚠️ 全市场标的较多，筛选预计需要5-12分钟，请不要关闭页面")
        results = run_screener(market, min_price, lookback_days)
        
        if not results:
            st.info("暂无符合条件的标的，建议把最低价格调低至2-3元，或拉长回看天数再试")
        else:
            st.success(f"✅ 筛选完成！共找到 {len(results)} 只符合条件的标的（按信号新鲜度排序）")
            
            # 遍历输出结果
            for res in results:
                # 标题颜色分级
                if res["是否近期信号"]:
                    title_color = "red"
                    title_tag = "🔥 一周内新信号"
                elif res["是否中期信号"]:
                    title_color = "orange"
                    title_tag = "📌 一个月内信号"
                else:
                    title_color = "gray"
                    title_tag = "📅 半年内信号"
                
                with st.expander(f"{title_tag} | {res['代码']} | 最新价:{res['最新价']} | 综合得分:{title_color}[{res['综合得分']}]"):
                    st.markdown(f"**信号出现时间**：{res['几天前出现信号']} 天前")
                    st.markdown(f"**触发信号**：{res['信号详情']}")
                    
                    # 绘制K线图
                    df = res["K线数据"]
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(
                        x=df.index,
                        open=df["Open"],
                        high=df["High"],
                        low=df["Low"],
                        close=df["Close"],
                        name="K线"
                    ))
                    fig.update_layout(
                        title=f"{res['代码']} 日线走势",
                        xaxis_rangeslider_visible=False,
                        height=500
                    )
                    st.plotly_chart(fig, use_container_width=True)
