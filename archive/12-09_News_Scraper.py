#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import logging
import os
import random
import time
import re
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# --- Selenium ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# --- Requests ---
import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter('ignore', InsecureRequestWarning)

# ===============================================================
#  1. 全域設定 (Global Settings)
# ===============================================================

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

# 資料庫路徑
DATA_FILENAME = os.path.join(BASE_DIR, 'News_Data.csv')
LOG_FILENAME = os.path.join(BASE_DIR, 'scraper_final.log')

# 標準欄位
V5_COLUMNS = ['url', 'media', 'category', 'publish_time', 'title', 'content', 'fetch_time', 'label']

# 抓取目標數量
LIMIT_L1 = 50
LIMIT_L0 = 75

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILENAME, encoding='utf-8', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Referer': 'https://www.google.com/'
}

# ===============================================================
#  2. 媒體設定檔 (Media Configs)
# ===============================================================

MEDIA_CONFIGS = [
    {
        'name': 'SETN',
        'hot_url': 'https://www.setn.com/ViewAll.aspx?PageGroupID=6',
        'latest_url': 'https://www.setn.com/ViewAll.aspx',
        'base_url': 'https://www.setn.com',
        'hot_selector': ['h3.view-li-title a', 'div.news-list-group a.gt', 'div.col-sm-12 h3 a'],
        'latest_selector': ['h3.view-li-title a', 'div.col-sm-12 > a']
    },
    {
        'name': 'TVBS',
        'hot_url': 'https://news.tvbs.com.tw/hot',
        'latest_url': 'https://news.tvbs.com.tw/realtime',
        'base_url': 'https://news.tvbs.com.tw',
        'hot_selector': ['div.news_list li a', 'div.list li a'],
        'latest_selector': ['div.news_list li a']
    },
    {
        'name': 'ETtoday',
        'hot_url': 'https://www.ettoday.net/news/hot-news.htm',
        'latest_url': 'https://www.ettoday.net/news/news-list.htm',
        'base_url': 'https://www.ettoday.net',
        'hot_selector': ['div.part_list_2 h3 a', 'div.block_content h3 a'],
        'latest_selector': ['div.part_list_2 h3 a']
    },
    {
        'name': 'LTN',
        'hot_url': 'https://news.ltn.com.tw/list/breakingnews/popular',
        'latest_url': 'https://news.ltn.com.tw/list/breakingnews',
        'base_url': 'https://news.ltn.com.tw',
        # 廣域容器掃描 (之後再過濾網址)
        'hot_selector': ['div.whitecon a', 'ul.list a', 'div.boxTitle a', 'a.tit'],
        'latest_selector': ['div.whitecon ul.list li a', 'div.whitecon a', 'ul.list a']
    },
    {
        'name': 'ChinaTimes',
        'hot_url': 'https://www.chinatimes.com/hotnews/?chdtv',
        'latest_url': 'https://www.chinatimes.com/realtimenews/?chdtv',
        'base_url': 'https://www.chinatimes.com',
        'hot_selector': ['section.hot-news li h3.title a', 'ul.vertical-list li h3 a'],
        'latest_selector': ['section.article-list li h3.title a']
    },
    {
        'name': 'UDN',
        'hot_url': 'https://udn.com/rank/pv/2',
        'latest_url': 'https://udn.com/news/breaknews/1',
        'base_url': 'https://udn.com',
        'hot_selector': ['div.story-list__text h2 a', 'section.rank-list h3 a'],
        'latest_selector': ['div.story-list__text h2 a']
    }
]

# 全子網域內文選擇器矩陣
CONTENT_SELECTORS = [
    'div.article-content',          # 通用
    'div.story',                    # ETtoday
    'div.article-body',             # ChinaTimes
    'div[itemprop="articleBody"]',  # LTN 主站
    'div.text',                     # LTN 財經/娛樂/通用
    'div.news_content',             # LTN 體育
    'div.box_data',                 # LTN 汽車/其他
    'div.content',                  # 子版通用
    'div#Content1',                 # SETN 主站
    'div.article_content',          # TVBS
    'section.article-content__editor', # UDN
    'div.p-note',
    'div.fncnews-content',
    'div.post-content',
    'article'                       # 終極備案
]

# ===============================================================
#  3. 資料清洗與中文優化模組 (V13.1)
# ===============================================================

# 翻譯字典 (最後一道防線)
CATEGORY_MAP = {
    'politics': '政治', 'society': '社會', 'life': '生活', 'world': '國際',
    'local': '地方', 'novelty': '搜奇', 'business': '財經', 'finance': '財經',
    'ec': '財經', 'sports': '體育', 'entertainment': '娛樂', 'ent': '娛樂',
    'star': '娛樂', 'health': '健康', 'supplement': '副刊', 'opinion': '言論',
    'talk': '言論', 'focus': '焦點', '3c': '3C科技', 'auto': '汽車', 'fashion': '時尚'
}

def clean_category(cat_str):
    """清洗並翻譯分類"""
    if not cat_str: return "即時"
    
    cat_str = str(cat_str).strip()
    
    # 處理麵包屑格式 "首頁 > 政治"
    if '>' in cat_str: 
        parts = cat_str.split('>')
        if len(parts) >= 2:
            candidate = parts[-1].strip()
            # 若最後一段太長(>10字)可能是標題，改取上一層
            if len(candidate) > 10:
                cat_str = parts[-2].strip()
            else:
                cat_str = candidate
        else:
            cat_str = parts[-1].strip()
            
    elif '/' in cat_str and len(cat_str) < 20: 
        cat_str = cat_str.split('/')[-1].strip()

    # 去除多餘字樣
    cat_str = cat_str.replace("自由時報", "").replace("LTN", "").strip()

    # 查表翻譯 (若仍為英文)
    lower_cat = cat_str.lower()
    if lower_cat in CATEGORY_MAP:
        return CATEGORY_MAP[lower_cat]
        
    return cat_str

def format_time_strict(time_str):
    now = datetime.now()
    if not time_str or str(time_str).lower() in ['nan', 'n/a', 'none', '']:
        return now.strftime("%Y/%-m/%-d %-I:%M:%S %p")
    try:
        raw = str(time_str).replace("發布時間：", "").replace("更新時間：", "").strip()
        if "小時前" in raw:
            hours = int(re.search(r'(\d+)', raw).group(1))
            dt = now - timedelta(hours=hours)
        elif "分鐘前" in raw:
            mins = int(re.search(r'(\d+)', raw).group(1))
            dt = now - timedelta(minutes=mins)
        elif "剛剛" in raw:
            dt = now
        else:
            dt = date_parser.parse(raw, fuzzy=True)
        
        hour_12 = int(dt.strftime("%I"))
        time_part = f"{hour_12}:{dt.strftime('%M:%S %p')}"
        return f"{dt.year}/{dt.month}/{dt.day} {time_part}"
    except:
        return now.strftime("%Y/%-m/%-d %-I:%M:%S %p")

def parse_html_content(html_text):
    soup = BeautifulSoup(html_text, 'lxml')
    content = np.nan
    
    # 1. 內文
    for sel in CONTENT_SELECTORS:
        elm = soup.select_one(sel)
        if elm:
            for tag in elm(['script', 'style', 'iframe', 'div.knn_related', 'div.fb-root', 'div.author', 'div.ad', 'div.click_mic', 'p.app_ad']):
                tag.decompose()
            text = elm.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)
            if len(text) > 30:
                content = text
                break
    
    # 2. 分類 (優先抓麵包屑，因為是中文)
    category = None
    crumbs_selectors = [
        'div.guide', 'div.breadcrumbs', 'div.breadcrumb', 
        'nav[aria-label="breadcrumb"]', 'div.path'
    ]
    for sel in crumbs_selectors:
        crumbs = soup.select_one(sel)
        if crumbs:
            category = crumbs.get_text(separator=' > ', strip=True)
            break
    
    # 備案：抓 Meta Tag
    if not category:
        meta_sec = soup.select_one('meta[property="article:section"]')
        if meta_sec and meta_sec.get('content'):
            category = meta_sec.get('content')
    
    if not category: category = "即時"

    # 3. 時間
    raw_time = None
    time_elm = soup.select_one('meta[property="article:published_time"], meta[name="pubdate"], time, span.time, div.date, div.meta-info time')
    if time_elm:
        raw_time = time_elm.get('content') if time_elm.has_attr('content') else time_elm.get_text(strip=True)
    
    return clean_category(category), format_time_strict(raw_time), content

# ===============================================================
#  4. 爬蟲核心 (HumanNavigator)
# ===============================================================

class HumanNavigator:
    def __init__(self, driver):
        self.driver = driver
        self.action = ActionChains(driver)

    def random_sleep(self, min_s=1.5, max_s=3.0):
        time.sleep(random.uniform(min_s, max_s))

    def smooth_scroll(self):
        try:
            current_pos = self.driver.execute_script("return window.pageYOffset;")
            target_distance = random.randint(800, 1200)
            steps = random.randint(10, 20)
            for _ in range(steps):
                move = (target_distance / steps) + random.uniform(-5, 5) 
                current_pos += move
                self.driver.execute_script(f"window.scrollTo(0, {current_pos});")
                time.sleep(0.02)
        except: pass

    def random_mouse_move(self):
        try:
            links = self.driver.find_elements(By.TAG_NAME, "a")
            if len(links) > 0:
                target = random.choice(links[:15]) 
                self.action.move_to_element(target).perform()
        except: pass

class NewsSpider:
    def __init__(self):
        self.options = Options()
        self.options.add_argument("--headless") # 正式跑時可開啟 headless
        # self.options.add_argument("--start-maximized") # 測試時可開啟視窗
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument(f"user-agent={HEADERS['User-Agent']}")
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        
        prefs = {"profile.managed_default_content_settings.images": 2}
        self.options.add_experimental_option("prefs", prefs)
        
        self.driver = None
        self.human = None
        self.existing_data = self._get_existing_data()

    def _get_existing_data(self):
        existing = {}
        if os.path.exists(DATA_FILENAME):
            try:
                df = pd.read_csv(DATA_FILENAME)
                if 'url' in df.columns and 'label' in df.columns:
                    for idx, row in df.iterrows():
                        existing[str(row['url'])] = row['label']
            except: pass
        return existing

    def start(self):
        # 🔥 [修正重點] 強制指定與您 Chrome 143 匹配的 Driver 版本
        # 143.0.7499.169 是目前 WD Manager 支援的最接近版本
        service = Service(ChromeDriverManager(driver_version="143.0.7499.169").install())
        
        self.driver = webdriver.Chrome(service=service, options=self.options)
        self.driver.set_page_load_timeout(45)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.human = HumanNavigator(self.driver)

    def stop(self):
        if self.driver:
            try: self.driver.quit()
            except: pass
            self.driver = None

    def fetch_content_smart(self, url):
        try:
            res = requests.get(url, headers=HEADERS, timeout=6, verify=False)
            if res.status_code == 200:
                cat, t, c = parse_html_content(res.text)
                if isinstance(c, str): return cat, t, c
        except: pass

        try:
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            try:
                self.driver.get(url)
            except TimeoutException:
                self.driver.execute_script("window.stop();")
            
            self.human.random_sleep(1.0, 2.0)
            html = self.driver.page_source
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return parse_html_content(html)
        except:
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except: pass
        return "即時", format_time_strict(None), np.nan

    def crawl_task(self, site_config, label, limit):
        url = site_config['hot_url'] if label == 1 else site_config['latest_url']
        selectors = site_config['hot_selector'] if label == 1 else site_config['latest_selector']
        site_name = site_config['name']

        logging.info(f"      L{label} 任務啟動 (目標: {limit} 筆)...")
        try:
            try:
                self.driver.get(url)
                # 增加 Log 確認是否成功進入頁面
                logging.info(f"      🔍 已訪問: {url} | Title: {self.driver.title}")
                
                try:
                    WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    if site_name == 'LTN': time.sleep(5) 
                    else: self.human.random_sleep(2, 4)
                except: pass
            except TimeoutException:
                logging.warning("      ⚠️ 列表載入超時，強制停止...")
                self.driver.execute_script("window.stop();")

            collected = []
            seen_links = set()
            
            scroll_target = int((limit / 8) * 1.5) + 3
            for _ in range(scroll_target):
                self.human.smooth_scroll()
                self.human.random_mouse_move()
                self.human.random_sleep(1.0, 1.5)
                soup = BeautifulSoup(self.driver.page_source, 'lxml')
                found_count = 0
                for sel in selectors: found_count += len(soup.select(sel))
                if found_count >= limit * 1.2: break
            
            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            elements = []
            for sel in selectors:
                found = soup.select(sel)
                if found: elements.extend(found)

            logging.info(f"      -> 掃描到 {len(elements)} 個連結...")

            for item in elements:
                if len(collected) >= limit: break
                try:
                    link = item.get('href')
                    # LTN 過濾器
                    if site_name == 'LTN':
                        if not link: continue
                        if not any(x in link for x in ['/news/', '/article/', 'sports', 'ent', 'ec', 'auto']): continue
                    
                    title = item.get('title') or item.get_text(strip=True)
                    if not link or not title or len(title) < 4: continue
                    
                    if link.startswith('/'):
                        base = site_config['base_url']
                        full_url = base.rstrip('/') + '/' + link.lstrip('/')
                    elif link.startswith('http'):
                        full_url = link
                    else: continue
                    
                    if 'setn.com' in full_url and 'NewsID=' in full_url: clean_url = full_url 
                    elif 'udn.com' in full_url and 'story/' in full_url: clean_url = full_url 
                    else: clean_url = full_url.split('?')[0]

                    if clean_url in seen_links: continue
                    seen_links.add(clean_url)

                    # 智慧去重與升級
                    is_in_db = clean_url in self.existing_data
                    db_label = self.existing_data.get(clean_url, -1)

                    if is_in_db:
                        if label == 1 and db_label == 0:
                            logging.info(f"         [Upgrade] 發現 L0->L1 潛力股: {title[:8]}")
                        elif label == 1 and db_label == 1: continue
                        elif label == 0: continue

                    cat, t_str, content = self.fetch_content_smart(full_url)
                    if not isinstance(content, str) or len(content) < 30: continue 

                    fetch_time = datetime.now().strftime("%Y/%-m/%-d %-I:%M:%S %p")
                    
                    collected.append({
                        'url': full_url,
                        'media': site_name,
                        'category': cat, # V13.1 Native Chinese
                        'publish_time': t_str,
                        'title': title,
                        'content': content,
                        'fetch_time': fetch_time,
                        'label': label
                    })
                    
                    print(f"         [L{label}] {title[:8]}... (OK) - {cat}")
                    time.sleep(random.uniform(1.5, 3.0))

                except Exception: continue
            
            return collected

        except Exception as e:
            logging.error(f"      🔥 任務錯誤: {e}")
            return []

# ===============================================================
#  5. 主程式
# ===============================================================

def main():
    logging.info(f"🚀 T-Forecast V13.1 Final (Clean & Native) 啟動")
    
    spider = NewsSpider()
    
    for site_config in MEDIA_CONFIGS:
        site_name = site_config['name']
        logging.info(f"--- 處理媒體: {site_name} ---")
        try:
            spider.start()
            all_data = []
            
            l1_data = spider.crawl_task(site_config, label=1, limit=LIMIT_L1)
            all_data.extend(l1_data)
            logging.info(f"      ✅ {site_name} L1 完成: {len(l1_data)} 筆")
            spider.human.random_sleep(2, 3)
            
            l0_data = spider.crawl_task(site_config, label=0, limit=LIMIT_L0)
            all_data.extend(l0_data)
            logging.info(f"      ✅ {site_name} L0 完成: {len(l0_data)} 筆")
            
            spider.stop()
        except Exception as e:
            logging.error(f"   🔥 {site_name} 發生錯誤: {e}")
            spider.stop()
        
        logging.info(f"   💤 休息 5 秒...")
        time.sleep(5)

        if all_data:
            df = pd.DataFrame(all_data)
            for col in V5_COLUMNS:
                if col not in df.columns: df[col] = np.nan
            df = df[V5_COLUMNS]
            try:
                # 若檔案不存在則寫入 Header
                header = not os.path.exists(DATA_FILENAME)
                df.to_csv(DATA_FILENAME, mode='a', header=header, index=False, encoding='utf-8-sig')
                logging.info(f"   💾 {site_name} 存檔成功 (共 {len(all_data)} 筆)")
            except:
                df.to_csv(f"backup_{site_name}_{int(time.time())}.csv", index=False)

    logging.info("🏁 任務結束")

if __name__ == "__main__":
    main()