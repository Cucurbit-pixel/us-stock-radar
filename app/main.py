import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# 1. 網頁全域設定
st.set_page_config(page_title="臨玖 - 全美股超級量化運算終端", layout="wide")

# 2. 安全調用 Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit 設定好金鑰。")
    st.stop()

# 🌟 核心優化一：全自動穿透 Alpaca 獲取全美股常規上市股票名單 (NYSE + NASDAQ)
@st.cache_data(ttl=86400) # 股票名單一天只向交易所同步一次
def get_all_us_tickers():
    assets_url = "https://paper-api.alpaca.markets/v2/assets?status=active&asset_class=us_equity"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    try:
        response = requests.get(assets_url, headers=headers)
        if response.status_code == 200:
            assets_list = response.json()
            # 嚴格篩選：必須可交易(tradable)、並且屬於主板交易所 (NASDAQ / NYSE)，過濾掉 OTC 垃圾場
            tickers = [
                asset['symbol'] for asset in assets_list 
                if asset.get('tradable') and asset.get('exchange') in ['NASDAQ', 'NYSE']
            ]
            return sorted(tickers)
    except Exception as e:
        st.error(f"無法獲取全美股名單: {e}")
    # 備用核心資產
    return ["NVDA", "AMD", "SMCI", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX"]

# 輔助函數：火箭動能等級
def get_rocket_emoji(rs):
    if rs >= 85: return "🚀🚀🚀"
    if rs >= 70: return "🚀🚀"
    return "🚀"

# 🌟 核心優化二：全美股大數據高速分批池（極速、輕量、防死機）
@st.cache_data(ttl=3600) # 全美股數據每小時快取一次
def load_and_calculate_all_us_market(tickers):
    data_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    
    all_bars = {}
    chunk_size = 200  # 每次打包 200 隻股票進行高速並行請求
    
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
            # 免費通道安全冷卻，防止頻率過快被 Alpaca 斷線
            time.sleep(0.15)
        except Exception:
            continue

    results = []
    # ⚡ 輕量化矩陣運算：直接解構字典，拒絕生成幾千個 DataFrame 導致過載
    for ticker, bars in all_bars.items():
        if len(bars) < 150: 
            continue
            
        current_price = bars[-1]['c'] # 撈取最新收盤價
        
        # 💡 防禦機制：自動洗走小於 $5 美元的仙股/投機細價股
        if current_price < 5.0:
            continue
            
        # 計算半年期 (126個交易日) 漲跌幅動能
        price_6mo_ago = bars[-126]['c'] if len(bars) >= 126 else bars[0]['c']
        half_year_perf = ((current_price - price_6mo_ago) / price_6mo_ago) * 100
        
        # 換算強勢度相對強度 (RS) 評分
        rs_rating = min(max(int(50 + half_year_perf), 10), 99)
        
        results.append({
            "股票代號": ticker,
            "最新現價 ($)": round(current_price, 2),
            "相對強度 (RS 分數)": rs_rating,
            "三級火箭動能": get_rocket_emoji(rs_rating)
        })
        
    return pd.DataFrame(results)

# 獨立高速通道：手動搜尋對比圖專用
@st.cache_data(ttl=600)
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

# 3. 【左側側邊欄】雷達導航中心
st.sidebar.title("🤖 雷達導航中心")
st.sidebar.markdown("---")

# A. 手動搜尋框
st.sidebar.subheader("🔍 個股即時診斷 & 大盤對比")
search_input = st.sidebar.text_input("輸入美股代碼 (例如: TSM, NVDA)", "").strip().upper()

st.sidebar.markdown("---")

# B. RS 分數滑桿 (面對全美股，強烈建議拉到 85-90分以上狙擊真龍頭)
st.sidebar.subheader("⚙️ 全美股量化濾網")
rs_score_min = st.sidebar.slider("最低相對強度 (RS) 分數", 10, 99, 90)

st.sidebar.markdown("---")
st.sidebar.caption("數據源：Alpaca API 全美股資產通道")


# 4. 【右側主畫面】分層渲染
st.title("📈 臨玖量化雷達終端機 - 全美股版")

# ==================== 區塊一：個股即時搜尋結果 + TradingView 對比圖 ====================
if search_input:
    st.markdown(f"### 🔍 手動搜尋個股結果：`{search_input}`")
    
    with st.spinner(f"🚀 正在穿透交易所，提取 `{search_input}` 與大盤的實時對比數據..."):
        history_bars = fetch_ticker_and_spy_history(search_input)
        
    if history_bars and search_input in history_bars:
        single_metrics = calculate_metrics = calculate_metrics(search_input, history_bars[search_input]) if 'calculate_metrics' in globals() else None
        
        # 為了保持結構完整，若上面被打包，這裡直接重寫一個最穩陣嘅即時解析
        bars = history_bars[search_input]
        if len(bars) >= 150:
            c_price = bars[-1]['c']
            p_6m = bars[-126]['c'] if len(bars) >= 126 else bars[0]['c']
            perf = ((c_price - p_6m) / p_6m) * 100
            rs_val = min(max(int(50 + perf), 10), 99)
            
            single_df = pd.DataFrame([{
                "股票代號": search_input, "最新現價 ($)": round(c_price, 2), "相對強度 (RS 分數)": rs_val, "三級火箭動能": get_rocket_emoji(rs_val)
            }])
            st.success(f"🎯 成功獲取 `{search_input}` 量化診斷報告：")
            st.dataframe(single_df, use_container_width=True, hide_index=True)
            
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


# ==================== 區塊二：動態全美股強勢股掃描器表格 ====================
st.markdown("### 📊 全美股強勢股實時掃描器 (NASDAQ + NYSE)")

# 步驟一：即時同步全美股代碼
with st.spinner("🔄 正在向美股交易所實時同步全市場股票名單..."):
    all_us_tickers = get_all_us_tickers()

# 步驟二：執行全大數據輕量化吞噬計算
with st.spinner(f"🤖 正在全自動計算全美股 {len(all_us_tickers)} 隻標的之大數據量化指標... (初次加載需時約 30 秒)"):
    master_df = load_and_calculate_all_us_market(all_us_tickers)

if not master_df.empty:
    # 執行強度過濾
    filtered_df = master_df[master_df["相對強度 (RS 分數)"] >= rs_score_min]
    
    if not filtered_df.empty:
        filtered_df = filtered_df.sort_values(by="相對強度 (RS 分數)", ascending=False)
        st.success(f"🎉 瞬間掃描完畢！全美股中當前 RS 分數 ≧ {rs_score_min} 嘅真龍頭股票共有 {len(filtered_df)} 隻：")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info(f"⚠️ 全美股篩選條件太嚴格（當前設定最低 {rs_score_min} 分），暫無股票達標。可嘗試在左側將分數調低。")
else:
    st.warning("⚠️ 大數據加載失敗，請檢查網絡連線或密鑰。")
