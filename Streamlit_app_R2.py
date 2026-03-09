import os
# 🔥 終極護城河：關閉 Tokenizer 與 PyTorch 的底層多執行緒
# 徹底解決 Mac M 系列晶片 (Apple Silicon) 與 Streamlit 刷新機制衝突造成的 Segmentation fault
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"

import streamlit as st
import pandas as pd
import numpy as np
import subprocess
import time
import sys
import re
from datetime import datetime

# ==========================================
# 0. 系統環境檢查與匯入
# ==========================================
st.set_page_config(
    page_title="News Viral Lens | 全域戰情室",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    from inference_engine_R2 import NewsPredictor
    from trend_validator import TrendValidator
except ImportError as e:
    st.error(f"⚠️ 核心模組匯入失敗: {e}\n請確認 inference_engine.py 與 trend_validator.py 皆在同目錄下。")
    st.stop()

CRAWLER_SCRIPT = "News_Scraper_Optimized_2.py"
DATA_FILE = "News_Data.csv"

# ==========================================
# 1. 文字清洗模組
# ==========================================
def clean_text(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    stop_phrases = ["點我訂閱", "延伸閱讀", "加入會員", "更多新聞請看", "記者/", "圖／"]
    for phrase in stop_phrases:
        text = text.replace(phrase, '')
    return text.strip()

# ==========================================
# 2. 介面樣式優化 (CSS)
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
    .news-container {
        background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;
        padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .news-container:hover { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(0,0,0,0.1); }
    .risk-badge {
        display: inline-block; padding: 4px 12px; border-radius: 99px;
        font-weight: bold; font-size: 0.85rem; margin-bottom: 8px;
    }
    .risk-high { background-color: #FEE2E2; color: #DC2626; border: 1px solid #FECACA; }
    .risk-mid { background-color: #FEF3C7; color: #D97706; border: 1px solid #FDE68A; }
    .risk-low { background-color: #DCFCE7; color: #16A34A; border: 1px solid #BBF7D0; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 後台爬蟲控制核心
# ==========================================
def is_crawler_running():
    try:
        if os.name == 'posix':
            cmd = ["pgrep", "-f", CRAWLER_SCRIPT]
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        else:
            return st.session_state.get('crawler_active', False)
    except:
        return False

def start_crawler():
    if not is_crawler_running():
        # 🔥 將爬蟲輸出導入 DEVNULL，避免 Log 狂印塞爆 Streamlit 導致網頁假死
        subprocess.Popen(
            [sys.executable, CRAWLER_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        st.session_state['crawler_active'] = True
        st.toast("🚀 全域爬蟲引擎已啟動！", icon="🤖")
        time.sleep(3)
    else:
        st.toast("⚠️ 爬蟲已經在背景執行中", icon="ℹ️")

def stop_crawler():
    if os.name == 'posix':
        os.system(f"pkill -f {CRAWLER_SCRIPT}")
        os.system("pkill -f chromedriver")
    else:
        os.system(f"taskkill /F /IM python.exe /FI \"WINDOWTITLE eq {CRAWLER_SCRIPT}\"")
        os.system("taskkill /F /IM chromedriver.exe")
    st.session_state['crawler_active'] = False
    st.toast("🛑 爬蟲與監控已停止", icon="✅")

# ==========================================
# 4. 初始化 AI 引擎與驗證器
# ==========================================
@st.cache_resource
def load_ai_resources():
    with st.spinner("正在載入 Wide & Deep 模型與擴散驗證器..."):
        try:
            predictor = NewsPredictor()
            validator = TrendValidator()
            return predictor, validator
        except Exception as e:
            st.error(f"模型載入失敗: {e}")
            return None, None

predictor, validator = load_ai_resources()

# ==========================================
# 5. 側邊欄與主畫面
# ==========================================
with st.sidebar:
    st.title("🛡️ 戰情控制台")
    st.markdown("---")
    
    if is_crawler_running():
        st.success("🟢 爬蟲即時監控中")
        if st.button("🛑 停止監控"):
            stop_crawler()
            st.rerun()
    else:
        st.error("🔴 監控已離線")
        if st.button("🚀 啟動全自動監控"):
            start_crawler()
            st.rerun()

    st.markdown("---")
    # 預設關閉自動刷新，避免 Demo 時畫面一直跳動，改由手動控制節奏
    auto_refresh = st.toggle("開啟自動刷新", value=False)
    refresh_rate = st.slider("刷新頻率 (秒)", 5, 60, 10)
    
    st.markdown("---")
    st.caption("2026 Coding 101 複賽展示系統")
    st.caption("核心架構: Wide & Deep + Trend Validation")

st.title("News Viral Lens 全域戰情室")
st.markdown("透過 **NLP 語意潛力預測** 與 **外部全網擴散動能** 進行雙軌即時監控。")

# ==========================================
# 6. 讀取數據與雙軌決策展示
# ==========================================
if os.path.exists(DATA_FILE):
    try:
        df = pd.read_csv(DATA_FILE)
        
        if not df.empty:
            if 'fetch_time' in df.columns:
                # 🔥 加入 format='mixed', errors='coerce' 徹底消除 UserWarning 警告
                df['fetch_time'] = pd.to_datetime(df['fetch_time'], format='mixed', errors='coerce')
                df = df.sort_values(by='fetch_time', ascending=False)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("即時監控總量", f"{len(df)} 篇")
            m2.metric("最新進稿媒體", df.iloc[0]['media'])
            m3.metric("AI 引擎狀態", "🟢 運作中" if predictor.ai_ready else "🟡 備用模式")
            st.markdown("---")

            latest_news = df.head(5)
            
            for idx, row in latest_news.iterrows():
                raw_title = str(row['title'])
                raw_content = str(row['content'])
                clean_title_str = clean_text(raw_title)
                clean_content_str = clean_text(raw_content)
                
                try:
                    viral_score = predictor.predict(clean_title_str, clean_content_str, row.get('publish_time'))
                except Exception as e:
                    st.error(f"預測發生錯誤: {e}")
                    viral_score = 0.5
                
                trend_result = validator.check_diffusion(clean_title_str)
                
                if viral_score > 0.75:
                    risk_class, risk_label, emoji = "risk-high", "P0 紅色警戒", "🔥"
                elif viral_score > 0.5:
                    risk_class, risk_label, emoji = "risk-mid", "P1 黃色觀察", "⚠️"
                else:
                    risk_class, risk_label, emoji = "risk-low", "P2 綠色安全", "✅"

                with st.container():
                    st.markdown(f"""
                    <div class="news-container">
                        <div class="risk-badge {risk_class}">{emoji} {risk_label} | AI 潛力預測: {int(viral_score*100)}%</div>
                        <h3 style="margin: 5px 0 10px 0;">{clean_title_str}</h3>
                        <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 10px;">
                            📅 {row.get('publish_time', 'Unknown')} | 📰 {row.get('media', 'Unknown')} | 🔗 <a href="{row.get('url', '#')}" target="_blank">原始連結</a>
                        </div>
                        <div style="font-size: 0.95rem; color: #334155; line-height: 1.5; margin-bottom: 15px;">
                            {clean_content_str[:150]}... 
                        </div>
                    """, unsafe_allow_html=True)

                    c1, c2 = st.columns([3, 1])
                    with c1:
                        if trend_result['momentum'] == "HIGH":
                            st.success(f"📈 **擴散動能**：{trend_result['status_text']}")
                        elif trend_result['momentum'] == "MEDIUM":
                            st.warning(f"📊 **擴散動能**：{trend_result['status_text']}")
                        else:
                            if viral_score > 0.75:
                                st.error(f"🛑 **混淆訊息預警**：AI 判定極具爆紅潛力，但 {trend_result['status_text']}。請留意是否為農場文或獨家烏龍，需多方查證。")
                            else:
                                st.info(f"❄️ **擴散動能**：{trend_result['status_text']}")
                    
                    st.markdown("</div>", unsafe_allow_html=True)

        else:
            st.info("📭 等待資料進稿中... 請啟動爬蟲。")
            
    except Exception as e:
        st.error(f"讀取數據錯誤: {e}")
else:
    st.warning("⚠️ 尚未建立資料庫，請點擊左側啟動全自動監控。")

# 自動刷新機制
if auto_refresh and is_crawler_running():
    time.sleep(refresh_rate)
    st.rerun()