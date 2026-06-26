import streamlit as st
# 從你剛剛建好的 views 資料夾中引入觀察名單邏輯
from app.views.watchlist import load_view

# 1. 網頁全域基本設定
st.set_page_config(
    page_title="美股自動化雷達系統",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 建立側邊欄導航 (Sidebar)
# 這樣寫不僅乾淨，還幫你留好了底。日後你想加「AI分析」或「歷史回測」分頁，直接在下面加選項即可！
st.sidebar.title("🧭 雷達導航中心")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "選擇功能分頁", 
    ["📈 動態觀測雷達"]
)

# 3. 根據側邊欄的選擇，渲染對應的畫面
if page == "📈 動態觀測雷達":
    load_view()
