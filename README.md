# 🛡️ News Viral Lens (Pre-Viral) | 新聞熱度預測系統

> **Coding 101 競賽專案 | 團隊：NEWS HUNTER (李明哲、何立淳)**
> AI 驅動的數位檢傷防線：將防禦推進至 $T=0$ 時刻，精準攔截混淆訊息

![Python](https://img.shields.io/badge/Python-3.10-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.30-red) ![PyTorch](https://img.shields.io/badge/PyTorch-2.0-orange) ![License](https://img.shields.io/badge/License-MIT-green)

---

## 📖 專案簡介 (Project Overview)

**News Viral Lens** 是一套針對事實查核中心與媒體編輯台設計的 **AI 雙軌預警系統**。

在生成式 AI 帶來的內容海嘯中，謠言擴散速度為真實新聞的 6 倍，傳統「事後查核」往往錯失黃金防禦窗口。本系統利用 **Semantics-First Stacking 集成學習** 技術，結合語意、結構與讀者情緒特徵，並首創 **雙軌交互驗證機制 (Dual-Track Validation)**，在新聞發布初期 ($T=0$) 即可自動預判潛力與風險，精準攔截混淆訊息與農場文。

### 🚀 核心功能與數位檢傷分級 (Digital Triage)
* 🔴 **P0 紅色警戒 (Risk ≥ 80)**：高熱度 + 具煽動性（如憤怒、恐懼），優先啟動查核。
* 🚨 **混淆訊息預警 (防禦亮點)**：AI 判定具極高爆紅潛力，但外部查無擴散共識（單一來源），精準攔截烏龍爆料。
* 🟡 **P1 橘色觀察 (50-79)**：熱度上升中，持續監控。
* 🟢 **P2 綠色安全 (<50)**：常規資訊自動歸檔，節省查核人力。

---

## 🛠️ 技術架構與創新 (Methodology & Breakthrough)

本專案建構了 24/7 全自動化資料流（涵蓋台灣 6 大主流媒體，23,000+ 筆數據），並克服熱門與一般新聞 1:4 的資料不平衡。

### 1. 多模態特徵融合 (Multi-modal Features)
* **在地語意**: 使用 `MacBERT` 精準捕捉台灣網路語境與標題黨特徵。
* **情緒 DNA (Emotion Radar)**: 使用 `RoBERTa-Large` 結合 FGM 對抗訓練進行情緒量化。針對高危害情緒（如擔憂）精準度達 88%，F1-Score 創下 **0.770** 歷史新高。
* **脈絡結構**: 萃取發布黃金時段、標點符號誘餌等環境特徵。

### 2. Semantics-First Stacking 終極架構
突破傳統單一模型瓶頸，解決基準模型 (XGBoost) 誤報率過高的「狼來了」效應：
* 將 F1-Score 躍升至 **0.7456** (+40%)。
* 在維持 **89.67% 超高召回率**（寧可錯殺不漏放）的前提下，將準確率翻倍至 **63.82%**，成功進入最佳權衡的 Target Zone。

### 3. 雙軌交互驗證 (Dual-Track Validation)
結合「AI 內在潛力預測」與「TrendValidator 外部擴散動能查證」交叉比對，絕不盲從單一 AI 分數，構成堅固防護網。

---

## 💻 快速啟動 (Quick Start)

若您希望在本地端執行本系統戰情室，請依照以下步驟操作：

### 1. 環境準備
建議使用 **Python 3.10** 以確保最佳相容性。

```bash
# 建議建立虛擬環境
conda create -n news_env python=3.10 -y
conda activate news_env