import streamlit as st
import requests
import time
import csv
from datetime import datetime
from bs4 import BeautifulSoup
import os
import threading

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===================== 配置 =====================
SITE1_URL = "https://www.ka-yo.com/hk/en/l/arcteryx"
SITE2_BASE = "https://www.vallgatan12.se/en/trademarks/arcteryx"
SITE3_BASE = "https://graduatestore.fr/en/276_arc-teryx"
SCKEY = st.secrets.get("SCKEY", "")
CHECK_INTERVAL = 180  # 30分钟

CSV_KAYO = "arcteryx_kayo.csv"
CSV_VALL = "arcteryx_vall.csv"
CSV_GRAD = "arcteryx_grad.csv"

st.set_page_config(page_title="ARCTERYX 监控", layout="wide")
st.title("ARCTERYX 三网站自动监控 🔍")
st.caption("GitHub + Streamlit 24小时云端运行版 | 上新自动微信推送")

# ------------------- 初始化 session_state 必须放在最前面 -------------------
if "running" not in st.session_state:
    st.session_state.running = False
if "log" not in st.session_state:
    st.session_state.log = []

# ===================== 工具函数 =====================
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

def push(site_name, title, content):
    if not SCKEY:
        log(f"ℹ️ {site_name} | 未配置推送KEY")
        return
    full_title = f"【{site_name}】{title}"
    url = f"https://sctapi.ftqq.com/{SCKEY}.send"
    data = {"title": full_title, "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
        log(f"✅ {site_name} | 推送成功")
    except Exception as e:
        log(f"❌ {site_name} | 推送失败：{e}")

def solve_checkbox_verify(driver):
    try:
        checkbox = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox']"))
        )
        if not checkbox.is_selected():
            driver.execute_script("arguments[0].click();", checkbox)
            log("✅ 已自动勾选验证框")
            time.sleep(2)
    except:
        log("ℹ️ 未找到验证框，继续")

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    full = f"[{t}] {msg}"
    st.session_state.log.append(full)
    print(full)

# ===================== 爬虫逻辑 =====================
def get_browser_page(url):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(3)
    solve_checkbox_verify(driver)

    try:
        load_more = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.ca-list-pagination__button--next"))
        )
        driver.execute_script("arguments[0].click();", load_more)
        log("✅ KAYO 已点击加载更多")
        time.sleep(8)
    except:
        log("ℹ️ KAYO 无需加载更多")

    html = driver.page_source
    driver.quit()
    return html

def crawl_kayo():
    try:
        html = get_browser_page(SITE1_URL)
        soup = BeautifulSoup(html, "html.parser")
        products = []
        items = soup.find_all("li", class_="ca-product-card")
        for item in items:
            name_elem = item.select_one("h2[class*='ca-brand-and-name__name']")
            price_elem = item.select_one("span[class*='ca-price__selling']")
            info_a = item.select_one("a[href*='/hk/en/p/']")
            if name_elem and price_elem and info_a:
                name = name_elem.get_text(strip=True)
                price = price_elem.get_text(strip=True)
                href = info_a.get("href", "")
                full_url = "https://www.ka-yo.com" + href
                products.append((name, price, full_url))
        log(f"✅ KAYO 抓取完成：{len(products)} 件")
        return products
    except Exception as e:
        log(f"❌ KAYO 错误：{e}")
        return []

def crawl_vall():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    all_items = []
    page = 1
    while True:
        url = SITE2_BASE if page == 1 else f"{SITE2_BASE}?page={page}"
        log(f"📄 正在爬取 vall 第 {page} 页")
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
        log(f"✅ 第 {page} 页：{current} 件")
        if current == 0:
            break
        page += 1
        time.sleep(2)
    driver.quit()
    return all_items

def crawl_graduate():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    all_items = []
    page = 1
    while True:
        url = SITE3_BASE if page == 1 else f"{SITE3_BASE}?page={page}"
        log(f"📄 正在爬取 graduate 第 {page} 页")
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
        log(f"✅ 第 {page} 页：{current} 件")
        if current == 0:
            break
        page += 1
        time.sleep(2)
    driver.quit()
    return all_items

# ===================== 统一处理 =====================
def process_site(site_name, csv_file, crawl_func):
    log(f"\n===== 开始处理：{site_name} =====")
    init_csv(csv_file)
    existed_urls = load_existed_urls(csv_file)
    current_products = crawl_func()
    new_products = [p for p in current_products if p[2] not in existed_urls]
    log(f"📊 历史：{len(existed_urls)} | 本次：{len(current_products)} | 新增：{len(new_products)}")
    if new_products:
        content = ""
        for idx, (name, price, url) in enumerate(new_products, 1):
            content += f"{idx}. {name}\n💰 价格：{price}\n🔗 链接：{url}\n\n"
        push(site_name, f"上新 {len(new_products)} 件", content)
        append_to_csv(csv_file, new_products)
    else:
        log(f"ℹ️ {site_name} 暂无上新")

# ===================== 后台任务 =====================
def background_task():
    while st.session_state.get("running", False):
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log(f"\n\n==================== {now} ====================")
            process_site("KAYO", CSV_KAYO, crawl_kayo)
            process_site("vallgatan12", CSV_VALL, crawl_vall)
            process_site("GraduateStore", CSV_GRAD, crawl_graduate)
            log(f"\n⏳ 等待 {CHECK_INTERVAL//60} 分钟后继续...")

            # 分段sleep，防止卡死
            for _ in range(CHECK_INTERVAL):
                if not st.session_state.get("running", False):
                    return
                time.sleep(1)
        except Exception as e:
            log(f"⚠️ 监控异常：{str(e)}")
            time.sleep(60)

# ===================== 界面 =====================
col1, col2 = st.columns(2)
with col1:
    if st.button("▶ 启动监控"):
        if not st.session_state.running:
            st.session_state.running = True
            threading.Thread(target=background_task, daemon=True).start()
            st.success("✅ 监控已启动（后台24小时运行）")
with col2:
    if st.button("⏹ 停止监控"):
        st.session_state.running = False
        st.warning("⏹ 监控已停止")

st.subheader("实时运行日志")
log_container = st.empty()
with log_container:
    st.code("\n".join(st.session_state.log[-100:]), language="text")
