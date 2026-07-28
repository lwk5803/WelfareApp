"""
app.py
------
사회복지 대상자 관리 - 새로 시작하는 버전 (1단계: 회원가입 양식 1페이지) _ 1차 수정

실행 방법:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from io import BytesIO

import database as db

st.set_page_config(page_title="사회복지 대상자 관리", layout="wide")

db.init_db()

st.title("사회복지 대상자 관리")

menu = st.sidebar.radio("메뉴", ["대상자 목록", "대상자 등록/수정/삭제", "엑셀 내보내기"])

WELFARE_TYPES = ["일반", "차상위", "수급자"]


# ----------------------------------------------------------------------
# 1) 대상자 목록 - 조회 전용 (검색 + 인쇄)
# ----------------------------------------------------------------------
if menu == "대상자 목록":
    st.subheader("대상자 목록")

    df = db.get_all_clients()

    if df.empty:
        st.info("등록된 대상자가 없습니다. '대상자 등록/수정/삭제' 메뉴에서 추가해보세요.")
    else:
        search_keyword = st.text_input("이름으로 검색", placeholder="이름을 입력하세요 (전체를 보려면 비워두세요)")

        if search_keyword:
            filtered_df = df[df["name"].str.contains(search_keyword, na=False)]
        else:
            filtered_df = df

        st.caption(f"총 {len(filtered_df)}명")

        st.dataframe(
            filtered_df[["id", "name", "birth_date", "phone", "welfare_type", "created_at"]],
            use_container_width=True,
            hide_index=True,
        )

        # 브라우저의 인쇄 기능(Ctrl+P)을 버튼으로 바로 띄워주는 부분입니다.
        # window.print()는 파이썬이 아니라 브라우저에서 실행되는 자바스크립트 명령입니다.
        st.markdown(
            """
            <button onclick="window.print()" style="
                width:100%; padding:0.5rem; margin-top:0.5rem;
                border-radius:0.5rem; border:1px solid #d0d0d0;
                background-color:#f0f2f6; cursor:pointer; font-size:1rem;">
                🖨️ 목록 인쇄하기
            </button>
            """,
            unsafe_allow_html=True,
        )


# ----------------------------------------------------------------------
# 2) 대상자 등록/수정/삭제 - 통합 화면 (탭으로 구분)
# ----------------------------------------------------------------------
elif menu == "대상자 등록/수정/삭제":
    tab_add, tab_edit = st.tabs(["신규 등록", "기존 대상자 수정/삭제"])

    # --- 신규 등록 탭 ---
    with tab_add:
        st.subheader("신규 대상자 등록")

        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("성명 *")
                birth_date = st.text_input("생년월일 (예: 1990-01-01)")
                address = st.text_input("주소")
            with col2:
                phone = st.text_input("전화번호")
                welfare_type = st.selectbox("대상자 계층", WELFARE_TYPES)
            note = st.text_area("비고 (가입목적, 특이사항 등)")

            submitted = st.form_submit_button("등록하기", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("성명은 필수 입력 항목입니다.")
            else:
                db.add_client(name, birth_date, address, phone, welfare_type, note)
                st.success(f"'{name}' 님을 등록했습니다.")

    # --- 기존 대상자 수정/삭제 탭 ---
    with tab_edit:
        st.subheader("기존 대상자 수정 / 삭제")

        df = db.get_all_clients()

        if df.empty:
            st.info("등록된 대상자가 없습니다. '신규 등록' 탭에서 먼저 추가해주세요.")
        else:
            options = {f"{row['id']} - {row['name']}": row["id"] for _, row in df.iterrows()}
            selected_label = st.selectbox("대상자 선택", options.keys())
            selected_id = options[selected_label]
            client = db.get_client(selected_id)

            with st.form("edit_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("성명", value=client["name"])
                    birth_date = st.text_input("생년월일 (예: 1990-01-01)", value=client["birth_date"] or "")
                    address = st.text_input("주소", value=client["address"] or "")
                with col2:
                    phone = st.text_input("전화번호", value=client["phone"] or "")
                    welfare_type = st.selectbox(
                        "대상자 계층",
                        WELFARE_TYPES,
                        index=WELFARE_TYPES.index(client["welfare_type"])
                        if client["welfare_type"] in WELFARE_TYPES else 0,
                    )
                note = st.text_area("비고 (가입목적, 특이사항 등)", value=client["note"] or "")

                col_a, col_b = st.columns(2)
                with col_a:
                    edit_submitted = st.form_submit_button("수정하기", use_container_width=True)
                with col_b:
                    deleted = st.form_submit_button("삭제하기", use_container_width=True, type="secondary")

            if edit_submitted:
                db.update_client(selected_id, name, birth_date, address, phone, welfare_type, note)
                st.success(f"'{name}' 님의 정보를 수정했습니다.")
                st.rerun()

            if deleted:
                db.delete_client(selected_id)
                st.warning(f"'{client['name']}' 님의 정보를 삭제했습니다.")
                st.rerun()


# ----------------------------------------------------------------------
# 3) 엑셀 내보내기
# ----------------------------------------------------------------------
elif menu == "엑셀 내보내기":
    st.subheader("엑셀 내보내기")

    df = db.get_all_clients()

    if df.empty:
        st.info("내보낼 데이터가 없습니다.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="대상자목록")
        buffer.seek(0)

        st.download_button(
            label="엑셀 파일 다운로드",
            data=buffer,
            file_name="대상자목록.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )