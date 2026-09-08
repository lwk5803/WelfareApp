"""
recommend_graph.py
-------------------
복지서비스 추천의 "초안(draft) → 코드 검증(verify) → 문장화(finalize)" 단계를
LangGraph로 구성합니다. main.py가 이미 나이·성별·지역 조건으로 코드에서 걸러
fetch_welfare_detail까지 마친 "후보 목록"을 넘겨주면, 이 파일이 하는 일은 그
안에서 회원에게 맞는 걸 고르고 설명을 붙이는 것뿐입니다.

LLM은 딱 두 군데서만 자유 텍스트를 씁니다:
    1) draft  - 후보 목록 "안에서만" 골라 우선순위와 1~2문장 추천 이유를 답니다.
    2) finalize - 서비스 목록을 안내하기 직전에 붙일 짧은 도입부 한 문단만 씁니다.
서비스명·기관명·신청방법·출처링크 같은 "사실" 항목은 전부 candidates 데이터에서
코드가 그대로 꺼내 렌더링합니다 - LLM이 그 값을 다시 옮겨 적을 일이 없으므로,
자격요건 문구를 지어내거나 링크를 잘못 옮기는 종류의 할루시네이션이 애초에
발생할 자리가 없습니다.

draft가 후보 목록에 없는 servId를 지어내면 verify가 코드로 걸러내고, 그 이유를
draft에게 알려줘 최대 2번까지 다시 고르게 합니다(무한루프 방지).
"""
import json
from typing import TypedDict

from langgraph.graph import END, StateGraph

import ai_recommend

MAX_RETRIES = 2
MAX_ITEMS = 5


class RecommendState(TypedDict):
    candidates: list
    profile_summary: str
    draft_items: list
    verified: list
    rejected: list
    retry_count: int
    feedback: str
    intro: str
    draft_error: str


def _candidates_block(candidates: list) -> str:
    lines = [
        f"- servId: {c['servId']} | 서비스명: {c['servNm']} | 범위: {c['scope']}\n"
        f"  개요: {(c['outline'] or '')[:200]}"
        for c in candidates
    ]
    return "\n".join(lines) or "(후보 없음)"


def _draft_node(state: RecommendState) -> dict:
    candidates = state["candidates"]
    if not candidates:
        return {"draft_items": [], "retry_count": state.get("retry_count", 0) + 1}

    client, model = ai_recommend.get_client()
    prompt = f"""당신은 사회복지사의 업무를 돕는 보조 도우미입니다.
아래는 회원 프로필과, 이미 나이·성별·지역 조건으로 코드가 걸러낸 복지서비스 후보
목록입니다. 이 목록 "안에서만" 회원에게 실제로 도움이 될 서비스를 최대 {MAX_ITEMS}개
골라 우선순위(1이 가장 우선)를 매기고, 왜 이 회원에게 맞는지 1~2문장으로 설명하세요.

[회원 프로필]
{state['profile_summary']}

[후보 목록 - 아래 servId에 없는 서비스는 절대 언급하지 마세요]
{_candidates_block(candidates)}

{state.get('feedback', '')}

반드시 아래 JSON 형식으로만 답하세요 (다른 설명 텍스트 없이):
{{"items": [{{"servId": "위 목록의 servId 중 하나 그대로", "priority": 1, "reason": "회원에게 맞는 이유 1~2문장"}}]}}
servId는 위 목록에 실제로 있는 값과 정확히 같아야 합니다. 맞는 후보가 없으면 "items": []로 답하세요.
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        items = parsed.get("items", [])
        if not isinstance(items, list):
            items = []
        draft_error = ""
    except Exception as e:
        # API 호출 실패(모델이 지원 안 하는 파라미터, 네트워크 오류 등)나 JSON 파싱 실패입니다.
        # 이번 시도는 빈 결과로 넘어가되, 오류 내용을 기록해뒀다가 끝까지 아무 것도 검증되지
        # 않으면 화면에 경고로 보여줍니다 - 예전에 이 부분을 그냥 삼키기만 했더니 "조건에 맞는
        # 서비스를 못 찾았다"는 문구만 나오고 실제로는 API 호출 자체가 실패했던 걸 못 알아챈
        # 적이 있어서, 이후엔 반드시 원인을 남기도록 고쳤습니다.
        items = []
        draft_error = f"{type(e).__name__}: {e}"

    # draft_error는 "가장 최근 시도"의 결과만 담습니다(이전 시도의 실패를 계속 이어붙이면,
    # 재시도가 이번엔 성공했는데도 _should_retry가 옛날 실패 기록 때문에 불필요하게 한 번 더
    # 재시도하게 되는 버그가 있었습니다). 최종적으로 하나도 통과 못 했을 때 보여줄 원인은
    # 어차피 "마지막 시도가 왜 실패했는지"가 가장 유의미합니다.
    return {
        "draft_items": items,
        "retry_count": state.get("retry_count", 0) + 1,
        "draft_error": draft_error,
    }


def _verify_node(state: RecommendState) -> dict:
    """
    draft가 고른 항목을 실제 후보 데이터와 대조합니다: 존재하지 않는 servId를
    지어내지 않았는지, 같은 서비스를 중복으로 고르지 않았는지, 추천 이유를 비워두지
    않았는지 확인합니다. 이전 시도에서 이미 통과한 항목은 재시도 중에도 유지합니다
    (재시도할 때 LLM이 그 항목을 다시 언급하지 않아도 사라지지 않도록).
    """
    candidates_by_id = {c["servId"]: c for c in state["candidates"]}
    new_verified, rejected, seen = [], [], set()

    for item in state.get("draft_items", []):
        serv_id = str(item.get("servId", "")).strip()
        reason = str(item.get("reason", "")).strip()

        if not serv_id or serv_id not in candidates_by_id:
            rejected.append({"servId": serv_id or "(없음)", "reason": "후보 목록에 없는 servId를 사용했습니다."})
            continue
        if serv_id in seen:
            rejected.append({"servId": serv_id, "reason": "같은 servId를 중복으로 골랐습니다."})
            continue
        if not reason:
            rejected.append({"servId": serv_id, "reason": "추천 이유가 비어 있습니다."})
            continue

        seen.add(serv_id)
        new_verified.append({**candidates_by_id[serv_id], "reason": reason, "priority": item.get("priority", 99)})

    merged = {v["servId"]: v for v in state.get("verified", [])}
    for v in new_verified:
        merged[v["servId"]] = v
    verified = sorted(merged.values(), key=lambda v: v.get("priority", 99))[:MAX_ITEMS]

    return {"verified": verified, "rejected": rejected}


def _should_retry(state: RecommendState) -> str:
    if len(state.get("verified", [])) >= MAX_ITEMS:
        return "finalize"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "finalize"
    # 거부된 항목이 있었거나(잘못 골랐음), draft_error가 있으면(API 호출 자체가
    # 실패했음 - 일시적 네트워크 오류일 수 있음) 재시도합니다. 둘 다 없다면
    # (예: 처음부터 맞는 후보가 없어 items:[]로 정상 응답한 경우) 재시도할 이유가
    # 없으므로 바로 finalize로 넘어갑니다.
    if state.get("rejected") or state.get("draft_error"):
        return "retry"
    return "finalize"


def _prepare_retry_node(state: RecommendState) -> dict:
    kept = ", ".join(v["servId"] for v in state.get("verified", [])) or "(없음)"
    rejected = state.get("rejected") or []
    if rejected:
        failed_block = (
            "[아래 항목은 거부되었습니다 - 같은 실수를 반복하지 말고, 필요하면 다른 후보로 교체하세요]\n"
            + "\n".join(f"- servId {r['servId']}: {r['reason']}" for r in rejected)
        )
    else:
        # rejected는 없는데 재시도로 왔다면 draft_error 때문입니다(API 호출 실패 등).
        failed_block = "[이전 시도에서 응답을 받지 못했습니다 - 다시 한 번 시도해주세요]"
    feedback = (
        f"[이미 통과해서 유지 중인 servId: {kept} - 이 항목들은 다시 고르지 않아도 됩니다]\n"
        f"{failed_block}"
    )
    return {"feedback": feedback}


def _finalize_node(state: RecommendState) -> dict:
    verified = state["verified"]
    if not verified:
        return {"intro": ""}

    client, model = ai_recommend.get_client()
    names = ", ".join(v["servNm"] for v in verified)
    prompt = f"""아래 복지서비스들을 회원에게 안내하기 직전에 붙일, 자연스러운 도입부
1~2문장만 한국어로 작성하세요. 서비스 이름을 나열하거나 다시 설명하지 말고,
회원 프로필을 참고해서 왜 이런 서비스들을 골랐는지 짧게 짚어주는 톤으로 쓰세요.

[회원 프로필]
{state['profile_summary']}

[안내할 서비스] {names}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        intro = (response.choices[0].message.content or "").strip()
    except Exception:
        intro = ""
    return {"intro": intro}


def _build_graph():
    graph = StateGraph(RecommendState)
    graph.add_node("draft", _draft_node)
    graph.add_node("verify", _verify_node)
    graph.add_node("prepare_retry", _prepare_retry_node)
    graph.add_node("finalize", _finalize_node)

    graph.set_entry_point("draft")
    graph.add_edge("draft", "verify")
    graph.add_conditional_edges("verify", _should_retry, {"retry": "prepare_retry", "finalize": "finalize"})
    graph.add_edge("prepare_retry", "draft")
    graph.add_edge("finalize", END)
    return graph.compile()


_GRAPH = _build_graph()


def _render_service_block(v: dict, index: int) -> str:
    """
    사실 항목(서비스 설명·신청방법·문의처·출처링크)은 전부 candidates 데이터에서
    코드가 그대로 꺼내 씁니다. "이 서비스는" 한 줄을 추가한 건, 사할린동포 지원처럼
    처음 들어보는 서비스명만으로는 뭔지 알기 어렵다는 피드백을 반영한 것입니다.
    """
    apply_methods = v.get("apply_methods") or []
    apply_text = "; ".join(apply_methods) if apply_methods else "확인 필요"
    outline = (v.get("outline") or "").strip()
    contact = (v.get("contact") or "").strip()
    link_text = f" ([자세히 보기]({v['link']}))" if v.get("link") else ""
    lines = [f"{index}. {v['servNm']} ({v['scope']})"]
    if outline:
        lines.append(f"   - 이 서비스는: {outline[:150]}")
    lines.append(f"   - 추천 이유: {v['reason']}")
    lines.append(f"   - 신청방법: {apply_text}")
    lines.append(f"   - 문의처: {contact or '확인 필요'}")
    lines.append(f"   - 출처: {v['jurMnofNm'] or '확인 필요'}{link_text}")
    return "\n".join(lines)


def run_recommendation(candidates: list, profile_summary: str, reference_lines: list[str]) -> dict:
    """
    candidates: 코드가 이미 나이/성별/지역 조건까지 걸러 상세정보(fetch_welfare_detail 등)까지
    받아온 "일반" 서비스 후보 목록 (main.py가 만들어 넘겨줍니다).
    reference_lines: [회원 프로필]에 없는 특수 자격이 필요해 "참고"로만 다루는 서비스
    한 줄 요약 목록 - 이미 코드가 만든 것이라 LLM 없이 그대로 렌더링합니다.

    반환값: {"answer": 최종 답변 텍스트(마크다운), "verified": 실제로 안내된 서비스 목록,
             "warnings": LLM 호출이 실패해 결과에 영향을 줬다면 그 내용}
    """
    if candidates:
        final_state = _GRAPH.invoke({
            "candidates": candidates,
            "profile_summary": profile_summary,
            "draft_items": [],
            "verified": [],
            "rejected": [],
            "retry_count": 0,
            "feedback": "",
            "intro": "",
            "draft_error": "",
        })
    else:
        final_state = {"verified": [], "intro": "", "draft_error": ""}

    verified = final_state.get("verified", [])
    intro = final_state.get("intro", "")
    warnings = []

    parts = ["## 회원님께 맞는 복지서비스"]
    if verified:
        if intro:
            parts.append(intro)
        parts.extend(_render_service_block(v, i) for i, v in enumerate(verified, start=1))
    else:
        parts.append("조건에 맞는 정부 공식 서비스를 찾지 못했습니다.")
        # 후보는 있었는데 하나도 통과하지 못했다면, 정말 다 안 맞아서인지 LLM 호출
        # 자체가 실패한 건지 구분할 수 있도록 원인을 남깁니다.
        if candidates and final_state.get("draft_error"):
            warnings.append(f"복지서비스 추천 생성 중 오류가 있어 결과가 비어있을 수 있습니다: {final_state['draft_error']}")

    if reference_lines:
        parts.append("## 참고: 조건부 서비스 (자격 확인 필요)")
        parts.extend(f"- {line}" for line in reference_lines)

    parts.append("정확한 자격 요건은 반드시 해당 기관에 재확인이 필요합니다.")

    return {"answer": "\n\n".join(parts), "verified": verified, "warnings": warnings}
