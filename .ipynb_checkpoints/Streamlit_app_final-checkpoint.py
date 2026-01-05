import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import torch
from datetime import datetime

# ==========================================
# 0. 系統配置與 CSS 優化
# ==========================================
st.set_page_config(
    page_title="News Viral Lens | 新聞熱度風險預警系統",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# News Viral Lens v1.0\nAI 驅動的媒體決策輔助工具"
    }
)

# 專業級 CSS 樣式表
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Roboto+Mono:wght@500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
        background-color: #F8FAFC;
        color: #1E293B;
    }
    
    /* 標題與導覽列 */
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 0.5rem;
        background: -webkit-linear-gradient(45deg, #0F172A, #334155);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* 輸入區塊優化 */
    .stTextInput input, .stTextArea textarea {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 12px;
        font-size: 1rem;
        transition: all 0.2s;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #3B82F6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    
    /* 按鈕優化 */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #0F172A 0%, #334155 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        font-weight: 600;
        border-radius: 8px;
        transition: transform 0.1s, box-shadow 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        color: #E2E8F0;
    }
    
    /* 儀表板卡片 */
    .dashboard-card {
        background: white;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border: 1px solid #E2E8F0;
        overflow: hidden;
        margin-top: 20px;
    }
    
    /* 分數圈圈動畫 */
    @keyframes pulse-ring {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.1); }
        70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(0, 0, 0, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
    }
    .score-container {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 2rem;
        background: linear-gradient(to bottom, #F8FAFC, #FFFFFF);
    }
    .score-circle {
        width: 150px;
        height: 150px;
        border-radius: 50%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        background: white;
        animation: pulse-ring 2s infinite;
    }
    .score-val { font-size: 3.5rem; font-weight: 800; line-height: 1; }
    .score-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; color: #64748B; margin-top: 5px; }
    
    /* 指標條 */
    .metric-row { display: flex; align-items: center; margin-bottom: 12px; }
    .metric-label { width: 100px; font-size: 0.9rem; font-weight: 600; color: #475569; text-align: right; padding-right: 12px; }
    .metric-bar-bg { flex-grow: 1; height: 8px; background: #F1F5F9; border-radius: 99px; overflow: hidden; }
    .metric-val-text { width: 45px; text-align: right; font-size: 0.9rem; font-weight: 700; color: #334155; }
    
    /* 側邊欄優化 */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 載入推論引擎
# ==========================================
# 嘗試載入 inference_engine.py，如果失敗提供友善提示
try:
    from inference_engine import NewsPredictor
except ImportError:
    st.error("""
    ❌ **系統錯誤：找不到 `inference_engine.py`**
    
    請確保以下檔案都在同一個資料夾內：
    1. `Streamlit_app_final.py` (本檔案)
    2. `inference_engine.py` (推論核心)
    3. 模型權重檔 (如 `best_model.pth` 等)
    """)
    st.stop()

# ==========================================
# 2. 側邊欄：專案資訊
# ==========================================
with st.sidebar:
    st.markdown("### 🔮 News Viral Lens")
    st.markdown("**新聞熱度與風險預警系統**")
    st.caption("v1.0.0 Stable Release")
    
    st.markdown("---")
    
    st.markdown("#### 📖 關於本專案")
    st.info(
        """
        本系統利用 **Stacking 集成學習** 與 **情緒特徵分析**，
        協助媒體編輯台在新聞發布前預測其 **擴散潛力** 與 **風險等級**。
        """
    )
    
    st.markdown("#### 🛠️ 核心技術")
    st.markdown(
        """
        - **NLP Model**: MacBERT + RoBERTa
        - **Algorithm**: Stacking Ensemble
        - **Risk**: Focal Loss Optimization
        """
    )
    
    st.markdown("---")
    st.markdown("#### ⚠️ 免責聲明")
    st.caption("本系統預測結果僅供輔助參考，最終決策請依據專業編輯判斷。")
    
    # 裝置狀態偵測
    if torch.cuda.is_available():
        device_type = "CUDA (GPU)"
    elif torch.backends.mps.is_available():
        device_type = "MPS (Mac GPU)"
    else:
        device_type = "CPU"
    st.caption(f"🚀 Running on: {device_type}")

# ==========================================
# 3. 主程式邏輯
# ==========================================

# 標題區
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<div class="main-header">News Viral Lens Dashboard</div>', unsafe_allow_html=True)
    st.markdown("AI 驅動的媒體決策輔助工具：從流量預測到資訊品質把關")
with col_h2:
    st.markdown(f"<div style='text-align:right; color:#64748B; padding-top:10px;'>{datetime.now().strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)

st.markdown("---")

# 載入模型 (使用快取，效能優化關鍵)
@st.cache_resource
def load_engine():
    try:
        predictor = NewsPredictor()
        return predictor
    except Exception as e:
        return None

predictor = load_engine()

if predictor is None:
    st.error("❌ 模型載入失敗！請檢查模型路徑與 `inference_engine.py` 是否正確。")
    st.stop()

# 版面配置：左側輸入，右側分析
col_input, col_result = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("📝 新聞內容輸入 (Input)")
    with st.container(border=True):
        news_title = st.text_input("新聞標題 (Title)", placeholder="請輸入完整標題，包含標點符號...", max_chars=100)
        news_content = st.text_area("新聞內文 (Content)", placeholder="請貼上新聞內文或摘要 (建議 > 50 字)...", height=250)
        
        c1, c2 = st.columns(2)
        with c1:
            pub_date = st.date_input("發布日期", datetime.now())
        with c2:
            pub_time = st.time_input("發布時間", datetime.now())
            
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        btn_analyze = st.button("🚀 開始分析 (Analyze)", use_container_width=True)

with col_result:
    st.subheader("📊 預測分析報告 (Analysis)")
    
    if btn_analyze:
        if not news_title or not news_content:
            st.warning("⚠️ 請輸入標題與內文以開始分析")
        else:
            # 整合時間
            publish_dt = datetime.combine(pub_date, pub_time)
            
            with st.spinner("🤖 AI 正在進行多維度特徵掃描..."):
                time.sleep(0.5) # 模擬運算感
                
                try:
                    # 呼叫預測引擎
                    prob, feats = predictor.predict(news_title, news_content, publish_dt)
                    score = int(prob * 100)
                    
                    # 判斷邏輯
                    if score >= 80:
                        theme_color = "#DC2626" # Red
                        bg_badge = "#FEF2F2"
                        status_text = "Critical Risk / 高風險預警"
                        action_advice = "建議立即人工查核，並留意留言區風向。"
                    elif score >= 50:
                        theme_color = "#D97706" # Amber
                        bg_badge = "#FFFBEB"
                        status_text = "Warning / 潛在熱點"
                        action_advice = "具備擴散潛力，建議監控早期流量數據。"
                    else:
                        theme_color = "#10B981" # Green
                        bg_badge = "#ECFDF5"
                        status_text = "Safe / 常態資訊"
                        action_advice = "符合常態分佈，可依標準流程發布。"

                    # 情緒解析
                    emo_map = {
                        'angry': '憤怒', 'happy': '開心', 'sad': '悲傷',
                        'fear': '恐懼', 'surprise': '驚訝', 'warm': '溫馨'
                    }
                    top_emos = []
                    # 處理 feats，相容不同的回傳格式
                    if isinstance(feats, dict):
                        for k, v in feats.items():
                            # 嘗試捕捉 prob_ 開頭或直接是情緒名稱的 key
                            clean_k = k.replace('prob_', '').replace('feel_', '')
                            if clean_k in emo_map:
                                top_emos.append((emo_map[clean_k], v))
                    
                    # 排序取前三
                    top_emos = sorted(top_emos, key=lambda x: x[1], reverse=True)[:3]
                    
                    # 生成 HTML
                    metrics_html = ""
                    for label, val in top_emos:
                        pct = int(val * 100)
                        metrics_html += f"""
                        <div class="metric-row">
                            <div class="metric-label">{label}</div>
                            <div class="metric-bar-bg">
                                <div style="width: {pct}%; height: 100%; background: {theme_color};"></div>
                            </div>
                            <div class="metric-val-text">{pct}%</div>
                        </div>
                        """
                    
                    dashboard_html = f"""
                    <div class="dashboard-card">
                        <div class="score-container">
                            <div class="score-circle" style="border: 4px solid {theme_color};">
                                <div class="score-val" style="color: {theme_color};">{score}</div>
                                <div class="score-label">Viral Score</div>
                            </div>
                        </div>
                        <div style="text-align:center; padding-bottom: 20px;">
                            <span style="background:{bg_badge}; color:{theme_color}; padding:6px 16px; border-radius:20px; font-weight:700; border:1px solid {theme_color}30;">
                                {status_text}
                            </span>
                        </div>
                        <div style="padding: 0 2rem 2rem 2rem;">
                            <div style="font-size:0.8rem; color:#94A3B8; font-weight:700; margin-bottom:10px;">SENTIMENT DNA</div>
                            {metrics_html}
                            <div style="margin-top:20px; padding:15px; background:#F8FAFC; border-radius:8px; border-left:4px solid {theme_color};">
                                <div style="font-weight:700; color:#334155; font-size:0.9rem; margin-bottom:4px;">🛡️ AI 總編輯建議：</div>
                                <div style="color:#475569; font-size:0.9rem;">{action_advice}</div>
                            </div>
                        </div>
                    </div>
                    """
                    
                    st.markdown(dashboard_html, unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"分析過程中發生錯誤: {str(e)}")
                    st.info("請檢查輸入內容是否過短，或模型檔案是否完整。")

    else:
        # 預設空狀態
        st.info("👈 請在左側輸入新聞資訊以檢視分析報告")
        st.markdown(
            """
            <div style="text-align:center; opacity:0.5; margin-top:50px;">
                <div style="font-size:4rem;">🔮</div>
                <div style="color:#94A3B8;">Awaiting Input...</div>
            </div>
            """, unsafe_allow_html=True
        )