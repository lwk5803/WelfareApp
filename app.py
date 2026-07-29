"""
app.py
------
사회복지 대상자 관리

실행 방법:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from io import BytesIO

import database as db
import parsers

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

    # ====================================================================
    # --- 신규 등록 탭 ---
    # ====================================================================
    with tab_add:
        st.subheader("신규 대상자 등록")

        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("성명 *")
                birth_date = st.text_input(
                    "생년월일",
                    placeholder="예: 1990-01-01, 900101 등 자유롭게 입력 가능",
                )
                address = st.text_input("주소")
            with col2:
                phone = st.text_input(
                    "전화번호",
                    placeholder="예: 01012345678 (숫자만 입력해도 자동 변환)",
                )
                welfare_type = st.selectbox("대상자 계층", WELFARE_TYPES)
            note = st.text_area("비고 (가입목적, 특이사항 등)")

            submitted = st.form_submit_button("등록하기", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("성명은 필수 입력 항목입니다.")
            else:
                # ---- 기능 2: 입력 파싱 ----
                # 사용자가 자유롭게 입력한 텍스트를 정해진 형식으로 정규화합니다.
                parsed_birth_date = parsers.parse_birth_date(birth_date) if birth_date.strip() else ""
                parsed_phone = parsers.parse_phone(phone) if phone.strip() else ""

                # ---- 기능 3: 중복 방지 ----
                # 저장하기 전에, 같은 사람으로 보이는 기존 대상자가 있는지 먼저 확인합니다.
                duplicates = db.find_duplicates(name.strip(), parsed_birth_date, parsed_phone)

                if not duplicates.empty:
                    # 바로 저장하지 않고, 폼에 입력했던 값을 잠시 세션에 보관해둡니다.
                    # (다음 화면 새로고침에서도 이 값을 기억하고 있어야 하기 때문)
                    st.session_state["pending_client"] = {
                        "name": name.strip(),
                        "birth_date": parsed_birth_date,
                        "address": address,
                        "phone": parsed_phone,
                        "welfare_type": welfare_type,
                        "note": note,
                    }
                else:
                    db.add_client(name.strip(), parsed_birth_date, address, parsed_phone, welfare_type, note)
                    st.success(
                        f"'{name}' 님을 등록했습니다. "
                        f"(생년월일: {parsed_birth_date or '미입력'}, 전화번호: {parsed_phone or '미입력'})"
                    )

        # 중복 의심 대상자가 발견된 경우, 별도의 확인 절차를 보여줍니다.
        # (폼 submit 처리 블록 밖에 있어야, 버튼을 눌러도 값이 계속 유지됩니다.)
        if "pending_client" in st.session_state:
            pending = st.session_state["pending_client"]

            st.warning(
                f"'{pending['name']}' 님과 이름·생년월일 또는 전화번호가 같은 대상자가 "
                "이미 등록되어 있습니다. 동일인이 아닌지 확인해주세요."
            )

            existing = db.find_duplicates(pending["name"], pending["birth_date"], pending["phone"])
            st.dataframe(
                existing[["id", "name", "birth_date", "phone", "welfare_type"]],
                use_container_width=True,
                hide_index=True,
            )

            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("다른 사람입니다 - 그래도 등록", use_container_width=True):
                    db.add_client(
                        pending["name"], pending["birth_date"], pending["address"],
                        pending["phone"], pending["welfare_type"], pending["note"],
                    )
                    del st.session_state["pending_client"]
                    st.success(f"'{pending['name']}' 님을 등록했습니다.")
                    st.rerun()
            with col_no:
                if st.button("취소 (등록하지 않음)", use_container_width=True):
                    del st.session_state["pending_client"]
                    st.rerun()

    # ====================================================================
    # --- 기존 대상자 수정/삭제 탭 ---
    # ====================================================================
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
                    birth_date = st.text_input("생년월일", value=client["birth_date"] or "")
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

                edit_submitted = st.form_submit_button("수정하기", use_container_width=True)

            if edit_submitted:
                parsed_birth_date = parsers.parse_birth_date(birth_date) if birth_date.strip() else ""
                parsed_phone = parsers.parse_phone(phone) if phone.strip() else ""
                db.update_client(selected_id, name, parsed_birth_date, address, parsed_phone, welfare_type, note)
                st.success(f"'{name}' 님의 정보를 수정했습니다.")
                st.rerun()

            # ---- 기능 1: 삭제 확인 ----
            # "삭제하기"를 폼 밖의 일반 버튼으로 분리해서, 클릭 즉시 삭제되지 않고
            # 한 번 더 "정말 삭제할지" 확인하는 단계를 거치도록 만듭니다.
            st.divider()
            st.markdown("**대상자 삭제**")

            if st.session_state.get("confirm_delete_id") == selected_id:
                st.warning(f"정말 '{client['name']}' 님을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("예, 삭제합니다", use_container_width=True, type="primary"):
                        db.delete_client(selected_id)
                        del st.session_state["confirm_delete_id"]
                        st.success(f"'{client['name']}' 님의 정보를 삭제했습니다.")
                        st.rerun()
                with col_no:
                    if st.button("취소", use_container_width=True):
                        del st.session_state["confirm_delete_id"]
                        st.rerun()
            else:
                if st.button("삭제하기", use_container_width=True, type="secondary"):
                    st.session_state["confirm_delete_id"] = selected_id
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