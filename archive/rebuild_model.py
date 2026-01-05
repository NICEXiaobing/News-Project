import sys
import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import HistGradientBoostingClassifier

# ==========================================
# 💉 NumPy 2.0 -> 1.x 相容性補丁 (Magic Patch)
# ==========================================
# 目的：讓 Python 3.10 (NumPy 1.x) 能讀取 Python 3.13 (NumPy 2.x) 的 Pickle 檔
try:
    import numpy._core.numeric
except ImportError:
    print("⚠️ 偵測到 Pickle 版本來自 NumPy 2.0，正在注入相容性修正...")
    # 手動將 numpy._core 指向 numpy.core (舊版路徑)
    try:
        sys.modules['numpy._core'] = np.core
        sys.modules['numpy._core.numeric'] = np.core.numeric
        sys.modules['numpy._core.multiarray'] = np.core.multiarray
    except Exception as e:
        print(f"⚠️ 補丁注入部分失敗: {e} (若無後續錯誤可忽略)")

print(f"🚀 [System Repair] 正在為當前環境重建 Stacking 模型...")

# 1. 檢查 Cache 檔
required_files = ['cache_L1_train.npy', 'cache_L1_test.npy', 'cache_y_train.npy', 'cache_y_test.npy', 'cache_meta_train.pkl', 'cache_meta_test.pkl']
for f in required_files:
    if not os.path.exists(f):
        print(f"❌ 缺少檔案: {f}")
        print("💡 請確認您沒有刪除之前的 cache_*.npy 檔案。")
        raise SystemExit

# 2. 讀取緩存
# .npy 檔案通常跨版本相容性較好，直接讀取
L1_train = np.load('cache_L1_train.npy')
y_train = np.load('cache_y_train.npy')

# .pkl 檔案含有 DataFrame，這裡就會用到上面的補丁
try:
    X_train_meta = pd.read_pickle('cache_meta_train.pkl')
    print("✅ 成功讀取 Meta 特徵檔 (Pickle)")
except Exception as e:
    print(f"❌ 讀取 Pickle 失敗: {e}")
    print("💡 建議方案：這代表補丁失效。請直接使用 News_Data_with_Emotion_Features.csv 重新生成特徵，或者忽略 Meta 特徵僅用 MacBERT 分數測試。")
    raise SystemExit

# 3. 組合特徵
X_train_meta['macbert_score'] = L1_train

# 確保型態 (將可能存在的 Object 轉為數值)
for col in X_train_meta.columns:
    X_train_meta[col] = pd.to_numeric(X_train_meta[col], errors='coerce')

# 4. 重新訓練 (使用當前環境的 sklearn 與 numpy)
print("🏋️ 重新訓練 Meta Learner...")
meta_model = HistGradientBoostingClassifier(
    learning_rate=0.03, max_iter=500, max_depth=6,
    l2_regularization=0.1, early_stopping=True,
    class_weight='balanced', random_state=42
)
meta_model.fit(X_train_meta, y_train)

# 5. 覆蓋舊的模型檔
print("💾 儲存新版模型...")
joblib.dump(meta_model, 'meta_model.joblib')
joblib.dump(list(X_train_meta.columns), 'feature_columns.joblib')

print("✅ 修復完成！現在您的模型與當前環境完全相容了。")
print("👉 請執行: streamlit run app_professional.py")