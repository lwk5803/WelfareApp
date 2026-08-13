import datetime

import extra_streamlit_components as stx
import streamlit as st
import pandas as pd
import requests

import excel_import

API_BASE = "http://localhost:8000/api"
REFRESH_COOKIE = "welfare_refresh_token"

st.set_page_config(page_title="복지관 회원 관리 (통합 시스템)", page_icon="🤝", layout="wide")


# CookieManager는 내부적으로 위젯처럼 동작해서 st.cache_resource로 감싸면 안 됩니다
# (감싸면 "CachedWidgetWarning" 오류가 남) - 매 스크립트 실행마다 새로 만들되,
# key를 고정해두면 브라우저 쪽 컴포넌트 상태는 그대로 유지됩니다.
cookie_manager = stx.CookieManager(key="cookie_manager")

# ====================================================================
# 로그인
# ====================================================================
# 로그인 성공 시 브라우저 쿠키에 refresh_token을 저장해둡니다 - 새로고침(F5)하거나
# 브라우저를 껐다 켜도(최대 30일) 비밀번호를 다시 입력하지 않고 자동으로 로그인이
# 이어집니다. access_token 자체는 세션에만 두고(1시간 정도만 유효), 만료되면
# 이 refresh_token으로 새 access_token을 조용히 발급받습니다.
# 계정은 Supabase 대시보드 > Authentication > Users에서 만들고, 관리자로 지정하려면
# SQL Editor에서 profiles 테이블의 role을 'admin'으로 바꿔주세요.
# CookieManager는 브라우저(JS)에서 쿠키 값을 읽어와 파이썬에 전달하기까지 한 번의
# 왕복이 필요합니다. 그래서 페이지를 새로 열면 첫 실행에서는 아직 쿠키 값이 안 와있을
# 수 있는데(get()이 None), "한 번 해보고 안 되면 끝" 식으로 짜면 그 왕복이 끝나기 전에
# 포기하게 됩니다. 그래서 "auth"가 없는 동안은(=로그인 안 된 동안은) 매 실행마다
# 다시 확인합니다 - 쿠키가 없으면 결국 로그인 화면이 그대로 보일 뿐이라 안전합니다.
#
# 쿠키를 저장(cookie_manager.set)한 직후에 st.rerun()으로 바로 화면을 갈아치우면,
# 브라우저가 그 쿠키 저장 스크립트를 실행할 틈도 없이 페이지가 다시 그려질 수 있습니다.
# 그래서 로그인 성공 시에는 rerun을 강제로 부르지 않고, 그냥 스크립트가 끝까지
# 이어지도록 둡니다 - 아래 st.stop()이 "auth가 없을 때만" 실행되므로, 로그인 직후에는
# 자연스럽게 이 스크립트 실행 안에서 바로 메인 화면까지 이어져서 그려집니다.
if "auth" not in st.session_state:
    saved_refresh_token = cookie_manager.get(REFRESH_COOKIE)
    if saved_refresh_token:
        res = requests.post(f"{API_BASE}/auth/refresh", json={"refresh_token": saved_refresh_token})
        if res.status_code == 200:
            data = res.json()
            st.session_state["auth"] = data
            cookie_manager.set(
                REFRESH_COOKIE, data["refresh_token"], key="auto_refresh_set",
                expires_at=datetime.datetime.now() + datetime.timedelta(days=30),
            )

if "auth" not in st.session_state:
    st.title("복지관 회원 관리")
    st.subheader("로그인")
    with st.form("login_form"):
        login_email = st.text_input("이메일")
        login_password = st.text_input("비밀번호", type="password")
        login_submitted = st.form_submit_button("로그인")

    if login_submitted:
        res = requests.post(f"{API_BASE}/auth/login", json={"email": login_email, "password": login_password})
        if res.status_code == 200:
            data = res.json()
            st.session_state["auth"] = data
            cookie_manager.set(
                REFRESH_COOKIE, data["refresh_token"], key="login_set",
                expires_at=datetime.datetime.now() + datetime.timedelta(days=30),
            )
        else:
            st.error(res.json().get("detail", "로그인에 실패했습니다."))

    if "auth" not in st.session_state:
        st.stop()

AUTH_HEADERS = {"Authorization": f"Bearer {st.session_state['auth']['access_token']}"}
IS_ADMIN = st.session_state["auth"]["role"] == "admin"

st.sidebar.caption(f"👤 {st.session_state['auth']['email']} ({'관리자' if IS_ADMIN else '직원'})")
if st.sidebar.button("로그아웃"):
    cookie_manager.delete(REFRESH_COOKIE, key="logout_delete")
    del st.session_state["auth"]
    st.rerun()

st.title("복지관 회원 관리")
st.caption("🚀 모든 비즈니스 로직과 데이터 처리는 FastAPI 백엔드 서버를 통해 안전하게 처리됩니다.")

MENU_OPTIONS = ["회원 목록", "신규 회원 등록", "회원 수정", "엑셀 일괄등록", "회원 통계", "추천 복지 서비스"]
if IS_ADMIN:
    MENU_OPTIONS.insert(3, "회원 삭제")
menu = st.sidebar.radio("메뉴", MENU_OPTIONS)

# DB 컬럼명(영어)은 그대로 두고, 화면에 보여줄 때만 한글로 바꿔주기 위한 매핑입니다.
COLUMN_LABELS = {
    "id": "내부ID",
    "member_no": "회원번호",
    "name": "성명",
    "gender": "성별",
    "birth_date": "생년월일",
    "address": "주소",
    "phone": "전화번호",
    "welfare_type": "회원 구분",
    "manager": "담당자",
    "note": "비고",
    "household_types": "가구 유형",
    "has_disability": "장애 여부",
    "disability_type": "장애 유형",
    "created_at": "등록일시",
    "consent_personal": "개인정보 동의",
    "consent_sensitive": "민감정보 동의",
    "consent_third_party": "제3자제공 동의",
    "consent_portrait": "초상권 동의",
    "consent_signed_at": "동의 확인일시",
}

HOUSEHOLD_TYPE_OPTIONS = ["독거노인", "노인부부", "조손가정", "한부모가정", "다문화가정", "장애인가구", "일반가구"]


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

                # "연번"은 DB에 저장된 값이 아니라, 지금 화면에 보이는 순서대로 매번
                # 새로 매기는 번호입니다. 그래서 회원이 삭제돼도 항상 1번부터 빈틈없이
                # 보입니다. 서류 등에 쓰는 영구 식별자는 "회원번호" 컬럼을 쓰세요.
                display_df = df.drop(columns=["id"]).rename(columns=COLUMN_LABELS)
                display_df.insert(0, "연번", range(1, len(display_df) + 1))
                st.dataframe(display_df, use_container_width=True, hide_index=True)
    except requests.exceptions.ConnectionError:
        st.error("🚨 FastAPI 서버(8000포트)가 꺼져있습니다. `uvicorn main:app --reload`를 실행해주세요.")

# ====================================================================
# 2. 신규 회원 등록
# ====================================================================
elif menu == "신규 회원 등록":
    st.subheader("신규 회원 등록")

    with st.expander("🔎 기존 등록 이력 확인 (이름 + 생년월일)"):
        st.caption("예전에 등록했다가 탈퇴한 회원인지, 이미 등록되어 있는 회원인지 확인합니다.")
        check_name = st.text_input("성명", key="check_name")
        check_birth = st.text_input("생년월일 (예: 1990-01-01)", key="check_birth")
        if st.button("조회", key="check_btn"):
            if check_name.strip():
                res = requests.post(
                    f"{API_BASE}/clients/check_duplicates",
                    json={"name": check_name.strip(), "birth_date": check_birth.strip(), "phone": ""},
                    headers=AUTH_HEADERS,
                )
                st.session_state["dup_check_results"] = handle_response(res)
            else:
                st.warning("성명을 입력해주세요.")

        dup_results = st.session_state.get("dup_check_results")
        if dup_results is not None:
            active_matches = [r for r in dup_results if not r.get("deleted_at")]
            deleted_matches = [r for r in dup_results if r.get("deleted_at")]

            if active_matches:
                for r in active_matches:
                    st.warning(f"이미 등록되어 있는 회원입니다 (회원번호: {r.get('member_no', '?')}). 중복 등록에 주의하세요.")

            for r in deleted_matches:
                st.info(
                    f"예전에 등록했던 기록이 있습니다 (회원번호: {r.get('member_no', '?')}, "
                    f"등록일: {r.get('created_at', '')[:10]}, 탈퇴일: {r.get('deleted_at', '')[:10]})"
                )
                if st.button(f"이 정보 불러오기 ({r.get('member_no', '?')})", key=f"load_{r['id']}"):
                    st.session_state["prefill_client"] = r
                    st.session_state.pop("dup_check_results", None)
                    st.rerun()

            if not dup_results:
                st.caption("일치하는 기록이 없습니다.")

    with st.expander("🔍 주소 검색"):
        addr_kw = st.text_input("지번 또는 건물명 입력", key="addr_kw_add")
        if st.button("주소 검색", key="addr_btn_add"):
            if addr_kw:
                res = requests.get(f"{API_BASE}/address/search", params={"keyword": addr_kw})
                st.session_state["addr_results_add"] = handle_response(res)

        if st.session_state.get("addr_results_add"):
            results = st.session_state["addr_results_add"]
            if not results:
                st.info("검색 결과가 없습니다. 다른 검색어로 시도해보세요 (예: 건물명, 동/읍/면 이름 등).")
            else:
                def _label(r):
                    zip_part = f" ({r['zip_code']})" if r["zip_code"] else ""
                    place_part = f"{r['place_name']} - " if r.get("place_name") else ""
                    return f"{place_part}{r['road_address']}{zip_part}"

                options = {_label(r): r["road_address"] for r in results}
                picked = st.selectbox("주소 선택", options.keys(), key="pick_add")
                if st.button("이 주소로 채우기", key="fill_add"):
                    st.session_state["prefilled_addr"] = options[picked]
                    del st.session_state["addr_results_add"]
                    st.rerun()

    prefill = st.session_state.get("prefill_client", {})
    if prefill:
        st.success(f"'{prefill.get('member_no', '?')}' 회원의 예전 정보를 불러왔습니다. 내용을 확인하고 필요한 부분만 고쳐서 등록하세요.")
        if st.button("불러온 정보 지우기"):
            st.session_state.pop("prefill_client", None)
            st.rerun()

    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("성명 *", value=prefill.get("name", ""))
        gender = st.radio("성별", ["남", "여"], horizontal=True, index=1 if prefill.get("gender") == "여" else 0)
        birth_date = st.text_input("생년월일 (예: 1990-01-01)", value=prefill.get("birth_date", ""))
        address = st.text_input("주소", value=prefill.get("address") or st.session_state.get("prefilled_addr", ""))
        phone = st.text_input("전화번호 (010-0000-0000)", value=prefill.get("phone", ""))
        welfare_type_options = ["일반", "차상위", "수급자"]
        welfare_type = st.selectbox(
            "회원 구분", welfare_type_options,
            index=welfare_type_options.index(prefill["welfare_type"]) if prefill.get("welfare_type") in welfare_type_options else 0,
        )
        household_types = st.multiselect(
            "가구 유형 (해당 사항 모두 선택)", HOUSEHOLD_TYPE_OPTIONS,
            default=[h for h in (prefill.get("household_types") or "").split(",") if h in HOUSEHOLD_TYPE_OPTIONS],
        )
        has_disability = st.radio(
            "장애 여부", ["아니오", "예"], horizontal=True,
            index=1 if prefill.get("has_disability") == "예" else 0,
        )
        disability_type = st.text_input("장애 유형/정도 (있는 경우)", value=prefill.get("disability_type", ""))
        note = st.text_area("비고", value=prefill.get("note", ""))

        st.markdown("**개인정보 수집 및 이용 동의**")
        consent_personal = st.checkbox("개인정보(성명, 생년월일, 연락처, 주소 등) 수집·이용에 동의합니다. (필수)")
        consent_sensitive = st.checkbox("건강상태 등 민감정보 수집·이용에 동의합니다. (필수)")
        consent_third_party = st.checkbox("복지서비스 연계를 위한 관계기관 제3자 제공에 동의합니다. (필수)")
        consent_portrait = st.checkbox("사진·영상 촬영 및 활용(초상권)에 동의합니다. (선택)")

        submitted = st.form_submit_button("등록하기", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("성명은 필수입니다.")
        elif not (consent_personal and consent_sensitive and consent_third_party):
            st.error("필수 동의 항목(개인정보 / 민감정보 / 제3자 제공)에 모두 동의해야 등록할 수 있습니다.")
        else:
            payload = {
                "name": name.strip(), "gender": gender, "birth_date": birth_date,
                "address": address, "phone": phone, "welfare_type": welfare_type, "note": note,
                "household_types": ",".join(household_types),
                "has_disability": has_disability,
                "disability_type": disability_type.strip() if has_disability == "예" else "",
                "consent_personal": "동의함" if consent_personal else "동의안함",
                "consent_sensitive": "동의함" if consent_sensitive else "동의안함",
                "consent_third_party": "동의함" if consent_third_party else "동의안함",
                "consent_portrait": "동의함" if consent_portrait else "동의안함",
            }
            res = requests.post(f"{API_BASE}/clients", json=payload, headers=AUTH_HEADERS)
            if res.status_code == 200:
                st.success(f"'{name}' 님을 등록했습니다.")
                st.session_state.pop("prefilled_addr", None)
                st.session_state.pop("prefill_client", None)
            else:
                st.error(res.json().get("detail"))

# ====================================================================
# 2-1. 회원 수정
# ====================================================================
elif menu == "회원 수정":
    st.subheader("회원 수정")
    try:
        res = requests.get(f"{API_BASE}/clients")
        data = handle_response(res)
        if data:
            df = pd.DataFrame(data)
            if df.empty:
                st.info("등록된 회원이 없습니다.")
            else:
                options = {f"{row.get('member_no') or row['id']} - {row['name']}": row['id'] for _, row in df.iterrows()}
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
                        e_household = st.multiselect(
                            "가구 유형 (해당 사항 모두 선택)",
                            HOUSEHOLD_TYPE_OPTIONS,
                            default=[h for h in client.get("household_types", "").split(",") if h in HOUSEHOLD_TYPE_OPTIONS],
                        )
                        e_has_disability = st.radio(
                            "장애 여부", ["아니오", "예"], horizontal=True,
                            index=1 if client.get("has_disability") == "예" else 0,
                        )
                        e_disability_type = st.text_input("장애 유형/정도 (있는 경우)", value=client.get("disability_type", ""))
                        e_note = st.text_area("비고", value=client["note"])

                        edit_sub = st.form_submit_button("수정하기", use_container_width=True)

                    if edit_sub:
                        update_payload = {
                            "name": e_name, "gender": e_gender, "birth_date": e_birth,
                            "address": e_addr, "phone": e_phone, "welfare_type": e_type, "note": e_note,
                            "household_types": ",".join(e_household),
                            "has_disability": e_has_disability,
                            "disability_type": e_disability_type.strip() if e_has_disability == "예" else "",
                        }
                        up_res = requests.put(f"{API_BASE}/clients/{selected_id}", json=update_payload, headers=AUTH_HEADERS)
                        if up_res.status_code == 200:
                            st.success("회원 정보를 수정했습니다.")
                            st.rerun()
    except Exception as e:
        st.error(f"오류 발생: {e}")

# ====================================================================
# 2-2. 회원 삭제
# ====================================================================
elif menu == "회원 삭제":
    st.subheader("회원 삭제")
    try:
        res = requests.get(f"{API_BASE}/clients")
        data = handle_response(res)
        if data:
            df = pd.DataFrame(data)
            if df.empty:
                st.info("등록된 회원이 없습니다.")
            else:
                options = {f"{row.get('member_no') or row['id']} - {row['name']}": row['id'] for _, row in df.iterrows()}
                selected_label = st.selectbox("삭제할 회원 선택", options.keys(), key="delete_select")
                selected_id = options[selected_label]

                client_res = requests.get(f"{API_BASE}/clients/{selected_id}")
                client = handle_response(client_res)
                if client:
                    st.dataframe(
                        pd.DataFrame([client]).rename(columns=COLUMN_LABELS),
                        use_container_width=True, hide_index=True,
                    )
                    st.warning("삭제하면 되돌릴 수 없습니다.")
                    if st.button("회원 삭제하기", type="primary"):
                        del_res = requests.delete(f"{API_BASE}/clients/{selected_id}", headers=AUTH_HEADERS)
                        if del_res.status_code == 200:
                            st.success("삭제되었습니다.")
                            st.rerun()
    except Exception as e:
        st.error(f"오류 발생: {e}")

# ====================================================================
# 2-3. 엑셀 일괄등록
# ====================================================================
elif menu == "엑셀 일괄등록":
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

            bulk_consent = st.checkbox(
                "업로드하는 명단에 있는 회원 전원에 대해 개인정보·민감정보 수집·이용 및 "
                "제3자 제공 동의를 이미 서면 등으로 받았음을 확인합니다. (필수)"
            )

            if st.button("일괄 등록 실행", use_container_width=True, type="primary"):
                if mapping["name"] == "(사용 안 함)":
                    st.error("성명 컬럼은 반드시 매칭해야 합니다.")
                elif not bulk_consent:
                    st.error("위 동의 확인 체크박스를 선택해야 일괄 등록을 실행할 수 있습니다.")
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
                            "consent_third_party": "동의함", "consent_portrait": "동의안함",
                        }
                        res = requests.post(f"{API_BASE}/clients", json=payload, headers=AUTH_HEADERS)
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