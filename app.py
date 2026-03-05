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
# 阿斯达克请求头（模拟浏览器，避免反爬）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.aastocks.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

# 标的池（可自定义，格式：港股=01810.HK，美股=AAPL，A股=600519.SS）
STOCK_POOL = {
    "港股": ["0700.HK", "01810.HK", "9988.HK", "3690.HK", "0005.HK", "0941.HK"],
    "美股": ["AAPL", "MSFT", "NVDA", "TSLA", "META"],
    "A股": ["600519.SS", "300750.SZ", "002594.SZ"]
}

# ===================== 多源数据抓取核心模块 =====================
def get_yfinance_data(stock_code, days=180):
    """
    优先从Yahoo Finance抓取日线数据
    :param stock_code: 股票代码（如01810.HK、AAPL）
    :param days: 抓取最近N天的日线
    :return: 标准化的DataFrame（datetime/high/low/close/volume）
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 20)  # 多抓20天备用
        
        # 抓取yfinance数据
        df = yf.download(
            stock_code,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1d",
            progress=False
        )
        
        # 数据清洗：去重、补空值、标准化字段
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
        
        # 确保数据量足够
        if len(df) >= days:
            return df.tail(days)  # 只保留最近days天
        else:
            return None
    except Exception as e:
        print(f"⚠️ Yahoo Finance抓取{stock_code}失败：{str(e)[:50]}")
        return None

def get_aastocks_data(stock_code, days=180):
    """
    备用：从阿斯达克（Aastocks）抓取港股/美股日线数据（延迟15-30分钟）
    :param stock_code: 股票代码（如01810.HK、AAPL）
    :param days: 抓取最近N天的日线
    :return: 标准化的DataFrame（datetime/high/low/close/volume）
    """
    try:
        # 适配阿斯达克的代码格式
        if ".HK" in stock_code:
            aastock_code = f"0{stock_code.replace('.HK', '')}"  # 01810.HK → 001810
            market = "hk"
        elif ".SS" in stock_code or ".SZ" in stock_code:
            # 阿斯达克A股数据有限，优先用yfinance，这里仅做示例
            return None
        else:
            aastock_code = stock_code
            market = "us"
        
        # 阿斯达克日线数据接口（公开接口，返回JSON）
        url = f"https://www.aastocks.com/tc/resources/data/getchartdata.aspx?symbol={aastock_code}&resolution=D&count={days}&period=1"
        
        # 发送请求（加延迟，避免反爬）
        time.sleep(0.5)
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None
        
        # 解析JSON数据
        data = json.loads(response.text)
        if "data" not in data or len(data["data"]) == 0:
            return None
        
        # 转换为DataFrame并标准化
        df = pd.DataFrame(data["data"])
        # 时间戳转日期
        df["datetime"] = pd.to_datetime(df["t"], unit="s")
        # 标准化字段
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
        print(f"⚠️ 阿斯达克抓取{stock_code}失败：{str(e)[:50]}")
        return None

def get_stock_data(stock_code, days=180):
    """
    统一数据入口：优先Yahoo，失败则用阿斯达克
    :param stock_code: 股票代码
    :param days: 抓取天数
    :return: 标准化的日线DataFrame
    """
    # 第一步：尝试Yahoo Finance
    df = get_yfinance_data(stock_code, days)
    if df is not None and len(df) >= days * 0.8:  # 数据量≥80%即可用
        return df
    
    # 第二步：备用→阿斯达克
    df = get_aastocks_data(stock_code, days)
    if df is not None and len(df) >= days * 0.8:
        return df
    
    # 都失败则返回None
    print(f"❌ {stock_code} 所有数据源抓取失败，跳过")
    return None

# ===================== Wyckoff+VCP 核心筛选逻辑 =====================
def calculate_atr(df, period=14):
    """计算ATR（平均真实波幅，VCP核心指标）"""
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
    df['atr'] = df['tr'].rolling(window=period).mean()
    return df

def check_wyckoff_spring(df):
    """识别Wyckoff弹簧效应（测试支撑后收回）"""
    if len(df) < 30:
        return False, 0, 0
    
    # 30天滚动支撑位
    df['support_30d'] = df['low'].rolling(window=30).min()
    recent_data = df.iloc[-20:]  # 放宽到最近20天找弹簧
    
    for idx, row in recent_data.iterrows():
        # 核心逻辑：测试支撑（±5%）+ 收盘收回支撑上方
        if row['low'] <= row['support_30d'] * 1.05 and row['close'] > row['support_30d']:
            # 计算强度：反弹幅度+成交量匹配度
            bounce_rate = (row['close'] - row['low']) / row['low'] * 100
            vol_ratio = row['volume'] / df['volume'].mean() if df['volume'].mean() > 0 else 0
            score = bounce_rate * 0.7 + vol_ratio * 0.3
            return True, row['support_30d'], round(score, 2)
    
    return False, 0, 0

def check_vcp_contraction(df):
    """识别VCP波动收缩（波动率逐波下降）"""
    if len(df) < 60:
        return False, 0, 0
    
    df = calculate_atr(df)
    # 分3个阶段检查ATR收缩
    stage1_atr = df['atr'].iloc[-60:-40].mean()
    stage2_atr = df['atr'].iloc[-40:-20].mean()
    stage3_atr = df['atr'].iloc[-20:].mean()
    
    contraction_count = 0
    if stage2_atr < stage1_atr * 0.9:
        contraction_count += 1
    if stage3_atr < stage2_atr * 0.9:
        contraction_count += 1
    
    # 价格区间收窄验证
    stage1_range = df['high'].iloc[-60:-40].max() - df['low'].iloc[-60:-40].min()
    stage3_range = df['high'].iloc[-20:].max() - df['low'].iloc[-20:].min()
    if stage3_range < stage1_range * 0.7:
        contraction_count += 1
    
    # 收缩次数≥2则符合VCP
    if contraction_count >= 2:
        score = (1 - stage3_atr/stage1_atr) * 100
        return True, contraction_count, round(score, 2)
    return False, 0, 0

def analyze_stock(stock_code, days=180):
    """单只股票完整分析：数据抓取+形态筛选+点位计算"""
    # 1. 获取稳定的日线数据
    df = get_stock_data(stock_code, days)
    if df is None:
        return None
    
    current_price = df['close'].iloc[-1]
    
    # 2. 核心形态判断
    wyck_spring, wyck_support, wyck_score = check_wyckoff_spring(df)
    vcp_contraction, vcp_count, vcp_score = check_vcp_contraction(df)
    
    # 3. 阶段定位
    if wyck_spring and vcp_contraction:
        stage = "✅ 吸筹末期+VCP收缩，临近突破"
    elif wyck_spring:
        stage = "⚠️ 仅Wyckoff弹簧，无VCP收缩"
    elif vcp_contraction:
        stage = "⚠️ 仅VCP收缩，无Wyckoff弹簧"
    else:
        stage = "❌ 无核心形态"
    
    # 4. 交易点位（基于支撑/压力）
    support = round(wyck_support, 2) if wyck_support > 0 else current_price * 0.95
    resistance = df['high'].iloc[-20:].max()  # 20天压力位
    
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

# ===================== 批量选股主函数 =====================
def run_screener(market="港股", days=180):
    """
    批量筛选符合Wyckoff+VCP的股票
    :param market: 市场（港股/美股/A股）
    :param days: 回看天数（默认180天=半年）
    """
    if market not in STOCK_POOL:
        print("❌ 市场选择错误，仅支持：港股/美股/A股")
        return []
    
    stock_list = STOCK_POOL[market]
    results = []
    print(f"\n🚀 开始筛选{market}标的（共{len(stock_list)}只，回看{days}天）...")
    
    for idx, stock in enumerate(stock_list):
        print(f"[{idx+1}/{len(stock_list)}] 分析 {stock}")
        analysis = analyze_stock(stock, days)
        if analysis and (analysis['Wyckoff弹簧'] or analysis['VCP收缩']):
            results.append(analysis)
    
    # 输出结果
    if not results:
        print("\n📊 暂无符合Wyckoff+VCP的标的（可放宽天数/标的池）")
    else:
        print(f"\n🎉 共筛选出{len(results)}只符合条件的标的：")
        print("-" * 80)
        for res in results:
            for k, v in res.items():
                print(f"{k:<10}: {v}")
            print("-" * 80)
        
        # 导出Excel（可选）
        df_result = pd.DataFrame(results)
        df_result.to_excel(f"Wyckoff_VCP_{market}_选股结果.xlsx", index=False)
        print(f"\n📁 结果已导出为：Wyckoff_VCP_{market}_选股结果.xlsx")
    
    return results

# ===================== 执行筛选 =====================
if __name__ == "__main__":
    # 选择要筛选的市场：港股/美股/A股
    run_screener(market="港股", days=180)
