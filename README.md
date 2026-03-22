# 🌿 OliveAI Review Intelligence

올리브영 상품 URL → 실시간 리뷰 수집 → Claude AI 분석 → 인터랙티브 대시보드

## 실행 흐름

```
URL 입력
  └─ STEP 1: Selenium 크롤링 (리뷰 100개+, CSV 저장)
       └─ STEP 2: Claude API 분석
            ├─ Sentiment Analysis (긍/부정 키워드 맵)
            ├─ Persona Mapping (피부 고민별 만족도)
            └─ Product Gap (미충족 니즈)
                 └─ STEP 3: Claude Artifacts HTML 대시보드 생성
                      ├─ Word Cloud (성분/효과)
                      ├─ AI Score (피부 타입별 추천 지수)
                      └─ Competitor Comparison (경쟁사 시뮬레이션)
```

## 설치 및 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 배포

1. GitHub에 이 레포 push
2. [share.streamlit.io](https://share.streamlit.io) → New app → 이 레포 선택
3. **Secrets** 설정:
   ```toml
   CLAUDE_API_KEY = "sk-ant-..."
   ```

## 주요 기능

| 기능 | 설명 |
|------|------|
| 실시간 크롤링 | Selenium + 더보기 자동 클릭으로 100개+ 수집 |
| 감성 분석 | 긍정/부정 키워드 추출 및 비율 시각화 |
| 페르소나 매핑 | 잡티/탄력/민감/보습 고민별 만족도 비교 |
| 제품 갭 분석 | 고객 미충족 니즈(Unmet Needs) 발굴 |
| AI 리뷰 위젯 | Claude가 생성하는 HTML 대시보드 (Word Cloud, AI Score, 경쟁사 비교) |
| CSV 다운로드 | 수집 데이터 로컬 저장 |
