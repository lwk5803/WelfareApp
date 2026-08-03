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
import address_api
import excel_import

st.set_page_config(page_title="복지관 회원 관리", layout="wide")

# 테이블/전화번호 중복 방지 인덱스를 준비합니다. (화면에 별도 안내는 띄우지 않고,
# 실제로 중복된 전화번호를 등록/수정하려는 시점에만 오류 메시지로 알려줍니다.)
if "db_ready" not in st.session_state:
    db.init_db()
    st.session_state["db_ready"] = True

st.title("복지관 회원 관리")

menu = st.sidebar.radio("메뉴", ["회원 목록", "회원 등록/수정/삭제", "회원 통계"])

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

CONSENT_OPTIONS = ["동의함", "동의하지 않음"]

# 개인정보 동의서 안내문입니다. 첨부해주신 이용신청서의 "개인정보 등 수집 및 이용 동의서"
# 내용을 화면에 보여주기 좋게 정리한 것입니다. 실제 기관 문구와 다르면 이 딕셔너리만 고치면 됩니다.
CONSENT_TEXTS = {
    "personal": (
        "**개인정보 수집·이용 동의**\n\n"
        "- 수집 항목: 성명, 성별, 생년월일, 주소, 연락처 등\n"
        "- 수집 목적: 회원가입과 프로그램 참여 및 서비스 제공·관리\n"
        "- 보유 기간: 신청서 제출 시부터 회원 자격 상실 시까지\n"
        "- 동의를 거부할 권리가 있으며, 거부 시 회원가입과 서비스 이용이 제한될 수 있습니다."
    ),
    "sensitive": (
        "**민감정보 수집·이용 동의**\n\n"
        "- 수집 항목: 건강정보, 소득 및 재산정보, 보호구분 등\n"
        "- 수집 목적: 서비스 제공 대상자 선정 및 맞춤형 서비스 연계\n"
        "- 동의를 거부할 권리가 있으며, 거부 시 회원가입과 서비스 이용이 제한될 수 있습니다."
    ),
    "third_party": (
        "**개인정보 제3자 제공 동의**\n\n"
        "- 제공받는 자: 관할 행정기관(시청, 구청, 주민센터 등) 및 사회복지서비스 제공기관\n"
        "- 제공 목적: 관계 법령에 따른 제출·요청, 서비스 의뢰, 외부기관 예산지원 신청 등\n"
        "- 동의를 거부할 권리가 있으며, 거부 시 일부 서비스 이용이 제한될 수 있습니다."
    ),
    "portrait": (
        "**초상권 사용 및 이용 동의**\n\n"
        "- 사용 목적: 기관 온·오프라인 사업소개 및 홍보, 기록자료 활용\n"
        "- 사용 항목: 서비스 이용사진 및 운영사진 등\n"
        "- 동의를 거부할 권리가 있으며, 거부해도 회원가입 자체에는 영향이 없습니다."
    ),
}


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
        search_keyword = st.text_input("이름으로 검색", placeholder="이름을 입력하세요 (전체를 보려면 비워두세요)")

        if search_keyword:
            filtered_df = df[df["name"].str.contains(search_keyword, na=False, regex=False)]
        else:
            filtered_df = df

        st.caption(f"총 {len(filtered_df)}명")

        if filtered_df.empty:
            st.info("검색 결과가 없습니다. 다른 이름으로 검색해보세요.")
        else:
            display_df = filtered_df[
                ["id", "name", "gender", "birth_date", "address", "phone", "welfare_type", "created_at"]
            ].rename(columns=COLUMN_LABELS)

            st.dataframe(
                display_df.style.apply(highlight_old_members, axis=1),
                use_container_width=True,
                hide_index=True,
            )

            # 동의 관련 컬럼(consent_*)은 법적 확인 기록이라 일반 명단 다운로드에서는 제외합니다.
            # 화면 표(display_df)와 마찬가지로, 여기서도 내보낼 컬럼을 명시적으로 골라줍니다.
            export_df = filtered_df[
                ["id", "name", "gender", "birth_date", "address", "phone", "welfare_type", "note", "created_at"]
            ].rename(columns=COLUMN_LABELS)

            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False, sheet_name="회원 명단")
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
    tab_add, tab_import, tab_edit = st.tabs(["신규 회원 등록", "엑셀 일괄 등록", "기존 회원 수정/삭제"])

    # ====================================================================
    # --- 신규 등록 탭 ---
    # ====================================================================
    with tab_add:
        st.subheader("신규 회원 등록")

        # ---- 주소 검색 도우미 (폼 밖에 둡니다) ----
        # 검색 → 결과 선택 → 아래 폼의 주소 입력창에 자동으로 채워지는 흐름입니다.
        #
        # 이 입력창(주소)에는 일부러 key를 주지 않습니다. key가 있는 위젯은 한 번이라도
        # 값이 세팅되면 그 이후로 value= 파라미터를 무시하는데, 그 상태에서 버튼 클릭 시점에
        # session_state[key]를 직접 바꾸려고 하면 "이미 그려진 위젯은 못 바꾼다"는 에러가 납니다.
        # key 없이 value=만 매번 새로 넘겨주는 방식이 이런 충돌 없이 안정적으로 동작합니다.
        with st.expander("🔍 주소 검색 (지번/구주소 입력 시 도로명주소로 자동 변환)"):
            address_keyword = st.text_input("지번(구주소) 또는 건물명을 입력하세요", key="address_keyword_add")

            if st.button("주소 검색", key="address_search_btn_add"):
                if not address_keyword.strip():
                    st.warning("검색어를 먼저 입력해주세요.")
                else:
                    try:
                        st.session_state["address_results_add"] = address_api.search_road_address(
                            address_keyword.strip()
                        )
                    except address_api.AddressLookupError as e:
                        st.error(str(e))

            if st.session_state.get("address_results_add") is not None:
                results = st.session_state["address_results_add"]
                if not results:
                    st.info("검색 결과가 없습니다. 다른 키워드로 다시 검색해보세요.")
                else:
                    result_options = {
                        f"{r['road_address']} ({r['zip_code']})": r["road_address"] for r in results
                    }
                    picked_label = st.selectbox(
                        "검색된 주소 중 선택하세요", result_options.keys(), key="address_pick_add"
                    )
                    if st.button("이 주소로 채우기", key="address_fill_btn_add"):
                        st.session_state["prefilled_address_add"] = result_options[picked_label]
                        del st.session_state["address_results_add"]
                        st.rerun()

        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("성명 *")
                gender = st.radio("성별", GENDER_OPTIONS, horizontal=True)
                birth_date = st.text_input(
                    "생년월일",
                    placeholder="예: 1990-01-01, 900101 등 자유롭게 입력 가능",
                )
                # 주소 검색 도우미에서 고른 주소가 있으면 그 값을 기본값으로 보여줍니다.
                # 검색 없이 직접 타이핑해도 되고, 검색 후에도 자유롭게 수정할 수 있습니다.
                address = st.text_input("주소", value=st.session_state.get("prefilled_address_add", ""))
            with col2:
                phone = st.text_input(
                    "전화번호",
                    placeholder="예: 01012345678 (숫자만 입력해도 자동 변환)",
                )
                welfare_type = st.selectbox("회원 구분", WELFARE_TYPES)
            note = st.text_area("비고 (가입목적, 특이사항 등)")

            st.divider()
            st.markdown("#### 개인정보 동의")
            st.caption("각 항목의 내용을 확인하신 후 동의 여부를 선택해주세요. 개인정보·민감정보 동의는 회원가입에 필수입니다.")

            with st.expander("① 개인정보 수집·이용 동의 내용 보기"):
                st.markdown(CONSENT_TEXTS["personal"])
            consent_personal = st.radio(
                "개인정보 수집 및 이용에 동의하십니까? *", CONSENT_OPTIONS, index=None, key="consent_personal_add",
            )

            with st.expander("② 민감정보 수집·이용 동의 내용 보기"):
                st.markdown(CONSENT_TEXTS["sensitive"])
            consent_sensitive = st.radio(
                "민감정보 수집 및 이용에 동의하십니까? *", CONSENT_OPTIONS, index=None, key="consent_sensitive_add",
            )

            with st.expander("③ 개인정보 제3자 제공 동의 내용 보기"):
                st.markdown(CONSENT_TEXTS["third_party"])
            consent_third_party = st.radio(
                "개인정보 제3자 제공에 동의하십니까? *", CONSENT_OPTIONS, index=None, key="consent_third_party_add",
            )

            with st.expander("④ 초상권 사용 동의 내용 보기"):
                st.markdown(CONSENT_TEXTS["portrait"])
            consent_portrait = st.radio(
                "초상권 사용 및 이용에 동의하십니까? *", CONSENT_OPTIONS, index=None, key="consent_portrait_add",
            )

            signature_name = st.text_input(
                "서명 (본인 성명을 다시 한 번 입력해주세요) *",
                placeholder="위 성명란과 동일하게 입력",
            )

            submitted = st.form_submit_button("등록하기", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("성명은 필수 입력 항목입니다.")
            elif None in (consent_personal, consent_sensitive, consent_third_party, consent_portrait):
                st.error("개인정보 동의 4개 항목에 모두 응답해주세요 (동의함 / 동의하지 않음 중 선택).")
            elif consent_personal != "동의함" or consent_sensitive != "동의함":
                st.error("개인정보 및 민감정보 수집·이용에 동의하셔야 회원가입이 가능합니다.")
            elif signature_name.strip() != name.strip():
                st.error("서명란에 입력하신 성명이 위에 입력하신 성명과 일치하지 않습니다.")
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
                            "consent_personal": consent_personal,
                            "consent_sensitive": consent_sensitive,
                            "consent_third_party": consent_third_party,
                            "consent_portrait": consent_portrait,
                        }
                    else:
                        try:
                            db.add_client(
                                name=name.strip(),
                                gender=gender,
                                birth_date=parsed_birth_date,
                                address=address,
                                phone=parsed_phone,
                                welfare_type=welfare_type,
                                note=note,
                                consent_personal=consent_personal,
                                consent_sensitive=consent_sensitive,
                                consent_third_party=consent_third_party,
                                consent_portrait=consent_portrait,
                            )
                            st.session_state.pop("prefilled_address_add", None)
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
                            name=pending["name"],
                            gender=pending["gender"],
                            birth_date=pending["birth_date"],
                            address=pending["address"],
                            phone=pending["phone"],
                            welfare_type=pending["welfare_type"],
                            note=pending["note"],
                            consent_personal=pending["consent_personal"],
                            consent_sensitive=pending["consent_sensitive"],
                            consent_third_party=pending["consent_third_party"],
                            consent_portrait=pending["consent_portrait"],
                        )
                        del st.session_state["pending_client"]
                        st.session_state.pop("prefilled_address_add", None)
                        st.success(f"'{pending['name']}' 님을 등록했습니다.")
                        st.rerun()
                    except db.DatabaseError as e:
                        st.error(str(e))
            with col_no:
                if st.button("취소 (등록하지 않음)", use_container_width=True):
                    del st.session_state["pending_client"]
                    st.rerun()

    # ====================================================================
    # --- 엑셀 일괄 등록 탭 ---
    # ====================================================================
    with tab_import:
        st.subheader("엑셀로 회원 일괄 등록")
        st.caption(
            "기존에 쓰시던 회원 명단 엑셀 파일(.xlsx)을 업로드하고, "
            "각 항목이 파일의 어떤 열에 해당하는지 지정해주세요."
        )
        st.info(
            "이렇게 가져온 회원은 이 앱의 '개인정보 동의' 절차를 거치지 않은 상태로 등록됩니다. "
            "동의 여부는 미확인 상태로 저장되니, 실제 동의는 기존에 받아두신 서류나 "
            "별도 절차로 관리해주세요."
        )
        st.warning(
            "⚠️ 원본 엑셀에서 전화번호나 생년월일이 '숫자' 형식 셀로 저장되어 있었다면, "
            "엑셀이 맨 앞자리 0을 이미 지웠을 수 있습니다 (예: 010... → 10...). "
            "가져오기 후 목록에서 꼭 확인해주시고, 틀린 값은 '기존 회원 수정/삭제' 탭에서 고쳐주세요."
        )

        uploaded_file = st.file_uploader("엑셀 파일 업로드 (.xlsx)", type=["xlsx"], key="import_excel_uploader")

        if uploaded_file is not None:
            try:
                raw_df = excel_import.read_excel_preview(uploaded_file)
            except Exception as e:
                st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다. 파일 형식을 확인해주세요. ({e})")
                raw_df = None

            if raw_df is not None:
                if raw_df.empty:
                    st.warning("업로드한 파일에 데이터가 없습니다.")
                else:
                    st.markdown("**업로드된 파일 미리보기 (상위 5행)**")
                    st.dataframe(raw_df.head(), use_container_width=True)

                    st.markdown("**항목 매칭**")
                    st.caption("우리 시스템의 각 항목이 업로드한 파일의 어떤 열에 해당하는지 선택해주세요.")

                    column_options = ["(선택 안 함)"] + list(raw_df.columns)

                    map_col1, map_col2 = st.columns(2)
                    with map_col1:
                        map_name = st.selectbox("성명 * (필수)", column_options, key="map_name")
                        map_gender = st.selectbox("성별", column_options, key="map_gender")
                        map_birth = st.selectbox("생년월일", column_options, key="map_birth")
                        map_address = st.selectbox("주소", column_options, key="map_address")
                    with map_col2:
                        map_phone = st.selectbox("전화번호", column_options, key="map_phone")
                        map_type = st.selectbox("회원 구분", column_options, key="map_type")
                        map_note = st.selectbox("비고", column_options, key="map_note")

                    if st.button("가져오기 실행", use_container_width=True):
                        if map_name == "(선택 안 함)":
                            st.error("성명 항목은 반드시 지정해야 합니다.")
                        else:
                            mapping = {
                                "name": map_name,
                                "gender": map_gender,
                                "birth_date": map_birth,
                                "address": map_address,
                                "phone": map_phone,
                                "welfare_type": map_type,
                                "note": map_note,
                            }

                            success_count = 0
                            skipped_count = 0
                            failed_rows = []

                            with st.spinner("가져오는 중입니다..."):
                                for idx, row in raw_df.iterrows():
                                    mapped_row = {
                                        field: (row[col] if col != "(선택 안 함)" else None)
                                        for field, col in mapping.items()
                                    }
                                    normalized, _warnings = excel_import.normalize_row(mapped_row)

                                    if not normalized["name"]:
                                        skipped_count += 1
                                        continue

                                    try:
                                        duplicates = db.find_duplicates(
                                            normalized["name"], normalized["birth_date"], normalized["phone"]
                                        )
                                    except db.DatabaseError as e:
                                        failed_rows.append((idx + 2, normalized["name"], str(e)))
                                        continue

                                    if not duplicates.empty:
                                        skipped_count += 1
                                        continue

                                    try:
                                        db.add_client(
                                            name=normalized["name"],
                                            gender=normalized["gender"],
                                            birth_date=normalized["birth_date"],
                                            address=normalized["address"],
                                            phone=normalized["phone"],
                                            welfare_type=normalized["welfare_type"],
                                            note=normalized["note"],
                                            consent_personal="",
                                            consent_sensitive="",
                                            consent_third_party="",
                                            consent_portrait="",
                                        )
                                        success_count += 1
                                    except db.DatabaseError as e:
                                        failed_rows.append((idx + 2, normalized["name"], str(e)))

                            st.success(
                                f"가져오기 완료 — 등록 성공: {success_count}건 / "
                                f"중복·이름없음으로 건너뜀: {skipped_count}건 / 실패: {len(failed_rows)}건"
                            )

                            if failed_rows:
                                st.markdown("**실패한 행**")
                                st.dataframe(
                                    pd.DataFrame(failed_rows, columns=["엑셀 행 번호", "성명", "실패 사유"]),
                                    use_container_width=True,
                                    hide_index=True,
                                )

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
            edit_search_keyword = st.text_input(
                "이름으로 검색 (수정/삭제 대상 찾기)",
                placeholder="이름을 입력하세요 (전체를 보려면 비워두세요)",
                key="edit_search_keyword",
            )

            if edit_search_keyword:
                edit_target_df = df[df["name"].str.contains(edit_search_keyword, na=False, regex=False)]
            else:
                edit_target_df = df

            if edit_target_df.empty:
                st.info("검색 결과가 없습니다.")
                st.stop()

            options = {f"{row['id']} - {row['name']}": row["id"] for _, row in edit_target_df.iterrows()}
            selected_label = st.selectbox("회원 선택", options.keys())
            selected_id = options[selected_label]

            try:
                client = db.get_client(selected_id)
            except db.DatabaseError as e:
                st.error(str(e))
                st.stop()

            if client is None:
                # 다른 세션에서 방금 삭제됐거나 하는 등, 목록엔 있었지만 실제로는
                # 이미 없는 회원일 수 있습니다. 이 경우 화면이 깨지지 않도록 방어합니다.
                st.warning("선택하신 회원 정보를 찾을 수 없습니다. 목록이 방금 바뀌었을 수 있어요. 새로고침 후 다시 시도해주세요.")
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
                            client_id=selected_id,
                            name=name.strip(),
                            gender=gender,
                            birth_date=parsed_birth_date,
                            address=address,
                            phone=parsed_phone,
                            welfare_type=welfare_type,
                            note=note,
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


# ----------------------------------------------------------------------
# 3) 회원 통계 - 일/월/년별 표
# ----------------------------------------------------------------------
elif menu == "회원 통계":
    st.subheader("회원 통계")

    try:
        df = db.get_all_clients()
    except db.DatabaseError as e:
        st.error(str(e))
        st.stop()

    if df.empty:
        st.info("등록된 회원이 없습니다.")
    else:
        summary = stats.build_summary(df)
        st.markdown(
            f"**전체 회원수 : {summary['total']}명**"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"오늘 신규가입 : {summary['today']}명"
            f"&nbsp;&nbsp;/&nbsp;&nbsp;"
            f"이번 달 신규가입 : {summary['this_month']}명"
        )
        st.divider()

        tab_daily, tab_monthly, tab_yearly = st.tabs(["일별", "월별", "년별"])

        with tab_daily:
            st.caption("등록일 기준, 하루 단위로 신규가입·성별·구분을 집계합니다.")
            daily_df = stats.build_period_breakdown(df, "일")
            if daily_df.empty:
                st.info("표시할 데이터가 없습니다.")
            else:
                st.dataframe(daily_df, use_container_width=True, hide_index=True)

        with tab_monthly:
            st.caption("등록일 기준, 월 단위로 신규가입·성별·구분을 집계합니다.")
            monthly_df = stats.build_period_breakdown(df, "월")
            if monthly_df.empty:
                st.info("표시할 데이터가 없습니다.")
            else:
                st.dataframe(monthly_df, use_container_width=True, hide_index=True)

        with tab_yearly:
            st.caption("등록일 기준, 연 단위로 신규가입·성별·구분을 집계합니다.")
            yearly_df = stats.build_period_breakdown(df, "년")
            if yearly_df.empty:
                st.info("표시할 데이터가 없습니다.")
            else:
                st.dataframe(yearly_df, use_container_width=True, hide_index=True)