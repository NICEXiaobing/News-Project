# 🛡️ News Viral Lens | 新聞熱度風險預警系統

> **Coding 101 競賽專案**
> AI 驅動的查核輔助工具：從流量預測到資訊品質把關

![Python](https://img.shields.io/badge/Python-3.10-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.30-red) ![PyTorch](https://img.shields.io/badge/PyTorch-2.0-orange) ![License](https://img.shields.io/badge/License-MIT-green)

---

## 📖 專案簡介 (Project Overview)

**News Viral Lens** 是一套針對事實查核中心與媒體編輯台設計的 **AI 預警系統**。

在假新聞與極端言論快速傳播的時代，查核人員往往面臨「資訊過載」的挑戰。本系統利用 **Stacking 集成學習 (Ensemble Learning)** 技術，結合 **MacBERT** 熱度預測與 **RoBERTa** 情緒分析，在新聞發布初期即可預測其 **「擴散潛力」** 與 **「風險等級」**，協助查核人員將有限的資源優先投入高風險內容的查核。

### 🚀 核心功能
* **Risk Assessment**: 自動將新聞分為 `P0 (高危)`、`P1 (警告)`、`P2 (安全)` 三級。
* **Viral Score Prediction**: 預測新聞潛在的擴散熱度分數。
* **Sentiment DNA**: 解析文本的情緒組成（憤怒、悲傷、快樂等），識別煽動性內容。
* **Interactive Dashboard**: 提供直覺的視覺化儀表板，支援即時分析。

---

## 🛠️ 技術架構 (Technical Architecture)

本專案採用 **Two-Stage Stacking Strategy** 以提升預測準確度與泛化能力：

1.  **Level-1 Base Models (基模型)**:
    * 🔥 **Viral Model**: 使用 `hfl/chinese-macbert-base` 提取文本語意特徵，預測基礎熱度。
    * 🎭 **Emotion Model**: 使用 `hfl/chinese-roberta-wwm-ext-large` 進行多標籤情緒分類。
2.  **Level-2 Meta Learner (元模型)**:
    * 使用 **HistGradientBoosting** 結合上述特徵與時間參數，進行最終的風險決策。

---

## 💻 快速啟動 (Quick Start)

若您希望在本地端執行本系統，請依照以下步驟操作：

### 1. 環境準備
建議使用 **Python 3.10** 以確保最佳相容性。

```bash
# 建議建立虛擬環境
conda create -n news_env python=3.10 -y
conda activate news_env
2. 安裝依賴套件

Bash
pip install -r requirements.txt
3. 啟動系統

Bash
streamlit run Streamlit_app_final.py
啟動後，瀏覽器將自動開啟操作介面 (預設為 http://localhost:8501)。

📂 專案結構 (Project Structure)
Plaintext
News_Projects/
├── .streamlit/             # 系統介面設定檔 (強制淺色主題)
├── archive/                # 🧪 實驗紀錄與舊版開發檔案 (Development Log)
├── Streamlit_app_final.py  # 🚀 應用程式主入口 (Main App)
├── inference_engine.py     # 🧠 AI 推論核心引擎
├── my_utils.py             # 🔧 模型架構定義與工具函式
├── requirements.txt        # 📦 專案依賴套件清單
├── feature_columns.joblib  # 特徵定義檔
├── meta_model.joblib       # Stacking Meta 模型權重
└── README.md               # 專案說明文件
⚠️ 注意事項
模型權重: 由於 GitHub 檔案大小限制，部分大型模型權重 (.bin / .pth) 若未包含在 Repo 中，請自行訓練或聯繫開發團隊。

硬體需求: 系統支援 CPU (Safe Mode) 與 GPU (Accelerated Mode)。在 Mac M系列晶片上會自動適配 MPS 加速（若版本支援），否則將以 CPU 穩定模式運行。

👨‍💻 開發團隊
Coding 101 Team

Developer: Coding 101 參賽團隊

Contact: [您的 Email 或留空]

Created with ❤️ for Coding 101 Competition