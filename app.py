"""
app.py · OliveAI Insight
─────────────────────────
구조:
  1. st.markdown으로 팝업 CSS/HTML을 Streamlit 레이어에 직접 주입
  2. oliveyoung_best.html을 st.components.v1.html로 임베드
  3. HTML 내 openProduct()가 postMessage → Streamlit 레이어의 JS가 팝업 on/off
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

# ── 분석 함수 ──
@st.cache_data(ttl=86400, show_spinner=False)
def analyze(filename: str, _hash: int) -> dict:
    df_w   = pd.read_csv(os.path.join(DATA_DIR, filename))
    sample = df_w["text"].dropna().head(80).tolist()
    avg    = round(df_w["rating"].mean(), 2) if "rating" in df_w.columns else 0
    tags   = (
        df_w["skin_type"].dropna().str.split(", ").explode()
        .value_counts().head(8).to_dict()
    ) if "skin_type" in df_w.columns else {}

    prompt = f"""뷰티 MD로서 아래 고객 리뷰 {len(sample)}개를 분석하세요. JSON만 출력하세요.

[통계] 평균별점:{avg} / 피부타입:{json.dumps(tags,ensure_ascii=False)}
[리뷰]
{chr(10).join(f'{i+1}. {t}' for i,t in enumerate(sample))}

{{"summary":"핵심 한 문장(최대 50자)","overall_score":83,"positive_ratio":78,
"skin_scores":{{"민감성":85,"건성":78,"지성":70,"복합성":75}},
"positive_keywords":["키워드1","키워드2","키워드3","키워드4","키워드5"],
"negative_keywords":["주의1","주의2"],
"best_for":"추천 대상 한 줄","caution":"주의 상황 한 줄",
"one_line_personas":["인사이트1","인사이트2"]}}"""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=800, temperature=0,
        messages=[{"role":"user","content":prompt}]
    )
    raw = msg.content[0].text
    m   = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(m.group() if m else raw)

# ── 모든 상품 사전 분석 ──
with st.spinner("🤖 리뷰 AI 분석 중..."):
    insights = {}
    for pid, product in PRODUCTS.items():
        csv_path = os.path.join(DATA_DIR, product["filename"])
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            _hash = hash(df.to_csv(index=False)[:2000])
            try:
                insights[pid] = analyze(product["filename"], _hash)
            except Exception as e:
                insights[pid] = None

# ── 팝업 HTML 생성 ──
def make_popup(pid):
    p   = PRODUCTS[pid]
    ins = insights.get(pid)
    c   = p["color"]

    if not ins:
        return f"""
<div id="oy-popup-{pid}" class="oy-overlay">
 <div class="oy-box">
  <div class="oy-hdr"><div class="oy-title">{p['emoji']} {p['name']}</div>
  <button class="oy-cls" onclick="oyClose()">✕</button></div>
  <div style="text-align:center;padding:40px 0;color:#888">
    <div style="font-size:36px">📭</div>
    <div style="margin-top:10px">리뷰 데이터가 없습니다.</div>
  </div>
  <button class="oy-done" onclick="oyClose()">닫기</button>
 </div>
</div>"""

    overall   = ins.get("overall_score", 80)
    pos_ratio = ins.get("positive_ratio", 75)
    summary   = ins.get("summary", "")
    pos_kws   = ins.get("positive_keywords", [])
    neg_kws   = ins.get("negative_keywords", [])
    skin_sc   = ins.get("skin_scores", {})
    best_for  = ins.get("best_for", "")
    caution   = ins.get("caution", "")
    personas  = ins.get("one_line_personas", [])

    bars = "".join(f"""<div class="oy-sr">
  <div class="oy-sl">{sk}</div>
  <div class="oy-st"><div class="oy-sf" style="width:{sc}%;background:{c}"></div></div>
  <div class="oy-sn" style="color:{c}">{sc}</div>
</div>""" for sk, sc in skin_sc.items())

    pos_html = "".join(f'<span class="oy-kp">✓ {k}</span>' for k in pos_kws)
    neg_html = "".join(f'<span class="oy-kn">△ {k}</span>' for k in neg_kws) or '<span style="color:#aaa;font-size:12px">특이사항 없음</span>'
    p_html   = "".join(f'<li style="font-size:13px;color:#444;margin:4px 0">{x}</li>' for x in personas)

    return f"""
<div id="oy-popup-{pid}" class="oy-overlay">
 <div class="oy-box">
  <div class="oy-hdr">
    <div>
      <div style="font-size:11px;color:{c};font-weight:600;margin-bottom:2px">{p['brand']} · AI 리뷰 분석</div>
      <div class="oy-title">{p['emoji']} {p['name']}</div>
    </div>
    <button class="oy-cls" onclick="oyClose()">✕</button>
  </div>

  <div style="display:flex;gap:10px;margin-bottom:16px">
    <div style="flex:1;background:{p['bg']};border-radius:14px;padding:16px;text-align:center">
      <div style="font-size:11px;color:#888;margin-bottom:2px">AI 종합 점수</div>
      <div style="font-size:44px;font-weight:800;color:{c};line-height:1">{overall}</div>
      <div style="font-size:11px;color:#aaa;margin-top:2px">/ 100</div>
    </div>
    <div style="flex:1;background:#fafafa;border-radius:14px;padding:16px;text-align:center">
      <div style="font-size:11px;color:#888;margin-bottom:2px">구매자 만족도</div>
      <div style="font-size:44px;font-weight:800;color:#4CAF50;line-height:1">{pos_ratio}<span style="font-size:18px">%</span></div>
      <div style="font-size:11px;color:#aaa;margin-top:2px">긍정 리뷰 비율</div>
    </div>
  </div>

  <div class="oy-sum">💬 {summary}</div>

  <div style="margin-bottom:14px">
    <div style="font-size:12px;font-weight:700;margin-bottom:8px">피부타입별 적합도</div>
    {bars}
  </div>

  <div style="margin-bottom:14px">
    <div style="font-size:12px;font-weight:700;margin-bottom:6px">리뷰 키워드</div>
    {pos_html}<br style="margin:2px 0">{neg_html}
  </div>

  <div style="display:flex;gap:8px;margin-bottom:14px">
    <div style="flex:1;background:#e8f5e9;border-radius:10px;padding:11px">
      <div style="font-size:10px;font-weight:700;color:#2e7d32;margin-bottom:3px">✅ 추천</div>
      <div style="font-size:12px;color:#1b5e20;line-height:1.5">{best_for}</div>
    </div>
    <div style="flex:1;background:#fff8e1;border-radius:10px;padding:11px">
      <div style="font-size:10px;font-weight:700;color:#e65100;margin-bottom:3px">⚠️ 참고</div>
      <div style="font-size:12px;color:#bf360c;line-height:1.5">{caution}</div>
    </div>
  </div>

  {'<div style="margin-bottom:14px"><div style="font-size:12px;font-weight:700;margin-bottom:6px">📊 구매자 인사이트</div><ul style="margin:0;padding-left:16px">' + p_html + '</ul></div>' if p_html else ''}

  <button class="oy-done" onclick="oyClose()">✕ 닫기</button>
 </div>
</div>"""

popups_html = "\n".join(make_popup(pid) for pid in PRODUCTS)

# ── Streamlit 레이어에 팝업 CSS + HTML + postMessage 수신 JS 주입 ──
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&display=swap');
.oy-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:99999;
  display:none;align-items:center;justify-content:center;padding:20px;
  font-family:'Noto Sans KR',sans-serif}}
.oy-overlay.on{{display:flex}}
.oy-box{{background:#fff;border-radius:20px;width:100%;max-width:680px;
  max-height:88vh;overflow-y:auto;padding:28px 24px;
  box-shadow:0 24px 60px rgba(0,0,0,.3);animation:oyPop .2s ease}}
@keyframes oyPop{{from{{opacity:0;transform:scale(.95)}}to{{opacity:1;transform:scale(1)}}}}
.oy-hdr{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px}}
.oy-title{{font-size:17px;font-weight:700;color:#1a1a1a;margin-top:3px}}
.oy-cls{{background:none;border:none;font-size:22px;cursor:pointer;color:#aaa;
  padding:2px 8px;border-radius:6px;line-height:1;font-family:inherit}}
.oy-cls:hover{{background:#f0f0f0;color:#333}}
.oy-sum{{background:linear-gradient(135deg,#f8fffe,#f0fff8);border-left:4px solid #4CAF50;
  border-radius:0 12px 12px 0;padding:12px 16px;margin:0 0 14px;
  font-size:13px;line-height:1.7;color:#1a1a1a}}
.oy-kp{{display:inline-block;background:#e8f5e9;color:#2e7d32;
  border-radius:20px;padding:3px 11px;margin:2px;font-size:12px;font-weight:500}}
.oy-kn{{display:inline-block;background:#fce4ec;color:#c62828;
  border-radius:20px;padding:3px 11px;margin:2px;font-size:12px;font-weight:500}}
.oy-sr{{display:flex;align-items:center;gap:10px;margin:6px 0}}
.oy-sl{{font-size:12px;color:#555;width:56px;flex-shrink:0}}
.oy-st{{flex:1;background:#eee;border-radius:4px;height:8px;overflow:hidden}}
.oy-sf{{height:100%;border-radius:4px}}
.oy-sn{{font-size:12px;font-weight:700;width:28px;text-align:right;flex-shrink:0}}
.oy-done{{display:block;width:100%;margin-top:20px;padding:11px;
  background:#1a1a1a;color:#fff;border:none;border-radius:10px;
  font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}}
.oy-done:hover{{background:#333}}
.block-container{{padding:0!important}}
header{{display:none!important}}
</style>

{popups_html}

<script>
function oyOpen(id) {{
  document.querySelectorAll('.oy-overlay').forEach(e => e.classList.remove('on'));
  var el = document.getElementById('oy-popup-' + id);
  if (el) {{ el.classList.add('on'); document.body.style.overflow='hidden'; }}
}}
function oyClose() {{
  document.querySelectorAll('.oy-overlay').forEach(e => e.classList.remove('on'));
  document.body.style.overflow='';
}}
document.addEventListener('keydown', function(e){{ if(e.key==='Escape') oyClose(); }});

// iframe(oliveyoung_best.html) 에서 postMessage 수신
window.addEventListener('message', function(e) {{
  if (e.data && e.data.type === 'OPEN_PRODUCT') {{
    oyOpen(e.data.id);
  }}
}});
</script>
""", unsafe_allow_html=True)

# ── 랭킹 HTML 임베드 ──
html_path = "oliveyoung_best.html"
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    # openProduct → postMessage로 부모(Streamlit)에 전달
    inject = """<script>
function openProduct(id) {
  window.parent.postMessage({type:'OPEN_PRODUCT', id: id}, '*');
}
</script>"""
    html = html.replace("</body>", inject + "</body>")
    st.components.v1.html(html, height=1000, scrolling=True)
