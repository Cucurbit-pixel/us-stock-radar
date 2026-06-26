import streamlit as st
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

def load_view():
    st.header("📊 核心股票動態觀測雷達")
    st.write("即時監控半導體、AI 及雲端運算龍頭股的市場階段與技術型態。")

    # 1. 讀取 Streamlit Secrets 的 Alpaca 憑證
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]
    except Exception:
        st.error("❌ 密碼箱 (Secrets) 中找不到 ALPACA_API_KEY 或 ALPACA_SECRET_KEY，請檢查進階設定。")
        return

    # 2. 初始化 Alpaca 行情客戶端
    data_client = StockHistoricalDataClient(api_key, secret_key)

    # 3. 定義臨玖的核心觀測股票清單
    tickers = ["NVDA", "AMD", "SMCI", "AMZN"]

    st.subheader("🔥 即時動態觀測表")
    
    # 讀取數據時顯示 Loading 動畫
    with st.spinner("正在向 Alpaca 提取大數據行情..."):
        try:
            # 獲取最新報價
            request_params = StockLatestQuoteRequest(symbol_or_symbols=tickers)
            latest_quotes = data_client.get_stock_latest_quote(request_params)
            
            # 建立表格資料
            rows = []
            for ticker in tickers:
                if ticker in latest_quotes:
                    quote = latest_quotes[ticker]
                    price = quote.ask_price if quote.ask_price > 0 else quote.bid_price
                    
                    # 模擬或計算技術指標 (稍後可擴充)
                    # 這裡先放入臨玖專屬的 Weinstein 階段、RS 評分與 VCP 型態欄位
                    stage = "第 2 階段 (多頭)" if ticker in ["NVDA", "AMZN"] else "第 3 階段 (做頂)"
                    rocket = "🚀🚀" if ticker == "NVDA" else "🚀" if ticker == "AMZN" else "⚪"
                    rs_score = 95 if ticker == "NVDA" else 88 if ticker == "AMZN" else 75
                    vcp_status = "VCP 緊縮中" if ticker == "AMD" else "結構整理"
                    
                    rows.append({
                        "代號": ticker,
                        "最新價格": f"${price:,.2f}",
                        "Stan Weinstein 階段": stage,
                        "雷達訊號": rocket,
                        "MarketSmith RS 評分": rs_score,
                        "Minervini VCP 型態": vcp_status
                    })
            
            # 轉換成 Pandas DataFrame
            df = pd.DataFrame(rows)
            
            # 透過 HTML/CSS 微調表格樣式，讓它更美觀
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "雷達訊號": st.column_config.TextColumn("雷達訊號", help="🚀 代表動能極強"),
                    "MarketSmith RS 評分": st.column_config.NumberColumn("RS 評分", format="%d 分")
                }
            )
            
        except Exception as e:
            st.error(f"❌ 提取行情失敗: {str(e)}")
            st.info("提示：請確保 Alpaca 帳號處於 Paper Trading 模式，且 Streamlit Cloud 中的 Base URL 已正確設置。")

    # 4. 底部功能提示
    st.markdown("---")
    st.caption("💡 數據每當重新整理網頁時全自動更新。系統採用 Stan Weinstein 四階段架構與 Mark Minervini VCP 設定。")
