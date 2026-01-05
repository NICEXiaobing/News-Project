#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ===============================================================
#   T-Forecast 全自動爬蟲系統 (V2 完整修復版)
#   
#   功能說明：
#   1. [Content] 抓取 9 大媒體內文 (Part 1 & 2)
#   2. [Label]   抓取 Google News 熱度標籤 (Part 3)
#   3. [Merge]   自動合併產出黃金交叉資料集 (Part 4)
#
#   輸出檔案 (V2)：
#   - news_data_v2_content.csv (內文庫)
#   - news_data_v2_google.csv  (標籤庫)
#   - news_data_v2_final.csv   (最終訓練集)
# ===============================================================

import sys
import logging
import os
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import time
import random
from difflib import SequenceMatcher
import warnings

# 忽略 SSL 警告
warnings.filterwarnings("ignore")

# ===============================================================
# 1. 環境與路徑設定
# ===============================================================
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

# --- V2 全新檔案系統 (與舊資料切斷，確保乾淨) ---
CONTENT_DB_V2 = os.path.join(BASE_DIR, 'news_data_v2_content.csv')   # V32 內文
GOOGLE_DB_V2  = os.path.join(BASE_DIR, 'news_data_v2_google.csv')    # Google 標籤
FINAL_DB_V2   = os.path.join(BASE_DIR, 'news_data_v2_final.csv')     # 最終合併檔

TEMP_JSON_FILENAME = os.path.join(BASE_DIR, 'temp_headlines_v2.json')
LOG_FILENAME = os.path.join(BASE_DIR, 'scraper_v2.log')

# --- Logging ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')

if not logger.hasHandlers():
    file_handler = logging.FileHandler(LOG_FILENAME, encoding='utf-8', mode='a')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

# --- Headers ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}

# --- 資料欄位 ---
COLUMNS_CONTENT = ['url', 'title', 'content', 'source', 'published_at', 'scraped_at', 'headline_level']
COLUMNS_GOOGLE = ['category', 'url', 'title', 'source', 'published_at', 'scraped_at', 'headline_level']

# --- 清理規則 ---
JUNK_PATTERNS = re.compile(
    r'延伸閱讀|相關新聞|看更多|點我下載|▲|▼|'
    r'（圖／.*(提供|翻攝)）|'
    r'★.*?Disclaimer.*?★|'
    r'下載APP|'
    r'※.*?提醒您.*?※|'
    r'《.*?》提醒您|'
    r'★.*?關心您.*?★|'
    r'記者.*?／.*?報導|'
    r'編輯.*?／.*?報導'
)

# ===============================================================
# 2. 共用工具函式
# ===============================================================
def get_soup(url):
    """發送請求並取得 BeautifulSoup 物件 (含 SSL 繞過)"""
    try:
        # verify=False 是為了繞過某些網站的 SSL 憑證問題
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        return BeautifulSoup(response.text, 'lxml')
    except Exception as e:
        logging.warning(f"🟡 抓取 {url} 失敗: {e}")
        return None

def normalize_url(base_url, link):
    """標準化 URL"""
    if not link: return None
    link = link.strip() 
    if link.startswith('//'): return 'https:' + link
    if link.startswith('/'): return base_url.rstrip('/') + link
    if link.startswith('http'): return link
    return base_url.rstrip('/') + '/' + link.lstrip('/')

def safe_find_text(soup, selector, default='N/A'):
    if not soup: return default
    element = soup.select_one(selector)
    if element: return element.get_text(separator='\n', strip=True)
    return default

def get_current_utc_time():
    taiwan_tz = timezone(timedelta(hours=8))
    return datetime.now(taiwan_tz).strftime("%Y-%m-%d %H:%M:%S")

def remove_duplicates(headlines):
    if not headlines: return []
    df = pd.DataFrame(headlines)
    df = df.sort_values('headline_level', ascending=False)
    df_unique = df.drop_duplicates(subset=['url', 'title'], keep='first')
    df_unique = df_unique.drop_duplicates(subset=['url'], keep='first')
    return df_unique.to_dict('records')

def clean_content(text):
    if text == 'N/A' or not text: return 'N/A'
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if JUNK_PATTERNS.search(line): continue
        if len(line) < 15: continue
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines).strip()

def scrape_article_content_base(url, content_selector, time_selector):
    soup = get_soup(url)
    if not soup: return 'N/A', get_current_utc_time()
    content = safe_find_text(soup, content_selector, default='N/A')
    published_at = safe_find_text(soup, time_selector, default=get_current_utc_time()) 
    published_at = re.sub(r'^(發布時間|更新時間)：', '', published_at).strip()
    match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2})', published_at)
    if match: published_at = match.group(1).replace('/', '-')
    else: published_at = get_current_utc_time()
    return content, published_at

def clean_google_link(link):
    if link.startswith("./"): return "https://news.google.com" + link[1:]
    return link

def similar(a, b):
    return SequenceMatcher(None, str(a), str(b)).ratio()

# ===============================================================
# 3. [Part 1] 九合一頭條抓取
# ===============================================================

def fetch_cna_headlines():
    base_url = 'https://www.cna.com.tw'
    soup = get_soup(base_url)
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    # Level 3
    for item in soup.select('div.main-idx-row.top-news div.box-title a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'CNA'})
    # Level 2
    for item in soup.select('div.main-idx-row.major-news div.box-title a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'CNA'})
    # Level 1
    for item in soup.select('div.main-idx-row.instant-news div.box-title a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CNA'})
    return headlines

def fetch_udn_headlines():
    base_url = 'https://udn.com'
    soup = get_soup(base_url + '/news/breaknews/1')
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    # Level 2
    for item in soup.select('div.context-box__content--main h2 a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'UDN'})
    # Level 1
    for item in soup.select('div.story-list__news div.story-list__info h2 a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'UDN'})
    return headlines

def fetch_setn_headlines():
    base_url = 'https://www.setn.com'
    soup = get_soup(base_url)
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    # Level 3, 2, 1
    for item in soup.select('div.focus_news div.captionText a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'SETN'})
    for item in soup.select('div.top-hot-list li a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'SETN'})
    for item in soup.select('div.immediate-news-area div.news-list li a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'SETN'})
    return headlines

def fetch_tvbs_headlines():
    base_domain = 'https://www.tvbs.com.tw'
    soup = get_soup(base_domain)
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    # Level 3, 2, 1
    for item in soup.select('div.hero_main a.swiper-slide'):
        img = item.select_one('img')
        title = img['alt'] if img else item.get_text(strip=True)
        headlines.append({'url': normalize_url(base_domain, item.get('href')), 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'TVBS'})
    for item in soup.select('div.hero_sub a.sub_item'):
        headlines.append({'url': normalize_url(base_domain, item.get('href')), 'title': item.select_one('h3').get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'TVBS'})
    for item in soup.select('div.section_news a.news_popular'):
        headlines.append({'url': normalize_url(base_domain, item.get('href')), 'title': item.select_one('h2').get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'TVBS'})
    return headlines

def fetch_ebc_headlines():
    base_url = 'https://news.ebc.net.tw'
    soup = get_soup(base_url)
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    # Level 3, 2, 1
    for item in soup.select('div.latest_news a.swiper-slide'):
        title = item.get('data-title')
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'EBC'})
    for item in soup.select('div.hot_news div.list_slider li a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.select_one('h3.item_title').get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'EBC'})
    for item in soup.select('div.focus_box div.section_content a.item'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.select_one('h3.item_title').get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'EBC'})
    return headlines

def fetch_nownews_headlines():
    base_url = 'https://www.nownews.com'
    soup = get_soup(base_url)
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    # Level 3, 2, 1
    for item in soup.select('div#focusSlider div.slider-item a'):
        title = item.select_one('figcaption').get_text(strip=True) if item.select_one('figcaption') else "N/A"
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': title, 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
    for item in soup.select('ul.hotnews-wrap li a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
    for item in soup.select('div.nnBlk.focus li.item a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.select_one('h3.title').get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'NOWNEWS'})
    return headlines

def fetch_chinatimes_headlines():
    base_url = 'https://www.chinatimes.com'
    headlines = []
    scraped_at = get_current_utc_time()
    soup_homepage = get_soup(base_url)
    if soup_homepage:
        for item in soup_homepage.select('div.focus-gallery ul.item-group li.item-entry a'):
            headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.select_one('h3.caption-title').get_text(strip=True), 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
        for item in soup_homepage.select('section.hot-news ul.vertical-list li h4.title a'):
            headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 2, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
    soup_realtime = get_soup(base_url + '/realtimenews/')
    if soup_realtime:
        for item in soup_realtime.select('div.article-list h3.title a'):
            headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'CHINATIMES'})
    return headlines

def fetch_ettoday_headlines():
    base_url = 'https://www.ettoday.net'
    soup = get_soup(base_url + '/news/list.htm')
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.c1 > h3 > a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'ETTODAY'})
    for item in soup.select('div.part_list_2 > div > h3 > a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'ETTODAY'})
    return headlines

def fetch_ltn_headlines():
    base_url = 'https://www.ltn.com.tw'
    soup = get_soup('https://news.ltn.com.tw/list/breakingnews')
    if not soup: return []
    headlines = []
    scraped_at = get_current_utc_time()
    for item in soup.select('div.focus-news ul.list li a'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 3, 'scraped_at': scraped_at, 'source': 'LTN'})
    for item in soup.select('ul.list li a.title'):
        headlines.append({'url': normalize_url(base_url, item.get('href')), 'title': item.get_text(strip=True), 'headline_level': 1, 'scraped_at': scraped_at, 'source': 'LTN'})
    return headlines

def run_part1_headline_fetch():
    """執行所有頭條抓取"""
    logging.info("--- [V2] Part 1: 抓取 9 大媒體頭條 ---")
    all_headlines = []
    
    try: all_headlines.extend(fetch_cna_headlines())
    except: pass
    try: all_headlines.extend(fetch_udn_headlines())
    except: pass
    try: all_headlines.extend(fetch_setn_headlines())
    except: pass
    try: all_headlines.extend(fetch_tvbs_headlines())
    except: pass
    try: all_headlines.extend(fetch_ebc_headlines())
    except: pass
    try: all_headlines.extend(fetch_nownews_headlines())
    except: pass
    try: all_headlines.extend(fetch_chinatimes_headlines())
    except: pass
    try: all_headlines.extend(fetch_ettoday_headlines())
    except: pass
    try: all_headlines.extend(fetch_ltn_headlines())
    except: pass
    
    unique_headlines = remove_duplicates(all_headlines)
    try:
        with open(TEMP_JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(unique_headlines, f, ensure_ascii=False, indent=4)
        logging.info(f"✅ Part 1 完成: 抓到 {len(unique_headlines)} 筆，存入 {TEMP_JSON_FILENAME}")
    except Exception as e:
        logging.error(f"🔥 Part 1 失敗: {e}")

# ===============================================================
# 4. [Part 2] 內文抓取
# ===============================================================

def scrape_cna_article(url):
    content, time = scrape_article_content_base(url, 'div.article-body', 'div.update-time')
    return clean_content(content), time

def scrape_udn_article(url):
    content, time = scrape_article_content_base(url, 'section.article-content__editor', 'div.article-content__time')
    return clean_content(content), time

def scrape_setn_article(url):
    content, time = scrape_article_content_base(url, 'div#Content1', 'time.page-date')
    return clean_content(content), time

def scrape_tvbs_article(url):
    content, time = scrape_article_content_base(url, 'div.article_content', 'div.time')
    return clean_content(content), time

def scrape_ebc_article(url):
    content, time = scrape_article_content_base(url, 'div.article-main-content', 'span.date')
    return clean_content(content), time

def scrape_nownews_article(url):
    soup = get_soup(url)
    if not soup: return 'N/A', get_current_utc_time()
    content_element = soup.select_one('div.article-content')
    content = content_element.get_text(separator='\n', strip=True) if content_element else 'N/A'
    time = safe_find_text(soup, 'time.date', default=get_current_utc_time())
    return clean_content(content), time

def scrape_chinatimes_article(url):
    content, time = scrape_article_content_base(url, 'div.article-body', 'div.meta-info time')
    return clean_content(content), time

def scrape_ettoday_article(url):
    content, time = scrape_article_content_base(url, 'div.story', 'time.date')
    return clean_content(content), time

def scrape_ltn_article(url):
    content, time = scrape_article_content_base(url, 'div[itemprop="articleBody"]', 'span.time')
    return clean_content(content), time

def scrape_article(url, source):
    try:
        if source == 'CNA': return scrape_cna_article(url)
        elif source == 'UDN': return scrape_udn_article(url)
        elif source == 'SETN': return scrape_setn_article(url)
        elif source == 'TVBS': return scrape_tvbs_article(url) if 'news.tvbs.com.tw' in url else ('N/A', get_current_utc_time())
        elif source == 'EBC': return scrape_ebc_article(url)
        elif source == 'NOWNEWS': return scrape_nownews_article(url)
        elif source == 'CHINATIMES': return scrape_chinatimes_article(url)
        elif source == 'ETTODAY': return scrape_ettoday_article(url)
        elif source == 'LTN': return scrape_ltn_article(url)
        else: return 'N/A', get_current_utc_time()
    except Exception:
        return 'N/A', get_current_utc_time()

def run_part2_scrape_and_append():
    """讀取頭條，抓內文，存入 V2 Content DB"""
    logging.info("--- [V2] Part 2: 抓取內文並存檔 ---")
    try:
        with open(TEMP_JSON_FILENAME, 'r', encoding='utf-8') as f:
            headlines = json.load(f)
    except:
        logging.warning("找不到 JSON，跳過")
        return

    new_data = []
    for h in headlines:
        try:
            if not h.get('url'): continue
            content, pub_time = scrape_article(h['url'], h['source'])
            if content != 'N/A':
                new_data.append({
                    'url': h['url'], 'title': h['title'], 'content': content, 'source': h['source'],
                    'published_at': pub_time, 'scraped_at': h['scraped_at'], 'headline_level': h['headline_level']
                })
                time.sleep(0.1)
        except: pass

    if new_data:
        df = pd.DataFrame(new_data, columns=COLUMNS_CONTENT)
        df['headline_level'] = pd.to_numeric(df['headline_level'], errors='coerce').astype('Int64')
        
        # 存入 V2 Content DB (Append)
        is_exist = os.path.exists(CONTENT_DB_V2)
        df.to_csv(CONTENT_DB_V2, mode='a', header=not is_exist, index=False, encoding='utf-8-sig')
        logging.info(f"✅ Part 2 完成: 寫入 {len(new_data)} 筆到 {CONTENT_DB_V2}")
    else:
        logging.info("Part 2 無有效資料")

# ===============================================================
# 5. [Part 3] Google News 極速爬蟲 (標籤來源)
# ===============================================================
GOOGLE_URLS = {
    "焦點頭條": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRFZxYUdjU0JXVnVMVWRDR2dKSlRpZ0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
    "國際財經": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx6TVdZU0JXVnVMVWRDR2dKSlRpZ0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
    "科技科學": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGRqTVhZU0JXVnVMVWRDR2dKSlRpZ0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant",
    "運動體育": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRFp1ZEdvU0JXVnVMVWRDR2dKSlRpZ0FQAQ?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant"
}

def run_part3_google_v2():
    logging.info("--- [V2] Part 3: Google News 標籤抓取 ---")
    data_list = []
    for cat, url in GOOGLE_URLS.items():
        try:
            time.sleep(random.uniform(1, 2))
            res = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            articles = soup.find_all('article')
            
            for i, art in enumerate(articles):
                # 找連結 (含 ./read/ 或 ./articles/)
                link_tag = None
                all_links = art.find_all('a', href=True)
                
                # 智慧搜尋：選字數最長的連結 (避免抓到圖片連結)
                candidate_links = []
                for l in all_links:
                    href = l['href']
                    if './read/' in href or './articles/' in href:
                        txt = l.get_text(strip=True)
                        candidate_links.append({'link': l, 'len': len(txt)})
                
                if not candidate_links: continue
                candidate_links.sort(key=lambda x: x['len'], reverse=True)
                link_tag = candidate_links[0]['link']
                
                # 抓取 MetaData
                title = link_tag.get_text(strip=True) or link_tag.get('aria-label') or "無標題"
                full_url = clean_google_link(link_tag['href'])
                src_div = art.find('div', class_='vr1PYe')
                source = src_div.get_text(strip=True) if src_div else "Google News"
                
                # 定義 Google 觀點的熱度
                hl = 3 if (cat == "焦點頭條" and i < 5) else 2
                
                data_list.append({
                    'category': cat, 'url': full_url, 'title': title, 'source': source,
                    'published_at': get_current_utc_time(), 'scraped_at': get_current_utc_time(),
                    'headline_level': hl
                })
        except Exception as e:
            logging.error(f"Google [{cat}] 失敗: {e}")

    if data_list:
        df = pd.DataFrame(data_list, columns=COLUMNS_GOOGLE)
        is_exist = os.path.exists(GOOGLE_DB_V2)
        df.to_csv(GOOGLE_DB_V2, mode='a', header=not is_exist, index=False, encoding='utf-8-sig')
        logging.info(f"✅ Part 3 完成: 寫入 {len(data_list)} 筆到 {GOOGLE_DB_V2}")
    else:
        logging.warning("⚠️ Part 3 未抓到任何 Google 資料")

# ===============================================================
# 6. [Part 4] 黃金交叉合併
# ===============================================================
def run_part4_merge_v2():
    logging.info("--- [V2] Part 4: 資料合併與標籤對齊 ---")
    
    if not os.path.exists(CONTENT_DB_V2) or not os.path.exists(GOOGLE_DB_V2):
        logging.warning("⚠️ 資料不足，跳過合併")
        return

    try:
        df_content = pd.read_csv(CONTENT_DB_V2)
        df_google = pd.read_csv(GOOGLE_DB_V2)
        
        # 初始化新欄位
        if 'google_level' not in df_content.columns: df_content['google_level'] = 0
        if 'is_google_top' not in df_content.columns: df_content['is_google_top'] = False
        
        # 優化：只比對最近 500 筆 Google 資料
        recent_google = df_google.tail(500).to_dict('records')
        match_count = 0
        
        for i, row in df_content.iterrows():
            # 若已標記則跳過
            if row['google_level'] > 0: continue
            
            v_title = str(row['title'])
            v_source = str(row['source'])
            
            best_score = 0
            best_level = 0
            
            for g in recent_google:
                # 來源比對 (模糊匹配，例如 CNA vs 中央社)
                if v_source in str(g['source']) or str(g['source']) in v_source:
                    score = similar(v_title, str(g['title']))
                    if score > best_score:
                        best_score = score
                        best_level = g['headline_level']
            
            # 相似度門檻 0.6
            if best_score > 0.6:
                df_content.at[i, 'google_level'] = best_level
                df_content.at[i, 'is_google_top'] = True
                match_count += 1
        
        # 覆寫最終合併檔
        df_content.to_csv(FINAL_DB_V2, index=False, encoding='utf-8-sig')
        logging.info(f"🎉 合併完成! 新增 {match_count} 筆關聯。最終檔: {FINAL_DB_V2}")
        
    except Exception as e:
        logging.error(f"合併失敗: {e}")

# ===============================================================
# 7. 主程式入口
# ===============================================================
def main_execution():
    start_time = time.time()
    logging.info(f"======= V2 整合爬蟲開始 {get_current_utc_time()} =======")
    
    # 1. 抓內文 (9 大媒體)
    run_part1_headline_fetch()
    run_part2_scrape_and_append()
    
    # 2. 抓標籤 (Google News)
    run_part3_google_v2()
    
    # 3. 合併
    run_part4_merge_v2()
    
    end_time = time.time()
    logging.info(f"======= V2 任務結束，耗時 {end_time - start_time:.2f} 秒 =======")

if __name__ == "__main__":
    main_execution()