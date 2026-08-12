import streamlit as st
import pandas as pd
import requests

import excel_import

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="복지관 회원 관리 (통합 시스템)", page_icon="🤝", layout="wide")

st.title("복지관 회원 관리")
st.caption("🚀 모든 비즈니스 로직과 데이터 처리는 FastAPI 백엔드 서버를 통해 안전하게 처리됩니다.")

menu = st.sidebar.radio("메뉴", ["회원 목록", "회원 등록/수정/삭제", "회원 통계", "추천 복지 서비스"])

# DB 컬럼명(영어)은 그대로 두고, 화면에 보여줄 때만 한글로 바꿔주기 위한 매핑입니다.
COLUMN_LABELS = {
    "id": "번호",
    "name": "성명",
    "gender": "성별",
    "birth_date": "생년월일",
    "address": "주소",
    "phone": "전화번호",
    "welfare_type": "회원 구분",
    "manager": "담당자",
    "note": "비고",
    "created_at": "등록일시",
    "consent_personal": "개인정보 동의",
    "consent_sensitive": "민감정보 동의",
    "consent_third_party": "제3자제공 동의",
    "consent_portrait": "초상권 동의",
    "consent_signed_at": "동의 확인일시",
}

def handle_response(response):
    if response.status_code == 200:
        return response.json()
    else:
        try:
            err_detail = response.json().get('detail', '알 수 없는 오류')
        except:
            err_detail = response.text
        st.error(f"서버 오류: {err_detail}")
        return None

# ====================================================================
# 1. 회원 목록
# ====================================================================
if menu == "회원 목록":
    st.subheader("회원 목록")
    try:
        res = requests.get(f"{API_BASE}/clients")
        data = handle_response(res)
        if data is not None:
            df = pd.DataFrame(data)
            if df.empty:
                st.info("등록된 회원이 없습니다.")
            else:
                search_keyword = st.text_input("이름으로 검색")
                if search_keyword:
                    df = df[df["name"].str.contains(search_keyword, na=False, regex=False)]
                st.caption(f"총 {len(df)}명")
                st.dataframe(
                    df.rename(columns=COLUMN_LABELS), use_container_width=True, hide_index=True
                )
    except requests.exceptions.ConnectionError:
        st.error("🚨 FastAPI 서버(8000포트)가 꺼져있습니다. `uvicorn main:app --reload`를 실행해주세요.")

# ====================================================================
# 2. 회원 등록/수정/삭제
# ====================================================================
elif menu == "회원 등록/수정/삭제":
    tab_add, tab_edit, tab_bulk = st.tabs(["신규 회원 등록", "기존 회원 수정/삭제", "엑셀 일괄등록"])
    
    with tab_add:
        st.subheader("신규 회원 등록")
        with st.expander("🔍 주소 검색"):
            addr_kw = st.text_input("지번 또는 건물명 입력", key="addr_kw_add")
            if st.button("주소 검색", key="addr_btn_add"):
                if addr_kw:
                    res = requests.get(f"{API_BASE}/address/search", params={"keyword": addr_kw})
                    st.session_state["addr_results_add"] = handle_response(res)
            
            if st.session_state.get("addr_results_add"):
                results = st.session_state["addr_results_add"]
                options = {f"{r['road_address']} ({r['zip_code']})": r['road_address'] for r in results}
                picked = st.selectbox("주소 선택", options.keys(), key="pick_add")
                if st.button("이 주소로 채우기", key="fill_add"):
                    st.session_state["prefilled_addr"] = options[picked]
                    del st.session_state["addr_results_add"]
                    st.rerun()

        with st.form("add_form", clear_on_submit=True):
            name = st.text_input("성명 *")
            gender = st.radio("성별", ["남", "여"], horizontal=True)
            birth_date = st.text_input("생년월일 (예: 1990-01-01)")
            address = st.text_input("주소", value=st.session_state.get("prefilled_addr", ""))
            phone = st.text_input("전화번호 (010-0000-0000)")
            welfare_type = st.selectbox("회원 구분", ["일반", "차상위", "수급자"])
            note = st.text_area("비고")
            
            submitted = st.form_submit_button("등록하기", use_container_width=True)
            
        if submitted:
            if not name.strip():
                st.error("성명은 필수입니다.")
            else:
                payload = {
                    "name": name.strip(), "gender": gender, "birth_date": birth_date,
                    "address": address, "phone": phone, "welfare_type": welfare_type, "note": note,
                    "consent_personal": "동의함", "consent_sensitive": "동의함",
                    "consent_third_party": "동의함", "consent_portrait": "동의함"
                }
                res = requests.post(f"{API_BASE}/clients", json=payload)
                if res.status_code == 200:
                    st.success(f"'{name}' 님을 등록했습니다.")
                    st.session_state.pop("prefilled_addr", None)
                else:
                    st.error(res.json().get("detail"))

    with tab_edit:
        st.subheader("기존 회원 수정 / 삭제")
        try:
            res = requests.get(f"{API_BASE}/clients")
            data = handle_response(res)
            if data:
                df = pd.DataFrame(data)
                if df.empty:
                    st.info("등록된 회원이 없습니다.")
                else:
                    options = {f"{row['id']} - {row['name']}": row['id'] for _, row in df.iterrows()}
                    selected_label = st.selectbox("회원 선택", options.keys())
                    selected_id = options[selected_label]
                    
                    client_res = requests.get(f"{API_BASE}/clients/{selected_id}")
                    client = handle_response(client_res)
                    
                    if client:
                        with st.form("edit_form"):
                            e_name = st.text_input("성명", value=client["name"])
                            e_gender = st.radio("성별", ["남", "여"], horizontal=True, index=0 if client["gender"]=="남" else 1)
                            e_birth = st.text_input("생년월일", value=client["birth_date"])
                            e_addr = st.text_input("주소", value=client["address"])
                            e_phone = st.text_input("전화번호", value=client["phone"])
                            e_type = st.selectbox("회원 구분", ["일반", "차상위", "수급자"], index=["일반", "차상위", "수급자"].index(client["welfare_type"] if client["welfare_type"] in ["일반", "차상위", "수급자"] else "exceptions"))
                            e_note = st.text_area("비고", value=client["note"])
                            
                            edit_sub = st.form_submit_button("수정하기", use_container_width=True)
                            
                        if edit_sub:
                            update_payload = {
                                "name": e_name, "gender": e_gender, "birth_date": e_birth,
                                "address": e_addr, "phone": e_phone, "welfare_type": e_type, "note": e_note
                            }
                            up_res = requests.put(f"{API_BASE}/clients/{selected_id}", json=update_payload)
                            if up_res.status_code == 200:
                                st.success("회원 정보를 수정했습니다.")
                                st.rerun()
                                
                        if st.button("회원 삭제하기", type="primary"):
                            del_res = requests.delete(f"{API_BASE}/clients/{selected_id}")
                            if del_res.status_code == 200:
                                st.success("삭제되었습니다.")
                                st.rerun()
        except Exception as e:
            st.error(f"오류 발생: {e}")

    with tab_bulk:
        st.subheader("엑셀 일괄등록")
        st.caption("기존에 쓰시던 회원 명단 엑셀 파일을 업로드하고, 각 컬럼이 어떤 항목인지 매칭해주세요.")

        # st.file_uploader는 자체적으로 다국어를 지원하지 않아서, 내부 안내 문구를
        # CSS ::after로 덮어씁니다. stFileUploaderDropzone 하위로만 한정해서, 다른
        # 곳의 일반 버튼(kind="secondary")까지 같이 바뀌는 걸 막습니다.
        st.markdown(
            """
            <style>
            [data-testid="stFileUploaderDropzoneInstructions"] div span:nth-of-type(1) {
                font-size: 0;
            }
            [data-testid="stFileUploaderDropzoneInstructions"] div span:nth-of-type(1)::after {
                content: "여기에 파일을 끌어다 놓으세요";
                font-size: 14px;
            }
            [data-testid="stFileUploaderDropzoneInstructions"] div span:nth-of-type(2) {
                font-size: 0;
            }
            [data-testid="stFileUploaderDropzoneInstructions"] div span:nth-of-type(2)::after {
                content: "파일당 제한 200MB • XLSX, XLS";
                font-size: 12px;
            }
            [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] {
                font-size: 0;
            }
            [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]::after {
                content: "파일 찾기";
                font-size: 14px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader("엑셀 파일 선택", type=["xlsx", "xls"], key="bulk_upload")

        if uploaded_file is not None:
            try:
                preview_df = excel_import.read_excel_preview(uploaded_file)
            except Exception as e:
                st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
                preview_df = None

            if preview_df is not None:
                st.caption(f"미리보기 (총 {len(preview_df)}행)")
                st.dataframe(preview_df.head(5), use_container_width=True, hide_index=True)

                st.markdown("**컬럼 매칭**")
                excel_columns = ["(사용 안 함)"] + list(preview_df.columns)
                field_labels = {
                    "name": "성명 *", "gender": "성별", "birth_date": "생년월일",
                    "address": "주소", "phone": "전화번호",
                    "welfare_type": "회원 구분", "note": "비고",
                }

                def _guess_index(field: str) -> int:
                    for i, col in enumerate(excel_columns):
                        if str(col).strip() == field or str(col).strip() == field_labels[field].rstrip(" *"):
                            return i
                    return 0

                mapping = {}
                map_col1, map_col2 = st.columns(2)
                for i, (field, label) in enumerate(field_labels.items()):
                    with (map_col1 if i % 2 == 0 else map_col2):
                        mapping[field] = st.selectbox(
                            label, excel_columns, index=_guess_index(field), key=f"map_{field}"
                        )

                if st.button("일괄 등록 실행", use_container_width=True, type="primary"):
                    if mapping["name"] == "(사용 안 함)":
                        st.error("성명 컬럼은 반드시 매칭해야 합니다.")
                    else:
                        success, skipped, failed = 0, [], []
                        progress = st.progress(0.0)
                        total = len(preview_df)
                        for i, row in preview_df.iterrows():
                            mapped_row = {
                                field: (row[col] if col != "(사용 안 함)" else None)
                                for field, col in mapping.items()
                            }
                            normalized, warnings = excel_import.normalize_row(mapped_row)
                            progress.progress((i + 1) / total)

                            if not normalized["name"]:
                                skipped.append(f"{i + 2}행: 성명이 비어있어 건너뜀")
                                continue

                            payload = {
                                **normalized,
                                "consent_personal": "동의함", "consent_sensitive": "동의함",
                                "consent_third_party": "동의함", "consent_portrait": "동의함",
                            }
                            res = requests.post(f"{API_BASE}/clients", json=payload)
                            if res.status_code == 200:
                                success += 1
                                for w in warnings:
                                    skipped.append(f"{i + 2}행 ({normalized['name']}): {w}")
                            else:
                                detail = res.json().get("detail", res.text)
                                failed.append(f"{i + 2}행 ({normalized['name']}): {detail}")

                        st.success(f"{success}건 등록 완료")
                        if skipped:
                            with st.expander(f"경고 {len(skipped)}건"):
                                for msg in skipped:
                                    st.caption(msg)
                        if failed:
                            with st.expander(f"실패 {len(failed)}건"):
                                for msg in failed:
                                    st.caption(msg)

# ====================================================================
# 3. 회원 통계
# ====================================================================
elif menu == "회원 통계":
    st.subheader("회원 통계")
    try:
        summary = handle_response(requests.get(f"{API_BASE}/stats/summary"))
        if summary:
            st.markdown(
                f"**전체 회원수 : {summary['total']}명** | "
                f"오늘 신규가입 : {summary['today']}명 | "
                f"이번 달 신규가입 : {summary['this_month']}명"
            )
            st.divider()
            period_data = handle_response(requests.get(f"{API_BASE}/stats/period/월"))
            if period_data:
                st.markdown("#### 월별 가입 현황")
                st.dataframe(pd.DataFrame(period_data), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"통계 불러오기 실패: {e}")

# ====================================================================
# 4. 추천 복지 서비스 (AI 챗봇)
# ====================================================================
elif menu == "추천 복지 서비스":
    st.subheader("추천 복지 서비스")
    try:
        res = requests.get(f"{API_BASE}/clients")
        clients = handle_response(res)
        if not clients:
            st.info("등록된 회원이 없습니다.")
        else:
            options = {f"{c['id']} - {c['name']}": c['id'] for c in clients}
            sel_label = st.selectbox("회원 선택", options.keys())
            sel_id = options[sel_label]
            
            chat_state_key = f"chat_messages_{sel_id}"
            gov_state_key = f"gov_services_{sel_id}"
            sources_state_key = f"sources_{sel_id}"
            warnings_state_key = f"gov_warnings_{sel_id}"

            if chat_state_key not in st.session_state:
                st.session_state[chat_state_key] = []
                st.session_state[gov_state_key] = []
                st.session_state[sources_state_key] = []
                st.session_state[warnings_state_key] = []
                
            if not st.session_state[chat_state_key]:
                if st.button("복지서비스 검색 및 추천 받기", use_container_width=True):
                    with st.spinner("공공데이터 및 AI 분석 중..."):
                        init_res = requests.post(f"{API_BASE}/recommend/fetch_initial", params={"client_id": sel_id})
                        data = handle_response(init_res)
                        if data:
                            st.session_state[chat_state_key] = data["updated_messages"]
                            st.session_state[gov_state_key] = data["gov_services"]
                            st.session_state[sources_state_key] = data["sources"]
                            st.session_state[warnings_state_key] = data.get("warnings", [])
                            st.rerun()
            else:
                if st.button("대화 초기화", use_container_width=True):
                    st.session_state[chat_state_key] = []
                    st.session_state[gov_state_key] = []
                    st.session_state[sources_state_key] = []
                    st.session_state[warnings_state_key] = []
                    st.rerun()

            # 정부 공공데이터 조회 중 일부가 실패했다면(예: 일일 요청 한도 초과),
            # 조용히 넘어가지 않고 담당자가 원인을 알 수 있도록 경고로 보여줍니다.
            for w in st.session_state.get(warnings_state_key, []):
                st.warning(f"⚠️ {w}")
                    
            # 채팅 화면 출력 (system/tool 메시지, 그리고 맨 처음 자동 생성되는
            # "다음은 정부 공공데이터에서..." 원본 컨텍스트 메시지는 숨깁니다.
            # tool 메시지는 search_web이 가져온 원본 검색 결과라 매우 길고 사람이 읽을
            # 형태가 아니라서 화면에는 숨기고, GPT가 그걸 요약한 최종 답변만 보여줍니다.
            # 인덱스 1은 항상 backend가 자동으로 만든 초기 컨텍스트 메시지입니다
            # (0번=system, 1번=fetch_initial_recommendations가 붙인 공공데이터 원문).
            # GPT가 도구 호출만 하는 turn은 content가 없는 assistant 메시지를 남기므로
            # (model_dump(exclude_none=True)라 "content" 키 자체가 없음) 이것도 건너뜁니다.
            for i, msg in enumerate(st.session_state[chat_state_key]):
                if msg["role"] in ("system", "tool") or i == 1:
                    continue
                content = msg.get("content")
                if not content:
                    continue
                with st.chat_message(msg["role"]):
                    st.markdown(content)
                        
            # 공식 조회된 정부 복지 서비스 표
            if st.session_state[gov_state_key]:
                st.markdown("**공식 조회된 정부 복지서비스**")
                st.dataframe(pd.DataFrame(st.session_state[gov_state_key]), use_container_width=True, hide_index=True)
                
            # 유저 후속 질문 입력
            user_q = st.chat_input("추가로 궁금한 점을 물어보세요")
            if user_q:
                st.session_state[chat_state_key].append({"role": "user", "content": user_q})
                with st.spinner("AI가 답변을 준비 중입니다..."):
                    turn_payload = {"client_id": sel_id, "messages": st.session_state[chat_state_key]}
                    turn_res = requests.post(f"{API_BASE}/recommend/chat_turn", json=turn_payload)
                    turn_data = handle_response(turn_res)
                    if turn_data:
                        st.session_state[chat_state_key] = turn_data["updated_messages"]
                        if turn_data["sources"]:
                            st.session_state[sources_state_key].extend(turn_data["sources"])
                        st.rerun()
    except Exception as e:
        st.error(f"추천 서비스 오류: {e}")