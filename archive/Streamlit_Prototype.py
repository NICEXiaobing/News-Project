import streamlit as st
import pandas as pd
import numpy as np
import time
import re

# ==========================================
# 1. 頁面設定 (Page Config)
# ==========================================
st.set_page_config(
    page_title="AI 總編輯 - 新聞熱度預測",
    page_icon="📰",
    layout="centered",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 美化
st.markdown("""
    <style>
    .big-font { font-size:30px !important; font-weight: bold; color: #FF4B4B; }
    .stButton>button { width: 100%; border-radius: 20px; }
    .metric-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 模擬模型 (Mock Model)
# ==========================================
class MockModel:
    def predict_proba(self, features):
        # 模擬：根據標題長度和驚嘆號給出一個假機率
        score = 0.3
        # 簡單規則：有驚嘆號或數字就加分
        if features['punct_count'] > 0: score += 0.3
        if features['has_digit'] > 0: score += 0.2
        if features['title_len'] > 15: score += 0.1
        
        # 確保在 0~1 之間
        final_score = min(score + np.random.uniform(-0.1, 0.1), 0.99)
        return [[1-final_score, final_score]]

    def predict(self, features):
        prob = self.predict_proba(features)[0][1]
        return 1 if prob > 0.5 else 0

@st.cache_resource
def load_model():
    """
    載入模型函數。
    """
    time.sleep(1) # 模擬載入時間
    return MockModel()

# ==========================================
# 3. 特徵處理函數 (Feature Engineering)
# ==========================================
def extract_features(text):
    text = str(text)
    return {
        'title_len': len(text),
        'punct_count': text.count('!') + text.count('！') + text.count('?') + text.count('？'),
        'has_digit': 1 if re.search(r'\d', text) else 0
    }

# ==========================================
# 4. 主介面邏輯 (Main UI)
# ==========================================
def main():
    # --- 側邊欄 ---
    with st.sidebar:
        # 使用簡單的圖示或替代圖片
        st.header("⚙️ 設定面板")
        st.info("此系統利用 AI 模型預測新聞標題是否具備「爆紅潛力」。")
        st.markdown("---")
        st.write("🔧 **模型設定**")
        model_type = st.selectbox("選擇模型", ["XGBoost (Hybrid)", "RoBERTa (Deep Learning)", "LightGBM (Fast)"])
        threshold = st.slider("熱度判定門檻", 0.0, 1.0, 0.5, 0.05)
        st.markdown("---")
        st.caption("Designed by AI Editor Team")

    # --- 主標題 ---
    st.markdown('<p class="big-font">🔥 AI 總編輯：新聞熱度預測系統</p>', unsafe_allow_html=True)
    st.write("請輸入新聞標題，AI 將為您分析其潛在流量與熱度。")

    # --- 輸入區 ---
    news_title = st.text_area("📰 請輸入新聞標題：", height=100, placeholder="例如：驚！颱風假真的來了？氣象局最新回應...")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_btn = st.button("🚀 開始預測 (Predict)", type="primary")

    # --- 預測邏輯 ---
    if analyze_btn:
        if not news_title:
            st.warning("⚠️ 請輸入標題後再試！")
        else:
            # 顯示進度條
            with st.spinner('🤖 AI 正在分析語意與特徵...'):
                # 1. 載入模型
                model = load_model()
                
                # 2. 提取特徵
                feats = extract_features(news_title)
                
                # 3. 預測
                probs = model.predict_proba(feats)
                prob_hot = probs[0][1]  # 熱門的機率
                
                time.sleep(0.5) # 增加一點儀式感

            # --- 結果顯示區 ---
            st.markdown("### 📊 分析結果報告")
            
            # 使用 container 框起來
            with st.container():
                # 上半部：結果大字
                r_col1, r_col2 = st.columns([1, 1])
                
                with r_col1:
                    st.write("#### 預測判定")
                    if prob_hot > threshold:
                        st.markdown(f"# 🔥 **熱門新聞**")
                        st.success("這則標題具有高度爆紅潛力！")
                    else:
                        st.markdown(f"# 🧊 **一般新聞**")
                        st.info("這則標題較為平鋪直敘。")
                
                with r_col2:
                    st.write("#### 爆紅指數 (Viral Score)")
                    st.metric(label="Probability", value=f"{prob_hot*100:.1f}%", delta=f"門檻: {threshold*100:.0f}%")
                    st.progress(prob_hot)

            # 下半部：特徵解析 (Explainability)
            st.markdown("---")
            st.subheader("🧐 AI 看到了什麼？ (特徵解析)")
            
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                st.metric("字數長度", f"{feats['title_len']} 字", help="過短或過長都可能影響閱讀意願")
            with f_col2:
                st.metric("情緒標點", f"{feats['punct_count']} 個", help="驚嘆號與問號能有效提升點擊率")
            with f_col3:
                digit_status = "有 ✅" if feats['has_digit'] else "無 ❌"
                st.metric("包含數字", digit_status, help="具體的數字通常更吸睛")

            # 若是熱門新聞，給出建議
            if prob_hot < threshold:
                st.markdown("### 💡 AI 修改建議")
                st.write("- 試著加入**具體數字**（例如：3大關鍵、6000元）。")
                st.write("- 增加**情緒性標點**（！或？）。")
                st.write("- 使用**誘餌詞**（例如：驚、曝光、結局）。")

if __name__ == "__main__":
    main()