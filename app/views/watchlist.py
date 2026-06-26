import streamlit as st
import pandas as pd
import datetime
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

@st.cache_data(ttl=3600)  # 快取 1 小時，避免頻繁請求導致網頁變慢
def fetch_nasdaq100_tickers():
    """自動從維基百科抓取最新納斯達克 100 成分股，完全免手動輸入"""
    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        tables = pd.read_html(url)
        # 尋找含有成分股代號的表格
        df_tickers = tables[4]  
        return df_tickers['Ticker'].tolist()
    except Exception:
        # 備用方案：萬一網路斷線，提供核心科技股
        return ["NVDA", "AMD", "SMCI", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "STX", "AAOI", "WDC", "SNDK", "SPCX", "MU", "NBIS", "MRVL", "TSLA", "AVGO"]

def load_view():
    st.header("🚀 條條大路通多頭 — 全自動強勢股篩選器")
    st.write("系統正自動掃描納斯達克 100 成分股，利用 Stan Weinstein 系統篩選出「最強勢的第二階段」龍頭股。")

    # 1. 讀取憑證
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]
    except Exception:
        st.error("❌ 密碼箱 (Secrets) 中找不到 Alpaca 憑證，請檢查設定。")
        return

    data_client = StockHistoricalDataClient(api_key, secret_key)

    # 2. 自動獲取股票池
    with st.spinner("正在自動獲取最新 Nasdaq 100 成分股名單..."):
        all_tickers = fetch_nasdaq100_tickers()
        # 為了加快初次掃描速度，我們先篩選前 50 隻進行技術型態分析
        test_tickers = all_tickers[:50] 

    # 3. 批量向 Alpaca 請求過去一年的日 K 線數據
    st.subheader("🔍 大數據量化濾網掃描中...")
    
    with st.spinner(f"正在透過 Alpaca 批量下載 {len(test_tickers)} 隻股票的一年期數據..."):
        try:
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=365)

            request_params = StockBarsRequest(
                symbol_or_symbols=test_tickers,
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date
            )
            
            # 一次性獲取所有股票數據
            bars = data_client.get_stock_bars(request_params)
            df_bars = bars.df  # 回傳多重索引 DataFrame (symbol, timestamp)
            
            strong_stocks = []

            # 4. 用程式全自動進行 Weinstein 濾網計算
            for ticker in test_tickers:
                if ticker not in df_bars.index.levels[0]:
                    continue
                    
                df_stock = df_bars.xs(ticker, level=0).sort_index()
                
                if len(df_stock) < 200:
                    continue  # 數據不足 200 天則跳過

                # 計算 50MA 和 200MA
                df_stock['50MA'] = df_stock['close'].rolling(window=50).mean()
                df_stock['200MA'] = df_stock['close'].rolling(window=200).mean()

                # 獲取最新一天的數據
                current_price = df_stock['close'].iloc[-1]
                ma50_current = df_stock['50MA'].iloc[-1]
                ma200_current = df_stock['200MA'].iloc[-1]
                
                # 獲取 20 天前的 200MA，用來判斷 200MA 趨勢是否向上
                ma200_past = df_stock['200MA'].iloc[-20]

                # 🛑 Stan Weinstein 第 2 階段黃金濾網 🛑
                # 1. 價格高於 50MA，50MA 高於 200MA
                # 2. 200MA 必須是正在向上爬升的
                if current_price > ma50_current and ma50_current > ma200_current and ma200_current > ma200_past:
                    
                    # 計算 3 個月漲幅作為「動能評分」
                    three_months_ago_price = df_stock['close'].iloc[-60]
                    momentum = ((current_price - three_months_ago_price) / three_months_ago_price) * 100
                    
                    strong_stocks.append({
                        "代號": ticker,
                        "最新收盤價": f"${current_price:,.2f}",
                        "50MA": f"${ma50_current:,.2f}",
                        "200MA": f"${ma200_current:,.2f}",
                        "近3個月漲幅": momentum
                    })

            # 5. 呈現結果
            if strong_stocks:
                df_result = pd.DataFrame(strong_stocks)
                # 根據漲幅動能從大到小排序，揪出「強勢中的強勢」
                df_result = df_result.sort_values(by="近3個月漲幅", ascending=False).reset_index(drop=True)
                
                st.success(f"🎯 掃描完畢！成功自動揪出 {len(df_result)} 隻正處於「多頭第二階段」的強勢標的：")
                
                st.dataframe(
                    df_result,
                    use_container_width=True,
                    column_config={
                        "近3個月漲幅": st.column_config.NumberColumn("動能指標 (3M 漲幅)", format="%.2f%%")
                    }
                )
            else:
                st.warning("當前市場環境較弱，暫時沒有成分股符合嚴格的第二階段多頭標準。")

        except Exception as e:
            st.error(f"❌ 自動篩選失敗: {str(e)}")
            st.info("提示：請確保 Alpaca Secrets 已經填寫正確。")
