import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import time
import re
import os
import shutil
from anthropic import Anthropic
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException,
    ElementClickInterceptedException,
)

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="🌿 OliveAI Insight",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
.step-badge {
    display:inline-block;background:#e8f5e9;color:#2e7d32;
    border-radius:20px;padding:4px 14px;font-size:.78rem;font-weight:600;margin-bottom:.5rem;
}
.metric-card {
    background:#fafafa;border:1px solid #e8e8e8;border-radius:12px;
    padding:1.2rem 1.5rem;text-align:center;
}
.metric-card .value{font-size:2.2rem;font-weight:700;color:#1a1a2e;}
.metric-card .label{font-size:.82rem;color:#888;margin-top:4px;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);padding:2rem 2.5rem;
border-radius:16px;margin-bottom:2rem;border:1px solid rgba(255,255,255,.08)">
<h1 style="color:#fff;margin:0;font-size:2rem;font-weight:700">🌿 OliveAI Review Intelligence</h1>
<p style="color:rgba(255,255,255,.6);margin:.5rem 0 0;font-size:.95rem">
URL 입력 → 실시간 리뷰 수집 → Claude AI 분석 → 인터랙티브 대시보드</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# API 키
# ─────────────────────────────────────────────
if "CLAUDE_API_KEY" in st.secrets:
    api_key = st.secrets["CLAUDE_API_KEY"]
else:
    with st.sidebar:
        st.subheader("⚙️ 설정")
        api_key = st.text_input("Claude API Key", type="password", placeholder="sk-ant-...")

if not api_key:
    st.warning("👈 사이드바에서 Claude API Key를 입력해주세요.")
    st.stop()

client = Anthropic(api_key=api_key)

# ─────────────────────────────────────────────
# STEP 1 : ChromeDriver — 클라우드/로컬 자동 감지
# ─────────────────────────────────────────────
def _get_driver() -> webdriver.Chrome:
    """
    Streamlit Cloud (Debian) 과 로컬 환경을 모두 지원.

    우선순위
    ① 시스템 chromium + chromedriver  (packages.txt 경유, 클라우드 환경)
    ② webdriver-manager 자동 다운로드 (로컬 개발 환경)
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--single-process")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=ko-KR")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # ① 시스템 설치 경로 탐색 (Streamlit Cloud / Debian / Ubuntu)
    CHROME_BINS = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
    ]
    DRIVER_BINS = [
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
        "/snap/bin/chromium.chromedriver",
    ]

    chrome_bin = next(
        (p for p in CHROME_BINS if os.path.exists(p) or shutil.which(p)), None
    )
    driver_bin = next(
        (p for p in DRIVER_BINS if os.path.exists(p) or shutil.which(p)), None
    )

    if chrome_bin and driver_bin:
        options.binary_location = chrome_bin
        return webdriver.Chrome(service=Service(driver_bin), options=options)

    # ② webdriver-manager (로컬 개발)
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        return webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )
    except Exception as e:
        raise RuntimeError(
            "ChromeDriver 시작 실패.\n"
            "Streamlit Cloud: 레포 루트에 packages.txt 파일이 있고 "
            "'chromium'과 'chromium-driver'가 포함되어 있는지 확인하세요.\n"
            f"원본 오류: {e}"
        ) from e


# ─────────────────────────────────────────────
# 셀렉터 상수
# ─────────────────────────────────────────────
CARD_SELECTORS = [
    ".review_list li", ".review_wrap li", ".prd_review_list li",
    "#reviewArea li", ".review_item", "[class*='review'] li",
]
MORE_BTN_SELECTORS = [
    "button.more_btn", "a.more_btn", ".review_more button",
    ".btn_more", ".more_area button",
]


def _parse_card(card) -> dict | None:
    def _try(sels):
        for s in sels:
            try:
                t = card.find_element(By.CSS_SELECTOR, s).text.strip()
                if t:
                    return t
            except NoSuchElementException:
                pass
        return ""

    text = _try([".review_cont", ".txt_review", ".review_text", "p.review", ".prd_review_cont"])
    if not text:
        raw = card.text.strip()
        text = raw if len(raw) > 30 else ""
    if not text:
        return None

    rating_raw = _try([".point", ".grade_point", ".star_score"])
    try:
        rating = float(re.sub(r"[^0-9.]", "", rating_raw)[:3])
    except Exception:
        rating = 0.0

    tags = []
    for s in [".tag_list .tag", ".review_tag li", ".skin_tag span", "[class*='tag'] li"]:
        try:
            for el in card.find_elements(By.CSS_SELECTOR, s):
                t = el.text.strip()
                if t and t not in tags:
                    tags.append(t)
        except Exception:
            pass

    return {
        "text":      text,
        "rating":    rating,
        "skin_type": ", ".join(tags),
        "date":      _try([".date", ".review_date", "time"]),
        "author":    _try([".name", ".reviewer_id", ".user_id"]),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def crawl_reviews(url: str, target: int = 100) -> pd.DataFrame:
    driver = _get_driver()
    wait   = WebDriverWait(driver, 10)
    rows: list[dict] = []

    try:
        driver.get(url)
        time.sleep(3)

        for sel in [".ly_close", ".close_btn", ".popup_close"]:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    btn.click(); time.sleep(0.4)
            except Exception:
                pass

        for sel in ["#review_link", "a[href*='review']", ".tab_review"]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel).click()
                time.sleep(2); break
            except Exception:
                pass

        seen:  set[str] = set()
        clicks = 0
        no_new = 0

        while len(rows) < target and clicks < 50:
            for sel in CARD_SELECTORS:
                cards = driver.find_elements(By.CSS_SELECTOR, sel)
                if not cards:
                    continue
                for card in cards:
                    try:
                        d = _parse_card(card)
                        if d and d["text"] not in seen:
                            seen.add(d["text"])
                            rows.append(d)
                    except StaleElementReferenceException:
                        pass
                if rows:
                    break

            if len(rows) >= target:
                break

            prev    = len(rows)
            clicked = False
            for sel in MORE_BTN_SELECTORS:
                try:
                    btn = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    if btn.is_displayed() and btn.is_enabled():
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", btn
                        )
                        time.sleep(0.4)
                        try:
                            btn.click()
                        except ElementClickInterceptedException:
                            driver.execute_script("arguments[0].click();", btn)
                        clicked = True
                        clicks += 1
                        time.sleep(2)
                        break
                except Exception:
                    pass

            if not clicked:
                break
            if len(rows) == prev:
                no_new += 1
                if no_new >= 3:
                    break
            else:
                no_new = 0

    finally:
        driver.quit()

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ─────────────────────────────────────────────
# STEP 2 : Claude 분석
# ─────────────────────────────────────────────
COMPETITOR = "구달 청귤 비타C 패드"


@st.cache_data(ttl=86400, show_spinner=False)
def analyze_with_claude(_df: pd.DataFrame) -> dict:
    sample    = _df["text"].head(80).tolist()
    skin_tags = (
        _df["skin_type"].dropna()
        .str.split(", ").explode()
        .value_counts().head(10).to_dict()
    )
    avg_r = round(_df["rating"].mean(), 2) if "rating" in _df.columns else 0

    prompt = f"""당신은 올리브영 시니어 PM 겸 데이터 애널리스트입니다.
아래 고객 리뷰 {len(sample)}개를 분석하여 전략 리포트를 JSON으로만 작성하세요.
다른 텍스트 없이 순수 JSON만 출력하세요.

[기본 통계] 평균 별점: {avg_r} / 피부 태그: {json.dumps(skin_tags, ensure_ascii=False)}
[리뷰]: {chr(10).join(f'{i+1}. {t}' for i, t in enumerate(sample))}

{{
  "summary": "한 문장 핵심 요약",
  "ai_score": {{"sensitive_skin":85,"oily_skin":70,"dry_skin":78,"overall":82}},
  "sentiment": {{
    "positive_keywords":["키워드1","키워드2","키워드3","키워드4","키워드5","키워드6","키워드7","키워드8"],
    "negative_keywords":["키워드1","키워드2","키워드3","키워드4"],
    "positive_ratio":78
  }},
  "persona_analysis":[
    {{"persona":"잡티/미백 고민","satisfaction":88,"key_review":"대표 리뷰","count_ratio":35}},
    {{"persona":"탄력/주름 고민","satisfaction":72,"key_review":"대표 리뷰","count_ratio":28}},
    {{"persona":"민감/진정 고민","satisfaction":81,"key_review":"대표 리뷰","count_ratio":25}},
    {{"persona":"보습/건조 고민","satisfaction":76,"key_review":"대표 리뷰","count_ratio":12}}
  ],
  "top_ingredients":[
    {{"name":"성분명","mention_count":30,"sentiment":"positive"}},
    {{"name":"성분명","mention_count":22,"sentiment":"positive"}},
    {{"name":"성분명","mention_count":18,"sentiment":"positive"}},
    {{"name":"성분명","mention_count":14,"sentiment":"neutral"}},
    {{"name":"성분명","mention_count":10,"sentiment":"negative"}}
  ],
  "unmet_needs":[
    {{"need":"미충족 니즈 1","frequency":"높음","opportunity":"기회 설명"}},
    {{"need":"미충족 니즈 2","frequency":"중간","opportunity":"기회 설명"}},
    {{"need":"미충족 니즈 3","frequency":"중간","opportunity":"기회 설명"}}
  ],
  "competitor_simulation":{{
    "competitor_name":"{COMPETITOR}",
    "comparison":[
      {{"dimension":"보습력","this_product":82,"competitor":75}},
      {{"dimension":"흡수력","this_product":88,"competitor":80}},
      {{"dimension":"자극없음","this_product":85,"competitor":72}},
      {{"dimension":"가성비","this_product":70,"competitor":88}},
      {{"dimension":"성분","this_product":78,"competitor":82}},
      {{"dimension":"향/사용감","this_product":80,"competitor":76}}
    ]
  }},
  "winning_points":[
    {{"factor":"강점 1","score":90,"reason":"설명"}},
    {{"factor":"강점 2","score":83,"reason":"설명"}},
    {{"factor":"강점 3","score":77,"reason":"설명"}}
  ]
}}"""

    msg   = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    raw   = msg.content[0].text
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(match.group() if match else raw)


# ─────────────────────────────────────────────
# STEP 3 : Claude Artifacts HTML 대시보드
# ─────────────────────────────────────────────
def generate_dashboard_html(df: pd.DataFrame, insight: dict, product_name: str) -> str:
    avg_r = round(df["rating"].mean(), 2) if "rating" in df.columns else 0
    prompt = f"""당신은 시니어 프론트엔드 개발자입니다.
올리브영 AI 리뷰 분석 데이터를 바탕으로 완전한 인터랙티브 HTML 대시보드를 생성하세요.

[데이터] 상품: {product_name} / 리뷰: {len(df)}개 / 별점: {avg_r}
[AI 분석]: {json.dumps(insight, ensure_ascii=False, indent=2)}

[구현 요소]
1. Word Cloud (Canvas, 빈도 기반 폰트 크기)
2. AI Score 프로그레스바 (피부 타입별 추천 지수)
3. Sentiment 태그 클라우드 (긍정=초록, 부정=빨강)
4. Persona 만족도 바 차트 (Chart.js)
5. Product Gap 카드
6. Competitor 비교 바 차트 ({insight.get('competitor_simulation',{}).get('competitor_name','경쟁사')})
7. 올리브영 브랜드 컬러 #4CAF50/#2e7d32, 반응형

[요건] 단일 HTML / CDN만(Chart.js) / 실제 데이터 하드코딩 / 카운터 애니메이션

완전한 HTML만 출력하세요. 설명 없이."""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=6000,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text
    for pat in [r"<!DOCTYPE html>.*?</html>", r"<html.*?</html>"]:
        m = re.search(pat, raw, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group()
    return raw


# ─────────────────────────────────────────────
# 메인 UI
# ─────────────────────────────────────────────
c_url, c_btn = st.columns([5, 1])
with c_url:
    input_url = st.text_input(
        "올리브영 URL",
        placeholder="https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=...",
        label_visibility="collapsed",
    )
with c_btn:
    run_btn = st.button("🔍 분석 시작", use_container_width=True, type="primary")

if run_btn:
    if not input_url.strip():
        st.warning("URL을 입력해주세요.")
        st.stop()

    # ── STEP 1 ────────────────────────────────
    st.markdown('<span class="step-badge">STEP 1</span> **실시간 리뷰 수집**',
                unsafe_allow_html=True)
    with st.spinner("🔄 Selenium으로 리뷰 수집 중... (20~40초)"):
        df = crawl_reviews(input_url, target=100)

    if df.empty:
        st.error("❌ 리뷰 수집 실패. URL을 확인하거나 잠시 후 다시 시도해주세요.")
        st.stop()

    st.success(f"✅ **{len(df)}개** 리뷰 수집 완료!")
    st.download_button(
        "📥 reviews.csv 다운로드",
        df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
        "reviews.csv", "text/csv",
    )
    with st.expander("📋 수집 데이터 미리보기"):
        st.dataframe(df.head(10), use_container_width=True)

    st.divider()

    # ── STEP 2 ────────────────────────────────
    st.markdown('<span class="step-badge">STEP 2</span> **Claude AI 분석**',
                unsafe_allow_html=True)
    with st.spinner("🧠 Claude 분석 중..."):
        try:
            insight = analyze_with_claude(df)
        except Exception as e:
            st.error(f"AI 분석 오류: {e}")
            st.stop()

    st.success("✅ AI 분석 완료!")
    st.markdown(f"> 💡 **핵심 요약:** {insight.get('summary','')}")

    avg_r2 = round(df["rating"].mean(), 2) if "rating" in df.columns else 0
    pos_r  = insight.get("sentiment", {}).get("positive_ratio", 0)
    ai_s   = insight.get("ai_score",  {}).get("overall", 0)
    unmet  = len(insight.get("unmet_needs", []))

    for col, val, label in zip(
        st.columns(4),
        [f"⭐ {avg_r2}", f"{pos_r}%", f"{ai_s}점", f"{unmet}건"],
        ["평균 별점", "긍정 리뷰 비율", "AI 종합 지수", "미충족 니즈"],
    ):
        col.markdown(
            f'<div class="metric-card"><div class="value">{val}</div>'
            f'<div class="label">{label}</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    tab1, tab2, tab3, tab4 = st.tabs(
        ["😊 감성 분석", "👤 페르소나", "🚀 제품 갭", "🏆 경쟁사 비교"]
    )

    with tab1:
        s   = insight.get("sentiment", {})
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("✅ 긍정")
            for kw in s.get("positive_keywords", []):
                st.markdown(
                    f'<span style="background:#e8f5e9;color:#2e7d32;padding:4px 12px;'
                    f'border-radius:20px;margin:3px;display:inline-block">{kw}</span>',
                    unsafe_allow_html=True,
                )
        with c2:
            st.subheader("⚠️ 부정")
            for kw in s.get("negative_keywords", []):
                st.markdown(
                    f'<span style="background:#fce4ec;color:#c62828;padding:4px 12px;'
                    f'border-radius:20px;margin:3px;display:inline-block">{kw}</span>',
                    unsafe_allow_html=True,
                )
        pr = s.get("positive_ratio", 0)
        fig = go.Figure(data=[go.Pie(
            labels=["긍정", "부정"], values=[pr, 100-pr], hole=0.65,
            marker_colors=["#4CAF50", "#ef5350"],
        )])
        fig.update_layout(
            showlegend=True, height=300,
            annotations=[dict(text=f"{pr}%", x=0.5, y=0.5, font_size=22, showarrow=False)],
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        personas = insight.get("persona_analysis", [])
        if personas:
            df_p = pd.DataFrame(personas)
            fig  = px.bar(
                df_p, x="persona", y="satisfaction",
                color="satisfaction", color_continuous_scale="Greens",
                text="satisfaction", title="피부 고민별 만족도",
            )
            fig.update_traces(texttemplate="%{text}점", textposition="outside")
            fig.update_layout(coloraxis_showscale=False, height=380)
            st.plotly_chart(fig, use_container_width=True)
            for p in personas:
                st.markdown(
                    f'<div style="background:#f5f5ff;border:1px solid #ddd;border-radius:12px;'
                    f'padding:1rem 1.4rem;margin:.5rem 0">'
                    f'<strong>{p["persona"]}</strong> (만족도 {p["satisfaction"]}점 · {p["count_ratio"]}%)'
                    f'<br><span style="color:#555;font-size:.9rem">"{p["key_review"]}"</span></div>',
                    unsafe_allow_html=True,
                )

    with tab3:
        for item in insight.get("unmet_needs", []):
            fc = {"높음": "#ef5350", "중간": "#FF9800", "낮음": "#4CAF50"}.get(
                item.get("frequency", ""), "#999"
            )
            st.markdown(
                f'<div style="border-left:4px solid {fc};padding:.8rem 1.2rem;'
                f'margin:.6rem 0;background:#fafafa;border-radius:0 8px 8px 0">'
                f'<strong>{item["need"]}</strong> '
                f'<span style="background:{fc};color:#fff;padding:2px 8px;'
                f'border-radius:10px;font-size:.75rem">{item.get("frequency","")}</span>'
                f'<br><span style="color:#666;font-size:.88rem">💡 {item["opportunity"]}</span></div>',
                unsafe_allow_html=True,
            )

    with tab4:
        comp = insight.get("competitor_simulation", {})
        cl   = comp.get("comparison", [])
        if cl:
            df_c = pd.DataFrame(cl)
            fig  = go.Figure([
                go.Bar(name="분석 상품", x=df_c["dimension"],
                       y=df_c["this_product"], marker_color="#4CAF50"),
                go.Bar(name=comp.get("competitor_name", COMPETITOR),
                       x=df_c["dimension"], y=df_c["competitor"], marker_color="#90A4AE"),
            ])
            fig.update_layout(barmode="group", height=380, yaxis=dict(range=[0, 100]))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── STEP 3 ────────────────────────────────
    st.markdown('<span class="step-badge">STEP 3</span> **AI 리뷰 요약 위젯 (Claude Artifacts)**',
                unsafe_allow_html=True)
    product_guess = input_url.split("goodsNo=")[-1] if "goodsNo=" in input_url else "올리브영 상품"
    with st.spinner("🎨 Claude가 대시보드 HTML 생성 중... (20~30초)"):
        try:
            html_code = generate_dashboard_html(df, insight, product_guess)
        except Exception as e:
            st.error(f"대시보드 생성 오류: {e}")
            st.stop()

    st.success("✅ AI 리뷰 요약 위젯 생성 완료!")
    st.components.v1.html(html_code, height=900, scrolling=True)
    st.download_button(
        "💾 대시보드 HTML 다운로드",
        html_code.encode("utf-8"),
        "olive_ai_dashboard.html",
        "text/html",
    )
