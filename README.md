# 🌿 OliveAI Review Intelligence

올리브영 베스트 랭킹 상품의 리뷰를 수집·분석·시각화하는 3-파트 시스템

## 파일 구조

```
olive-ai-insight/
├── oliveyoung_best.html      # 1) 올리브영 베스트 페이지 클론 (4개 상품 클릭 가능)
├── 2_crawl_reviews.py        # 2) 사전 크롤링 스크립트 (로컬 1회 실행)
├── app.py                    # 3) Streamlit 분석 앱 (CSV 읽어 Claude 분석)
├── requirements.txt
├── packages.txt              # Streamlit Cloud용 시스템 패키지
└── data/                     # 크롤링 결과 CSV (git에 함께 커밋)
    ├── product_1_roundlab_toner.csv
    ├── product_2_anua_toner.csv
    ├── product_3_torriden_serum.csv
    ├── product_4_goodal_serum.csv
    └── meta.json
```

## 실행 순서

### STEP 1 — 크롤링 (로컬에서 1회만)
```bash
pip install -r requirements.txt
python 2_crawl_reviews.py
```
→ `data/` 폴더에 CSV 4개 생성됨

### STEP 2 — CSV를 GitHub에 커밋
```bash
git add data/
git commit -m "Add pre-crawled review data"
git push
```
⚠ Streamlit Cloud는 Selenium 크롤링이 불안정하므로 **CSV를 미리 커밋**하는 것이 핵심

### STEP 3 — Streamlit 앱 실행
```bash
streamlit run app.py
```
또는 Streamlit Cloud에 배포

## Streamlit Cloud 배포

1. `packages.txt` / `requirements.txt` 포함해서 레포 push
2. [share.streamlit.io](https://share.streamlit.io) → New app
3. **Secrets** 설정:
   ```toml
   CLAUDE_API_KEY = "sk-ant-..."
   ```

## 흐름

```
oliveyoung_best.html  (상품 클릭)
        ↓
    app.py  (?product=N 파라미터)
        ↓
  data/product_N_xxx.csv  (미리 수집된 리뷰)
        ↓
  Claude API 분석
  ├─ Sentiment Analysis (긍/부정 키워드)
  ├─ Persona Mapping (피부 고민별 만족도)
  └─ Product Gap (미충족 니즈)
        ↓
  Plotly 인터랙티브 대시보드
```
