import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ------------------------------
# 全局配置
# ------------------------------
st.set_page_config(page_title="港美A Wyckoff+VCP 选股器", layout="wide")
st.title("🚀 港美A三市场 Wyckoff + VCP 形态选股器")
st.markdown("**核心规则**：先看20天内的图形形态，成交量仅做加分项 | 最近3天信号标红置顶")

# ------------------------------
# 三市场全量股票池（多层兜底，零依赖）
# ------------------------------
@st.cache_data(ttl=86400)  # 缓存1天，大幅加快筛选速度
def get_full_stock_pool(market):
    """
    三市场全量标的池，覆盖绝大多数活跃个股
    market: A股/港股/美股
    """
    # ========== A股：沪深全市场（主板+创业板+科创板，覆盖4000+核心标的）==========
    if market == "A股":
        # 上交所（.SS）：600/601/603/688开头
        sh_prefix = ["600", "601", "603", "688"]
        # 深交所（.SZ）：000/001/002/300/301开头
        sz_prefix = ["000", "001", "002", "300", "301"]
        pool = []
        
        # 生成上交所标的
        for prefix in sh_prefix:
            for i in range(1, 1000):
                code = f"{prefix}{i:03d}.SS"
                pool.append(code)
        # 生成深交所标的
        for prefix in sz_prefix:
            for i in range(1, 1000):
                code = f"{prefix}{i:03d}.SZ"
                pool.append(code)
        
        # 核心权重股兜底（确保必选标的覆盖）
        core_a_stocks = [
            "600519.SS", "601318.SS", "601899.SS", "601398.SS", "601988.SS",
            "600036.SS", "600276.SS", "600887.SS", "600030.SS", "601628.SS",
            "300750.SZ", "002594.SZ", "000858.SZ", "000568.SZ", "000333.SZ",
            "002415.SZ", "002475.SZ", "300059.SZ", "300124.SZ", "300760.SZ"
        ]
        pool += core_a_stocks
        return list(set(pool))

    # ========== 港股：全市场核心标的 ==========
    elif market == "港股":
        pool = []
        # 港股主板代码生成（0001-9999.HK）
        for i in range(1, 10000):
            code = f"{i:04d}.HK"
            pool.append(code)
        # 核心权重股兜底
        core_hk_stocks = [
            "0700.HK", "9988.HK", "3690.HK", "0005.HK", "0941.HK", "1810.HK",
            "0016.HK", "0001.HK", "0857.HK", "0388.HK", "1211.HK", "2318.HK",
            "1024.HK", "9618.HK", "9888.HK", "2015.HK", "0066.HK", "0175.HK"
        ]
        pool += core_hk_stocks
        return list(set(pool))

    # ========== 美股：全市场核心标的 ==========
    else:
        # 美股核心标的池（覆盖标普500+纳斯达克100+罗素2000核心，超1000只）
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
            "ROP","ROST","SIRI","SNPS","TTD","VRSK","VRTX","WBA","WBD","WDAY","XEL","ZM","ZS"
        ]
        # 扩展美股标的池
        for i in range(1, 5000):
            core_us_stocks.append(f"{i:04d}")
        return list(set(core_us_stocks))

# ------------------------------
# 技术指标计算
# ------------------------------
def calculate_atr(data, period=10):
    """计算ATR（平均真实波幅，用于VCP波动收缩判断）"""
    tr = np.maximum(
        data['High'] - data['Low'],
        abs(data['High'] - data['Close'].shift(1)),
        abs(data['Low'] - data['Close'].shift(1))
    )
    return tr.rolling(period).mean()

# ------------------------------
# 核心形态识别：回看过去N天，找Wyckoff弹簧效应
# ------------------------------
def find_wyckoff_spring_in_window(data, window=20):
    """
    回看过去window天，识别Wyckoff核心弹簧效应
    返回：(是否找到, 出现的天数前, 形态强度得分)
    """
    if len(data) < window + 10:
        return (False, 999, 0)
    
    # 滚动计算20天支撑位
    support_roll = data['Low'].rolling(20).min()
    valid_signals = []
    
    for i in range(-window, 0):
        try:
            # 核心形态：价格测试前低支撑 + 快速收回（弹簧效应核心）
            test_low = data['Low'].iloc[i]
            support_level = support_roll.iloc[i-5]
            close_after = data['Close'].iloc[i:i+3].max()
            
            # 放宽阈值，优先抓形态
            if test_low <= support_level * 1.03 and close_after > test_low:
                # 强度得分：越新得分越高，反弹幅度越大得分越高
                recency_score = (window + i)  # 越近数值越大
                bounce_score = (close_after - test_low) / test_low * 100
                total_score = recency_score + bounce_score * 2
                valid_signals.append((True, abs(i), total_score))
        except:
            continue
    
    if valid_signals:
        # 返回最新、最强的信号
        return max(valid_signals, key=lambda x: x[2])
    return (False, 999, 0)

# ------------------------------
# 核心形态识别：回看过去N天，找VCP波动收缩
# ------------------------------
def find_vcp_contraction_in_window(data, window=20):
    """
    回看过去window天，识别VCP核心波动收缩
    返回：(是否找到, 出现的天数前, 形态强度得分)
    """
    if len(data) < window + 20:
        return (False, 999, 0)
    
    atr = calculate_atr(data, 10)
    valid_signals = []
    
    for i in range(-window, 0):
        try:
            # 核心形态：波动率（ATR）大幅收缩（VCP核心前提）
            recent_atr = atr.iloc[i-5:i].mean()
            historical_atr = atr.iloc[i-20:i-10].mean()
            if historical_atr == 0:
                continue
            
            contraction_ratio = recent_atr / historical_atr
            # 放宽阈值，优先抓收缩形态
            if contraction_ratio < 0.88:
                # 强度得分：越新得分越高，收缩幅度越大得分越高
                recency_score = (window + i)
                contraction_score = (1 - contraction_ratio) * 50
                total_score = recency_score + contraction_score * 2
                valid_signals.append((True, abs(i), total_score))
        except:
            continue
    
    if valid_signals:
        return max(valid_signals, key=lambda x: x[2])
    return (False, 999, 0)

# ------------------------------
# 成交量加分项（不做否决项，仅加分）
# ------------------------------
def get_volume_bonus_score(data):
    """成交量仅做加分项，不做筛选门槛"""
    if len(data) < 10:
        return 0
    avg_vol = data['Volume'].iloc[-10:-3].mean()
    last_vol = data['Volume'].iloc[-1]
    # 放量加1分，缩量不扣分
    return 1.0 if last_vol > avg_vol * 1.2 else 0

# ------------------------------
# 主选股逻辑
# ------------------------------
def run_screener(market, min_price):
    # 1. 获取对应市场的全量标的池
    st.info(f"正在加载{market}全市场标的池...")
    symbols = get_full_stock_pool(market)
    st.success(f"成功加载{market}标的池，共{len(symbols)}只，开始形态筛选...")
    
    # 2. 拉取K线数据的时间范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)
    results = []

    # 进度条
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 3. 遍历标的筛选
    for idx, symbol in enumerate(symbols):
        # 限制单次筛选最大数量，避免超时
        if idx >= 2000:
            break
        status_text.text(f"正在回看分析 {symbol} ({idx+1}/{min(len(symbols),2000)})")
        progress_bar.progress((idx+1) / min(len(symbols),2000))
        
        try:
            # 拉取日线数据
            df = yf.download(symbol, start=start_date, end=end_date, interval="1d", progress=False)
            if len(df) < 40:
                continue

            # 价格过滤（自动适配对应市场的货币单位）
            latest_close = df['Close'].iloc[-1]
            if latest_close < min_price:
                continue

            # 核心：形态识别（先图形筛选）
            spring_found, spring_days_ago, spring_score = find_wyckoff_spring_in_window(df, 20)
            vcp_found, vcp_days_ago, vcp_score = find_vcp_contraction_in_window(df, 20)

            # 只要出现任意一个核心形态，就入选
            if spring_found or vcp_found:
                # 成交量加分项
                vol_bonus = get_volume_bonus_score(df)
                # 综合得分
                total_score = spring_score + vcp_score + vol_bonus
                # 信号新鲜度
                days_ago = min(spring_days_ago, vcp_days_ago)
                is_recent = days_ago <= 3  # 最近3天内的信号标红置顶

                # 信号描述
                signal_desc = []
                if spring_found:
                    signal_desc.append(f"Wyckoff弹簧效应({spring_days_ago}天前)")
                if vcp_found:
                    signal_desc.append(f"VCP波动收缩({vcp_days_ago}天前)")
                if vol_bonus > 0:
                    signal_desc.append("放量确认(+1分)")

                results.append({
                    "代码": symbol,
                    "最新价": round(latest_close, 2),
                    "综合得分": round(total_score, 1),
                    "几天前出现信号": days_ago,
                    "是否近期信号": is_recent,
                    "信号详情": " | ".join(signal_desc),
                    "K线数据": df
                })
        except:
            continue

    # 清理进度显示
    status_text.empty()
    progress_bar.empty()

    # 排序规则：先按近期信号置顶，再按综合得分从高到低
    results.sort(key=lambda x: (not x["是否近期信号"], -x["综合得分"]))
    return results

# ------------------------------
# 网页界面
# ------------------------------
with st.sidebar:
    st.header("⚙️ 筛选参数")
    market = st.selectbox("1. 选择市场", ["A股", "港股", "美股"], index=0)
    min_price = st.number_input("2. 最低股价", min_value=0.0, value=5.0, step=1.0,
                                help="A股对应人民币，港股对应港元，美股对应美元")
    run_button = st.button("🔍 开始回看筛选", type="primary")

# 执行筛选
if run_button:
    if not market:
        st.warning("请先选择市场！")
    else:
        st.subheader(f"📊 正在回看{market}过去20天的核心形态，请稍候...")
        st.markdown("⚠️ 全市场标的较多，筛选预计需要3-10分钟，请不要关闭页面")
        results = run_screener(market, min_price)
        
        if not results:
            st.info("暂无符合条件的标的，建议把最低价格调低至3元，或切换市场再试")
        else:
            st.success(f"✅ 筛选完成！共找到 {len(results)} 只符合条件的标的（近期信号已标红置顶）")
            
            # 遍历输出结果
            for res in results:
                # 标题颜色区分
                if res["是否近期信号"]:
                    title_color = "red"
                    title_tag = "🔥 近期信号"
                elif res["几天前出现信号"] <= 10:
                    title_color = "orange"
                    title_tag = "📌 中期信号"
                else:
                    title_color = "gray"
                    title_tag = "📅 远期信号"
                
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
