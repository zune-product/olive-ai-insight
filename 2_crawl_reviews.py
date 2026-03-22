"""
2_crawl_reviews.py
──────────────────
4개 상품 리뷰를 미리 크롤링해서 data/ 폴더에 CSV로 저장합니다.
실시간 크롤링 없이 앱이 빠르게 동작하도록 사전에 한 번 실행하세요.

실행:
    python 2_crawl_reviews.py

결과:
    data/product_1_roundlab_toner.csv
    data/product_2_anua_toner.csv
    data/product_3_torriden_serum.csv
    data/product_4_goodal_serum.csv
"""

import os
import re
import time
import random
import csv
import json
from dataclasses import dataclass, asdict, fields

# ── Selenium ──────────────────────────────────────────────────────────────────
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException,
    ElementClickInterceptedException, TimeoutException,
)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WDM = True
except ImportError:
    USE_WDM = False

# ── 상품 정의 ─────────────────────────────────────────────────────────────────
PRODUCTS = [
    {
        "id": 1,
        "name": "라운드랩 1025 독도 토너",
        "brand": "라운드랩",
        "filename": "product_1_roundlab_toner.csv",
        # 올리브영 상품 URL (goodsNo는 실제 코드로 교체 가능)
        "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000164238",
    },
    {
        "id": 2,
        "name": "아누아 어성초 77 수딩 토너",
        "brand": "아누아",
        "filename": "product_2_anua_toner.csv",
        "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000187764",
    },
    {
        "id": 3,
        "name": "토리든 다이브인 히알루론산 세럼",
        "brand": "토리든",
        "filename": "product_3_torriden_serum.csv",
        "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000196952",
    },
    {
        "id": 4,
        "name": "구달 청귤 비타C 잡티케어 세럼",
        "brand": "구달",
        "filename": "product_4_goodal_serum.csv",
        "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000163809",
    },
]

TARGET_REVIEWS = 100   # 상품당 목표 리뷰 수
DATA_DIR       = "data"
MAX_CLICKS     = 60    # 더보기 최대 클릭 횟수

# ── 리뷰 데이터 클래스 ────────────────────────────────────────────────────────
@dataclass
class Review:
    product_id:   int
    product_name: str
    brand:        str
    author:       str
    rating:       float
    skin_type:    str
    date:         str
    text:         str
    helpful:      str


# ── 드라이버 팩토리 ───────────────────────────────────────────────────────────
def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--lang=ko-KR")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    # 시스템 chromium 우선 (Linux 서버)
    import shutil
    chrome_bins = ["/usr/bin/chromium", "/usr/bin/chromium-browser",
                   "/usr/bin/google-chrome"]
    driver_bins = ["/usr/bin/chromedriver",
                   "/usr/lib/chromium/chromedriver",
                   "/usr/lib/chromium-browser/chromedriver"]

    chrome = next((p for p in chrome_bins if os.path.exists(p) or shutil.which(p)), None)
    driver = next((p for p in driver_bins if os.path.exists(p) or shutil.which(p)), None)

    if chrome and driver:
        opts.binary_location = chrome
        return webdriver.Chrome(service=Service(driver), options=opts)

    if USE_WDM:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    raise RuntimeError("ChromeDriver를 찾을 수 없습니다.")


# ── 리뷰 카드 파싱 ────────────────────────────────────────────────────────────
CARD_SELS = [
    ".review_list li",
    ".review_wrap li",
    ".prd_review_list li",
    "#reviewArea li",
    ".review_item",
]
MORE_SELS = [
    "button.more_btn",
    "a.more_btn",
    ".review_more button",
    ".btn_more",
    ".more_area button",
]


def _try_text(el, sels: list[str]) -> str:
    for s in sels:
        try:
            t = el.find_element(By.CSS_SELECTOR, s).text.strip()
            if t:
                return t
        except NoSuchElementException:
            pass
    return ""


def parse_card(card, product: dict) -> Review | None:
    # 본문
    text = _try_text(card, [
        ".review_cont", ".txt_review", ".txt_inner",
        ".review_text", "p.review", ".prd_review_cont",
    ])
    if not text:
        raw = card.text.strip()
        text = raw if len(raw) > 20 else ""
    if not text:
        return None

    # 별점
    raw_r = _try_text(card, [".point", ".grade_point", ".star_score", "em.point"])
    try:
        rating = float(re.sub(r"[^0-9.]", "", raw_r)[:3])
        if rating > 5:
            rating = 5.0
    except Exception:
        rating = 0.0

    # 피부 태그
    tags: list[str] = []
    for s in [".tag_list .tag", ".review_tag li", ".skin_tag span", "[class*='tag'] li"]:
        try:
            for e in card.find_elements(By.CSS_SELECTOR, s):
                t = e.text.strip()
                if t and t not in tags and len(t) < 20:
                    tags.append(t)
        except Exception:
            pass

    author  = _try_text(card, [".name", ".reviewer_id", ".user_id", ".nick"])
    date    = _try_text(card, [".date", ".review_date", "time"])
    helpful = _try_text(card, [".helpful_cnt", ".like_count", ".cnt_help"])

    return Review(
        product_id=product["id"],
        product_name=product["name"],
        brand=product["brand"],
        author=author,
        rating=rating,
        skin_type=", ".join(tags),
        date=date,
        text=text.replace("\n", " ").strip(),
        helpful=helpful,
    )


# ── 상품 1개 크롤링 ───────────────────────────────────────────────────────────
def crawl_product(product: dict) -> list[Review]:
    print(f"\n{'='*55}")
    print(f"[{product['id']}] {product['name']}")
    print(f"    URL: {product['url']}")
    print(f"{'='*55}")

    driver = make_driver()
    wait   = WebDriverWait(driver, 12)
    rows:  list[Review] = []
    seen:  set[str]     = set()

    try:
        driver.get(product["url"])
        time.sleep(3)

        # 팝업 닫기
        for sel in [".ly_close", ".close_btn", ".popup_close",
                    "button[aria-label='닫기']", ".modal_close"]:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(0.4)
            except Exception:
                pass

        # 리뷰 탭 클릭
        review_tab_clicked = False
        for sel in ["#review_link", "a[href*='review']",
                    ".tab_review", "[data-tab='review']",
                    "li.tab_review a"]:
            try:
                tab = driver.find_element(By.CSS_SELECTOR, sel)
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tab)
                tab.click()
                time.sleep(2)
                review_tab_clicked = True
                print(f"  ✓ 리뷰 탭 클릭 성공: {sel}")
                break
            except Exception:
                pass

        if not review_tab_clicked:
            print("  ⚠ 리뷰 탭을 찾지 못했습니다. 현재 페이지에서 수집 시도.")

        # 리뷰 섹션으로 스크롤
        for sel in ["#reviewArea", ".review_area", "[id*='review']", ".prd_review"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                driver.execute_script("arguments[0].scrollIntoView({block:'start'});", el)
                time.sleep(1)
                break
            except Exception:
                pass

        no_new_streak = 0
        click_count   = 0

        while len(rows) < TARGET_REVIEWS and click_count <= MAX_CLICKS:

            # 현재 카드 수집
            for sel in CARD_SELS:
                cards = driver.find_elements(By.CSS_SELECTOR, sel)
                if not cards:
                    continue
                for card in cards:
                    try:
                        rv = parse_card(card, product)
                        if rv and rv.text not in seen:
                            seen.add(rv.text)
                            rows.append(rv)
                    except StaleElementReferenceException:
                        pass
                if rows:
                    break

            prev_count = len(rows)
            print(f"  → 클릭 {click_count:02d}회 | 수집 {len(rows):03d}개", end="\r")

            if len(rows) >= TARGET_REVIEWS:
                print(f"\n  🎯 목표 {TARGET_REVIEWS}개 달성!")
                break

            # 더보기 클릭
            clicked = False
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.6)

            for sel in MORE_SELS:
                try:
                    btn = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    if btn.is_displayed() and btn.is_enabled():
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", btn
                        )
                        time.sleep(0.3)
                        try:
                            btn.click()
                        except ElementClickInterceptedException:
                            driver.execute_script("arguments[0].click();", btn)
                        clicked = True
                        click_count += 1
                        time.sleep(random.uniform(1.8, 2.8))
                        break
                except Exception:
                    pass

            if not clicked:
                print(f"\n  ℹ '더보기' 버튼 없음. 수집 종료.")
                break

            if len(rows) == prev_count:
                no_new_streak += 1
                if no_new_streak >= 4:
                    print(f"\n  ℹ 새 리뷰 없음 {no_new_streak}회 연속. 수집 종료.")
                    break
            else:
                no_new_streak = 0

    except Exception as e:
        print(f"\n  ❌ 오류 발생: {e}")

    finally:
        driver.quit()

    print(f"\n  ✅ {product['name']} → {len(rows)}개 수집 완료")
    return rows


# ── CSV 저장 ──────────────────────────────────────────────────────────────────
def save_csv(rows: list[Review], filename: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    field_names = [f.name for f in fields(Review)]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        for r in rows:
            writer.writerow(asdict(r))
    print(f"  💾 저장 완료: {path} ({len(rows)}행)")
    return path


# ── 메타 파일 저장 ────────────────────────────────────────────────────────────
def save_meta(results: dict):
    """각 상품의 크롤링 결과 요약을 JSON으로 저장"""
    os.makedirs(DATA_DIR, exist_ok=True)
    meta = {}
    for pid, info in results.items():
        meta[str(pid)] = {
            "product_id":   info["product"]["id"],
            "product_name": info["product"]["name"],
            "brand":        info["product"]["brand"],
            "filename":     info["product"]["filename"],
            "review_count": info["count"],
            "avg_rating":   info["avg_rating"],
        }
    path = os.path.join(DATA_DIR, "meta.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"\n📋 메타 파일 저장: {path}")


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("올리브영 리뷰 미리 크롤링 스크립트")
    print(f"대상: {len(PRODUCTS)}개 상품 / 상품당 목표: {TARGET_REVIEWS}개")
    print("=" * 55)

    all_results = {}

    for product in PRODUCTS:
        csv_path = os.path.join(DATA_DIR, product["filename"])

        # 이미 수집된 경우 스킵 옵션
        if os.path.exists(csv_path):
            import pandas as pd
            existing = pd.read_csv(csv_path)
            if len(existing) >= TARGET_REVIEWS:
                print(f"\n[{product['id']}] {product['name']}")
                print(f"  ⏩ 이미 {len(existing)}개 수집됨. 스킵. (재수집하려면 CSV 삭제)")
                all_results[product["id"]] = {
                    "product":    product,
                    "count":      len(existing),
                    "avg_rating": round(existing["rating"].mean(), 2),
                }
                continue

        rows = crawl_product(product)
        save_csv(rows, product["filename"])

        avg_r = round(sum(r.rating for r in rows if r.rating) / max(len(rows), 1), 2)
        all_results[product["id"]] = {
            "product":    product,
            "count":      len(rows),
            "avg_rating": avg_r,
        }

        # 상품 간 딜레이 (봇 감지 방지)
        if product != PRODUCTS[-1]:
            delay = random.uniform(3, 6)
            print(f"\n  ⏳ 다음 상품까지 {delay:.1f}초 대기...")
            time.sleep(delay)

    save_meta(all_results)

    print("\n" + "=" * 55)
    print("크롤링 완료 요약")
    print("=" * 55)
    for pid, info in all_results.items():
        print(f"  [{pid}] {info['product']['name']}: "
              f"{info['count']}개 / 평균 {info['avg_rating']}점")
    print("\n✅ 모든 수집 완료! 이제 'streamlit run app.py' 를 실행하세요.")


if __name__ == "__main__":
    main()
