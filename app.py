import streamlit as st
import requests
import time
import csv
from datetime import datetime
from bs4 import BeautifulSoup
import os
import threading

# ===================== 配置 =====================
SITE1_URL = "https://www.ka-yo.com/hk/en/l/arcteryx"
SITE2_BASE = "https://www.vallgatan12.se/en/trademarks/arcteryx"
SITE3_BASE = "https://graduatestore.fr/en/276_arc-teryx"
SCKEY = "SCT330540T5Ji2UsRwefqa5t4Wkm1tNNKg"
CHECK_INTERVAL = 180  # 3分钟

CSV_KAYO = "arcterykayo.csv"
CSV_VALL = "arcteryvall.csv"
CSV_GRAD = "arcterygrad.csv"

st.set_page_config(page_title="ARCTERYX 监控", layout="wide")
st.title("ARCTERYX 自动监控 🔍")
st.caption("24小时云端运行 | 上新微信推送")

if "running" not in st.session_state:
    st.session_state.running = False
if "log" not in st.session_state:
    st.session_state.log = []

# ===================== 工具函数 =====================
def init_csv(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["商品名称", "价格", "链接", "时间"])

def load_existed_urls(file_path):
    urls = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "链接" in row and row["链接"]:
                    urls.add(row["链接"].strip())
    return urls

def append_to_csv(file_path, products):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        for name, price, url in products:
            writer.writerow([name, price, url, now])

def push(site_name, title, content):
    if not SCKEY:
        log(f"ℹ️ {site_name} | 未配置KEY")
        return
    url = f"https://sctapi.ftqq.com/{SCKEY}.send"
    data = {"title": f"【{site_name}】{title}", "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
        log(f"✅ {site_name} | 推送成功")
    except:
        log(f"❌ {site_name} | 推送失败")

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    st.session_state.log.append(f"[{t}] {msg}")

# ===================== 爬虫（无浏览器） =====================
def crawl_kayo():
    try:
        r = requests.get(SITE1_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all("li", class_="ca-product-card")
        res = []
        for item in items:
            n = item.find("h2", class_=lambda x: x and "name" in x)
            p = item.find("span", class_=lambda x: x and "selling" in x)
            a = item.find("a", href=lambda x: x and "/p/" in x)
            if n and p and a:
                res.append((n.get_text(strip=True), p.get_text(strip=True), "https://www.ka-yo.com"+a["href"]))
        log(f"KAYO：{len(res)} 件")
        return res
    except:
        log("❌ KAYO 失败")
        return []

def crawl_vall():
    try:
        r = requests.get(SITE2_BASE, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all("div", class_="grid-unit-inner")
        res = []
        for item in items:
            a = item.find("div", class_="title").find("a") if item.find("div", class_="title") else None
            p = item.find("div", class_="priceContainer")
            if a and p:
                res.append((a.get_text(strip=True), p.get_text(strip=True), a["href"]))
        log(f"VALL：{len(res)} 件")
        return res
    except:
        log("❌ VALL 失败")
        return []

def crawl_graduate():
    try:
        r = requests.get(SITE3_BASE, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all("div", class_="nq-c-ProductListItem-main")
        res = []
        for item in items:
            t = item.find("h3")
            p = item.find("span", class_="nq-c-ProductListItem-prices-current")
            if t and p:
                res.append((t.get_text(strip=True), p.get_text(strip=True), SITE3_BASE))
        log(f"GRAD：{len(res)} 件")
        return res
    except:
        log("❌ GRAD 失败")
        return []

# ===================== 核心流程 =====================
def process(site, csvf, func):
    log(f"\n===== {site} =====")
    init_csv(csvf)
    old = load_existed_urls(csvf)
    new = [x for x in func() if x[2] not in old]
    log(f"新增：{len(new)}")
    if new:
        push(site, f"上新 {len(new)} 件", "\n".join([f"{i+1}. {n}\n价：{p}\n" for i,(n,p,u) in enumerate(new)]))
        append_to_csv(csvf, new)

def loop():
    while st.session_state.running:
        log("\n==================== 开始检查 ====================")
        process("KAYO", CSV_KAYO, crawl_kayo)
        process("VALL", CSV_VALL, crawl_vall)
        process("GRAD", CSV_GRAD, crawl_graduate)
        log(f"\n⏳ 等待3分钟...")
        for _ in range(CHECK_INTERVAL):
            if not st.session_state.running: return
            time.sleep(1)

# ===================== 界面 =====================
c1,c2 = st.columns(2)
with c1:
    if st.button("▶ 启动监控"):
        st.session_state.running = True
        threading.Thread(target=loop, daemon=True).start()
        st.success("✅ 已启动")
with c2:
    if st.button("⏹ 停止"):
        st.session_state.running = False
        st.warning("⏹ 已停止")

st.subheader("日志")
st.code("\n".join(st.session_state.log[-100:]))
