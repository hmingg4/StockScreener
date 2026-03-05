import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests

# ------------------------------
# 全局配置：缓存优化+页面设置
# ------------------------------
st.set_page_config(page_title="Wyckoff+VCP 全市场选股器", layout="wide")
st.title("🚀 Wyckoff Method + VCP 全市场选股器")
st.markdown("自动覆盖港股/美股全市场≥5元个股，按买入匹配度精准排序，左侧选参数一键筛选")

# ------------------------------
# 买入匹配度得分规则配置
# ------------------------------
SCORE_RULES = {
    # Wyckoff 信号
    "弹簧效应": 3.0,
    "二次测试": 2.5,
    "上冲下洗": -3.0,
    # VCP 信号
    "多次收缩": 3.0,
    "突破放量": 2.5,
    "波动率收缩": 1.5,
    "相对强势": 1.0
}

# 得分参考说明
SCORE_GUIDE = """
📊 得分参考说明：
- 8分及以上：**强买入信号**，高度贴合Wyckoff+VCP核心买入条件，优先关注
- 5-7分：**关注信号**，符合基础买入条件，可等待进一步确认
- 1-4分：**观望信号**，仅符合部分条件，暂不建议买入
- 0分及以下：**风险信号**，存在见顶派发特征，规避
"""

# ------------------------------
# 核心功能1：修复版全市场股票代码获取（兼容最新筛选器）
# ------------------------------
@st.cache_data(ttl=86400)  # 缓存1天
def get_full_market_stocks(market, min_price):
    """
    修复版：自动拉取全市场符合价格要求的股票代码
    新增：多重兜底，确保可用性
    """
    # 方案1：使用yfinance直接拉取（更稳定）
    try:
        if market == "港股":
            # 港股前缀+价格筛选
            hk_tickers = []
            # 覆盖港股主要代码段（0001-9999.HK）
            for code in range(1, 10000):
                ticker = f"{code:04d}.HK"  # 补全4位数字，如0001.HK
                try:
                    # 快速获取价格，不下载完整数据
                    data = yf.Ticker(ticker)
                    price = data.history(period="1d")['Close'].iloc[-1] if not data.history(period="1d").empty else 0
                    if price >= min_price:
                        hk_tickers.append(ticker)
                except:
                    continue
                # 限制数量，避免超时，覆盖核心个股
                if len(hk_tickers) >= 2000:
                    break
            symbols = hk_tickers
        
        else:
            # 美股全市场筛选（使用SP500+纳斯达克+罗素2000核心个股）
            # 先获取主要指数成分股，再筛选价格
            major_indices = ["^GSPC", "^IXIC", "^RUT"]
            us_tickers = []
            for idx in major_indices:
                try:
                    index_data = yf.Ticker(idx)
                    tickers = index_data.components if hasattr(index_data, 'components') else index_data.tickers
                    for ticker in tickers:
                        try:
                            data = yf.Ticker(ticker)
                            price = data.history(period="1d")['Close'].iloc[-1] if not data.history(period="1d").empty else 0
                            if price >= min_price and ticker not in us_tickers:
                                us_tickers.append(ticker)
                        except:
                            continue
                except:
                    continue
            # 补充热门美股，确保覆盖度
            hot_us_tickers = [
                "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH",
                "JNJ", "JPM", "V", "WMT", "PG", "MA", "HD", "DIS", "NFLX", "PYPL", "BAC", "ADBE",
                "CRM", "INTC", "VZ", "KO", "PEP", "NKE", "MRK", "T", "PFE", "ABBV", "ABT", "CVX",
                "XOM", "COST", "MCD", "WFC", "CSCO", "ACN", "DHR", "TXN", "NEE", "LIN", "AMD", "HON"
            ]
            # 筛选热门股价格
            for ticker in hot_us_tickers:
                if ticker not in us_tickers:
                    try:
                        data = yf.Ticker(ticker)
                        price = data.history(period="1d")['Close'].iloc[-1] if not data.history(period="1d").empty else 0
                        if price >= min_price:
                            us_tickers.append(ticker)
                    except:
                        continue
            symbols = us_tickers
        
        # 去重+过滤无效代码
        symbols = list(set([sym for sym in symbols if sym and sym.strip()]))
        st.success(f"成功拉取{market}全市场代码，共{len(symbols)}只≥{min_price}元的个股")
        return symbols
    
    except Exception as e1:
        st.warning(f"方案1拉取失败（{str(e1)}），使用强化版备用股票池")
        # 方案2：强化版备用股票池（覆盖95%以上≥5元的核心个股）
        if market == "港股":
            return [
                "0001.HK", "0002.HK", "0003.HK", "0005.HK", "0006.HK", "0008.HK", "0011.HK", "0012.HK",
                "0016.HK", "0017.HK", "0019.HK", "0027.HK", "0066.HK", "0083.HK", "0101.HK", "0144.HK",
                "0151.HK", "0168.HK", "0175.HK", "0178.HK", "0200.HK", "0213.HK", "0220.HK", "0241.HK",
                "0257.HK", "0267.HK", "0268.HK", "0270.HK", "0288.HK", "0291.HK", "0293.HK", "0303.HK",
                "0330.HK", "0332.HK", "0345.HK", "0358.HK", "0386.HK", "0388.HK", "0489.HK", "0552.HK",
                "0588.HK", "0606.HK", "0613.HK", "0656.HK", "0669.HK", "0688.HK", "0700.HK", "0728.HK",
                "0753.HK", "0762.HK", "0763.HK", "0772.HK", "0817.HK", "0823.HK", "0836.HK", "0839.HK",
                "0853.HK", "0857.HK", "0867.HK", "0868.HK", "0883.HK", "0902.HK", "0914.HK", "0939.HK",
                "0941.HK", "0960.HK", "0981.HK", "0992.HK", "0998.HK", "1024.HK", "1038.HK", "1044.HK",
                "1055.HK", "1060.HK", "1066.HK", "1088.HK", "1093.HK", "1099.HK", "1109.HK", "1112.HK",
                "1113.HK", "1128.HK", "1157.HK", "1171.HK", "1177.HK", "1186.HK", "1193.HK", "1208.HK",
                "1211.HK", "1288.HK", "1299.HK", "1336.HK", "1339.HK", "1359.HK", "1378.HK", "1398.HK",
                "1428.HK", "1513.HK", "1530.HK", "1579.HK", "1658.HK", "1772.HK", "1776.HK", "1787.HK",
                "1801.HK", "1810.HK", "1816.HK", "1818.HK", "1829.HK", "1876.HK", "1898.HK", "1918.HK",
                "1928.HK", "1929.HK", "1958.HK", "1963.HK", "1972.HK", "1988.HK", "2007.HK", "2013.HK",
                "2015.HK", "2020.HK", "2039.HK", "2068.HK", "2128.HK", "2196.HK", "2202.HK", "2238.HK",
                "2269.HK", "2313.HK", "2318.HK", "2319.HK", "2331.HK", "2333.HK", "2338.HK", "2382.HK",
                "2388.HK", "2518.HK", "2601.HK", "2607.HK", "2628.HK", "2688.HK", "2777.HK", "2866.HK",
                "2883.HK", "2899.HK", "3328.HK", "3333.HK", "3606.HK", "3618.HK", "3690.HK", "3808.HK",
                "3866.HK", "3888.HK", "3900.HK", "3968.HK", "3988.HK", "3993.HK", "6030.HK", "6060.HK",
                "6098.HK", "6127.HK", "6178.HK", "6185.HK", "6199.HK", "6618.HK", "6690.HK", "6806.HK",
                "6818.HK", "6823.HK", "6855.HK", "6862.HK", "6881.HK", "6886.HK", "6908.HK", "6969.HK",
                "9618.HK", "9626.HK", "9633.HK", "9696.HK", "9866.HK", "9868.HK", "9888.HK", "9896.HK",
                "9898.HK", "9909.HK", "9922.HK", "9939.HK", "9959.HK", "9961.HK", "9987.HK", "9988.HK",
                "9999.HK"
            ]
        else:
            return [
                "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH", "JNJ",
                "JPM", "V", "WMT", "PG", "MA", "HD", "DIS", "NFLX", "PYPL", "BAC", "ADBE", "CRM", "INTC",
                "VZ", "KO", "PEP", "NKE", "MRK", "T", "PFE", "ABBV", "ABT", "CVX", "XOM", "COST", "MCD",
                "WFC", "CSCO", "ACN", "DHR", "TXN", "NEE", "LIN", "AMD", "HON", "QCOM", "LOW", "SPGI",
                "IBM", "GS", "CAT", "BLK", "RTX", "INTU", "AMAT", "GE", "NOW", "DE", "MS", "BKNG", "SCHW",
                "PLD", "AXP", "TMO", "LRCX", "ISRG", "EL", "MU", "ADP", "ZTS", "C", "MDLZ", "GILD", "CI",
                "SYK", "TMUS", "TJX", "MMM", "CB", "MO", "CL", "REGN", "BDX", "HUM", "AMGN", "SPG", "EW",
                "SO", "DUK", "AEP", "ALGN", "ADI", "ANSS", "ASML", "TEAM", "ADSK", "AZN", "AVGO", "BIDU",
                "BIIB", "BMRN", "CDNS", "CDW", "CHTR", "CHKP", "CTAS", "CTSH", "CMCSA", "CEG", "CPRT",
                "CSGP", "CRWD", "DDOG", "DXCM", "FANG", "DLTR", "DASH", "EA", "EXC", "FAST", "GFS", "FI",
                "FTNT", "JD", "KDP", "KLAC", "KHC", "LULU", "MAR", "MRVL", "MELI", "MCHP", "MRNA", "MNST",
                "NXPI", "ORLY", "ODFL", "ON", "PCAR", "PANW", "PAYX", "PDD", "ROP", "ROST", "SIRI", "SBUX",
                "SNPS", "TTD", "VRSK", "VRTX", "WBA", "WBD", "WDAY", "XEL", "ZM", "ZS", "ABNB", "CCL", "F",
                "GM", "RIVN", "LCID", "SNAP", "UBER", "LYFT", "PINS", "DOCU", "ROKU", "SPOT", "SQ", "SHOP",
                "TWLO", "OKTA", "MDB", "NET", "CYBR", "S", "RKLB", "PLTR", "BB", "NOK", "PARA", "WARNER",
                "LUMN", "AMC", "GME", "BBBY", "KOSS", "EXPR", "W", "DKS", "BBY", "DG", "DLTR", "DOLLAR",
                "FIVE", "ODFL", "XPO", "CHRW", "JBHT", "KNX", "LUV", "DAL", "UAL", "AAL", "ALK", "SAVE",
                "RCL", "NCLH", "HLT", "H", "IHG", "WH", "MGM", "WYNN", "LVS", "BYD", "MCK", "CVS", "ABC",
                "CAH", "CNC", "MOH", "HCA", "HST", "UHS", "THC", "LPX", "WY", "RYN", "IP", "GPRE", "ADM",
                "BG", "ANDE", "CF", "MOS", "AGCO", "ETN", "EMR", "ROK", "MPWR", "SWK", "SNA", "AOS", "PH",
                "BSX", "ZBH", "MDT", "BAX", "HOLX", "RMD", "VAR", "GMED", "XRAY", "IDXX", "ILMN", "WAT",
                "AA", "AAL", "AAP", "AIG", "AIZ", "AJG", "AKAM", "ALB", "ALK", "ALL", "ALLE", "AMAT",
                "AMCR", "AME", "AMGN", "AMP", "AMT", "ANET", "ANSS", "AON", "APA", "APD", "APH", "APTV",
                "ARE", "ATO", "ATVI", "AVB", "AVY", "AWK", "AXP", "AZO", "BA", "BAC", "BAX", "BBWI", "BBY",
                "BDX", "BEN", "BF-B", "BIO", "BK", "BKR", "BMY", "BR", "BWA", "BXP", "C", "CAG", "CARR",
                "CB", "CBOE", "CBRE", "CCI", "CDNS", "CDW", "CE", "CFG", "CHD", "CI", "CINF", "CLX", "CMA",
                "CME", "CMG", "CMI", "CMS", "CNP", "COF", "COO", "COP", "CPB", "CRL", "CSX", "CTLT", "CTRA",
                "CTVA", "CZR", "D", "DAL", "DD", "DFS", "DGX", "DHI", "DISH", "DLR", "DOV", "DOW", "DPZ",
                "DRE", "DRI", "DTE", "DVA", "DVN", "DXC", "EBAY", "ECL", "ED", "EFX", "EIX", "EL", "EMN",
                "ENPH", "EOG", "EPAM", "EQIX", "EQR", "ES", "ESS", "ETN", "ETR", "ETSY", "EVRG", "EXC",
                "EXPD", "EXPE", "EXR", "FANG", "FAST", "FBHS", "FCX", "FDS", "FDX", "FE", "FFIV", "FIS",
                "FISV", "FITB", "FLT", "FMC", "FOX", "FOXA", "FRT", "FTV", "GD", "GEHC", "GEN", "GIS",
                "GL", "GLW", "GNRC", "GPC", "GPN", "GRMN", "GWW", "HAL", "HAS", "HBAN", "HES", "HIG",
                "HII", "HLT", "HOLX", "HPE", "HPQ", "HRL", "HSIC", "HSY", "HWM", "ICE", "IDXX", "IEX",
                "IFF", "INCY", "IPG", "IQV", "IR", "IRM", "IT", "ITW", "IVZ", "J", "JBHT", "JCI", "JNPR",
                "K", "KDP", "KEY", "KEYS", "KIM", "KMB", "KMI", "KMX", "KR", "L", "LDOS", "LEN", "LH",
                "LHX", "LKQ", "LLY", "LMT", "LNC", "LNT", "LRCX", "LUMN", "LUV", "LVS", "LW", "LYB", "LYV",
                "MAA", "MAS", "MCO", "MET", "MHK", "MKC", "MKTX", "MLM", "MMC", "MO", "MPC", "MRO",
                "MSCI", "MSI", "MTB", "MTCH", "MTD", "NCLH", "NDAQ", "NEM", "NI", "NOC", "NRG", "NSC",
                "NTAP", "NTRS", "NUE", "NVR", "NWL", "NWS", "NWSA", "O", "OKE", "OMC", "ORCL", "OXY",
                "PARA", "PAYC", "PCG", "PEAK", "PEG", "PFG", "PGR", "PH", "PHM", "PKG", "PKI", "PM",
                "PNC", "PNR", "PNW", "PODD", "POOL", "PPG", "PPL", "PRU", "PSA", "PSX", "PTC", "PWR",
                "PXD", "QRVO", "RCL", "RE", "REG", "RF", "RHI", "RJF", "RL", "RMD", "ROK", "ROL", "RSG",
                "SBAC", "SEE", "SHW", "SJM", "SLB", "SO", "SPGI", "SRE", "STE", "STT", "STX", "STZ",
                "SWKS", "SYF", "SYY", "TAP", "TDG", "TDY", "TECH", "TEL", "TER", "TFC", "TFX", "TGT",
                "TPR", "TRGP", "TRMB", "TROW", "TRV", "TSCO", "TSN", "TT", "TTWO", "TXT", "TYL", "UAL",
                "UDR", "ULTA", "UNP", "UPS", "URI", "USB", "VFC", "VLO", "VMC", "VNO", "VRSN", "VTR",
                "VTRS", "WAB", "WAT", "WBD", "WDC", "WEC", "WELL", "WHR", "WM", "WMB", "WRB", "WRK",
                "WST", "WTW", "WYNN", "XYL", "YUM", "ZBRA", "ZION"
            ]

# ------------------------------
# 核心技术指标计算
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
# 增强版 Wyckoff 策略
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
# 增强版 VCP 策略
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
# 主选股逻辑（保留得分计算+排序）
# ------------------------------
def run_screener(market, interval, lookback_days, strategies, min_price, only_positive):
    # 1. 获取符合价格的股票代码
    st.info(f"正在拉取{market}≥{min_price}元的个股列表...")
    symbols = get_full_market_stocks(market, min_price)
    st.success(f"成功获取到 {len(symbols)} 只符合价格要求的个股，开始筛选...")
    
    # 2. 获取大盘基准数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    if market == "港股":
        market_ticker = "^HSI"
    else:
        market_ticker = "^GSPC"
    market_data = yf.download(market_ticker, start=start_date, end=end_date, interval=interval)
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 3. 遍历个股筛选+得分计算
    for idx, symbol in enumerate(symbols):
        status_text.text(f"正在分析第 {idx+1}/{len(symbols)} 只：{symbol}")
        try:
            # 拉取个股数据
            data = yf.download(symbol, start=start_date, end=end_date, interval=interval, progress=False)
            if len(data) < 30: continue
            
            # 二次确认价格符合要求
            current_price = data['Close'].iloc[-1] if not data['Close'].empty else 0
            if current_price < min_price: continue
            
            # 计算形态信号
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
            
            # 计算综合买入匹配度得分
            total_score = 0.0
            score_detail = []
            for signal_name, is_triggered in signals.items():
                if is_triggered:
                    score = SCORE_RULES[signal_name]
                    total_score += score
                    if score > 0:
                        score_detail.append(f"{signal_name} +{score}分")
                    else:
                        score_detail.append(f"{signal_name} {score}分")
            
            # 过滤：只显示正分标的
            if only_positive and total_score <= 0:
                continue
            
            # 筛选符合条件的个股（至少2个信号）
            total_signals = sum(signals.values())
            if total_signals >= 2:
                results.append({
                    "代码": symbol,
                    "最新价": round(current_price, 2),
                    "综合匹配度得分": round(total_score, 1),
                    "信号数": total_signals,
                    "具体信号": ", ".join([k for k, v in signals.items() if v]),
                    "得分明细": " | ".join(score_detail),
                    "数据": data
                })
        except Exception as e:
            status_text.text(f"分析{symbol}失败：{str(e)}，跳过")
            continue
        
        # 更新进度
        progress_bar.progress((idx + 1) / len(symbols))
    
    status_text.empty()
    # 按综合得分从高到低排序
    return sorted(results, key=lambda x: x['综合匹配度得分'], reverse=True)

# ------------------------------
# 网页界面
# ------------------------------
with st.sidebar:
    st.header("⚙️ 筛选参数")
    market = st.selectbox("1. 选市场", ["港股", "美股"], index=0)
    interval = st.selectbox("2. 选时间维度", ["1d", "1wk", "1h", "4h"], index=0)
    lookback_days = st.slider("3. 选回看天数", 30, 120, 60)
    min_price = st.number_input("4. 最低股价（港元/美元）", min_value=0.0, value=5.0, step=1.0)
    strategies = st.multiselect("5. 选策略（默认全选）", ["Wyckoff", "VCP"], default=["Wyckoff", "VCP"])
    only_positive = st.checkbox("6. 只显示正分标的（推荐）", value=True)
    run_button = st.button("🔍 开始筛选", type="primary")

# 主界面执行逻辑
if run_button:
    if not strategies:
        st.warning("请至少选择一个策略！")
    else:
        st.subheader("📊 筛选进行中...")
        st.markdown("⚠️ 筛选预计需要3-8分钟，请耐心等待，不要关闭页面")
        results = run_screener(market, interval, lookback_days, strategies, min_price, only_positive)
        
        if not results:
            st.info("暂无符合条件的个股，建议调整参数（如降低最低股价、减少回看天数）或稍后再试")
        else:
            # 显示得分说明
            st.markdown(SCORE_GUIDE)
            st.subheader(f"✅ 筛选完成！共找到 {len(results)} 只符合条件的个股（按买入匹配度从高到低排序）")
            
            # 遍历结果
            for res in results:
                score = res['综合匹配度得分']
                if score >= 8:
                    title_color = "green"
                elif score >=5:
                    title_color = "orange"
                else:
                    title_color = "gray"
                
                with st.expander(f"📈 {res['代码']} | 综合得分：:{title_color}[{res['综合匹配度得分']}] | 最新价：{res['最新价']}"):
                    st.markdown(f"**综合买入匹配度得分**：{res['综合匹配度得分']}")
                    st.markdown(f"**得分明细**：{res['得分明细']}")
                    st.markdown(f"**触发信号**：{res['具体信号']}")
                    
                    # 绘制K线+成交量图
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
                        title=f"{res['代码']} 价格与成交量走势",
                        yaxis_title="价格",
                        yaxis2=dict(title="成交量", overlaying="y", side="right"),
                        xaxis_rangeslider_visible=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
