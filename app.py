import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import time
import re
import io
import base64
from collections import Counter
from anthropic import Anthropic
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
)
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="🌿 OliveAI Insight",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# 커스텀 CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Pretendard', sans-serif;
}
.main-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    border: 1px solid rgba(255,255,255,0.08);
}
.main-header h1 { color: #fff; margin: 0; font-size: 2rem; font-weight: 700; }
.main-header p  { color: rgba(255,255,255,0.6); margin: 0.5rem 0 0; font-size: 0.95rem; }
.step-badge {
    display: inline-block;
    background: #e8f5e9;
    color: #2e7d32;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}
.metric-card {
    background: #fafafa;
    border: 1px solid #e8e8e8;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-card .value { font-size: 2.2rem; font-weight: 700; color: #1a1a2e; }
.metric-card .label { font-size: 0.82rem; color: #888; margin-top: 4px; }
.insight-box {
    background: linear-gradient(135deg, #667eea10, #764ba210);
    border: 1px solid #667eea30;
    border-radius: 12px;
    padding: 1rem 1.4rem;
    margin: 0.5rem 0;
}
.artifact-container {
    border: 2px solid #4CAF50;
    border-radius: 16px;
    padding: 1rem;
    background: #f9fff9;
    margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🌿 OliveAI Review Intelligence</h1>
    <p>URL 입력 → 실시간 리뷰 수집 → Claude AI 분석 → 인터랙티브 대시보드</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# API 키 설정
# ─────────────────────────────────────────────
if "CLAUDE_API_KEY" in st.secrets:
    api_key = st.secrets["CLAUDE_API_KEY"]
else:
    with st.sidebar:
        st.subheader("⚙️ 설정")
        api_key = st.text_input("Claude API Key", type="password", placeholder="sk-ant-...")
        st.caption("Anthropic Console에서 발급받은 키를 입력하세요.")

if not api_key:
    st.warning("👈 사이드바에서 Claude API Key를 입력해주세요.")
    st.stop()

client = Anthropic(api_key=api_key)

# ─────────────────────────────────────────────
# STEP 1 : 크롤링
# ─────────────────────────────────────────────
CARD_SELECTORS = [
    ".review_list li", ".review_wrap li", ".prd_review_list li",
    "#reviewArea li", ".review_item", "[class*='review'] li",
]
MORE_BTN_SELECTORS = [
    "button.more_btn", "a.more_btn", ".review_more button",
    ".btn_more", ".more_area button",
]

def _get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ko-KR")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    return driver

def _parse_card(card):
    """리뷰 카드 요소 → dict"""
    def _try(selectors, attr="text"):
        for sel in selectors:
            try:
                el = card.find_element(By.CSS_SELECTOR, sel)
                return el.text.strip() if attr == "text" else el.get_attribute(attr)
            except NoSuchElementException:
                continue
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
    for sel in [".tag_list .tag", ".review_tag li", ".skin_tag span", "[class*='tag'] li"]:
        try:
            for el in card.find_elements(By.CSS_SELECTOR, sel):
                t = el.text.strip()
                if t and t not in tags:
                    tags.append(t)
        except Exception:
            continue

    date   = _try([".date", ".review_date", "time"])
    author = _try([".name", ".reviewer_id", ".user_id"])

    return {"text": text, "rating": rating, "skin_type": ", ".join(tags),
            "date": date, "author": author}

@st.cache_data(ttl=3600, show_spinner=False)
def crawl_reviews(url: str, target: int = 100) -> pd.DataFrame:
    driver = _get_driver()
    wait   = WebDriverWait(driver, 10)
    rows   = []
    try:
        driver.get(url)
        time.sleep(3)

        # 팝업 닫기
        for sel in [".ly_close", ".close_btn", ".popup_close"]:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    btn.click(); time.sleep(0.4)
            except Exception:
                pass

        # 리뷰 탭 클릭
        for sel in ["#review_link", "a[href*='review']", ".tab_review"]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel).click()
                time.sleep(2); break
            except Exception:
                pass

        seen  = set()
        clicks = 0
        no_new = 0

        while len(rows) < target and clicks < 50:
            # 현재 페이지 카드 수집
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

            prev = len(rows)

            # 더보기 버튼 클릭
            clicked = False
            for sel in MORE_BTN_SELECTORS:
                try:
                    btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                    if btn.is_displayed() and btn.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
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
    sample = _df["text"].head(80).tolist()
    skin_tags = _df["skin_type"].dropna().str.split(", ").explode().value_counts().head(10).to_dict()
    avg_rating = round(_df["rating"].mean(), 2) if "rating" in _df.columns else 0

    prompt = f"""
당신은 올리브영 시니어 PM 겸 데이터 애널리스트입니다.
아래 고객 리뷰 {len(sample)}개를 분석하여 전략 리포트를 작성하세요.

[기본 통계]
- 평균 별점: {avg_rating}
- 피부 타입 태그 분포: {json.dumps(skin_tags, ensure_ascii=False)}

[리뷰 샘플]:
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(sample))}

반드시 아래 JSON 형식만 출력하세요. 다른 텍스트 없이 JSON만:
{{
  "summary": "한 문장 핵심 요약",
  "ai_score": {{
    "sensitive_skin": 85,
    "oily_skin": 70,
    "dry_skin": 78,
    "overall": 82
  }},
  "sentiment": {{
    "positive_keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5", "키워드6", "키워드7", "키워드8"],
    "negative_keywords": ["키워드1", "키워드2", "키워드3", "키워드4"],
    "positive_ratio": 78
  }},
  "persona_analysis": [
    {{"persona": "잡티/미백 고민", "satisfaction": 88, "key_review": "대표 리뷰 한 줄", "count_ratio": 35}},
    {{"persona": "탄력/주름 고민", "satisfaction": 72, "key_review": "대표 리뷰 한 줄", "count_ratio": 28}},
    {{"persona": "민감/진정 고민", "satisfaction": 81, "key_review": "대표 리뷰 한 줄", "count_ratio": 25}},
    {{"persona": "보습/건조 고민", "satisfaction": 76, "key_review": "대표 리뷰 한 줄", "count_ratio": 12}}
  ],
  "top_ingredients": [
    {{"name": "성분명", "mention_count": 30, "sentiment": "positive"}},
    {{"name": "성분명", "mention_count": 22, "sentiment": "positive"}},
    {{"name": "성분명", "mention_count": 18, "sentiment": "positive"}},
    {{"name": "성분명", "mention_count": 14, "sentiment": "neutral"}},
    {{"name": "성분명", "mention_count": 10, "sentiment": "negative"}},
    {{"name": "성분명", "mention_count": 8, "sentiment": "positive"}},
    {{"name": "성분명", "mention_count": 7, "sentiment": "positive"}}
  ],
  "unmet_needs": [
    {{"need": "미충족 니즈 1", "frequency": "높음", "opportunity": "기회 설명"}},
    {{"need": "미충족 니즈 2", "frequency": "중간", "opportunity": "기회 설명"}},
    {{"need": "미충족 니즈 3", "frequency": "중간", "opportunity": "기회 설명"}}
  ],
  "competitor_simulation": {{
    "competitor_name": "{COMPETITOR}",
    "comparison": [
      {{"dimension": "보습력", "this_product": 82, "competitor": 75}},
      {{"dimension": "흡수력", "this_product": 88, "competitor": 80}},
      {{"dimension": "자극없음", "this_product": 85, "competitor": 72}},
      {{"dimension": "가성비", "this_product": 70, "competitor": 88}},
      {{"dimension": "성분", "this_product": 78, "competitor": 82}},
      {{"dimension": "향/사용감", "this_product": 80, "competitor": 76}}
    ]
  }},
  "winning_points": [
    {{"factor": "강점 1", "score": 90, "reason": "설명"}},
    {{"factor": "강점 2", "score": 83, "reason": "설명"}},
    {{"factor": "강점 3", "score": 77, "reason": "설명"}}
  ]
}}
"""
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text
    # JSON 추출
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(raw)

# ─────────────────────────────────────────────
# STEP 3 : Claude Artifacts HTML 대시보드 생성
# ─────────────────────────────────────────────
def generate_dashboard_html(df: pd.DataFrame, insight: dict, product_name: str) -> str:
    """Claude API를 호출해 인터랙티브 HTML 대시보드를 생성합니다."""
    
    insight_str = json.dumps(insight, ensure_ascii=False, indent=2)
    avg_rating = round(df["rating"].mean(), 2) if "rating" in df.columns else 0
    total_reviews = len(df)

    prompt = f"""
당신은 시니어 프론트엔드 개발자입니다.
올리브영 AI 리뷰 분석 데이터를 바탕으로, 올리브영 앱 내 'AI 리뷰 요약 위젯' 수준의
완전한 인터랙티브 HTML 대시보드를 생성해주세요.

[분석 데이터]
- 상품명(추정): {product_name}
- 총 리뷰 수: {total_reviews}개
- 평균 별점: {avg_rating}
- AI 분석 결과: {insight_str}

[필수 구현 요소]
1. **Word Cloud 시각화** - 성분/효과 키워드를 크기별로 배치 (Canvas 또는 SVG, 빈도 기반 폰트 크기)
2. **AI Score 카드** - 민감성/지성/건성 피부 추천 지수를 원형 프로그레스바로 표현
3. **Sentiment Map** - 긍정/부정 키워드를 색상 구분된 태그 클라우드로
4. **Persona Radar** - 피부 고민별 만족도 차이를 레이더 차트로 (Canvas 기반)
5. **Product Gap** - 미충족 니즈를 시각적 카드로
6. **Competitor Comparison** - 경쟁사({insight['competitor_simulation']['competitor_name']})와의 방사형/바 차트 비교
7. **올리브영 스타일** - 초록 계열(#4CAF50, #2e7d32) 브랜드 컬러, 모바일 친화적 레이아웃

[기술 요건]
- 단일 HTML 파일 (외부 CDN만 사용 가능: Chart.js, D3.js 등)
- 애니메이션 포함 (로딩 시 카운터 애니메이션, 호버 효과)
- 실제 데이터 하드코딩해서 즉시 동작하게
- 반응형 디자인

완전한 HTML 코드만 출력하세요. 설명 텍스트 없이.
"""
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=6000,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text
    # HTML 추출
    match = re.search(r"<!DOCTYPE html>.*?</html>", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group()
    # <html>...</html> 형태
    match2 = re.search(r"<html.*?</html>", raw, re.DOTALL | re.IGNORECASE)
    if match2:
        return match2.group()
    return raw

# ─────────────────────────────────────────────
# 메인 UI
# ─────────────────────────────────────────────
col_url, col_btn = st.columns([5, 1])
with col_url:
    input_url = st.text_input(
        "올리브영 상품 URL",
        placeholder="https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=...",
        label_visibility="collapsed"
    )
with col_btn:
    run_btn = st.button("🔍 분석 시작", use_container_width=True, type="primary")

# ─────────────────────────────────────────────
# 실행 파이프라인
# ─────────────────────────────────────────────
if run_btn:
    if not input_url.strip():
        st.warning("URL을 입력해주세요.")
        st.stop()

    # ── STEP 1: 크롤링 ────────────────────────
    st.markdown('<span class="step-badge">STEP 1</span> **실시간 리뷰 수집**', unsafe_allow_html=True)
    with st.spinner("🔄 Selenium으로 리뷰 데이터 수집 중... (약 20~40초)"):
        df = crawl_reviews(input_url, target=100)

    if df.empty:
        st.error("❌ 리뷰 수집 실패. URL을 확인하거나 잠시 후 다시 시도해주세요.")
        st.stop()

    st.success(f"✅ 총 **{len(df)}개** 리뷰 수집 완료!")

    # CSV 다운로드 버튼
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("📥 reviews.csv 다운로드", csv_bytes, "reviews.csv", "text/csv")

    with st.expander("📋 수집된 리뷰 미리보기"):
        st.dataframe(df.head(10), use_container_width=True)

    st.divider()

    # ── STEP 2: AI 분석 ───────────────────────
    st.markdown('<span class="step-badge">STEP 2</span> **Claude AI 분석**', unsafe_allow_html=True)
    with st.spinner("🧠 Claude가 리뷰를 분석 중..."):
        try:
            insight = analyze_with_claude(df)
        except Exception as e:
            st.error(f"AI 분석 오류: {e}")
            st.stop()

    st.success("✅ AI 분석 완료!")
    st.markdown(f"> 💡 **핵심 요약:** {insight.get('summary', '')}")

    # ── 메트릭 카드 ───────────────────────────
    avg_r = round(df["rating"].mean(), 2) if "rating" in df.columns else 0
    pos_r = insight.get("sentiment", {}).get("positive_ratio", 0)
    ai_s  = insight.get("ai_score", {}).get("overall", 0)
    unmet = len(insight.get("unmet_needs", []))

    m1, m2, m3, m4 = st.columns(4)
    for col, val, label in [
        (m1, f"⭐ {avg_r}", "평균 별점"),
        (m2, f"{pos_r}%", "긍정 리뷰 비율"),
        (m3, f"{ai_s}점", "AI 종합 지수"),
        (m4, f"{unmet}건", "미충족 니즈"),
    ]:
        col.markdown(f"""
        <div class="metric-card">
          <div class="value">{val}</div>
          <div class="label">{label}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── 분석 차트 ─────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["😊 감성 분석", "👤 페르소나", "🚀 제품 갭", "🏆 경쟁사 비교"])

    with tab1:
        s = insight.get("sentiment", {})
        pos_kw = s.get("positive_keywords", [])
        neg_kw = s.get("negative_keywords", [])

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("✅ 긍정 키워드")
            for kw in pos_kw:
                st.markdown(f'<span style="background:#e8f5e9;color:#2e7d32;padding:4px 12px;border-radius:20px;margin:3px;display:inline-block;font-size:0.88rem">{kw}</span>', unsafe_allow_html=True)
        with c2:
            st.subheader("⚠️ 부정 키워드")
            for kw in neg_kw:
                st.markdown(f'<span style="background:#fce4ec;color:#c62828;padding:4px 12px;border-radius:20px;margin:3px;display:inline-block;font-size:0.88rem">{kw}</span>', unsafe_allow_html=True)

        # 감성 비율 도넛차트
        fig = go.Figure(data=[go.Pie(
            labels=["긍정", "부정"],
            values=[pos_r, 100 - pos_r],
            hole=0.65,
            marker_colors=["#4CAF50", "#ef5350"],
        )])
        fig.update_layout(showlegend=True, height=300,
                          annotations=[dict(text=f"{pos_r}%", x=0.5, y=0.5, font_size=22, showarrow=False)])
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        personas = insight.get("persona_analysis", [])
        if personas:
            df_p = pd.DataFrame(personas)
            fig = px.bar(df_p, x="persona", y="satisfaction", color="satisfaction",
                         color_continuous_scale="Greens", text="satisfaction",
                         labels={"satisfaction": "만족도 점수"}, title="피부 고민별 만족도")
            fig.update_traces(texttemplate="%{text}점", textposition="outside")
            fig.update_layout(coloraxis_showscale=False, height=380)
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("페르소나별 대표 리뷰")
            for p in personas:
                st.markdown(f"""
                <div class="insight-box">
                  <strong>{p['persona']}</strong> (만족도 {p['satisfaction']}점 · 비중 {p['count_ratio']}%)
                  <br><span style="color:#555;font-size:0.9rem">"{p['key_review']}"</span>
                </div>""", unsafe_allow_html=True)

    with tab3:
        unmet_list = insight.get("unmet_needs", [])
        for item in unmet_list:
            freq_color = {"높음": "#ef5350", "중간": "#FF9800", "낮음": "#4CAF50"}.get(item.get("frequency", ""), "#999")
            st.markdown(f"""
            <div style="border-left: 4px solid {freq_color}; padding: 0.8rem 1.2rem; margin: 0.6rem 0; background: #fafafa; border-radius: 0 8px 8px 0;">
              <strong>{item['need']}</strong>
              <span style="background:{freq_color};color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75rem;margin-left:8px">{item.get('frequency','')}</span>
              <br><span style="color:#666;font-size:0.88rem">💡 {item['opportunity']}</span>
            </div>""", unsafe_allow_html=True)

    with tab4:
        comp_data = insight.get("competitor_simulation", {})
        comp_name = comp_data.get("competitor_name", COMPETITOR)
        comp_list = comp_data.get("comparison", [])
        if comp_list:
            df_c = pd.DataFrame(comp_list)
            fig = go.Figure()
            fig.add_trace(go.Bar(name="분석 상품", x=df_c["dimension"], y=df_c["this_product"], marker_color="#4CAF50"))
            fig.add_trace(go.Bar(name=comp_name, x=df_c["dimension"], y=df_c["competitor"], marker_color="#90A4AE"))
            fig.update_layout(barmode="group", title=f"vs. {comp_name} 비교", height=380,
                              yaxis=dict(range=[0, 100]))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── STEP 3: Claude Artifacts 대시보드 ─────
    st.markdown('<span class="step-badge">STEP 3</span> **AI 리뷰 요약 위젯 (Claude Artifacts)**', unsafe_allow_html=True)

    product_guess = input_url.split("goodsNo=")[-1] if "goodsNo=" in input_url else "올리브영 상품"

    with st.spinner("🎨 Claude가 인터랙티브 대시보드 HTML을 생성 중... (약 20~30초)"):
        try:
            html_code = generate_dashboard_html(df, insight, product_guess)
        except Exception as e:
            st.error(f"대시보드 생성 오류: {e}")
            st.stop()

    st.success("✅ AI 리뷰 요약 위젯 생성 완료!")

    st.markdown('<div class="artifact-container">', unsafe_allow_html=True)
    st.components.v1.html(html_code, height=900, scrolling=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # HTML 다운로드 버튼
    html_bytes = html_code.encode("utf-8")
    st.download_button(
        "💾 대시보드 HTML 다운로드",
        html_bytes,
        "olive_ai_dashboard.html",
        "text/html"
    )
