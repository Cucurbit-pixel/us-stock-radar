import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np
import plotly.graph_objects as go

# 1. 網頁全域設定
st.set_page_config(page_title="臨玖 - 雙大腦智能量化搜尋端", layout="wide")

# 2. 安全調用 Secrets 密碼箱
try:
    ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
    ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]
except KeyError:
    st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證！請先前往 Streamlit 後台設定金鑰。")
    st.stop()

# 核心升級：擴展至全美股跨板塊核心名單 (涵蓋科技、金融、醫療、消費、能源、工業)
ALL_US_MARKET_TICKERS = [
    # 科技與半導體 (Tech / Semis)
    "NVDA", "SMCI", "AMD", "AVGO", "MSFT", "AAPL", "GOOGL", "META", "NFLX", "TSLA", "QCOM", "ASML",
    # 金融與支付 (Financials)
    "JPM", "BAC", "MS", "GS", "V", "MA", "AXP",
    # 醫療與製藥 (Healthcare / Pharma)
    "LLY", "UNH", "JNJ", "MRK", "ABBV", "AMGN",
    # 零售與民生消費 (Consumer Staples & Discretionary)
    "AMZN", "WMT", "COST", "HD", "PG", "KO", "PEP", "MCD", "NKE",
    # 能源、工業與材料 (Energy / Industrials / Materials)
    "XOM", "CVX", "CAT", "GE", "HON", "UNP", "LIN"
]

# 3. Alpaca 實時大數據提取函數 (含拆股修正 + 快取優化)
@st.cache_data(ttl=600)  # 快取 10 分鐘，確保滑桿拉動時能夠瞬間反應，不重複轟炸 API
def fetch_all_market_data(symbols, days_back=150):
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
        "adjustment": "all",  # 自動校正拆股價格誤差 (如 SMCI)
        "feed": "sip"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("bars", {})
        return {}
    except Exception:
        return {}

# 4. 買入點與 RS 分數核心量化算法
def analyze_stock_signals(df):
    if df.empty or len(df) < 25:
        return {"rs": 50, "buy_signal": "數據不足", "current_price": 0}
    
    df['close'] = pd.to_numeric(df['c'])
    df['high'] = pd.to_numeric(df['h'])
    df['low'] = pd.to_numeric(df['l'])
    df['vol'] = pd.to_numeric(df['v'])
    
    current_price = df['close'].iloc[-1]
    current_vol = df['vol'].iloc[-1]
    ma_vol_20 = df['vol'].rolling(20).mean().iloc[-1]
    
    # 半年期相對強度 (RS 評分基準)
    price_6mo_ago = df['close'].iloc[-126] if len(df) >= 126 else df['close'].iloc[0]
    half_year_perf = ((current_price - price_6mo_ago) / price_6mo_ago) * 100
    rs_rating = min(max(int(50 + half_year_perf), 10), 99)
    
    # Minervini VCP 與突破買入點判定
    high_20_pivot = df['high'].iloc[-21:-1].max() if len(df) >= 21 else df['high'].max()
    range_5 = df['high'].iloc[-5:].max() - df['low'].iloc[-5:].min()
    range_20 = df['high'].iloc[-20:].max() - df['low'].iloc[-20:].min()
    is_vcp = (range_5 < range_20 * 0.5) if range_20 > 0 else False
    
    if current_price >= high_20_pivot:
        if current_vol > ma_vol_20:
            buy_signal = "💥 帶量突破買入點"
        else:
            buy_signal = "⚠️ 價格突破 (但量能不足)"
    elif current_price >= high_20_pivot * 0.95 and is_vcp:
        buy_signal = "⏳ VCP 蓄勢密集區 (接近買入點)"
    elif current_price >= high_20_pivot * 0.97:
        buy_signal = "👀 逼近前高 (進入 Cheat 觀察區)"
    else:
        buy_signal = "📈 穩定運行 (暫無突破型態)"
        
    return {
        "rs": rs_rating,
        "buy_signal": buy_signal,
        "current_price": round(current_price, 2)
    }

# 5. 🎛️ 雷達導航中心 (側邊欄)
st.sidebar.title("🎛️ 雷達導航中心")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 即時強制刷新數據", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
search_input = st.sidebar.text_input("🔍 手動個股穿透搜尋 (例如: TSLA, JPM)", "").strip().upper()

# 【核心功能】：連動滑桿
rs_score_min = st.sidebar.slider("🎯 篩選最低 RS 分數", min_value=10, max_value=99, value=70)

# 6. 主畫面顯示
st.title(" Bars 📊 臨玖 - 雙大腦智能量化搜尋端")
st.caption("全美股大盤聯網版 • 內置實心陰陽燭、自動趨勢線與量化買入點系統")

if search_input:
    st.subheader(f"個股透視面板: {search_input}")
    with st.spinner(f"正在向 Alpaca 調取 {search_input} 最新數據..."):
        raw_data = fetch_all_market_data([search_input], days_back=180)
        if search_input in raw_data and len(raw_data[search_input]) > 0:
            df_stock = pd.DataFrame(raw_data[search_input])
            analysis = analyze_stock_signals(df_stock)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("最新實時價", f"${analysis['current_price']}")
            col2.metric("相對強度 (RS 分數)", f"{analysis['rs']} 分")
            col3.metric("建議買入點狀態", analysis['buy_signal'])
            
            # 轉換數據格式供 Plotly 使用
            df_stock['t'] = pd.to_datetime(df_stock['t'])
            df_stock['o'] = pd.to_numeric(df_stock['o'])
            df_stock['h'] = pd.to_numeric(df_stock['h'])
            df_stock['l'] = pd.to_numeric(df_stock['l'])
            df_stock['c'] = pd.to_numeric(df_stock['c'])
            df_stock.set_index('t', inplace=True)
            
            # 📈 繪製專業實心陰陽燭
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df_stock.index,
                open=df_stock['o'],
                high=df_stock['h'],
                low=df_stock['l'],
                close=df_stock['c'],
                name='實心陰陽燭',
                increasing_line_color='#26a69a', increasing_fillcolor='#26a69a',  # 上漲實心綠 (美股標準)
                decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350'   # 下跌實心紅 (美股標準)
            ))
            
            # 🛠️ 自動計算並添加線性回歸趨勢線
            y_vals = df_stock['c'].values
            x_vals = np.arange(len(y_vals))
            slope, intercept = np.polyfit(x_vals, y_vals, 1)
            trend_line = slope * x_vals + intercept
            
            fig.add_trace(go.Scatter(
                x=df_stock.index,
                y=trend_line,
                mode='lines',
                name='自動線性趨勢線',
                line=dict(color='#ff9800', width=2, dash='dash')
            ))
            
            fig.update_layout(
                xaxis_rangeslider_visible=False,
                template='plotly_dark',
                height=450,
                margin=dict(l=10, r=10, t=20, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error(f"❌ 未能獲取 {search_input} 數據，或代號不在此基礎股池內。")
else:
    st.subheader("⚡ 全美股全板塊 • 強勢陣營監控雷達")
    with st.spinner("🚀 正在向 Alpaca 提取全美股大數據，進行跨板塊強勢度過濾..."):
        all_bars = fetch_all_market_data(ALL_US_MARKET_TICKERS, days_back=180)
        
        radar_results = []
        for ticker in ALL_US_MARKET_TICKERS:
            if ticker in all_bars and len(all_bars[ticker]) > 0:
                df_t = pd.DataFrame(all_bars[ticker])
                analysis = analyze_stock_signals(df_t)
                
                rockets = "🚀🚀🚀🚀" if analysis['rs'] >= 90 else ("🚀🚀🚀" if analysis['rs'] >= 80 else ("🚀🚀" if analysis['rs'] >= 70 else "🚀"))
                
                radar_results.append({
                    "Ticker": ticker,
                    "最新價格 ($)": analysis['current_price'],
                    "相對強度 (RS 分數)": analysis['rs'],
                    "動能階梯": rockets,
                    "💡 買入點建議提示": analysis['buy_signal']
                })
        
        if radar_results:
            df_master = pd.DataFrame(radar_results)
            
            # 【完美同步過濾】：當滑桿動，呢度即時過濾
            filtered_df = df_master[df_master["相對強度 (RS 分數)"] >= rs_score_min]
            filtered_df = filtered_df.sort_values(by="相對強度 (RS 分數)", ascending=False)
            
            # 【核心修改點】：對應第二段片，將寫死的 70 改為動態 {rs_score_min}，股票數量連動
            st.success(f"🎯 瞬間掃描完畢！符合 RS 門檻 (>= {rs_score_min}) 🚀強勢股票共有 {len(filtered_df)} 隻：")
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            
            # 高亮觸發买入点標的
            buy_triggered = filtered_df[filtered_df["💡 買入點建議提示"].str.contains("💥")]
            if not buy_triggered.empty:
                st.balloons()
                st.markdown(f"### 🔥 【臨玖量化警報】今日共有 **{len(buy_triggered)}** 隻跨板塊個股觸發『💥 帶量突破買入點』：**{', '.join(buy_triggered['Ticker'].tolist())}**！")
        else:
            st.warning("⚠️ 暫時無法獲取數據，請確認後台 Secret 金鑰是否正確。")
