import os
import torch
import numpy as np
import pandas as pd
import joblib
import re
from datetime import datetime
from transformers import BertTokenizer
from my_utils import BertClassifier # 引用 my_utils

class NewsPredictor:
    def __init__(self): 
        # 🔥 [關鍵修正] 強制使用 CPU，解決 M4 Pro + Python 3.13 的崩潰問題
        self.device = torch.device('cpu')
        print(f"🔄 初始化 AI 引擎 (Mode: Stable CPU)...")
        
        # 1. 載入設定與工具
        if not os.path.exists('feature_columns.joblib') or not os.path.exists('emotion_le.pkl'):
             raise FileNotFoundError("缺少必要的設定檔 (feature_columns.joblib 或 emotion_le.pkl)")

        self.feature_cols = joblib.load('feature_columns.joblib')
        self.emotion_le = joblib.load('emotion_le.pkl')
        self.emotions = self.emotion_le.classes_
        
        # 2. 載入情緒模型 (RoBERTa)
        if not os.path.exists('best_emotion_model.bin'):
            raise FileNotFoundError("找不到 best_emotion_model.bin")
            
        self.tokenizer_emo = BertTokenizer.from_pretrained("hfl/chinese-roberta-wwm-ext-large")
        self.model_emo = BertClassifier("hfl/chinese-roberta-wwm-ext-large", len(self.emotions))
        self.model_emo.load_state_dict(torch.load('best_emotion_model.bin', map_location=self.device))
        self.model_emo.to(self.device).eval()
        
        # 3. 載入熱度模型 (MacBERT)
        self.tokenizer_vir = BertTokenizer.from_pretrained("hfl/chinese-macbert-base")
        self.model_vir = BertClassifier("hfl/chinese-macbert-base", 2) 
        
        if os.path.exists('best_macbert_model.bin'):
            self.model_vir.load_state_dict(torch.load('best_macbert_model.bin', map_location=self.device))
        else:
            print("⚠️ 警告：找不到 best_macbert_model.bin，將使用隨機初始化模型")
            
        self.model_vir.to(self.device).eval()
        
        # 4. 載入 Meta Learner
        if not os.path.exists('meta_model.joblib'):
            raise FileNotFoundError("找不到 meta_model.joblib")
            
        self.meta_model = joblib.load('meta_model.joblib')
        print("✅ AI 引擎載入完畢 (Stable)")

    def _get_bert_prob(self, model, tokenizer, text, max_len=256):
        enc = tokenizer.encode_plus(
            str(text), max_length=max_len, padding='max_length', truncation=True, return_tensors='pt'
        )
        with torch.no_grad():
            input_ids = enc['input_ids'].to(self.device)
            mask = enc['attention_mask'].to(self.device)
            out = model(input_ids, mask)
            probs = torch.softmax(out, dim=1).cpu().numpy()[0]
        return probs

    def predict(self, title, content, publish_time=None):
        # A. 資料前處理
        text_input = str(title) + " [SEP] " + str(content)[:300]
        
        # B. 產生情緒特徵
        emo_probs = self._get_bert_prob(self.model_emo, self.tokenizer_emo, text_input)
        features = {}
        for i, emo in enumerate(self.emotions):
            features[f'prob_{emo}'] = emo_probs[i]
            
        # C. 產生 MacBERT 熱度分數
        vir_probs = self._get_bert_prob(self.model_vir, self.tokenizer_vir, text_input)
        features['macbert_score'] = vir_probs[1]
        
        # D. 產生結構特徵
        features['title_len'] = len(title)
        features['punct_count'] = title.count('!') + title.count('！') + title.count('?') + title.count('？')
        features['has_digit'] = 1 if re.search(r'\d', title) else 0
        
        # E. 時間特徵
        if publish_time is None: publish_time = datetime.now()
        features['hour'] = publish_time.hour
        features['is_weekend'] = 1 if publish_time.weekday() >= 5 else 0
        features['is_prime_time'] = 1 if (11 <= publish_time.hour <= 13) or (18 <= publish_time.hour <= 20) else 0
        features['is_work_hour'] = 1 if 9 <= publish_time.hour <= 18 else 0
        
        # 模擬特徵
        features['viral_latency_hours'] = np.nan 
        features['is_instant_viral'] = 0
        
        # F. 組合
        df_input = pd.DataFrame([features])
        for col in self.feature_cols:
            if col not in df_input.columns: df_input[col] = np.nan 
        
        # G. 最終預測
        final_prob = self.meta_model.predict_proba(df_input[self.feature_cols])[0][1]
        
        return final_prob, features