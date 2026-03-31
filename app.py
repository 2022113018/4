import streamlit as st
import requests
import time
import csv
from datetime import datetime
from bs4 import BeautifulSoup
import os
from threading import Thread

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===================== 配置 =====================
SITE1_URL = "https://www.ka-yo.com/hk/en/l/arcteryx"
SITE2_BASE = "https://www.vallgatan12.se/en/trademarks/arcteryx"
SITE3_BASE = "https://graduatestore.fr/en/276_arc-teryx"
SCKEY = "SCT330540T5Ji2UsRwefqa5t4Wkm1tNNKg"
CHECK_INTERVAL = 180  # 30分钟
# ==================================================

# Streamlit 页面初始化
st.set_page_config(page_title="ARCTERYX 24H监控", layout="wide")
st.title("🐦 ARCTERYX 三网站 24小时自动监控")
st.subheader("自动抓取 · 自动保存 · 上新微信推送")

# 状态保存（防止重复运行）
if "monitor_running" not in st.session_state:
    st.session_state.monitor_running = False
if "log_list" not in st.session_state:
    st.session_state.log_list = []

# 日志输出函数
def add_log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    log = f"[{now}] {msg}"
    st.session_state.log_list.append(log)
    print(log)

# ==================== CSV 工具函数 ====================
def init_csv(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["商品名称", "价格", "商品链接", "抓取时间"])

def load_existed_urls(file_path):
    urls = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "商品链接" in row and row["商品链接"]:
                    urls.add(row["商品链接"].strip())
    return urls

def append_to_csv(file_path, products):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        for name, price, url in products:
            writer.writerow([name, price, url, now])

# ==================== 微信推送 ====================
def push(site_name, title, content):
    if not SCKEY:
        add_log(f"ℹ️ {site_name} | 未配置推送KEY，跳过推送")
        return
    full_title = f"【{site_name}】{title}"
    url = f"https://sctapi.ftqq.com/{SCKEY}.send"
    data = {"title": full_title, "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
        add_log(f"✅ {site_name} | 推送成功")
    except Exception as e:
        add_log(f"❌ {site_name} | 推送失败：{e}")

# ==================== 浏览器配置（Streamlit专用） ====================
def get_chrome_options():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return options

# ==================== 验证框处理 ====================
def solve_checkbox_verify(driver):
    try:
        checkbox = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox']"))
        )
        if not checkbox.is_selected():
            driver.execute_script("arguments[0].click();", checkbox)
            add_log("✅ 已自动勾选验证复选框")
            time.sleep(2)
    except:
        add_log("ℹ️ 未找到复选框验证，继续执行")

# ==================== KAYO ====================
def get_products(soup):
    products = []
    items = soup.find_all("li", class_="ca-product-card")
    add_log(f"KAYO 找到商品总数：{len(items)}")
    for item in items:
        name_elem = item.select_one("h2[class*='ca-brand-and-name__name']")
        price_elem = item.select_one("span[class*='ca-price__selling']")
        info_a = item.select_one("a[href*='/hk/en/p/']")
        if not name_elem or not price_elem or not info_a:
            continue
        name = name_elem.get_text(strip=True)
        price = price_elem.get_text(strip=True)
        href = info_a.get("href", "")
        full_url = "https://www.ka-yo.com" + href
        products.append((name, price, full_url))
    add_log(f"✅ KAYO 成功抓取：{len(products)} 件")
    return products

def crawl_kayo():
    try:
        driver = webdriver.Chrome(options=get_chrome_options())
        driver.get(SITE1_URL)
        time.sleep(3)
        solve_checkbox_verify(driver)
        try:
            load_more = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.ca-list-pagination__button--next"))
            )
            driver.execute_script("arguments[0].click();", load_more)
            add_log("✅ KAYO 已点击加载更多")
            time.sleep(8)
        except:
            add_log("ℹ️ KAYO 无需加载更多")
        html = driver.page_source
        driver.quit()
        soup = BeautifulSoup(html, "html.parser")
        return get_products(soup)
    except Exception as e:
        add_log(f"❌ KAYO 错误：{e}")
        return []

# ==================== vallgatan12 ====================
def crawl_vall():
    try:
        driver = webdriver.Chrome(options=get_chrome_options())
        all_items = []
        page = 1
        while True:
            url = SITE2_BASE if page == 1 else f"{SITE2_BASE}?page={page}"
            add_log(f"\n📄 正在爬取 vallgatan12 第 {page} 页")
            driver.get(url)
            time.sleep(2)
            solve_checkbox_verify(driver)
            time.sleep(2)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            items = soup.find_all("div", class_="grid-unit-inner")
            current = 0
            for item in items:
                title_div = item.find("div", class_="title")
                if not title_div: continue
                a_tag = title_div.find("a")
                price_box = item.find("div", class_="priceContainer")
                if not a_tag: continue
                name = a_tag.get_text(strip=True)
                price = price_box.get_text(strip=True) if price_box else "N/A"
                href = a_tag["href"]
                full_url = href if href.startswith("http") else "https://www.vallgatan12.se" + href
                all_items.append((name, price, full_url))
                current += 1
            add_log(f"✅ 第 {page} 页抓取：{current} 件")
            if current == 0:
                break
            page += 1
            time.sleep(2)
        driver.quit()
        return all_items
    except Exception as e:
        add_log(f"❌ vall 错误：{e}")
        return []

# ==================== graduatestore ====================
def crawl_graduate():
    try:
        driver = webdriver.Chrome(options=get_chrome_options())
        all_items = []
        page = 1
        while True:
            url = SITE3_BASE if page == 1 else f"{SITE3_BASE}?page={page}"
            add_log(f"\n📄 正在爬取 graduatestore 第 {page} 页")
            driver.get(url)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            time.sleep(2)
            solve_checkbox_verify(driver)
            time.sleep(3)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            items = soup.find_all("div", class_="nq-c-ProductListItem-main")
            current = 0
            for item in items:
                brand = item.find("div", class_="nq-c-ProductListItem-name-brand")
                title_tag = item.find("h3")
                price_tag = item.find("span", class_="nq-c-ProductListItem-prices-current")
                link_tag = item.find("button", onclick=True)
                if not title_tag or not price_tag:
                    continue
                brand_str = brand.get_text(strip=True) if brand else "Arc'teryx"
                name_str = title_tag.get_text(strip=True)
                full_name = f"{brand_str} {name_str}"
                price = price_tag.get_text(strip=True).replace("\xa0", " ")
                onclick = link_tag["onclick"]
                prod_url = onclick.split("'")[1] if "'" in onclick else ""
                if prod_url:
                    all_items.append((full_name, price, prod_url))
                    current += 1
            add_log(f"✅ 第 {page} 页抓取：{current} 件")
            if current == 0:
                break
            page += 1
            time.sleep(2)
        driver.quit()
        return all_items
    except Exception as e:
        add_log(f"❌ graduate 错误：{e}")
        return []

# ==================== 统一处理 ====================
def process_site(site_name, csv_file, crawl_func):
    add_log(f"\n========================================")
    add_log(f"🔍 开始处理：{site_name}")
    init_csv(csv_file)
    existed_urls = load_existed_urls(csv_file)
    current_products = crawl_func()
    new_products = []
    for name, price, url in current_products:
        if url not in existed_urls:
            new_products.append((name, price, url))
    add_log(f"📊 {site_name} | 历史：{len(existed_urls)} | 本次：{len(current_products)} | 新增：{len(new_products)}")
    if new_products:
        content = ""
        for idx, (name, price, url) in enumerate(new_products, 1):
            content += f"{idx}. {name}\n💰 价格：{price}\n🔗 链接：{url}\n\n"
        push(site_name, f"ARCTERYX 上新 {len(new_products)} 件", content)
        append_to_csv(csv_file, new_products)
    else:
        add_log(f"ℹ️ {site_name} | 暂无上新")

# ==================== 主循环 ====================
def monitor_loop():
    while st.session_state.monitor_running:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        add_log(f"\n\n==================== {now} ====================")
        process_site("KAYO", "arcteryx_kayo.csv", crawl_kayo)
        process_site("vallgatan12", "arcteryx_vall.csv", crawl_vall)
        process_site("GraduateStore", "arcteryx_grad.csv", crawl_graduate)
        add_log(f"\n⏳ 等待 {CHECK_INTERVAL//60} 分钟后再次检查...")
        time.sleep(CHECK_INTERVAL)

# ==================== Streamlit 控制面板 ====================
col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ 启动 24小时监控"):
        if not st.session_state.monitor_running:
            st.session_state.monitor_running = True
            add_log("🚀 监控已启动！")
            Thread(target=monitor_loop, daemon=True).start()
        else:
            add_log("⚠️ 监控正在运行中")

with col2:
    if st.button("⏹️ 停止监控"):
        st.session_state.monitor_running = False
        add_log("🛑 监控已停止")

# 实时日志展示
st.markdown("---")
st.subheader("📜 实时运行日志")
log_container = st.container()
with log_container:
    for log in st.session_state.log_list[-30:]:
        st.text(log)
