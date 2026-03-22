import streamlit as st
import pandas as pd
import plotly.express as px
from anthropic import Anthropic
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service # 이 줄을 추가하세요
from webdriver_manager.chrome import ChromeDriverManager

# --- 페이지 설정 ---
st.set_page_config(page_title="올리브영 AI 리뷰 인텔리전스 v2.0", layout="wide")
st.title("🌿 Olive Young Review AI Insight (Real-time)")

# --- 1. API 키 설정 (Secrets 활용) ---
# Secrets에서 키를 가져오고, 없으면 사이드바에서 입력받음
if "CLAUDE_API_KEY" in st.secrets:
    api_key = st.secrets["CLAUDE_API_KEY"]
else:
    with st.sidebar:
        api_key = st.text_input("Claude API Key를 입력하세요", type="password")

client = Anthropic(api_key=api_key)

# --- 2. 크롤링 함수 (캐싱 적용: 1시간 동안 동일 URL은 재크롤링 안 함) ---
@st.cache_data(ttl=3600)
def crawl_olive_young_reviews(url):
    """올리브영 URL에서 리뷰 데이터를 실시간으로 수집합니다."""
    st.info("🔄 실시간 리뷰 데이터를 수집 중입니다... (약 10~20초 소요)")
    
    options = Options()
    options.add_argument("--headless") # 화면 없이 실행 (배포 필수)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # webdriver-manager를 써서 드라이버 자동 설치 (배포 환경 호환성)
    # 수정 전: driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    
    # 수정 후: 아래 2줄로 교체
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(url)
        time.sleep(5) # 페이지 로딩 대기
        
        # 리뷰 탭 클릭 (올리브영 구조에 따라 ID가 다를 수 있음, 확인 필요)
        try:
            review_tab = driver.find_element(By.ID, "review_link")
            review_tab.click()
            time.sleep(3)
        except:
            st.warning("리뷰 탭을 찾는 데 실패했습니다. 기본 페이지에서 수집을 시도합니다.")

        # 리뷰 데이터 수집 (최신 리뷰 30개 예시)
        reviews_data = []
        review_elements = driver.find_elements(By.CLASS_NAME, "review_cont") # 리뷰 컨테이너

        for el in review_elements[:30]:
            try:
                # 텍스트, 별점, 피부타입 추출 (올리브영 셀렉터 기준)
                text = el.find_element(By.CLASS_NAME, "txt_inner").text
                score = el.find_element(By.CLASS_NAME, "point").text.replace("점", "")
                skin_type = el.find_element(By.CLASS_NAME, "skin_type").text
                
                reviews_data.append({
                    "text": text,
                    "score": int(score),
                    "skin_type": skin_type
                })
            except:
                continue
                
        if not reviews_data:
            raise Exception("수집된 리뷰가 없습니다.")
            
        return pd.DataFrame(reviews_data)

    except Exception as e:
        st.error(f"크롤링 중 오류 발생: {e}")
        return None
    finally:
        driver.quit()

# --- 3. Claude 분석 함수 (캐싱 적용: 동일 데이터는 재분석 안 함) ---
@st.cache_data(ttl=86400) # 분석 결과는 하루 동안 캐싱
def analyze_reviews_with_claude(_df):
    """수집된 리뷰 데이터를 Claude API로 분석하여 JSON 인사이트를 도출합니다."""
    st.info("🧠 AI가 리뷰 인사이트를 도출 중입니다...")
    
    # 분석을 위한 텍스트 합치기 (최대 토큰 고려)
    all_reviews_text = "\n".join(_df['text'].tolist())
    
    prompt = f"""
    당신은 올리브영의 프로덕트 매니저(PM)입니다. 다음 30개의 고객 리뷰 데이터를 바탕으로 전략적 분석 보고서를 작성하세요.
    반드시 아래 JSON 형식을 지켜서 답변해야 합니다. 다른 텍스트는 포함하지 마세요.

    ```json
    {{
      "summary": "전체 리뷰를 관통하는 핵심 한 줄 요약",
      "winning_points": [
        {{"factor": "구매 결정 요소 1", "score": 95, "reason": "이유 설명"}},
        {{"factor": "구매 결정 요소 2", "score": 85, "reason": "이유 설명"}}
      ],
      "pain_points": [
        {{"issue": "불만 사항 1", "improvement": "개선 제안 1"}},
        {{"issue": "불만 사항 2", "improvement": "개선 제안 2"}}
      ],
      "persona": "가장 적합한 타겟 고객 페르소나 묘사 (피부타입, 연령대 등)"
    }}
    ```

    [리뷰 데이터]:
    {all_reviews_text}
    """
    
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2000,
            temperature=0, # 일관된 답변을 위해 0으로 설정
            messages=[{"role": "user", "content": prompt}]
        )
        
        # JSON 문자열만 추출하여 파싱
        response_text = message.content[0].text
        json_start = response_text.find("```json") + 7
        json_end = response_text.rfind("```")
        json_str = response_text[json_start:json_end].strip()
        
        return json.loads(json_str)
        
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {e}")
        return None

# --- 4. 메인 UI (Streamlit) ---
input_url = st.text_input("올리브영 상품 상세 페이지 URL을 입력하세요 (예: 메디큐브 패드)")

if st.button("실시간 AI 인사이트 추출"):
    if not input_url:
        st.warning("URL을 입력해주세요.")
    else:
        # 1단계: 크롤링 (캐싱됨)
        df_reviews = crawl_olive_young_reviews(input_url)
        
        if df_reviews is not None:
            # 2단계: AI 분석 (캐싱됨)
            insight_json = analyze_reviews_with_claude(df_reviews)
            
            if insight_json:
                # 3단계: 대시보드 시각화
                st.success("분석 완료! (캐싱된 데이터 활용)")
                
                # 가) 핵심 요약 카드
                st.metric(label="AI 핵심 요약", value="", help=insight_json['summary'])
                st.subheader(f"💡 {insight_json['summary']}")
                st.divider()
                
                # 나) 시각화 차트 (Winning Points)
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("📊 항목별 긍정 지수 (Winning Points)")
                    df_chart = pd.DataFrame(insight_json['winning_points'])
                    fig = px.bar(df_chart, x="factor", y="score", color="factor", text="score", labels={"score": "긍정 지수 (0-100)"})
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(fig, use_container_width=True)
                    
                with col2:
                    st.subheader("🎯 핵심 페르소나")
                    st.info(insight_json['persona'])
                    
                # 다) 불만 사항 및 개선 제안 표
                st.divider()
                st.subheader("⚠️ 불만 사항 및 개선 제안 (Pain Points)")
                df_pain = pd.DataFrame(insight_json['pain_points'])
                st.table(df_pain)
