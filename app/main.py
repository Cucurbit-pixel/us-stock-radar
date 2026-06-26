```python
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# 1. 網頁全域設定
st.set_page_config(page_title="臨玖 - 雙大盤智能量化搜尋終端", layout="wide")

# 2. 安全調用 Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit 設定好金鑰。")
    st.stop()

# 3. 全自動獲取標普 500 與納指 100 成分股清單
@st.cache_data(ttl=86400)  # 股票名單一天只從 Wikipedia 同步一次
def get_market_tickers():
    # A. 爬取標普 500
    sp500 = []
    try:
        url_sp = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        sp500 = pd.read_html(url_sp)[0]['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        sp500 = ["NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "TSLA"]

    # B. 爬取納斯達克 100
    nasdaq100 = []
    try:
        url_ndx = "https://en.wikipedia.org/wiki/Nasdaq-100"
        tables = pd.read_html(url_ndx)
        for df in tables:
            if 'Ticker' in df.columns:
                nasdaq100 = df['Ticker'].str.replace('.', '-', regex=False).tolist()
                break
            elif 'Symbol' in df.columns:
                nasdaq100 = df['Symbol'].str.replace('.', '-', regex=False).tolist()
                break
    except Exception as e:
        nasdaq100 = ["NVDA", "AMD", "AVGO", "SMCI", "NFLX", "COST", "TSM", "ARM"]

    return sp500, nasdaq100

# 輔助函數：火箭動能等級
def get_rocket_emoji(rs):
    if rs >= 85: return "🚀🚀🚀"
    if rs >= 70: return "🚀🚀"
    return "🚀"

# 4. 核心量化計算邏輯
def calculate_metrics(ticker, bars):
    if len(bars) < 150:
        return None
    df = pd.DataFrame(bars)
    df['close'] = df['c']
    current_price = df['close'].iloc[-1]
    
    # 計算半年期 (126個交易日) 漲跌幅動能
    price_6mo_ago = df['close'].iloc[-126] if len(df) >= 126 else df['close'].iloc[0]
    half_year_perf = ((current_price - price_6mo_ago) / price_6mo_ago) * 100
    
    # 換算相對強度 (RS) 評分
    rs_rating = min(max(int(50 + half_year_perf), 10), 99)
    
    return {
        "股票代號": ticker,
        "最新現價 ($)": round(current_price, 2),
        "相對強度 (RS 分數)": rs_rating,
        "三級火箭動能": get_rocket_emoji(rs_rating)
    }

# 🌟 效能與即時平衡優化：全大盤大數據計算 (快取設定為 5 分鐘，確保自動更新股價)
@st.cache_data(ttl=300)
def load_and_calculate_master_data(tickers):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
    all_bars = {}
    chunk_size = 100
    
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        params = {
            "symbols": ",".join(chunk),
            "timeframe": "1Day",
            "start": (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "feed": "iex",
            "adjustment": "all"
        }
        try:
            response = requests.get(data_url, headers=headers, params=params)
            if response.status_code == 200:
                bars_data = response.json().get("bars", {})
                if bars_data:
                    all_bars.update(bars_data)
            time.sleep(0.15)  # 免費密鑰安全延遲
        except Exception:
            continue

    results = []
    for ticker, bars in all_bars.items():
        metrics = calculate_metrics(ticker, bars)
        if metrics:
            results.append(metrics)
    return pd.DataFrame(results)

# 獨立高速通道：手動搜尋對比圖專用 (快取 5 分鐘)
@st.cache_data(ttl=300)
def fetch_ticker_and_spy_history(ticker):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
    params = {
        "symbols": f"{ticker},SPY",
        "timeframe": "1Day",
        "start": (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "feed": "iex",
        "adjustment": "all"
    }
    try:
        response = requests.get(data_url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("bars", {})
    except Exception:
        return None
    return None

# 5. 【左側側邊欄】雷達導航中心
st.sidebar.title("🤖 雷達導航中心")
st.sidebar.markdown("---")

# 🌟 核心新增一：實時強制手動刷新按鈕 (一按即時清空快取並重新加載最新股價)
st.sidebar.subheader("🔄 數據更新中心")
if st.sidebar.button("⚡ 實時強制刷新股價", use_container_width=True):
    st.cache_data.clear()  # 瞬間拔掉快取地雷
    st.success("✅ 已強制同步最新股價！")
    st.rerun()             # 重新運行程式

st.sidebar.markdown("---")

# A. 手動搜尋框
st.sidebar.subheader("🔍 個股即時診斷 & 大盤對比")
search_input = st.sidebar.text_input("輸入美股代碼 (例如: TSM, NVDA)", "").strip().upper()

st.sidebar.markdown("---")

# B. 掃描目標大盤選擇器
st.sidebar.subheader("⚙️ 掃描大盤配置")
market_target = st.sidebar.selectbox(
    "選擇觀測大盤群組",
    ["Nasdaq 100 (科技龍頭股)", "S&P 500 (標普五百大盤)", "兩大指數合體聯軍 (全明星大池)"]
)

# C. RS 分數滑桿
rs_score_min = st.sidebar.slider("最低相對強度 (RS) 分數", 10, 99, 85)

st.sidebar.markdown("---")
st.sidebar.caption("數據源：Wikipedia Tickers + Alpaca IEX Free")


# 6. 【右側主畫面】分層渲染
st.title("📈 臨玖量化雷達終端機")

# 同步下載大盤名單數據
with st.spinner("🔄 正在網絡同步最新美股大盤成分股名單..."):
    sp500_tickers, nasdaq_tickers = get_market_tickers()

# 根據選單動態決定當前的股票池
if market_target == "Nasdaq 100 (科技龍頭股)":
    current_pool = nasdaq_tickers
    display_title = "Nasdaq 100 強勢股實時掃描器"
elif market_target == "S&P 500 (標普五百大盤)":
    current_pool = sp500_tickers
    display_title = "S&P 500 強勢股實時掃描器"
else:
    # 兩大指數聯軍：合體並全自動去重疊 (Set Union)
    current_pool = list(set(sp500_tickers + nasdaq_tickers))
    display_title = "S&P 500 + Nasdaq 100 全明星聯軍掃描器"


# ==================== 區塊一：個股即時搜尋結果 + TradingView 對比圖 ====================
if search_input:
    st.markdown(f"### 🔍 手動搜尋個股結果：`{search_input}`")
    
    with st.spinner(f"🚀 正在穿透交易所，提取 `{search_input}` 與大盤的實時對比數據..."):
        history_bars = fetch_ticker_and_spy_history(search_input)
        
    if history_bars and search_input in history_bars:
        single_metrics = calculate_metrics(search_input, history_bars[search_input])
        if single_metrics:
            st.success(f"🎯 成功獲取 `{search_input}` 量化診斷報告：")
            st.dataframe(pd.DataFrame([single_metrics]), use_container_width=True, hide_index=True)
            
            if "SPY" in history_bars:
                df_stock = pd.DataFrame(history_bars[search_input])
                df_spy = pd.DataFrame(history_bars["SPY"])
                
                df_stock['日期'] = pd.to_datetime(df_stock['t']).dt.date
                df_spy['日期'] = pd.to_datetime(df_spy['t']).dt.date
                
                df_stock = df_stock.set_index('日期')[['c']].rename(columns={'c': f"{search_input} (個股)"})
                df_spy = df_spy.set_index('日期')[['c']].rename(columns={'c': "S&P 500 (SPY 大盤)"})
                
                df_compare = df_stock.join(df_spy, how='inner')
                if not df_compare.empty:
                    df_compare_pct = ((df_compare / df_compare.iloc[0]) - 1) * 100
                    st.markdown(f"#### 📊 TradingView 模式：`{search_input}` vs S&P 500 累計回報對比圖 (歷史 250 天)")
                    st.line_chart(df_compare_pct, use_container_width=True)
        else:
            st.error(f"❌ 股票 `{search_input}` 歷史數據不足，無法運算。")
    else:
        st.error(f"❌ 無法在交易所中尋獲 `{search_input}`。請檢查代號是否正確。")
    st.markdown("---")


# ==================== 區塊二：動態大盤強勢股掃描器表格 ====================
st.markdown(f"### 📊 {display_title}")

with st.spinner(f"🤖 正在實時計算該板塊 {len(current_pool)} 隻股票的量化大數據..."):
    master_df = load_and_calculate_master_data(current_pool)

if not master_df.empty:
    # 執行強度過濾
    filtered_df = master_df[master_df["相對強度 (RS 分數)"] >= rs_score_min]
    
    if not filtered_df.empty:
        filtered_df = filtered_df.sort_values(by="相對強度 (RS 分數)", ascending=False)
        st.success(f"🎉 瞬間掃描完畢！當前符合 RS 分數 ≧ {rs_score_min} 嘅強勢股票共有 {len(filtered_df)} 隻：")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info(f"⚠️ 當前選定大盤中，暫時沒有股票達到 {rs_score_min} 分。可嘗試在左側將分數調低。")
else:
    st.warning("⚠️ 大數據加載失敗，請檢查網絡連線或密鑰。")
 
```
