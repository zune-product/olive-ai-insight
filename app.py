"""
app.py  ·  OliveAI Insight
─────────────────────────
화면 구성:
  · 기본: oliveyoung_best.html 임베드 (랭킹 페이지)
  · ?product=N: AI 분석 팝업 모달 오버레이
    - 페이지 이동 없이 같은 화면 위에 팝업
    - 분석 자동 실행 → 간결한 시각화
"""

import os, json, re
import streamlit as st
import pandas as pd
from anthropic import Anthropic

DATA_DIR = "data"
PRODUCTS = {
    1: {"name":"라운드랩 1025 독도 토너",        "brand":"라운드랩","filename":"product_1_roundlab_toner.csv", "color":"#1a5fa8","bg":"#e8f4fd","emoji":"💧"},
    2: {"name":"아누아 어성초 77 수딩 토너",      "brand":"아누아",  "filename":"product_2_anua_toner.csv",     "color":"#2d6a2d","bg":"#f0faf0","emoji":"🌿"},
    3: {"name":"토리든 다이브인 히알루론산 세럼", "brand":"토리든",  "filename":"product_3_torriden_serum.csv", "color":"#3949ab","bg":"#e8f0fe","emoji":"✨"},
    4: {"name":"구달 청귤 비타C 잡티케어 세럼",  "brand":"구달",    "filename":"product_4_goodal_serum.csv",   "color":"#f57f17","bg":"#fffde7","emoji":"🍊"},
}

st.set_page_config(page_title="🌿 OliveAI Insight", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans KR',sans-serif;}
.popup-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px;}
.popup-box{background:#fff;border-radius:20px;width:100%;max-width:700px;max-height:88vh;overflow-y:auto;padding:32px 28px;box-shadow:0 24px 60px rgba(0,0,0,.25);animation:popIn .22s ease;}
@keyframes popIn{from{opacity:0;transform:scale(.95)}to{opacity:1;transform:scale(1)}}
.popup-header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:18px;}
.popup-title{font-size:18px;font-weight:700;color:#1a1a1a;margin-top:4px;}
.popup-close{background:none;border:none;font-size:22px;cursor:pointer;color:#aaa;line-height:1;padding:2px 8px;border-radius:6px;text-decoration:none;color:#aaa;}
.popup-close:hover{background:#f0f0f0;color:#333;}
.summary-box{background:linear-gradient(135deg,#f8fffe,#f0fff8);border-left:4px solid #4CAF50;border-radius:0 12px 12px 0;padding:14px 18px;margin:16px 0;font-size:14px;line-height:1.7;color:#1a1a1a;}
.kw-pos{display:inline-block;background:#e8f5e9;color:#2e7d32;border-radius:20px;padding:4px 12px;margin:3px;font-size:13px;font-weight:500;}
.kw-neg{display:inline-block;background:#fce4ec;color:#c62828;border-radius:20px;padding:4px 12px;margin:3px;font-size:13px;font-weight:500;}
.skin-row{display:flex;align-items:center;gap:10px;margin:7px 0;}
.skin-label{font-size:12px;color:#555;width:60px;flex-shrink:0;}
.skin-track{flex:1;background:#eee;border-radius:4px;height:8px;overflow:hidden;}
.skin-fill{height:100%;border-radius:4px;}
.skin-num{font-size:12px;font-weight:700;width:32px;text-align:right;flex-shrink:0;}
.close-btn{display:block;width:100%;margin-top:24px;padding:12px;background:#1a1a1a;color:#fff;border:none;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;font-family:'Noto Sans KR',sans-serif;}
.close-btn:hover{background:#333;}
/* Streamlit padding 제거 */
.block-container{padding-top:0!important;padding-bottom:0!important;}
header{display:none!important;}
</style>
""", unsafe_allow_html=True)

# ── API 키 ──
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

# ── URL 파라미터 ──
pid_str = st.query_params.get("product", "")
try:
    selected_pid = int(pid_str) if pid_str and pid_str.isdigit() else None
except Exception:
    selected_pid = None

# ── 메인 HTML 항상 임베드 ──
html_path = "oliveyoung_best.html"
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    inject_js = """
<script>
// HTML 내 openProduct → Streamlit URL 파라미터 변경 (팝업 트리거)
window.STREAMLIT_URL = '';
function openProduct(id) {
  window.parent.postMessage({type:'SELECT_PRODUCT', id: id}, '*');
}
</script>
<script>
window.addEventListener('message', function(e) {
  if (e.data && e.data.type === 'SELECT_PRODUCT') {
    window.location.search = '?product=' + e.data.id;
  }
});
</script>
"""
    html_content = html_content.replace("</body>", inject_js + "</body>")
    st.components.v1.html(html_content, height=980, scrolling=True)

# ── 팝업 모달 ──
if selected_pid and selected_pid in PRODUCTS:
    product  = PRODUCTS[selected_pid]
    csv_path = os.path.join(DATA_DIR, product["filename"])
    color    = product["color"]
    close_url = "/"

    @st.cache_data(ttl=86400, show_spinner=False)
    def analyze(filename: str, _hash: int) -> dict:
        df_w   = pd.read_csv(os.path.join(DATA_DIR, filename))
        sample = df_w["text"].dropna().head(80).tolist()
        avg    = round(df_w["rating"].mean(), 2) if "rating" in df_w.columns else 0
        tags   = (
            df_w["skin_type"].dropna()
            .str.split(", ").explode()
            .value_counts().head(8).to_dict()
        ) if "skin_type" in df_w.columns else {}

        prompt = f"""뷰티 MD로서 아래 고객 리뷰 {len(sample)}개를 분석하세요.
다른 텍스트 없이 JSON만 출력하세요.

[통계] 평균별점:{avg} / 피부타입:{json.dumps(tags,ensure_ascii=False)}
[리뷰]
{chr(10).join(f'{i+1}. {t}' for i,t in enumerate(sample))}

{{
  "summary": "핵심 한 문장 요약 (최대 50자)",
  "overall_score": 83,
  "positive_ratio": 78,
  "skin_scores": {{"민감성":85,"건성":78,"지성":70,"복합성":75}},
  "positive_keywords": ["키워드1","키워드2","키워드3","키워드4","키워드5"],
  "negative_keywords": ["주의점1","주의점2"],
  "best_for": "이 상품이 가장 잘 맞는 사람 한 줄",
  "caution": "주의가 필요한 상황 한 줄",
  "one_line_personas": ["페르소나 인사이트 1","페르소나 인사이트 2"]
}}"""

        msg   = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=800, temperature=0,
            messages=[{"role":"user","content":prompt}]
        )
        raw   = msg.content[0].text
        m     = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group() if m else raw)

    # 분석 실행
    if not os.path.exists(csv_path):
        insight = None
    else:
        df = pd.read_csv(csv_path)
        _hash = hash(df.to_csv(index=False)[:2000])
        with st.spinner(f"🤖 {product['name']} 리뷰 분석 중..."):
            try:
                insight = analyze(product["filename"], _hash)
            except Exception as e:
                insight = None
                st.error(f"분석 오류: {e}")

    # ── 팝업 HTML 생성 ──
    if insight:
        overall   = insight.get("overall_score", 80)
        pos_ratio = insight.get("positive_ratio", 75)
        summary   = insight.get("summary", "")
        pos_kws   = insight.get("positive_keywords", [])
        neg_kws   = insight.get("negative_keywords", [])
        skin_sc   = insight.get("skin_scores", {})
        best_for  = insight.get("best_for", "")
        caution   = insight.get("caution", "")
        personas  = insight.get("one_line_personas", [])

        # 피부타입 바
        skin_bars = ""
        for sk, sc in skin_sc.items():
            skin_bars += f"""
<div class="skin-row">
  <div class="skin-label">{sk}</div>
  <div class="skin-track"><div class="skin-fill" style="width:{sc}%;background:{color}"></div></div>
  <div class="skin-num" style="color:{color}">{sc}</div>
</div>"""

        pos_html = "".join(f'<span class="kw-pos">✓ {k}</span>' for k in pos_kws)
        neg_html = "".join(f'<span class="kw-neg">△ {k}</span>' for k in neg_kws) if neg_kws else '<span style="color:#aaa;font-size:13px">특이사항 없음</span>'
        persona_html = "".join(f'<li style="font-size:13px;color:#444;margin:5px 0">{p}</li>' for p in personas)

        popup = f"""
<div class="popup-overlay" onclick="if(event.target===this)window.location.href='{close_url}'">
 <div class="popup-box">

  <div class="popup-header">
    <div>
      <div style="font-size:11px;color:{color};font-weight:600;margin-bottom:3px">{product['brand']} · AI 리뷰 분석</div>
      <div class="popup-title">{product['emoji']} {product['name']}</div>
    </div>
    <a href="{close_url}" class="popup-close">✕</a>
  </div>

  <!-- 종합 스코어 -->
  <div style="display:flex;gap:12px;margin-bottom:18px">
    <div style="flex:1;background:{product['bg']};border-radius:14px;padding:18px;text-align:center">
      <div style="font-size:11px;color:#888;margin-bottom:4px">AI 종합 점수</div>
      <div style="font-size:48px;font-weight:800;color:{color};line-height:1">{overall}</div>
      <div style="font-size:11px;color:#aaa;margin-top:2px">/ 100</div>
    </div>
    <div style="flex:1;background:#fafafa;border-radius:14px;padding:18px;text-align:center">
      <div style="font-size:11px;color:#888;margin-bottom:4px">구매자 만족도</div>
      <div style="font-size:48px;font-weight:800;color:#4CAF50;line-height:1">{pos_ratio}<span style="font-size:20px">%</span></div>
      <div style="font-size:11px;color:#aaa;margin-top:2px">긍정 리뷰 비율</div>
    </div>
  </div>

  <!-- 요약 -->
  <div class="summary-box">💬 {summary}</div>

  <!-- 피부타입 적합도 -->
  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:700;color:#1a1a1a;margin-bottom:10px">피부타입별 적합도</div>
    {skin_bars}
  </div>

  <!-- 키워드 -->
  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:700;color:#1a1a1a;margin-bottom:8px">리뷰 키워드</div>
    <div>{pos_html}</div>
    <div style="margin-top:6px">{neg_html}</div>
  </div>

  <!-- 추천 / 주의 -->
  <div style="display:flex;gap:10px;margin-bottom:18px">
    <div style="flex:1;background:#e8f5e9;border-radius:12px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:#2e7d32;margin-bottom:6px">✅ 이런 분께 추천</div>
      <div style="font-size:13px;color:#1b5e20;line-height:1.5">{best_for}</div>
    </div>
    <div style="flex:1;background:#fff8e1;border-radius:12px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:#e65100;margin-bottom:6px">⚠️ 참고사항</div>
      <div style="font-size:13px;color:#bf360c;line-height:1.5">{caution}</div>
    </div>
  </div>

  <!-- 구매자 인사이트 -->
  {"" if not persona_html else f'<div style="margin-bottom:18px"><div style="font-size:13px;font-weight:700;color:#1a1a1a;margin-bottom:8px">📊 구매자 인사이트</div><ul style="margin:0;padding-left:18px">{persona_html}</ul></div>'}

  <a href="{close_url}"><button class="close-btn">✕ 닫기</button></a>
 </div>
</div>
"""
    else:
        popup = f"""
<div class="popup-overlay" onclick="if(event.target===this)window.location.href='{close_url}'">
 <div class="popup-box">
  <div class="popup-header">
    <div class="popup-title">{product['emoji']} {product['name']}</div>
    <a href="{close_url}" class="popup-close">✕</a>
  </div>
  <div style="text-align:center;padding:40px 0;color:#888">
    <div style="font-size:40px">📭</div>
    <div style="margin:12px 0">리뷰 데이터가 없습니다.</div>
    <div style="font-size:12px">크롤러를 실행하여 데이터를 수집해주세요.</div>
  </div>
  <a href="{close_url}"><button class="close-btn">닫기</button></a>
 </div>
</div>
"""

    st.markdown(popup, unsafe_allow_html=True)
