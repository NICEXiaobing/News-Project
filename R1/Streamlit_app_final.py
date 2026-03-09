import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import torch
from datetime import datetime

# ==========================================
# 0. 系統配置
# ==========================================
st.set_page_config(
    page_title="News Viral Lens | 新聞熱度風險預警系統",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# News Viral Lens v1.0\nAI 驅動的查核輔助工具"
    }
)

# ==========================================
# 1. 商業級 CSS 優化 (強制視覺一致性)
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Roboto+Mono:wght@500&display=swap');
    
    /* 全域字體設定 */
    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
        color: #1E293B; /* 強制深灰字體，防止深色模式反白 */
    }
    
    /* --- 側邊欄專屬修復 (Sidebar Fix) --- */
    /* 這裡強制覆蓋 Streamlit 的預設行為，確保側邊欄一定是白底黑字 */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0;
    }
    
    /* 側邊欄內的所有文字強制深色 */
    section[data-testid="stSidebar"] * {
        color: #334155 !important;
    }
    
    /* 側邊欄標題特化 */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3 {
        color: #0F172A !important;
    }

    /* --- 主畫面標題 --- */
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 0.2rem;
        background: -webkit-linear-gradient(0deg, #1E293B, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .sub-header {
        font-size: 1rem;
        color: #64748B;
        font-weight: 500;
        margin-bottom: 2rem;
        border-left: 4px solid #3B82F6;
        padding-left: 12px;
    }
    
    /* --- 輸入框優化 --- */
    .stTextInput input, .stTextArea textarea {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 12px;
        font-size: 1rem;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #3B82F6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    
    /* --- 按鈕優化 (漸層藍) --- */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: white !important;
        font-weight: 600;
        border: none;
        padding: 0.7rem 1rem;
        border-radius: 8px;
        transition: transform 0.1s, box-shadow 0.2s;
        margin-top: 10px;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px -3px rgba(37, 99, 235, 0.25);
        color: #FFFFFF !important;
    }
    
    /* --- 儀表板卡片 --- */
    .dashboard-card {
        background: white;
        border-radius: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
        border: 1px solid #E2E8F0;
        overflow: hidden;
        margin-top: 10px;
    }
    
    /* 分數圈圈 */
    .score-container {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 2.5rem;
        background: radial-gradient(circle at center, #F8FAFC 0%, #FFFFFF 70%);
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
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
        position: relative;
    }
    .score-val { font-size: 3.5rem; font-weight: 800; line-height: 1; letter-spacing: -2px;}
    .score-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: #64748B; margin-top: 5px; font-weight: 700; }

    /* 查核建議區塊 */
    .advice-box {
        padding: 1.5rem;
        background: #F8FAFC;
        border-top: 1px solid #E2E8F0;
    }
    
    /* 指標條 */
    .metric-row { display: flex; align-items: center; margin-bottom: 14px; }
    .metric-label { width: 90px; font-size: 0.9rem; font-weight: 600; color: #475569; text-align: right; padding-right: 15px; }
    .metric-bar-bg { flex-grow: 1; height: 10px; background: #F1F5F9; border-radius: 99px; overflow: hidden; }
    .metric-val-text { width: 45px; text-align: right; font-size: 0.9rem; font-weight: 700; color: #334155; padding-left: 10px;}
    
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 載入引擎
# ==========================================
try:
    from inference_engine import NewsPredictor
except ImportError:
    st.error("❌ 系統錯誤：找不到 inference_engine.py")
    st.stop()

@st.cache_resource
def load_engine():
    try:
        return NewsPredictor()
    except Exception as e:
        return None

predictor = load_engine()

if predictor is None:
    st.error("❌ 模型載入失敗！請檢查模型權重檔。")
    st.stop()

# ==========================================
# 3. 側邊欄 (Sidebar)
# ==========================================
with st.sidebar:
    st.markdown("### 🛡️ News Viral Lens")
    st.markdown("**新聞熱度與風險預警系統**")
    st.caption("v1.0.0 Stable | Coding 101")
    
    st.markdown("---")
    st.markdown("#### 🎯 系統目標")
    st.info(
        """
        協助查核人員在新聞發布初期，
        識別具有 **病毒式傳播潛力** 的高風險內容，
        以利提前部署查核資源。
        """
    )
    
    st.markdown("#### ⚙️ 系統狀態")
    st.markdown(f"- **Engine**: `NewsPredictor v1`")
    st.markdown(f"- **Device**: `{'GPU (Accelerated)' if torch.cuda.is_available() else 'CPU (Safe Mode)'}`")
    
    st.markdown("---")
    st.markdown("<div style='text-align: center; color: #94A3B8; font-size: 0.8rem;'>© 2026 Coding 101 Team</div>", unsafe_allow_html=True)

# ==========================================
# 4. 主畫面佈局
# ==========================================

st.markdown('<div class="main-header">News Viral Lens Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI 驅動的查核輔助工具：從流量預測到資訊品質把關</div>', unsafe_allow_html=True)

col_input, col_result = st.columns([1.1, 0.9], gap="large")

# --- 左欄：輸入區 ---
with col_input:
    st.subheader("📝 新聞內容輸入")
    with st.container():
        news_title = st.text_input("新聞標題 (Title)", placeholder="請輸入完整標題...", help="標題中的關鍵字與標點符號是重要的預測特徵")
        news_content = st.text_area("新聞內文 (Content)", placeholder="請貼上新聞內文 (建議 > 50 字)...", height=350)
        
        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        
        # 發布時間自動鎖定為當下
        publish_dt = datetime.now()
        
        btn_analyze = st.button("🚀 啟動風險評估 (Analyze)", use_container_width=True)

# --- 右欄：結果區 ---
with col_result:
    st.subheader("📊 風險評估報告")
    
    if btn_analyze:
        # === 防呆機制 (Validation) ===
        if not news_title:
            st.warning("⚠️ 請輸入「新聞標題」以進行分析")
        elif not news_content:
            st.warning("⚠️ 請輸入「新聞內文」以進行分析")
        elif len(news_content) < 30:
            st.warning("⚠️ 內文過短 (低於 30 字)，可能導致 AI 誤判，請補充更多內容。")
        else:
            # === 開始分析 ===
            with st.spinner("🤖 AI 正在進行多維度風險掃描..."):
                time.sleep(0.8) # UI 體驗延遲
                
                try:
                    prob, feats = predictor.predict(news_title, news_content, publish_dt)
                    score = int(prob * 100)
                    
                    # === 查核導向分級邏輯 ===
                    if score >= 80:
                        theme_color = "#DC2626" # Red
                        bg_badge = "#FEF2F2"
                        status_text = "Critical Risk / 高風險"
                        action_advice = "此內容具備極高擴散潛力與情緒煽動性。建議 **列為 P0 最優先查核**，並立即啟動社群輿情監控。"
                    elif score >= 50:
                        theme_color = "#D97706" # Amber
                        bg_badge = "#FFFBEB"
                        status_text = "Warning / 潛在熱點"
                        action_advice = "此內容具備擴散潛力。若涉及爭議議題，建議 **列為 P1 關注**，並預備澄清資料。"
                    else:
                        theme_color = "#10B981" # Green
                        bg_badge = "#ECFDF5"
                        status_text = "Safe / 常態資訊"
                        action_advice = "擴散風險較低，符合常態分佈。建議 **列為 P2 一般監控**，依標準流程處理即可。"

                    # === 情緒解析 ===
                    emo_map = {'angry': '憤怒', 'happy': '開心', 'sad': '悲傷', 'fear': '恐懼', 'surprise': '驚訝', 'warm': '溫馨'}
                    top_emos = []
                    if isinstance(feats, dict):
                        for k, v in feats.items():
                            clean_k = k.replace('prob_', '').replace('feel_', '')
                            if clean_k in emo_map:
                                top_emos.append((emo_map[clean_k], v))
                    top_emos = sorted(top_emos, key=lambda x: x[1], reverse=True)[:3]
                    
                    # === HTML 渲染 (安全無縮排) ===
                    html = []
                    html.append(f'<div class="dashboard-card">')
                    
                    # 1. 儀表板核心
                    html.append(f'<div class="score-container">')
                    html.append(f'<div class="score-circle" style="border: 6px solid {theme_color};">')
                    html.append(f'<div class="score-val" style="color: {theme_color};">{score}</div>')
                    html.append(f'<div class="score-label">Risk Score</div></div></div>')
                    
                    # 2. 狀態標籤
                    html.append(f'<div style="text-align:center; padding-bottom: 20px; border-bottom: 1px solid #F1F5F9;">')
                    html.append(f'<span style="background:{bg_badge}; color:{theme_color}; padding:6px 16px; border-radius:20px; font-weight:700; border:1px solid {theme_color}30;">{status_text}</span></div>')
                    
                    # 3. 情緒 DNA
                    html.append(f'<div style="padding: 1.5rem;">')
                    html.append(f'<div style="font-size:0.8rem; color:#94A3B8; font-weight:700; margin-bottom:12px; letter-spacing:1px;">EMOTION DNA</div>')
                    for label, val in top_emos:
                        pct = int(val * 100)
                        html.append(f'<div class="metric-row"><div class="metric-label">{label}</div>')
                        html.append(f'<div class="metric-bar-bg"><div style="width: {pct}%; height: 100%; background: {theme_color};"></div></div>')
                        html.append(f'<div class="metric-val-text">{pct}%</div></div>')
                    html.append(f'</div>')
                    
                    # 4. 查核建議
                    html.append(f'<div class="advice-box" style="border-left: 4px solid {theme_color};">')
                    html.append(f'<div style="font-weight:700; color:#334155; font-size:0.9rem; margin-bottom:5px;">🛡️ AI 查核建議：</div>')
                    html.append(f'<div style="color:#475569; font-size:0.9rem; line-height: 1.6;">{action_advice}</div></div>')
                    
                    html.append(f'</div>') # End Card
                    
                    st.markdown("".join(html), unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"分析錯誤: {str(e)}")
    else:
        # 空狀態
        st.info("👈 請在左側輸入新聞資訊")
        st.markdown("""
            <div style='text-align:center; opacity:0.1; margin-top:60px;'>
                <div style='font-size:6rem; filter: grayscale(100%);'>🛡️</div>
            </div>
        """, unsafe_allow_html=True)