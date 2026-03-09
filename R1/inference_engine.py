import os
import torch
import numpy as np
import pandas as pd
import joblib
import re
from datetime import datetime
from transformers import BertTokenizer
from my_utils import BertClassifier

class NewsPredictor:
    def __init__(self): 
        # 🔥 強制使用 CPU 以確保 Mac/Windows 最大相容性
        self.device = torch.device('cpu')
        print(f"🔄 初始化 AI 引擎 (Mode: Safe Local Testing)...")
        
        # 1. 載入設定 (若缺少則使用預設值，防止崩潰)
        if os.path.exists('feature_columns.joblib'):
            self.feature_cols = joblib.load('feature_columns.joblib')
        else:
            self.feature_cols = [] # 空列表備用

        if os.path.exists('emotion_le.pkl'):
            self.emotion_le = joblib.load('emotion_le.pkl')
            self.emotions = self.emotion_le.classes_
        else:
            # 預設情緒標籤 (防止缺檔崩潰)
            self.emotions = ['angry', 'bored', 'fear', 'happy', 'sad', 'surprise']
        
        # 2. 載入情緒模型 (RoBERTa)
        print("   -> 載入情緒模型...")
        self.tokenizer_emo = BertTokenizer.from_pretrained("hfl/chinese-roberta-wwm-ext-large")
        self.model_emo = BertClassifier("hfl/chinese-roberta-wwm-ext-large", len(self.emotions))
        
        if os.path.exists('best_emotion_model.bin'):
            state_dict = torch.load('best_emotion_model.bin', map_location=self.device)
            self.model_emo.load_state_dict(state_dict)
        else:
            print("⚠️ 警告：找不到 best_emotion_model.bin，情緒分析將使用隨機數值。")
            
        self.model_emo.to(self.device).eval()
        
        # 3. 載入熱度模型 (MacBERT)
        print("   -> 載入熱度模型...")
        self.tokenizer_vir = BertTokenizer.from_pretrained("hfl/chinese-macbert-base")
        self.model_vir = BertClassifier("hfl/chinese-macbert-base", 2) 
        
        if os.path.exists('best_macbert_model.bin'):
            state_dict = torch.load('best_macbert_model.bin', map_location=self.device)
            self.model_vir.load_state_dict(state_dict)
        else:
            print("⚠️ 警告：找不到 best_macbert_model.bin，熱度預測將不準確。")
            
        self.model_vir.to(self.device).eval()
        
        # 4. [關鍵修改] 嘗試載入 Meta Learner，若失敗則進入「Bypass 模式」
        self.meta_model = None
        try:
            if os.path.exists('meta_model.joblib'):
                self.meta_model = joblib.load('meta_model.joblib')
                print("✅ Meta Model 載入成功 (Stacking Mode)")
            else:
                print("⚠️ 找不到 meta_model.joblib，將切換至 [Bypass Mode]")
        except Exception as e:
            print(f"⚠️ Meta Model 版本不相容 ({e})，已自動切換至 [Bypass Mode]")
            self.meta_model = None

        print("✅ AI 引擎啟動完成！")

    def _get_bert_prob(self, model, tokenizer, text, max_len=256):
        try:
            enc = tokenizer.encode_plus(
                str(text), max_length=max_len, padding='max_length', truncation=True, return_tensors='pt'
            )
            with torch.no_grad():
                input_ids = enc['input_ids'].to(self.device)
                mask = enc['attention_mask'].to(self.device)
                out = model(input_ids, mask)
                probs = torch.softmax(out, dim=1).cpu().numpy()[0]
            return probs
        except Exception as e:
            print(f"❌ 推論錯誤: {e}")
            return np.zeros(model.classifier.out_features) # 回傳全零防止當機

    def predict(self, title, content, publish_time=None):
        # A. 資料前處理
        text_input = str(title) + " [SEP] " + str(content)[:300]
        
        # B. 產生情緒特徵
        emo_probs = self._get_bert_prob(self.model_emo, self.tokenizer_emo, text_input)
        features = {}
        for i, emo in enumerate(self.emotions):
            if i < len(emo_probs):
                features[f'prob_{emo}'] = emo_probs[i]
            else:
                features[f'prob_{emo}'] = 0.0
            
        # C. 產生 MacBERT 熱度分數
        vir_probs = self._get_bert_prob(self.model_vir, self.tokenizer_vir, text_input)
        macbert_score = vir_probs[1] if len(vir_probs) > 1 else 0.5
        features['macbert_score'] = macbert_score
        
        # D. 產生結構特徵 (簡單版)
        features['title_len'] = len(title)
        
        # E. 最終預測邏輯 (Bypass 核心)
        if self.meta_model and self.feature_cols:
            try:
                # 嘗試使用 Stacking 模型
                df_input = pd.DataFrame([features])
                # 補齊缺失欄位
                for col in self.feature_cols:
                    if col not in df_input.columns: df_input[col] = 0 
                
                final_prob = self.meta_model.predict_proba(df_input[self.feature_cols])[0][1]
            except Exception as e:
                print(f"⚠️ Stacking 預測失敗，降級使用 MacBERT 分數: {e}")
                final_prob = macbert_score
        else:
            # Bypass 模式：直接使用 MacBERT 的預測分數
            # 這在地端測試完全足夠，因為 MacBERT 貢獻了絕大部分的準確度
            final_prob = macbert_score
        
        return final_prob, features