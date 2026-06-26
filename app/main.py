import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# 1. 網頁全域設定
st.set_page_config(page_title="臨玖 - 雙大腦智能量化搜尋端", layout="wide")

# 2. 安全調用 Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit 後台設定金鑰。")
    st.stop()

# 核心自訂監控名單 (自動化雷達焦點)
FOCUS_TICKERS = ["NVDA", "SMCI", "AMD", "AMZN", "MSFT", "AAPL", "GOOGL", "META", "TSLA", "AVGO"]

# 3. Alpaca 實時大數據提取函數 (自動修正拆股價格)
def fetch_alpaca_bars(symbols, days_back=100):
    url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {
        "Apca-Api-Key-Id": ALPACA_API_KEY,
        "Apca-Api-Secret-Key": ALPACA_SECRET_KEY
    }
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00Z")
    params = {
        "symbols": ",".join(symbols),
        "timeframe": "1Day",
        "start": start_date,
        "adjustment": "all",  # 精確修正如 SMCI 拆股後的真實歷史價格
        "feed": "sip"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("bars", {})
        return {}
    except Exception:
        return {}

# 4. 核心演算法：RS 分數 與 VCP 買入點判定
def analyze_stock_signals(df):
    if df.empty or len(df) < 25:
        return {"buy_signal": "數據不足", "rs": 50, "current_price": 0, "signal_color": "gray"}
    
    # 資料數字化轉換
    df['close'] = pd.to_numeric(df['c'])
    df['high'] = pd.to_numeric(df['h'])
    df['low'] = pd.to_numeric(df['l'])
    df['vol'] = pd.to_numeric(df['v'])
    
    current_price = df['close'].iloc[-1]
    current_vol = df['vol'].iloc[-1]
    ma_vol_20 = df['vol'].rolling(20).mean().iloc[-1]
    
    # 1. 半年期相對強度 (RS 分數基準)
    price_6mo_ago = df['close'].iloc[-126] if len(df) >= 126 else df['close'].iloc[0]
    half_year_perf = ((current_price - price_6mo_ago) / price_6mo_ago) * 100
    rs_rating = min(max(int(50 + half_year_perf), 10), 99)
    
    # 2. 量化買入點邏輯 (結合 Minervini 突破與 VCP 收緊概念)
    # 過去 20 天的最高價 (剔除當天，作爲前高壓力位基準)
    high_20_pivot = df['high'].iloc[-21:-1].max() if len(df) >= 21 else df['high'].max()
    
    # 波動度收縮檢查 (VCP)：過去 5 天的波幅是否小於過去 20 天波幅的 50%
    range_5 = df['high'].iloc[-5:].max() - df['low'].iloc[-5:].min()
    range_20 = df['high'].iloc[-20:].max() - df['low'].iloc[-20:].min()
    is_vcp = (range_5 < range_20 * 0.5) if range_20 > 0 else False
    
    # 買入點狀態判定
    if current_price >= high_20_pivot:
        if current_vol > ma_vol_20:
            buy_signal = "💥 帶量突破買入點"
            signal_color = "red"
        else:
            buy_signal = "⚠️ 價格突破 (但量能不足)"
            signal_color = "orange"
    elif current_price >= high_20_pivot * 0.95 and is_vcp:
        buy_signal = "⏳ VCP 蓄勢密集區 (接近買入點)"
        signal_color = "green"
    elif current_price >= high_20_pivot * 0.97:
        buy_signal = "👀 逼近前高 (進入 Cheat 觀察區)"
        signal_color = "blue"
    else:
        buy_signal = "📈 穩定運行 (暫無突破型態)"
        signal_color = "gray"
        
    return {
        "rs": rs_rating,
        "buy_signal": buy_signal,
        "signal_color": signal_color,
        "current_price": round(current_price, 2)
    }

# 5. 🎛️ 雷達導航中心 (側邊欄)
st.sidebar.title("🎛️ 雷達導航中心")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 即時強制刷新數據", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
search_input = st.sidebar.text_input("🔍 手動投股尋找 (例如: TSLA, NVDA)", "").strip().upper()

# 核心連動滑桿
rs_score_min = st.sidebar.slider("🎯 篩選最低 RS 分數", min_value=10, max_value=99, value=70)

# 6. 主畫面顯示
st.title("📊 臨玖 - 雙大腦智能量化搜尋端")
st.caption("即時串接 Alpaca 數據庫 • 內置 Minervini VCP 與量化買入點提示系統")

if search_input:
    st.subheader(f"個別股票分析: {search_input}")
    with st.spinner(f"正在向 Alpaca 調取 {search_input} 最新數據..."):
        raw_data = fetch_alpaca_bars([search_input], days_back=180)
        if search_input in raw_data and len(raw_data[search_input]) > 0:
            df_stock = pd.DataFrame(raw_data[search_input])
            analysis = analytics = analyze_stock_signals(df_stock)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("最新實時價", f"${analysis['current_price']}")
            col2.metric("相對強度 (RS 分數)", f"{analysis['rs']} 分")
            col3.metric("建議買入點狀態", analysis['buy_signal'])
            
            # 純價格走勢圖 (完全移除了 150/200MA)
            df_stock['t'] = pd.to_datetime(df_stock['t'])
            df_stock.set_index('t', inplace=True)
            chart_df = df_stock[['c']].rename(columns={'c': '收盤價 (已修正拆股)'})
            st.line_chart(chart_df)
        else:
            st.error(f"❌ 未能獲取 {search_input} 數據。")
else:
    st.subheader("⚡ 當前強勢板塊 / 股票雷達監控")
    with st.spinner("🚀 正在抓取實時大數據，進行動能梯隊與買入點篩選..."):
        all_bars = fetch_alpaca_bars(FOCUS_TICKERS, days_back=180)
        
        radar_results = []
        for ticker in FOCUS_TICKERS:
            if ticker in all_bars and len(all_bars[ticker]) > 0:
                df_t = pd.DataFrame(all_bars[ticker])
                analysis = analyze_stock_signals(df_t)
                
                # 火箭動能分配
                rockets = "🚀🚀🚀🚀" if analysis['rs'] >= 90 else ("🚀🚀🚀" if analysis['rs'] >= 80 else ("🚀🚀" if analysis['rs'] >= 70 else "🚀"))
                
                radar_results.append({
                    "Ticker": ticker,
                    "最新價格 ($)": analysis['current_price'],
                    "相對強度 (RS 分數)": analysis['rs'],
                    "三階段火箭動能": rockets,
                    "💡 買入點建議提示": analysis['buy_signal']
                })
        
        if radar_results:
            df_master = pd.DataFrame(radar_results)
            
            # 依據滑桿選擇的 rs_score_min 進行動態過濾
            filtered_df = df_master[df_master["相對強度 (RS 分數)"] >= rs_score_min]
            filtered_df = filtered_df.sort_values(by="相對強度 (RS 分線)" if "相對強度 (RS 分線)" in filtered_df else "相對強度 (RS 分數)", ascending=False)
            
            # 影片要求的動態連動：標題、門檻與數量完美契合
            st.success(f"🎯 瞬間掃描完畢！符合 RS 門檻 (>= {rs_score_min}) 🚀強勢股票共有 {len(filtered_df)} 隻：")
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            
            # 特殊高亮提示：挑出今天已經觸發買入點的黃金標的
            buy_triggered = filtered_df[filtered_df["💡 買入點建議提示"].str.contains("💥")]
            if not buy_triggered.empty:
                st.balloons()
                st.markdown(f"### 🔥 【臨玖雷達警戒】今日觸發『💥 帶量突破買入點』的有：**{', '.join(buy_triggered['Ticker'].tolist())}**！請密切注意開盤突破的延續性！")
        else:
            st.warning("⚠️ 暫時無法獲取數據，請確認後台 Secret 金鑰是否正確。")
