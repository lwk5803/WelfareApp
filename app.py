"""
app.py
------
복지관 회원 관리

실행 방법:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from io import BytesIO

import database as db
import parsers
import stats

st.set_page_config(page_title="복지관 회원 관리", layout="wide")

# 테이블/전화번호 중복 방지 인덱스를 준비합니다. (화면에 별도 안내는 띄우지 않고,
# 실제로 중복된 전화번호를 등록/수정하려는 시점에만 오류 메시지로 알려줍니다.)
if "db_ready" not in st.session_state:
    db.init_db()
    st.session_state["db_ready"] = True

st.title("복지관 회원 관리")

menu = st.sidebar.radio("메뉴", ["회원 목록", "회원 등록/수정/삭제"])

GENDER_OPTIONS = ["남", "여"]
WELFARE_TYPES = ["일반", "차상위", "수급자"]

# DB 컬럼명(영어)은 그대로 두고, 화면/엑셀에 보여줄 때만 한글로 바꿔주기 위한 매핑입니다.
COLUMN_LABELS = {
    "id": "번호",
    "name": "성명",
    "gender": "성별",
    "birth_date": "생년월일",
    "address": "주소",
    "phone": "전화번호",
    "welfare_type": "회원 구분",
    "note": "비고",
    "created_at": "등록일시",
}

OLD_MEMBER_DAYS = 365  # 이 일수 이상 지난 회원은 목록에서 색을 다르게 표시합니다.


def highlight_old_members(row: pd.Series) -> list[str]:
    """등록일시가 OLD_MEMBER_DAYS일 이상 지난 행에 배경색을 입히는 스타일 함수입니다."""
    created = pd.to_datetime(row.get("등록일시"), errors="coerce")
    if pd.notna(created) and (pd.Timestamp.now() - created).days >= OLD_MEMBER_DAYS:
        return ["background-color: #fdecea"] * len(row)
    return [""] * len(row)


# ----------------------------------------------------------------------
# 1) 회원 목록 - 조회 + 다운로드
# ----------------------------------------------------------------------
if menu == "회원 목록":
    st.subheader("회원 목록")
    st.caption(f"🟥 붉은색으로 표시된 행은 등록일이 {OLD_MEMBER_DAYS}일(약 1년) 이상 지난 회원입니다.")

    try:
        df = db.get_all_clients()
    except db.DatabaseError as e:
        st.error(str(e))
        st.stop()

    if df.empty:
        st.info("등록된 회원이 없습니다. '회원 등록/수정/삭제' 메뉴에서 추가해보세요.")
    else:
        # ---- 요약 통계 (그래프 대신 텍스트로) ----
        summary = stats.build_summary(df)
        st.markdown(
            f"**전체 회원수 : {summary['total']}명**"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"오늘 신규가입 : {summary['today']}명"
            f"&nbsp;&nbsp;/&nbsp;&nbsp;"
            f"이번 달 신규가입 : {summary['this_month']}명"
        )
        st.markdown(
            f"성별 — 남 {summary['male']}명 / 여 {summary['female']}명"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"구분 — 일반 {summary['general']}명, "
            f"차상위 {summary['near_poor']}명, "
            f"수급자 {summary['recipient']}명"
        )
        st.divider()

        search_keyword = st.text_input("이름으로 검색", placeholder="이름을 입력하세요 (전체를 보려면 비워두세요)")

        if search_keyword:
            filtered_df = df[df["name"].str.contains(search_keyword, na=False, regex=False)]
        else:
            filtered_df = df

        st.caption(f"총 {len(filtered_df)}명")

        display_df = filtered_df[
            ["id", "name", "gender", "birth_date", "phone", "welfare_type", "created_at"]
        ].rename(columns=COLUMN_LABELS)

        st.dataframe(
            display_df.style.apply(highlight_old_members, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            filtered_df.rename(columns=COLUMN_LABELS).to_excel(writer, index=False, sheet_name="회원 명단")
        buffer.seek(0)

        st.download_button(
            label="회원 명단 다운로드",
            data=buffer,
            file_name="회원명단.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


# ----------------------------------------------------------------------
# 2) 회원 등록/수정/삭제 - 통합 화면 (탭으로 구분)
# ----------------------------------------------------------------------
elif menu == "회원 등록/수정/삭제":
    tab_add, tab_edit = st.tabs(["신규 회원 등록", "기존 회원 수정/삭제"])

    # ====================================================================
    # --- 신규 등록 탭 ---
    # ====================================================================
    with tab_add:
        st.subheader("신규 회원 등록")

        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("성명 *")
                gender = st.radio("성별", GENDER_OPTIONS, horizontal=True)
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
                welfare_type = st.selectbox("회원 구분", WELFARE_TYPES)
            note = st.text_area("비고 (가입목적, 특이사항 등)")

            submitted = st.form_submit_button("등록하기", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("성명은 필수 입력 항목입니다.")
            else:
                if birth_date.strip():
                    parsed_birth_date, birth_date_ok = parsers.parse_birth_date(birth_date)
                    if not birth_date_ok:
                        st.warning(f"생년월일 '{birth_date}'을(를) 인식하지 못해 입력하신 그대로 저장합니다.")
                else:
                    parsed_birth_date = ""

                if phone.strip():
                    parsed_phone, phone_ok = parsers.parse_phone(phone)
                    if not phone_ok:
                        st.warning(f"전화번호 '{phone}'을(를) 인식하지 못해 입력하신 그대로 저장합니다.")
                else:
                    parsed_phone = ""

                try:
                    duplicates = db.find_duplicates(name.strip(), parsed_birth_date, parsed_phone)
                except db.DatabaseError as e:
                    st.error(str(e))
                    duplicates = None

                if duplicates is not None:
                    if not duplicates.empty:
                        st.session_state["pending_client"] = {
                            "name": name.strip(),
                            "gender": gender,
                            "birth_date": parsed_birth_date,
                            "address": address,
                            "phone": parsed_phone,
                            "welfare_type": welfare_type,
                            "note": note,
                        }
                    else:
                        try:
                            db.add_client(
                                name.strip(), gender, parsed_birth_date, address,
                                parsed_phone, welfare_type, note,
                            )
                            st.success(
                                f"'{name}' 님을 등록했습니다. "
                                f"(생년월일: {parsed_birth_date or '미입력'}, 전화번호: {parsed_phone or '미입력'})"
                            )
                        except db.DatabaseError as e:
                            st.error(str(e))

        if "pending_client" in st.session_state:
            pending = st.session_state["pending_client"]

            st.warning(
                f"'{pending['name']}' 님과 이름·생년월일 또는 전화번호가 같은 회원이 "
                "이미 등록되어 있습니다. 동일인이 아닌지 확인해주세요."
            )

            try:
                existing = db.find_duplicates(pending["name"], pending["birth_date"], pending["phone"])
                st.dataframe(
                    existing[["id", "name", "gender", "birth_date", "phone", "welfare_type"]]
                    .rename(columns=COLUMN_LABELS),
                    use_container_width=True,
                    hide_index=True,
                )
            except db.DatabaseError as e:
                st.error(str(e))

            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("다른 사람입니다 - 그래도 등록", use_container_width=True):
                    try:
                        db.add_client(
                            pending["name"], pending["gender"], pending["birth_date"],
                            pending["address"], pending["phone"], pending["welfare_type"], pending["note"],
                        )
                        del st.session_state["pending_client"]
                        st.success(f"'{pending['name']}' 님을 등록했습니다.")
                        st.rerun()
                    except db.DatabaseError as e:
                        st.error(str(e))
            with col_no:
                if st.button("취소 (등록하지 않음)", use_container_width=True):
                    del st.session_state["pending_client"]
                    st.rerun()

    # ====================================================================
    # --- 기존 회원 수정/삭제 탭 ---
    # ====================================================================
    with tab_edit:
        st.subheader("기존 회원 수정 / 삭제")

        try:
            df = db.get_all_clients()
        except db.DatabaseError as e:
            st.error(str(e))
            st.stop()

        if df.empty:
            st.info("등록된 회원이 없습니다. '신규 등록' 탭에서 먼저 추가해주세요.")
        else:
            options = {f"{row['id']} - {row['name']}": row["id"] for _, row in df.iterrows()}
            selected_label = st.selectbox("회원 선택", options.keys())
            selected_id = options[selected_label]

            try:
                client = db.get_client(selected_id)
            except db.DatabaseError as e:
                st.error(str(e))
                st.stop()

            with st.form("edit_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("성명", value=client["name"])
                    gender = st.radio(
                        "성별", GENDER_OPTIONS, horizontal=True,
                        index=GENDER_OPTIONS.index(client["gender"]) if client["gender"] in GENDER_OPTIONS else 0,
                    )
                    birth_date = st.text_input("생년월일", value=client["birth_date"] or "")
                    address = st.text_input("주소", value=client["address"] or "")
                with col2:
                    phone = st.text_input("전화번호", value=client["phone"] or "")
                    welfare_type = st.selectbox(
                        "회원 구분",
                        WELFARE_TYPES,
                        index=WELFARE_TYPES.index(client["welfare_type"])
                        if client["welfare_type"] in WELFARE_TYPES else 0,
                    )
                note = st.text_area("비고 (가입목적, 특이사항 등)", value=client["note"] or "")

                edit_submitted = st.form_submit_button("수정하기", use_container_width=True)

            if edit_submitted:
                if not name.strip():
                    st.error("성명은 필수 입력 항목입니다.")
                else:
                    if birth_date.strip():
                        parsed_birth_date, birth_date_ok = parsers.parse_birth_date(birth_date)
                        if not birth_date_ok:
                            st.warning(f"생년월일 '{birth_date}'을(를) 인식하지 못해 입력하신 그대로 저장합니다.")
                    else:
                        parsed_birth_date = ""

                    if phone.strip():
                        parsed_phone, phone_ok = parsers.parse_phone(phone)
                        if not phone_ok:
                            st.warning(f"전화번호 '{phone}'을(를) 인식하지 못해 입력하신 그대로 저장합니다.")
                    else:
                        parsed_phone = ""

                    try:
                        db.update_client(
                            selected_id, name.strip(), gender, parsed_birth_date, address,
                            parsed_phone, welfare_type, note,
                        )
                        st.success(f"'{name}' 님의 정보를 수정했습니다.")
                        st.rerun()
                    except db.DatabaseError as e:
                        st.error(str(e))

            st.divider()
            st.markdown("**회원 삭제**")

            if st.session_state.get("confirm_delete_id") == selected_id:
                st.warning(f"정말 '{client['name']}' 님을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("예, 삭제합니다", use_container_width=True, type="primary"):
                        try:
                            db.delete_client(selected_id)
                            del st.session_state["confirm_delete_id"]
                            st.success(f"'{client['name']}' 님의 정보를 삭제했습니다.")
                            st.rerun()
                        except db.DatabaseError as e:
                            st.error(str(e))
                with col_no:
                    if st.button("취소", use_container_width=True):
                        del st.session_state["confirm_delete_id"]
                        st.rerun()
            else:
                if st.button("삭제하기", use_container_width=True, type="secondary"):
                    st.session_state["confirm_delete_id"] = selected_id
                    st.rerun()