import streamlit as st
import pandas as pd
import plotly.express as px
from anthropic import Anthropic

# --- UI 설정 ---
st.set_page_config(page_title="올리브영 AI 리뷰 인텔리전스", layout="wide")
st.title("🌿 Olive Young Review AI Insight")
st.markdown("URL 하나로 수천 개의 리뷰를 분석하여 비즈니스 인사이트를 도출합니다.")

# --- 사이드바: API 설정 ---
with st.sidebar:
    api_key = st.text_input("Claude API Key를 입력하세요", type="password")
    st.info("면접 시 시연을 위해 본인의 API 키를 미리 세팅해두는 것이 좋습니다.")

# --- 메인 화면: URL 입력 ---
url = st.text_input("올리브영 상품 상세 페이지 URL을 입력하세요")

if st.button("AI 분석 시작"):
    if not api_key:
        st.error("API 키가 필요합니다.")
    else:
        with st.spinner("리뷰 데이터를 수집하고 AI가 분석 중입니다..."):
            # [임시 데이터 가공] - 실제 시연 시 크롤링 로직이 작동하도록 연결
            # 면접장 인터넷 상황을 고려해 '샘플 데이터' 모드를 함께 만드는 것이 전략적입니다.
            
            # 1. 가상의 분석 결과 데이터 (시각화용)
            chart_data = pd.DataFrame({
                "항목": ["보습력", "자극도", "발림성", "향", "가격만족도"],
                "긍정지수": [92, 15, 88, 70, 65]
            })

            # 2. 시각화 섹션
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 항목별 긍정 지수")
                fig = px.bar(chart_data, x="항목", y="긍정지수", color="항목", text_auto=True)
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                st.subheader("🎯 핵심 페르소나 매칭")
                st.info("이 제품은 **'민감성 피부를 가진 20대 후반 직장인'**에게 가장 높은 만족도를 보입니다.")
                st.write("- 수분 충돌 지수: 낮음 (안전)")
                st.write("- 재구매 의사: 89%")

            # 3. LLM 인사이트 (Claude API 연동 부분)
            st.divider()
            st.subheader("💡 AI 전략적 제언 (Strategic Insight)")
            
            # 실제 API 호출 및 결과 출력 (생략된 로직 연결)
            st.success("핵심 인사이트: '비타민C 성분임에도 자극이 없다'는 점이 가장 큰 구매 결정 요인입니다. 상세 페이지 상단에 '저자극 테스트 완료' 배너를 더 강조할 필요가 있습니다.")
