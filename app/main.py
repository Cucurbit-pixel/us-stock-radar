import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# 1. 網頁全域設定
st.set_page_config(page_title="臨玖 - 智能量化搜尋與強勢股雷達", layout="wide")

# 2. 安全調用 Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit 設定好金鑰。")
    st.stop()

# 3. 全自動獲取標普 500 成分股清單
@st.cache_data(ttl=86400)
def get_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        return tickers
    except Exception as e:
        return ["NVDA", "AMD", "SMCI", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX"]

# 輔助函數：火箭動能等級
def get_rocket_emoji(rs):
    if rs >= 85: return "🚀🚀🚀"
    if rs >= 70: return "🚀🚀"
    return "🚀"

# 4. 核心量化計算邏輯 (統一處理歷史 K 線與 RS 換算)
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

# 🌟 大數據分批抓取與計算快取 (標普 500 用)
@st.cache_data(ttl=3600)
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
            time.sleep(0.2)
        except Exception:
            continue

    results = []
    for ticker, bars in all_bars.items():
        metrics = calculate_metrics(ticker, bars)
        if metrics:
            results.append(metrics)
    return pd.DataFrame(results)

# 🌟 獨立高速通道：專門處理手動搜尋的單隻股票 (快取時間較短，保持即時性)
@st.cache_data(ttl=600)
def fetch_single_ticker_live(ticker):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
    params = {
        "symbols": ticker,
        "timeframe": "1Day",
        "start": (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "feed": "iex",
        "adjustment": "all"
    }
    try:
        response = requests.get(data_url, headers=headers, params=params)
        if response.status_code == 200:
            bars_data = response.json().get("bars", {})
            if ticker in bars_data:
                return calculate_metrics(ticker, bars_data[ticker])
    except Exception:
        return None
    return None

# 5. 【左側側邊欄】雷達導航中心
st.sidebar.title("🤖 雷達導航中心")
st.sidebar.markdown("---")

# ✨ 新增：手動美股搜尋框 (自動轉換大寫並去除空格)
st.sidebar.subheader("🔍 個股即時診斷")
search_input = st.sidebar.text_input("輸入美股代碼 (例如: AVGO, TSM)", "").strip().upper()

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 大盤大數據濾網")
rs_score_min = st.sidebar.slider("最低相對強度 (RS) 分數", 10, 99, 80)

st.sidebar.markdown("---")
st.sidebar.caption("數據源：Wikipedia + Alpaca IEX Free")


# 6. 【右側主畫面】分層渲染
st.title("📈 臨玖量化雷達終端機")

# ==================== 區塊一：個股即時搜尋結果 ====================
if search_input:
    st.markdown(f"### 🔍 手動搜尋個股結果：`{search_input}`")
    
    # 預先載入大盤數據，看看搜的是不是大盤股
    sp500_list = get_sp500_tickers()
    with st.spinner("🤖 正在調度大數據庫..."):
        master_df = load_and_calculate_master_data(sp500_list)
    
    found_in_cache = False
    # 如果大總表裡面已經有，直接撈，速度快到飛起
    if not master_df.empty:
        match_row = master_df[master_df["股票代號"] == search_input]
        if not match_row.empty:
            st.success(f"✅ 在標普 500 快取中找到 `{search_input}` 數據：")
            st.dataframe(match_row, use_container_width=True, hide_index=True)
            found_in_cache = True
            
    # 如果大總表無（屬於外卡黑馬股），啟動獨立快速通道向交易所要數據
    if not found_in_cache:
        with st.spinner(f"🚀 `{search_input}` 不在大盤快取中，正在啟動外卡通道向交易所實時運算..."):
            single_data = fetch_single_ticker_live(search_input)
            
        if single_data:
            st.success(f"🎯 成功穿透交易所！`{search_input}` 量化診斷報告如下：")
            single_df = pd.DataFrame([single_data])
            st.dataframe(single_df, use_container_width=True, hide_index=True)
        else:
            st.error(f"❌ 無法獲取 `{search_input}` 的數據。請檢查代碼是否正確（如 NVDIA 錯字），或該股票歷史 K 線少於 150 天。")
    st.markdown("---") # 分割線

# ==================== 區塊二：標普 500 大數據強勢股雷達 ====================
st.markdown("### 📊 標普 500 強勢股實時掃描器")

with st.spinner("🔄 正在同步標普 500 最新成分股名單..."):
    sp500_list = get_sp500_tickers()

with st.spinner(f"🤖 正在實時計算大盤 {len(sp500_list)} 隻股票量化數據..."):
    master_df = load_and_calculate_master_data(sp500_list)

if not master_df.empty:
    # 執行 RS 分數篩選
    filtered_df = master_df[master_df["相對強度 (RS 分數)"] >= rs_score_min]
    
    if not filtered_df.empty:
        filtered_df = filtered_df.sort_values(by="相對強度 (RS 分數)", ascending=False)
        st.success(f"🎉 瞬間掃描完畢！標普 500 內 RS 分數 ≧ {rs_score_min} 嘅強勢股票共有 {len(filtered_df)} 隻：")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info("⚠️ 當前 RS 分數篩選太高，大盤暫無標的達標。")
else:
    st.warning("⚠️ 大數據加載失敗，請檢查網絡連線。")
