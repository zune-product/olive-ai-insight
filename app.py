"""
app.py
──────
올리브영 AI 리뷰 인사이트 - 메인 Streamlit 앱

구조:
  1. 올리브영 베스트 페이지 클론 (oliveyoung_best.html) 임베드
  2. ?product=N 파라미터로 상품 선택 → 해당 CSV 읽기
  3. Claude API로 분석 → 인터랙티브 대시보드 출력
"""

import os
import json
import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from anthropic import Anthropic

# ─────────────────────────────────────────────
# 상수 / 설정
# ─────────────────────────────────────────────
DATA_DIR = "data"
META_FILE = os.path.join(DATA_DIR, "meta.json")

PRODUCTS = {
    1: {
        "name":     "라운드랩 1025 독도 토너",
        "brand":    "라운드랩",
        "filename": "product_1_roundlab_toner.csv",
        "color":    "#1a5fa8",
        "bg":       "#e8f4fd",
        "emoji":    "💧",
        "desc":     "제주 독도 해양심층수 성분 · 저자극 데일리 토너",
    },
    2: {
        "name":     "아누아 어성초 77 수딩 토너",
        "brand":    "아누아",
        "filename": "product_2_anua_toner.csv",
        "color":    "#2d6a2d",
        "bg":       "#f0faf0",
        "emoji":    "🌿",
        "desc":     "어성초 추출물 77% · 진정 & 수분 특화 토너",
    },
    3: {
        "name":     "토리든 다이브인 히알루론산 세럼",
        "brand":    "토리든",
        "filename": "product_3_torriden_serum.csv",
        "color":    "#3949ab",
        "bg":       "#e8f0fe",
        "emoji":    "✨",
        "desc":     "저분자 히알루론산 5종 · 속건조 집중케어 세럼",
    },
    4: {
        "name":     "구달 청귤 비타C 잡티케어 세럼",
        "brand":    "구달",
        "filename": "product_4_goodal_serum.csv",
        "color":    "#f57f17",
        "bg":       "#fffde7",
        "emoji":    "🍊",
        "desc":     "제주 청귤 비타C · 잡티 & 피부톤 개선 세럼",
    },
}

COMPETITOR = "에스트라 아토베리어365 크림"

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
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
.product-hero {
    border-radius: 16px; padding: 28px 32px; margin-bottom: 24px;
    display: flex; align-items: center; gap: 20px;
}
.hero-emoji { font-size: 52px; line-height: 1; }
.hero-info h1 { font-size: 22px; font-weight: 700; margin: 0; }
.hero-info p  { font-size: 13px; opacity: .7; margin: 6px 0 0; }
.step-badge {
    display: inline-block; background: #e8f5e9; color: #2e7d32;
    border-radius: 20px; padding: 4px 14px; font-size: 0.78rem;
    font-weight: 600; margin-bottom: .5rem;
}
.metric-card {
    background: #fafafa; border: 1px solid #eee; border-radius: 12px;
    padding: 1rem 1.2rem; text-align: center;
}
.metric-card .v { font-size: 2rem; font-weight: 700; }
.metric-card .l { font-size: 0.78rem; color: #888; margin-top: 3px; }
.pos-tag {
    display: inline-block; background: #e8f5e9; color: #2e7d32;
    border-radius: 16px; padding: 4px 12px; margin: 3px;
    font-size: 0.82rem; font-weight: 500;
}
.neg-tag {
    display: inline-block; background: #fce4ec; color: #c62828;
    border-radius: 16px; padding: 4px 12px; margin: 3px;
    font-size: 0.82rem; font-weight: 500;
}
.persona-box {
    background: #f8f9fa; border-left: 4px solid #4CAF50;
    border-radius: 0 10px 10px 0; padding: 12px 16px; margin: 8px 0;
}
.gap-box {
    border-left: 4px solid var(--fc); background: #fafafa;
    border-radius: 0 10px 10px 0; padding: 12px 16px; margin: 8px 0;
}
.back-btn {
    display: inline-flex; align-items: center; gap: 6px;
    color: #555; font-size: 13px; text-decoration: none;
    margin-bottom: 16px; cursor: pointer;
}
.no-data-box {
    background: #fff3e0; border: 1px solid #ffe0b2; border-radius: 12px;
    padding: 24px; text-align: center; margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# API 키
# ─────────────────────────────────────────────
if "CLAUDE_API_KEY" in st.secrets:
    api_key = st.secrets["CLAUDE_API_KEY"]
else:
    with st.sidebar:
        st.subheader("⚙️ 설정")
        api_key = st.text_input("Claude API Key", type="password",
                                placeholder="sk-ant-...")
        st.caption("Anthropic Console에서 발급받은 키를 입력하세요.")

if not api_key:
    st.warning("👈 사이드바에서 Claude API Key를 입력해주세요.")
    st.stop()

client = Anthropic(api_key=api_key)

# ─────────────────────────────────────────────
# URL 파라미터로 상품 선택
# ─────────────────────────────────────────────
params  = st.query_params
pid_str = params.get("product", "")
try:
    selected_pid = int(pid_str) if pid_str and pid_str.isdigit() else None
except Exception:
    selected_pid = None

# ─────────────────────────────────────────────
# 화면 A: 메인 랭킹 페이지 (상품 선택 전)
# ─────────────────────────────────────────────
if selected_pid is None:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0d1b2a,#1a3a2e);padding:20px 28px;
    border-radius:14px;margin-bottom:20px">
    <h1 style="color:#fff;margin:0;font-size:1.8rem;font-weight:700">
        🌿 OliveAI Review Intelligence
    </h1>
    <p style="color:rgba(255,255,255,.6);margin:.4rem 0 0;font-size:.9rem">
        올리브영 베스트 랭킹 상품 · AI 리뷰 분석 · 인터랙티브 대시보드
    </p>
    </div>
    """, unsafe_allow_html=True)

    # 올리브영 베스트 페이지 HTML 임베드
    html_path = "oliveyoung_best.html"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Streamlit 내부 링크로 교체 (modal의 href 수정)
        for pid in [1, 2, 3, 4]:
            html_content = html_content.replace(
                f"http://localhost:8501?product={pid}",
                f"?product={pid}"
            )
        # modal의 링크를 st.query_params 방식으로 동작하도록
        # (iframe 내에서는 실제 네비게이션이 안 되므로 JS postMessage 활용)
        inject_js = """
<script>
// Streamlit iframe 내에서 상품 클릭 시 부모 페이지로 전달
function openProduct(id) {
  const products = {
    1: '라운드랩 1025 독도 토너',
    2: '아누아 어성초 77 수딩 토너',
    3: '토리든 다이브인 히알루론산 세럼',
    4: '구달 청귤 비타C 잡티케어 세럼',
  };
  window.parent.postMessage({type:'SELECT_PRODUCT', id: id, name: products[id]}, '*');
}
</script>
"""
        html_content = html_content.replace("</body>", inject_js + "</body>")
        st.components.v1.html(html_content, height=1000, scrolling=True)
    else:
        st.info("oliveyoung_best.html 파일이 필요합니다.")

    # JS → Streamlit 브릿지 (postMessage 수신)
    st.markdown("""
    <script>
    window.addEventListener('message', function(e) {
        if (e.data && e.data.type === 'SELECT_PRODUCT') {
            window.location.search = '?product=' + e.data.id;
        }
    });
    </script>
    """, unsafe_allow_html=True)

    # 대체 버튼 UI (iframe postMessage가 동작 안 할 경우 대비)
    st.markdown("---")
    st.markdown("### 상품을 선택해 AI 분석을 시작하세요")
    cols = st.columns(4)
    for idx, (pid, info) in enumerate(PRODUCTS.items()):
        csv_path = os.path.join(DATA_DIR, info["filename"])
        has_data = os.path.exists(csv_path)
        with cols[idx]:
            st.markdown(f"""
            <div style="background:{info['bg']};border-radius:12px;padding:16px;
            text-align:center;border:2px solid {'#4CAF50' if has_data else '#ddd'}">
              <div style="font-size:2rem">{info['emoji']}</div>
              <div style="font-size:12px;font-weight:700;color:{info['color']};margin:6px 0 2px">
                {info['brand']}</div>
              <div style="font-size:11px;color:#555;line-height:1.4">{info['name']}</div>
              <div style="margin-top:8px;font-size:10px;color:{'#2e7d32' if has_data else '#999'}">
                {'✅ 데이터 준비됨' if has_data else '⚠ 크롤링 필요'}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"{'AI 분석 보기 →' if has_data else '데이터 없음'}", key=f"btn_{pid}",
                         disabled=not has_data, use_container_width=True):
                st.query_params["product"] = str(pid)
                st.rerun()

    st.stop()

# ─────────────────────────────────────────────
# 화면 B: 개별 상품 분석 페이지
# ─────────────────────────────────────────────
if selected_pid not in PRODUCTS:
    st.error("잘못된 상품 ID입니다.")
    st.stop()

product = PRODUCTS[selected_pid]

# 뒤로가기 버튼
if st.button("← 랭킹으로 돌아가기"):
    st.query_params.clear()
    st.rerun()

# 히어로 섹션
st.markdown(f"""
<div class="product-hero" style="background:{product['bg']}">
  <div class="hero-emoji">{product['emoji']}</div>
  <div class="hero-info">
    <div style="font-size:11px;color:{product['color']};font-weight:600;margin-bottom:4px">
      {product['brand']} · 올리브영 랭킹 {selected_pid}위</div>
    <h1 style="font-size:22px;font-weight:700;color:#1a1a1a;margin:0">{product['name']}</h1>
    <p style="font-size:13px;color:#666;margin:6px 0 0">{product['desc']}</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── CSV 로드 ──────────────────────────────────
csv_path = os.path.join(DATA_DIR, product["filename"])

if not os.path.exists(csv_path):
    st.markdown(f"""
    <div class="no-data-box">
      <div style="font-size:2rem">📂</div>
      <div style="font-size:16px;font-weight:700;margin:8px 0">리뷰 데이터가 없습니다</div>
      <div style="font-size:13px;color:#666">
        먼저 <code>python 2_crawl_reviews.py</code> 를 실행해서<br>
        <code>{csv_path}</code> 파일을 생성해주세요.
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

df = pd.read_csv(csv_path)

if df.empty:
    st.error("CSV 파일에 데이터가 없습니다.")
    st.stop()

# 기본 통계
avg_r      = round(df["rating"].mean(), 2) if "rating" in df.columns else 0
total_rev  = len(df)
skin_dist  = (
    df["skin_type"].dropna()
    .str.split(", ").explode()
    .value_counts().head(8).to_dict()
) if "skin_type" in df.columns else {}

st.markdown(f'<span class="step-badge">STEP 1</span> **수집 데이터**', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
for col, val, label in [
    (c1, f"⭐ {avg_r}", "평균 별점"),
    (c2, f"{total_rev:,}개", "수집 리뷰"),
    (c3, f"{int(df['rating'].ge(4).sum() / total_rev * 100) if total_rev else 0}%", "4점 이상 비율"),
    (c4, f"{len(skin_dist)}개", "피부 태그 종류"),
]:
    col.markdown(
        f'<div class="metric-card"><div class="v">{val}</div>'
        f'<div class="l">{label}</div></div>',
        unsafe_allow_html=True
    )

with st.expander("📋 원본 데이터 미리보기"):
    st.dataframe(df.head(15), use_container_width=True)
    st.download_button("📥 CSV 다운로드", df.to_csv(index=False, encoding="utf-8-sig").encode(),
                       product["filename"], "text/csv")

st.divider()

# ── Claude 분석 ───────────────────────────────
st.markdown(f'<span class="step-badge">STEP 2</span> **Claude AI 분석**', unsafe_allow_html=True)

@st.cache_data(ttl=86400, show_spinner=False)
def analyze(_df_key: str, _df_hash: int) -> dict:
    """CSV 내용 해시 기반 캐싱 — 동일 파일은 재분석 안 함"""
    df_work = pd.read_csv(os.path.join(DATA_DIR, _df_key))
    sample  = df_work["text"].dropna().head(80).tolist()
    avg     = round(df_work["rating"].mean(), 2) if "rating" in df_work.columns else 0
    tags    = (
        df_work["skin_type"].dropna()
        .str.split(", ").explode()
        .value_counts().head(10).to_dict()
    ) if "skin_type" in df_work.columns else {}

    prompt = f"""당신은 올리브영 시니어 PM 겸 데이터 애널리스트입니다.
아래 고객 리뷰 {len(sample)}개를 분석하여 전략 리포트를 JSON으로만 작성하세요.
다른 텍스트 없이 순수 JSON만 출력하세요.

[기본 통계] 평균 별점: {avg} / 피부 태그 분포: {json.dumps(tags, ensure_ascii=False)}
[리뷰 샘플]:
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(sample))}

{{
  "summary": "전체 리뷰를 관통하는 핵심 한 줄 요약",
  "ai_score": {{
    "sensitive_skin": 85,
    "oily_skin": 70,
    "dry_skin": 78,
    "combo_skin": 75,
    "overall": 80
  }},
  "sentiment": {{
    "positive_keywords": ["키워드1","키워드2","키워드3","키워드4","키워드5","키워드6","키워드7","키워드8"],
    "negative_keywords": ["키워드1","키워드2","키워드3","키워드4"],
    "positive_ratio": 78
  }},
  "persona_analysis": [
    {{"persona":"잡티/미백 고민","satisfaction":88,"key_review":"대표 리뷰 한 줄","count_ratio":35}},
    {{"persona":"탄력/주름 고민","satisfaction":72,"key_review":"대표 리뷰 한 줄","count_ratio":28}},
    {{"persona":"민감/진정 고민","satisfaction":81,"key_review":"대표 리뷰 한 줄","count_ratio":25}},
    {{"persona":"보습/건조 고민","satisfaction":76,"key_review":"대표 리뷰 한 줄","count_ratio":12}}
  ],
  "top_ingredients": [
    {{"name":"성분명","mention_count":30,"sentiment":"positive"}},
    {{"name":"성분명","mention_count":22,"sentiment":"positive"}},
    {{"name":"성분명","mention_count":18,"sentiment":"positive"}},
    {{"name":"성분명","mention_count":14,"sentiment":"neutral"}},
    {{"name":"성분명","mention_count":10,"sentiment":"negative"}},
    {{"name":"성분명","mention_count":8,"sentiment":"positive"}}
  ],
  "unmet_needs": [
    {{"need":"미충족 니즈 1","frequency":"높음","opportunity":"기회 설명"}},
    {{"need":"미충족 니즈 2","frequency":"중간","opportunity":"기회 설명"}},
    {{"need":"미충족 니즈 3","frequency":"중간","opportunity":"기회 설명"}}
  ],
  "competitor_simulation": {{
    "competitor_name": "{COMPETITOR}",
    "comparison": [
      {{"dimension":"보습력","this_product":80,"competitor":75}},
      {{"dimension":"흡수력","this_product":85,"competitor":78}},
      {{"dimension":"자극없음","this_product":82,"competitor":70}},
      {{"dimension":"가성비","this_product":68,"competitor":85}},
      {{"dimension":"성분력","this_product":88,"competitor":80}},
      {{"dimension":"향/사용감","this_product":78,"competitor":74}}
    ]
  }},
  "winning_points": [
    {{"factor":"강점 1","score":90,"reason":"설명"}},
    {{"factor":"강점 2","score":84,"reason":"설명"}},
    {{"factor":"강점 3","score":78,"reason":"설명"}}
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


# 파일 변경 감지용 해시
df_hash = hash(df.to_csv(index=False)[:2000])

with st.spinner("🧠 Claude가 리뷰를 분석 중입니다..."):
    try:
        insight = analyze(product["filename"], df_hash)
    except Exception as e:
        st.error(f"AI 분석 오류: {e}")
        st.stop()

st.success(f"✅ 분석 완료! — *{insight.get('summary', '')}*")

# 분석 결과 메트릭
pos_r = insight.get("sentiment", {}).get("positive_ratio", 0)
ai_s  = insight.get("ai_score",  {}).get("overall", 0)
unmet = len(insight.get("unmet_needs", []))

m1, m2, m3, m4 = st.columns(4)
for col, val, label in [
    (m1, f"⭐ {avg_r}", "평균 별점"),
    (m2, f"{pos_r}%",   "긍정 리뷰 비율"),
    (m3, f"{ai_s}점",   "AI 종합 지수"),
    (m4, f"{unmet}건",  "미충족 니즈"),
]:
    col.markdown(
        f'<div class="metric-card"><div class="v" style="color:{product["color"]}">{val}</div>'
        f'<div class="l">{label}</div></div>',
        unsafe_allow_html=True,
    )

st.divider()

# ── 분석 탭 ──────────────────────────────────
st.markdown(f'<span class="step-badge">STEP 3</span> **시각화 대시보드**', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["😊 감성 분석", "👤 페르소나", "🚀 미충족 니즈", "🏆 경쟁사 비교", "📊 상세 통계"]
)

# ── TAB 1: 감성 분석 ──────────────────────────
with tab1:
    s = insight.get("sentiment", {})
    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.subheader("✅ 긍정 키워드")
        for kw in s.get("positive_keywords", []):
            st.markdown(f'<span class="pos-tag">{kw}</span>', unsafe_allow_html=True)

        st.subheader("⚠️ 부정 키워드")
        for kw in s.get("negative_keywords", []):
            st.markdown(f'<span class="neg-tag">{kw}</span>', unsafe_allow_html=True)

    with col_b:
        pr  = s.get("positive_ratio", 0)
        fig = go.Figure(data=[go.Pie(
            labels=["긍정", "중립", "부정"],
            values=[pr, max(100 - pr - 12, 0), 12],
            hole=0.65,
            marker_colors=[product["color"], "#e0e0e0", "#ef5350"],
        )])
        fig.update_layout(
            showlegend=True, height=280, margin=dict(t=10, b=10),
            annotations=[dict(text=f"{pr}%<br><span style='font-size:12px'>긍정</span>",
                              x=0.5, y=0.5, font_size=20, showarrow=False)]
        )
        st.plotly_chart(fig, use_container_width=True)

    # 피부 타입 분포
    if skin_dist:
        st.subheader("🏷️ 피부 타입 태그 분포")
        df_skin = pd.DataFrame(list(skin_dist.items()), columns=["태그", "건수"])
        fig2 = px.bar(df_skin, x="건수", y="태그", orientation="h",
                      color="건수", color_continuous_scale="Greens")
        fig2.update_layout(height=300, margin=dict(t=10, b=10),
                           coloraxis_showscale=False,
                           yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig2, use_container_width=True)

# ── TAB 2: 페르소나 매핑 ───────────────────────
with tab2:
    personas = insight.get("persona_analysis", [])
    if personas:
        df_p = pd.DataFrame(personas)
        fig  = px.bar(
            df_p, x="persona", y="satisfaction",
            color="satisfaction",
            color_continuous_scale=["#ffcdd2", product["color"]],
            text="satisfaction",
            title="피부 고민별 만족도 비교",
        )
        fig.update_traces(texttemplate="%{text}점", textposition="outside")
        fig.update_layout(coloraxis_showscale=False, height=360,
                          margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

        for p in personas:
            st.markdown(f"""
            <div class="persona-box" style="border-left-color:{product['color']}">
              <strong>{p['persona']}</strong>
              <span style="float:right;color:{product['color']};font-weight:700">
                {p['satisfaction']}점 · {p['count_ratio']}%</span><br>
              <span style="font-size:12px;color:#555;font-style:italic">
                "{p['key_review']}"</span>
            </div>
            """, unsafe_allow_html=True)

# ── TAB 3: 미충족 니즈 ────────────────────────
with tab3:
    for item in insight.get("unmet_needs", []):
        fc = {"높음": "#ef5350", "중간": "#FF9800", "낮음": "#4CAF50"}.get(
            item.get("frequency", ""), "#999"
        )
        st.markdown(f"""
        <div style="border-left:4px solid {fc};padding:12px 16px;
        margin:8px 0;background:#fafafa;border-radius:0 10px 10px 0">
          <strong>{item['need']}</strong>
          <span style="background:{fc};color:#fff;padding:2px 8px;
          border-radius:10px;font-size:.72rem;margin-left:8px">
          {item.get('frequency','')}</span>
          <br>
          <span style="color:#666;font-size:.85rem;margin-top:4px;display:block">
          💡 {item['opportunity']}</span>
        </div>
        """, unsafe_allow_html=True)

    # 성분 언급 빈도
    ingredients = insight.get("top_ingredients", [])
    if ingredients:
        st.subheader("🧪 주요 성분 언급 빈도")
        df_ing = pd.DataFrame(ingredients)
        color_map = {"positive": product["color"], "neutral": "#90A4AE", "negative": "#ef5350"}
        df_ing["color"] = df_ing["sentiment"].map(color_map)
        fig = go.Figure(go.Bar(
            x=df_ing["mention_count"],
            y=df_ing["name"],
            orientation="h",
            marker_color=df_ing["color"].tolist(),
        ))
        fig.update_layout(height=280, margin=dict(t=10, b=10),
                          yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig, use_container_width=True)

# ── TAB 4: 경쟁사 비교 ────────────────────────
with tab4:
    comp = insight.get("competitor_simulation", {})
    cl   = comp.get("comparison", [])
    if cl:
        df_c      = pd.DataFrame(cl)
        comp_name = comp.get("competitor_name", COMPETITOR)

        col_l, col_r = st.columns(2)

        with col_l:
            # 레이더
            fig_r = go.Figure()
            fig_r.add_trace(go.Scatterpolar(
                r=df_c["this_product"].tolist() + [df_c["this_product"].iloc[0]],
                theta=df_c["dimension"].tolist() + [df_c["dimension"].iloc[0]],
                fill="toself",
                name=product["name"],
                line_color=product["color"],
                fillcolor=product["color"] + "30",
            ))
            fig_r.add_trace(go.Scatterpolar(
                r=df_c["competitor"].tolist() + [df_c["competitor"].iloc[0]],
                theta=df_c["dimension"].tolist() + [df_c["dimension"].iloc[0]],
                fill="toself",
                name=comp_name,
                line_color="#90A4AE",
                fillcolor="#90A4AE30",
            ))
            fig_r.update_layout(
                polar=dict(radialaxis=dict(range=[50, 100])),
                showlegend=True, height=340,
                margin=dict(t=20, b=20),
                legend=dict(font=dict(size=11)),
            )
            st.plotly_chart(fig_r, use_container_width=True)

        with col_r:
            # 바 차트
            fig_b = go.Figure([
                go.Bar(name=product["name"], x=df_c["dimension"],
                       y=df_c["this_product"], marker_color=product["color"],
                       marker_line_width=0),
                go.Bar(name=comp_name, x=df_c["dimension"],
                       y=df_c["competitor"], marker_color="#B0BEC5",
                       marker_line_width=0),
            ])
            fig_b.update_layout(
                barmode="group", height=340,
                yaxis=dict(range=[50, 100]),
                margin=dict(t=20, b=20),
                legend=dict(font=dict(size=11)),
            )
            st.plotly_chart(fig_b, use_container_width=True)

        # 우위 요약
        wins  = df_c[df_c["this_product"] > df_c["competitor"]]
        loses = df_c[df_c["this_product"] <= df_c["competitor"]]
        st.markdown(f"""
        **{product['name']}** 우위 항목: {', '.join(wins['dimension'].tolist()) or '없음'} &nbsp;|&nbsp;
        **{comp_name}** 우위 항목: {', '.join(loses['dimension'].tolist()) or '없음'}
        """)

# ── TAB 5: 상세 통계 ──────────────────────────
with tab5:
    col_x, col_y = st.columns(2)

    with col_x:
        # 별점 분포
        rating_dist = df["rating"].value_counts().sort_index(ascending=False)
        fig = go.Figure(go.Bar(
            x=rating_dist.values,
            y=[f"{int(r) if r == int(r) else r}점" for r in rating_dist.index],
            orientation="h",
            marker_color=product["color"],
        ))
        fig.update_layout(title="별점 분포", height=240, margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_y:
        # Winning Points
        wp = insight.get("winning_points", [])
        if wp:
            df_w = pd.DataFrame(wp)
            fig  = px.bar(df_w, x="factor", y="score", text="score",
                          color="score",
                          color_continuous_scale=["#c8e6c9", product["color"]],
                          title="핵심 강점 지수")
            fig.update_traces(texttemplate="%{text}점", textposition="outside")
            fig.update_layout(coloraxis_showscale=False, height=240,
                              margin=dict(t=40, b=10),
                              yaxis=dict(range=[60, 100]))
            st.plotly_chart(fig, use_container_width=True)

    # AI Score 상세
    ai_score = insight.get("ai_score", {})
    if ai_score:
        st.subheader("🎯 AI Score — 피부 타입별 추천 지수")
        score_labels = {
            "sensitive_skin": "민감성 피부",
            "dry_skin":       "건성 피부",
            "combo_skin":     "복합성 피부",
            "oily_skin":      "지성 피부",
            "overall":        "종합 지수",
        }
        for key, label in score_labels.items():
            val = ai_score.get(key, 0)
            col_l2, col_r2 = st.columns([3, 1])
            with col_l2:
                st.markdown(
                    f'<div style="height:8px;background:#eee;border-radius:4px;overflow:hidden">'
                    f'<div style="height:100%;width:{val}%;background:{product["color"]};'
                    f'border-radius:4px;transition:width 1s"></div></div>',
                    unsafe_allow_html=True
                )
            with col_r2:
                st.markdown(f'<span style="font-weight:700;color:{product["color"]}">'
                            f'{label}: {val}점</span>', unsafe_allow_html=True)
