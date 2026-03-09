import os
import re
import numpy as np
import pandas as pd
from datetime import datetime

# 嘗試匯入 AI 套件，若無安裝則使用安全模式
try:
    import torch
    import joblib
    from transformers import BertTokenizer
    from my_utils import BertClassifier  # 依賴您在 Jupyter 建立的 my_utils.py
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

class NewsPredictor:
    def __init__(self):
        # 🔥 終極穩定版：強制使用 CPU，徹底解決 Mac MPS 多執行緒崩潰 (Segmentation Fault) 問題
        self.device = torch.device("cpu")
        print(f"🔄 初始化 AI 引擎 (Device: {self.device})...")
        
        self.ai_ready = False
        
        if AI_AVAILABLE:
            try:
                # 1. 載入 Tokenizer
                print("   -> 載入 Tokenizer...")
                self.tokenizer_emo = BertTokenizer.from_pretrained("hfl/chinese-roberta-wwm-ext-large")
                self.tokenizer_mac = BertTokenizer.from_pretrained("hfl/chinese-macbert-base")
                
                # 2. 載入 Emotion 模型與標籤
                print("   -> 載入 Emotion 語意模型...")
                self.emo_le = joblib.load('emotion_le.pkl')
                self.emo_model = BertClassifier("hfl/chinese-roberta-wwm-ext-large", len(self.emo_le.classes_)).to(self.device)
                self.emo_model.load_state_dict(torch.load('best_emotion_model.bin', map_location=self.device))
                self.emo_model.eval()
                
                # 3. 載入 MacBERT 模型
                print("   -> 載入 MacBERT 熱度模型...")
                self.mac_model = BertClassifier("hfl/chinese-macbert-base", 2).to(self.device)
                self.mac_model.load_state_dict(torch.load('best_macbert_model.bin', map_location=self.device))
                self.mac_model.eval()
                
                # 4. 載入 Stacking 決策模型
                print("   -> 載入 Stacking Meta 模型...")
                self.meta_model = joblib.load('meta_model.joblib')
                
                self.ai_ready = True
                print("✅ 真實 AI 模型載入成功！(Stacking Mode)")
                
            except Exception as e:
                print(f"⚠️ 模型載入失敗，將切換為安全備用模式。錯誤原因: {e}")

    def extract_features(self, title, publish_time_str):
        """提取環境脈絡特徵"""
        title_str = str(title)
        
        # --- 結構與誘餌特徵 ---
        title_len = len(title_str)
        punct_count = title_str.count('!') + title_str.count('?') + title_str.count('！') + title_str.count('？')
        has_digit = 1 if any(d.isdigit() for d in title_str) else 0
        
        # --- 時間脈絡特徵 ---
        now = datetime.now()
        try:
            pub_dt = pd.to_datetime(publish_time_str)
            hour = pub_dt.hour
            latency_hours = (now - pub_dt).total_seconds() / 3600.0
        except:
            hour = now.hour
            latency_hours = 0.5 
            
        is_prime_time = 1 if hour in [8, 9, 12, 18, 19, 20, 21, 22] else 0
        is_instant_viral = 1 if latency_hours < 3 else 0
        
        return {
            'title_len': title_len,
            'punct_count': punct_count,
            'has_digit': has_digit,
            'hour': hour,
            'is_prime_time': is_prime_time,
            'viral_latency_hours': latency_hours,
            'is_instant_viral': is_instant_viral
        }

    def predict(self, title, content, publish_time=None):
        """給定標題與內文，輸出 0.0 ~ 1.0 的爆紅機率"""
        # --- 模式 A：真實 AI 模型推論 (Wide & Deep Stacking) ---
        if self.ai_ready:
            try:
                with torch.no_grad():
                    text_input = str(title) + " [SEP] " + str(content)[:300]
                    
                    # 1. 取得情緒特徵 (RoBERTa)
                    enc_emo = self.tokenizer_emo.encode_plus(text_input, max_length=256, padding='max_length', truncation=True, return_tensors='pt')
                    out_emo = self.emo_model(enc_emo['input_ids'].to(self.device), enc_emo['attention_mask'].to(self.device))
                    emo_probs = torch.softmax(out_emo, dim=1).cpu().numpy()[0]
                    
                    # 2. 取得 MacBERT 語意熱度特徵
                    enc_mac = self.tokenizer_mac.encode_plus(text_input, max_length=256, padding='max_length', truncation=True, return_tensors='pt')
                    out_mac = self.mac_model(enc_mac['input_ids'].to(self.device), enc_mac['attention_mask'].to(self.device))
                    macbert_score = torch.softmax(out_mac, dim=1)[0, 1].item()
                    
                    # 3. 取得時間與結構特徵
                    meta_feats = self.extract_features(title, publish_time)
                    
                    # 4. 組合所有特徵餵給 Stacking 模型
                    feature_dict = {f'prob_{cls}': p for cls, p in zip(self.emo_le.classes_, emo_probs)}
                    feature_dict['macbert_score'] = macbert_score
                    feature_dict.update(meta_feats)
                    
                    X_meta = pd.DataFrame([feature_dict])
                    
                    # 🔥 強制將欄位對齊模型訓練時的順序與名稱 (防止順序錯亂報錯)
                    if hasattr(self.meta_model, 'feature_names_in_'):
                        expected_cols = self.meta_model.feature_names_in_
                        for col in expected_cols:
                            if col not in X_meta.columns:
                                X_meta[col] = 0.0
                        X_meta = X_meta[list(expected_cols)]
                    
                    final_prob = self.meta_model.predict_proba(X_meta)[0, 1]
                    return float(final_prob)
                    
            except Exception as e:
                print(f"⚠️ 真實 AI 預測錯誤，啟用備用機制: {e}")

        # --- 模式 B：安全備用模式 ---
        score = 0.3
        title_str = str(title)
        
        hot_keywords = ['網傳', '曝光', '驚爆', '竟然', '網友', '真相', '懶人包', '最新', '快訊']
        for kw in hot_keywords:
            if kw in title_str:
                score += 0.15
        
        if '!' in title_str or '?' in title_str or '！' in title_str:
            score += 0.1
        if any(d.isdigit() for d in title_str):
            score += 0.05
            
        return float(min(0.98, max(0.1, score + np.random.uniform(-0.05, 0.05))))