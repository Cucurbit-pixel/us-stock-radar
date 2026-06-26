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

# 3. Alpaca實時大數據提取函數 (含拆股修正)
def fetch_alpaca_bars(symbols, days_back=365):
    """
    從 Alpaca API 抓取歷史 K 線數據
    自動加入 adjustment=all 修正所有股票拆股(Split)帶來的價格誤差
    """
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
        "adjustment": "all",  # 核心：自動校正如 SMCI 等股票拆股後的真實歷史價格
        "feed": "sip"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("bars", {})
        else:
            st.sidebar.error(f"Alpaca API 報錯: {response.status_code}")
            return {}
    except Exception as e:
        st.sidebar.error(f"網絡連接失敗: {str(e)}")
        return {}

# 4. Stan Weinstein 階段與 RS 分數核心算法
def analyze_weinstein_stage(df):
    if df.empty or len(df) < 200:
        return {"stage": "數據不足", "color": "gray", "rs": 50, "ma150": 0, "ma200": 0}
    
    # 計算 150MA 與 200MA
    df['150MA'] = df['c'].rolling(window=150).mean()
    df['200MA'] = df['c'].rolling(window=200).mean()
    
    current_price = df['c'].iloc[-1]
    ma150_curr = df['150MA'].iloc[-1]
    ma200_curr = df['200MA'].iloc[-1]
    ma200_prev = df['200MA'].iloc[-20] if len(df) > 20 else df['200MA'].iloc[0] # 20天前的200MA
    
    # 半年期相對強度 (RS 分數基準)
    price_6mo_ago = df['c'].iloc[-126] if len(df) >= 126 else df['c'].iloc[0]
    half_year_perf = ((current_price - price_6mo_ago) / price_6mo_ago) * 100
    rs_rating = min(max(int(50 + half_year_perf), 10), 99)
    
    # Stan Weinstein 四階段判斷邏輯
    # 第二階段 (多頭主升浪)：價格 > 150MA > 200MA，且 200MA 向上揚
    if current_price > ma150_curr and ma150_curr > ma200_curr and ma200_curr > ma200_prev:
        stage = "第 2 階段 (🚀 強勢主升浪)"
        color = "green"
    # 第四階段 (空頭下跌浪)：價格 < 150MA < 200MA
    elif current_price < ma150_curr and ma150_curr < ma200_curr:
        stage = "第 4 階段 (⚠️ 空頭清算浪)"
        color = "red"
    # 第一階段 (底部築底) 或 第三階段 (高檔盤整)
    else:
        if ma200_curr > ma200_prev:
            stage = "第 3 階段 (🔄 高位做頭/震盪)"
            color = "orange"
        else:
            stage = "第 1 階段 (💤 底部打底蓄勢)"
            color = "blue"
            
    return {
        "stage": stage,
        "color": color,
        "rs": rs_rating,
        "ma150": round(ma150_curr, 2),
        "ma200": round(ma200_curr, 2),
        "current_price": round(current_price, 2)
    }

# 5. 🚀 側邊欄控制中心
st.sidebar.title("🎛️ 雙大腦導航中心")
st.sidebar.markdown("---")

# 手動搜尋輸入
search_input = st.sidebar.text_input("🔍 實時個股穿透分析 (輸入代號):", "").strip().upper()

# 門檻篩選
min_rs = st.sidebar.slider("🎯 核心雷達最低 RS 門檻", 10, 99, 70)

if st.sidebar.button("🔄 刷新大數據庫", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# 6. 主畫面排版
st.title("📊 臨玖 - 雙大腦智能量化搜尋端")
st.caption("即時串接 Alpaca 數據庫 • Stan Weinstein 階段突破識別系統")

# 邏輯分流 A：如果使用者有手動輸入搜尋特定股票
if search_input:
    st.header(f"🔍 個股全視角穿透：{search_input}")
    
    with st.spinner(f"正在向 Alpaca 調取 {search_input} 經拆股調整後的最新數據..."):
        raw_data = fetch_alpaca_bars([search_input], days_back=365)
        
        if search_input in raw_data and len(raw_data[search_input]) > 0:
            # 轉換為 DataFrame
            df_stock = pd.DataFrame(raw_data[search_input])
            df_stock['t'] = pd.to_datetime(df_stock['t'])
            df_stock.set_index('t', inplace=True)
            
            # 計算指標
            analysis = analyze_weinstein_stage(df_stock)
            
            # 儀表板數據顯示
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("最新實時價", f"${analysis['current_price']}")
            col2.metric(" Weinstein 階段", analysis['stage'])
            col3.metric("相對強度 (RS Score)", f"{analysis['rs']} 分")
            col4.metric("150MA / 200MA", f"${analysis['ma150']} / ${analysis['ma200']}")
            
            st.markdown("---")
            st.subheader("📈 Stan Weinstein 趨勢對照圖 (日K線與移動平均線)")
            
            # 建立圖表畫布數據
            df_stock['150MA'] = df_stock['c'].rolling(window=150).mean()
            df_stock['200MA'] = df_stock['c'].rolling(window=200).mean()
            
            chart_df = df_stock[['c', '150MA', '200MA']].rename(columns={
                'c': '收盤價 (Split-adjusted)',
                '150MA': '150日 趨勢線',
                '200MA': '200日 生命線'
            })
            
            # 繪製趨勢圖
            st.line_chart(chart_df, height=400)
            
            # 突破訊號文字提示
            if df_stock['c'].iloc[-1] > df_stock['150MA'].iloc[-1] and df_stock['c'].iloc[-2] <= df_stock['150MA'].iloc[-2]:
                st.success(f"🚀 【突破訊號】{search_input} 今日成功帶量向上突破 150日趨勢線，密切留意 VCP 型態是否完成！")
                
        else:
            st.error(f"❌ 未能從 Alpaca 獲取到 {search_input} 的數據，請檢查代號是否正確。")

# 邏輯分流 B：預設主畫面的自動化大數據雷達
else:
    st.header("⚡ 核心量化梯隊自動監達 (科技/半導體焦點)")
    
    with st.spinner("自動化全天候掃描焦點股池中..."):
        all_bars = fetch_alpaca_bars(FOCUS_TICKERS, days_back=365)
        
        radar_results = []
        for ticker in FOCUS_TICKERS:
            if ticker in all_bars and len(all_bars[ticker]) > 0:
                df_t = pd.DataFrame(all_bars[ticker])
                analysis = analyze_weinstein_stage(df_t)
                
                # 動態火箭符號
                rockets = "🚀🚀🚀" if analysis['rs'] >= 90 else ("🚀🚀" if analysis['rs'] >= 70 else "🔹")
                
                radar_results.append({
                    "代號": ticker,
                    "最新價格 ($)": analysis['current_price'],
                    "Weinstein 階段": analysis['stage'],
                    "相對強度 (RS 分數)": analysis['rs'],
                    "動能強度": rockets,
                    "150MA": analysis['ma150'],
                    "200MA": analysis['ma200']
                })
        
        if radar_results:
            df_radar = pd.DataFrame(radar_results)
            
            # 過濾滿足使用者設定的最低 RS 分數
            filtered_radar = df_radar[df_radar["相對強度 (RS 分數)"] >= min_rs]
            filtered_radar = filtered_radar.sort_values(by="相對強度 (RS 分數)", ascending=False)
            
            st.success(f"🎯 自動掃描完成！目前共有 {len(filtered_radar)} 隻股票符合最低 RS >= {min_rs} 門檻：")
            st.dataframe(filtered_radar, use_container_width=True, hide_index=True)
            
            # 額外分組提示：直接挑出 Stage 2 的股票
            stage2_stocks = filtered_radar[filtered_radar["Weinstein 階段"].str.contains("2")]
            if not stage2_stocks.empty:
                st.info(f"💡 臨玖小提示：目前處於 **第二階段（強勢主升浪）** 且符合門檻的標的有：{', '.join(stage2_stocks['代號'].tolist())}。入選 Weinstein 系統核心觀察範圍。")
        else:
            st.warning("⚠️ 暫時無法從 API 獲取任何股池數據，請確認後台 Secret 金鑰是否正確填寫。")
