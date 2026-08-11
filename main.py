from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import pandas as pd
import json

import supabase_db as db
import stats
import address_api
import welfare_search
import ai_recommend
import gov_welfare_api
import excel_import
import parsers

app = FastAPI(title="복지관 회원 관리 통합 API")

@app.on_event("startup")
def startup_event():
    db.init_db()

# --- 1. 회원 관리 (CRUD) ---
@app.get("/api/clients")
def get_clients():
    try:
        df = db.get_all_clients()
        return df.fillna("").to_dict(orient="records")
    except db.DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/clients/{client_id}")
def get_client(client_id: int):
    try:
        client = db.get_client(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
        return client
    except db.DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))

class ClientCreate(BaseModel):
    name: str
    gender: str = ""
    birth_date: str = ""
    address: str = ""
    phone: str = ""
    welfare_type: str = "일반"
    note: str = ""
    consent_personal: str = "동의함"
    consent_sensitive: str = "동의함"
    consent_third_party: str = "동의함"
    consent_portrait: str = "동의함"

@app.post("/api/clients")
def create_client(client: ClientCreate):
    try:
        data = client.dict()
        data["birth_date"], birth_ok = parsers.parse_birth_date(data["birth_date"]) if data["birth_date"] else ("", True)
        data["phone"], phone_ok = parsers.parse_phone(data["phone"]) if data["phone"] else ("", True)
        db.add_client(**data)
        warnings = []
        if not birth_ok:
            warnings.append(f"생년월일 '{data['birth_date']}'을(를) 인식하지 못해 원본 그대로 저장했습니다.")
        if not phone_ok:
            warnings.append(f"전화번호 '{data['phone']}'을(를) 인식하지 못해 원본 그대로 저장했습니다.")
        message = f"'{client.name}' 님을 등록했습니다."
        if warnings:
            message += " (" + " ".join(warnings) + ")"
        return {"message": message}
    except db.DatabaseError as e:
        raise HTTPException(status_code=400, detail=str(e))

class ClientUpdate(BaseModel):
    name: str
    gender: str = ""
    birth_date: str = ""
    address: str = ""
    phone: str = ""
    welfare_type: str = "일반"
    note: str = ""

@app.put("/api/clients/{client_id}")
def update_client(client_id: int, client: ClientUpdate):
    try:
        data = client.dict()
        data["birth_date"], birth_ok = parsers.parse_birth_date(data["birth_date"]) if data["birth_date"] else ("", True)
        data["phone"], phone_ok = parsers.parse_phone(data["phone"]) if data["phone"] else ("", True)
        db.update_client(client_id, **data)
        warnings = []
        if not birth_ok:
            warnings.append(f"생년월일 '{data['birth_date']}'을(를) 인식하지 못해 원본 그대로 저장했습니다.")
        if not phone_ok:
            warnings.append(f"전화번호 '{data['phone']}'을(를) 인식하지 못해 원본 그대로 저장했습니다.")
        message = "회원 정보를 수정했습니다."
        if warnings:
            message += " (" + " ".join(warnings) + ")"
        return {"message": message}
    except db.DatabaseError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/clients/{client_id}")
def delete_client(client_id: int):
    try:
        db.delete_client(client_id)
        return {"message": "회원 정보를 삭제했습니다."}
    except db.DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))

class DuplicateCheck(BaseModel):
    name: str
    birth_date: str
    phone: str
    exclude_id: Optional[int] = None

@app.post("/api/clients/check_duplicates")
def check_duplicates(req: DuplicateCheck):
    try:
        df = db.find_duplicates(req.name, req.birth_date, req.phone, req.exclude_id)
        return df.fillna("").to_dict(orient="records")
    except db.DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 2. 주소 및 외부 API (카카오, 공공데이터, 웹검색) ---
@app.get("/api/address/search")
def search_address(keyword: str):
    try:
        return address_api.search_road_address(keyword)
    except address_api.AddressLookupError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- 3. 통계 API ---
@app.get("/api/stats/summary")
def get_stats_summary():
    try:
        df = db.get_all_clients()
        return stats.build_summary(df)
    except db.DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/period/{period}")
def get_stats_period(period: str):
    try:
        df = db.get_all_clients()
        result_df = stats.build_period_breakdown(df, period)
        return result_df.fillna("").to_dict(orient="records")
    except db.DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 4. AI 복지 추천 및 공공복지 데이터 API ---
class WelfareRecommendRequest(BaseModel):
    client_id: int
    messages: List[Dict[str, Any]]

@app.post("/api/recommend/fetch_initial")
def fetch_initial_recommendations(client_id: int):
    """특정 회원의 조건에 맞는 중앙부처 및 지자체 복지서비스를 조회하고 초기 컨텍스트를 구성합니다."""
    try:
        client = db.get_client(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
        
        age = stats.compute_age(client["birth_date"] or "")
        gender = client["gender"]
        welfare_type = client["welfare_type"]
        address = client["address"] or ""
        note = client["note"] or ""
        # "조손가정, 손자녀(10세) 양육 중"처럼 쉼표로 여러 특이사항을 적는 경우가
        # 많아서, 첫 항목만 검색 키워드로 뽑아 씁니다 ("조손가정").
        note_keyword = note.split(",")[0].strip() if note else ""

        detail_blocks = []
        reference_lines = []
        gov_service_summary = []
        gov_data_warnings = []

        def _dedup_by_id(services: list[dict]) -> list[dict]:
            seen, result = set(), []
            for s in services:
                if s["servId"] not in seen:
                    seen.add(s["servId"])
                    result.append(s)
            return result

        # 중앙부처 서비스 조회. 나이/회원구분 기본 조건 + (있다면) 비고 키워드로
        # 한 번 더 검색해서 합칩니다("독거노인", "조손가정" 등이 결과에 반영되도록).
        # 성별/생애주기가 명백히 안 맞는 건 제외하고, 특수 신분이 필요한 서비스는
        # general/special로 코드에서 미리 분류해 LLM이 다시 틀리지 않게 합니다.
        try:
            nat_list = gov_welfare_api.fetch_welfare_list(age=age, welfare_type=welfare_type, num_of_rows=20)
            if note_keyword:
                nat_list += gov_welfare_api.fetch_welfare_list(
                    age=age, welfare_type=welfare_type, search_word=note_keyword, num_of_rows=10
                )
            nat_general, nat_special = gov_welfare_api.split_general_and_special(
                _dedup_by_id(nat_list), age=age, gender=gender
            )
            for s in nat_general[:5]:
                d = gov_welfare_api.fetch_welfare_detail(s["servId"])
                link = s.get("servDtlLink", "")
                detail_blocks.append(
                    f"[중앙부처] {d['servNm']}\n개요: {d['outline']}\n신청방법: {d['apply_methods']}\n"
                    f"주관기관: {d['jurMnofNm']}\n출처링크: {link or '(링크 없음)'}"
                )
                gov_service_summary.append({"서비스명": d["servNm"], "구분": "전국민 대상", "주관기관": d["jurMnofNm"]})
            for s in nat_special[:5]:
                reference_lines.append(f"{s['servNm']} - {s['_special_reason']} 자격이 있는 경우에만 해당")
        except gov_welfare_api.GovWelfareError as e:
            gov_data_warnings.append(f"중앙부처 복지서비스 조회 실패: {e}")
        except Exception as e:
            gov_data_warnings.append(f"중앙부처 복지서비스 조회 중 예상치 못한 오류가 발생했습니다: {e}")

        # 지자체 서비스 조회 (기본 + 비고 키워드)
        ctpv_nm, sgg_nm = welfare_search.extract_ctpv_sgg(address)
        try:
            loc_list = gov_welfare_api.fetch_local_welfare_list(
                ctpv_nm=ctpv_nm, sgg_nm=sgg_nm, welfare_type=welfare_type, num_of_rows=20
            )
            if note_keyword:
                loc_list += gov_welfare_api.fetch_local_welfare_list(
                    ctpv_nm=ctpv_nm, sgg_nm=sgg_nm, welfare_type=welfare_type,
                    search_word=note_keyword, num_of_rows=10,
                )
            loc_general, loc_special = gov_welfare_api.split_general_and_special(
                _dedup_by_id(loc_list), age=age, gender=gender
            )
            for s in loc_general[:5]:
                d = gov_welfare_api.fetch_local_welfare_detail(s["servId"])
                link = s.get("servDtlLink", "")
                detail_blocks.append(
                    f"[지자체({ctpv_nm} {sgg_nm})] {d['servNm']}\n개요: {d['outline']}\n신청방법: {d['apply_methods']}\n"
                    f"주관기관: {d['jurMnofNm']}\n출처링크: {link or '(링크 없음)'}"
                )
                gov_service_summary.append({"서비스명": d["servNm"], "구분": f"지자체({ctpv_nm} {sgg_nm}) 대상", "주관기관": d["jurMnofNm"]})
            for s in loc_special[:5]:
                reference_lines.append(f"{s['servNm']} - {s['_special_reason']} 자격이 있는 경우에만 해당")
        except gov_welfare_api.GovWelfareError as e:
            gov_data_warnings.append(f"지자체 복지서비스 조회 실패: {e}")
        except Exception as e:
            gov_data_warnings.append(f"지자체 복지서비스 조회 중 예상치 못한 오류가 발생했습니다: {e}")

        profile_summary = (
            f"나이: {age if age is not None else '미상'}세\n"
            f"성별: {gender or '미상'}\n"
            f"회원 구분: {welfare_type or '미상'}\n"
            f"거주 지역: {welfare_search.extract_region(address)}\n"
            f"비고: {note or '없음'}"
        )

        system_prompt = ai_recommend.build_system_prompt(profile_summary)
        gov_context = "\n\n".join(detail_blocks)
        reference_context = "\n".join(f"- {line}" for line in reference_lines)
        initial_user_msg = (
            "다음은 정부 공공데이터에서 이 회원님과 관련성이 높아 보이는 서비스입니다 "
            "(성별·생애주기가 명백히 안 맞는 서비스는 이미 제외했습니다):\n\n"
            f"{gov_context or '(조건에 맞는 정부 공식 서비스를 찾지 못했습니다.)'}\n\n"
            + (
                f"다음 서비스들은 [회원 프로필]에 없는 특수 신분(장애인·국가유공자 등)이 "
                f"있어야 대상이 되어 이미 '참고' 후보로 분류해뒀습니다. 그대로 구역B에 "
                f"반영하세요(직접 판단해서 구역A로 옮기지 마세요):\n{reference_context}\n\n"
                if reference_context else ""
            )
            + "위 자료와 추가 웹 검색을 통해 이 회원님께 맞는 복지서비스를 종합적으로 찾아 정리해주세요."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_user_msg}
        ]
        
        answer, new_results, updated_messages = ai_recommend.chat_turn(messages)
        
        return {
            "answer": answer,
            "gov_services": gov_service_summary,
            "sources": new_results,
            "updated_messages": updated_messages,
            "warnings": gov_data_warnings,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recommend/chat_turn")
def recommend_chat_turn(req: WelfareRecommendRequest):
    """챗봇 대화 후속 턴을 처리합니다."""
    try:
        answer, new_results, updated_messages = ai_recommend.chat_turn(req.messages)
        return {
            "answer": answer,
            "sources": new_results,
            "updated_messages": updated_messages
        }
    except ai_recommend.AIRecommendError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))