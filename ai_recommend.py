"""
ai_recommend.py
----------------
회원 프로필 요약과 웹 검색 결과를 바탕으로, GPT 계열 모델이 맞춤 복지서비스를
정리해주는 함수를 모아둔 파일입니다. 한 번 정리해서 끝나는 게 아니라, 후속 질문에
이어서 답하고 필요하면 스스로 추가 검색까지 하는 챗봇 구조입니다.

두 가지 방식으로 쓸 수 있습니다:
    1) OpenAI (기본값) - .streamlit/secrets.toml에 OPENAI_API_KEY 추가
    2) 로컬 모델 (Ollama) - 비용 없이 로컬 테스트용
       secrets.toml에 AI_PROVIDER = "local" 추가
       (선택) LOCAL_MODEL_NAME, LOCAL_BASE_URL로 모델/주소 변경 가능

로컬로 테스트하려면:
    ollama pull qwen3:8b
    ollama serve
그 다음 secrets.toml에 AI_PROVIDER = "local" 한 줄만 추가하면 됩니다.
"""

import json

from openai import OpenAI
import streamlit as st

import welfare_search

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_LOCAL_MODEL = "qwen3:8b"
DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"

# 검색 결과 하나당 GPT에게 넘기는 최대 글자 수입니다. 이게 없으면 검색 결과 본문이
# 길 때 대화가 순식간에 커져서, 컨텍스트 한도를 넘기거나 비용이 급격히 늘 수 있습니다.
# (로컬 모델은 VRAM이 넉넉하지 않을수록 이 값이 더 중요해집니다.)
MAX_CONTENT_CHARS = 800

SEARCH_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "복지서비스, 정책, 지원제도 등과 관련된 최신 정보를 웹에서 검색합니다. "
                "사용자가 추가 정보를 요청하거나, 지금까지의 대화에 없는 새로운 주제를 "
                "물어볼 때 사용하세요."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색할 키워드 또는 질문"}
                },
                "required": ["query"],
            },
        },
    }
]


class AIRecommendError(Exception):
    """AI 추천 생성 중 문제가 생겼을 때, 사용자에게 보여줄 친절한 메시지를 담는 예외입니다."""
    pass


def _get_provider() -> str:
    """
    "openai" 또는 "local" 중 어떤 걸 쓸지 결정합니다.
    secrets.toml에 AI_PROVIDER를 안 적어두면 기본값은 "openai"입니다.
    """
    try:
        provider = st.secrets.get("AI_PROVIDER")
    except FileNotFoundError:
        provider = None
    return (provider or "openai").strip().lower()


def get_client() -> tuple[OpenAI, str]:
    """
    설정(AI_PROVIDER)에 맞는 클라이언트와, 그 설정에서 쓸 모델 이름을 함께 돌려줍니다.

    - "openai"(기본값): OPENAI_API_KEY 필요, 유료 API
    - "local": Ollama 등 OpenAI 호환 로컬 서버 필요, 무료
    """
    provider = _get_provider()

    if provider == "local":
        try:
            model_name = st.secrets.get("LOCAL_MODEL_NAME")
        except FileNotFoundError:
            model_name = None
        try:
            base_url = st.secrets.get("LOCAL_BASE_URL")
        except FileNotFoundError:
            base_url = None

        # Ollama는 api_key 값을 실제로 검사하지 않지만, OpenAI 클라이언트 라이브러리는
        # 빈 값을 안 받아줘서 의미 없는 문자열("ollama")을 그냥 채워 넣습니다.
        client = OpenAI(base_url=base_url or DEFAULT_LOCAL_BASE_URL, api_key="ollama")
        return client, (model_name or DEFAULT_LOCAL_MODEL)

    # provider == "openai" (기본값)
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except FileNotFoundError:
        api_key = None

    if not api_key:
        raise AIRecommendError(
            "OpenAI API 키가 설정되지 않았습니다. .streamlit/secrets.toml에 "
            "OPENAI_API_KEY를 추가해주세요. (로컬 모델로 테스트하려면 대신 "
            "AI_PROVIDER = \"local\"을 추가하세요.)"
        )
    return OpenAI(api_key=api_key), DEFAULT_OPENAI_MODEL


def build_system_prompt(profile_summary: str) -> str:
    """대화 맨 앞에 한 번만 들어가는, AI의 역할과 회원 프로필을 알려주는 지침입니다."""
    return f"""당신은 사회복지사의 업무를 돕는 보조 도우미입니다.
아래는 지금 상담 중인 회원의 프로필입니다. 이 정보를 참고해서 답변하세요.

[회원 프로필]
{profile_summary}

답변 규칙:
- 복지서비스의 자격요건, 신청방법 등 최신 정보가 필요하면 반드시 search_web
  도구로 검색한 뒤, 그 결과에 실제로 있는 내용만 근거로 답변하세요. 검색 없이
  아는 척 지어내지 마세요.
- **지역 검증(중요)**: 각 서비스가 아래 중 어디에 해당하는지 반드시 확인하세요.
  1) 전국민 대상(중앙부처) 서비스 - 거주 지역과 무관하게 안내 가능
  2) [회원 프로필]의 "거주 지역"과 정확히 일치하는 지자체(시/도, 시/군/구)의 서비스
  [회원 프로필]의 거주 지역과 **다른** 지자체의 서비스는 절대 안내하지 마세요
  (예: 회원이 "서울특별시 강남구"인데 검색 자료가 "부산광역시" 사업이면 제외).
  검색 자료만으로 그 서비스가 전국 대상인지 특정 지역 대상인지 판단할 수 없으면,
  안내는 하되 "지역 해당 여부 확인 필요"라고 표시하세요.
- **성별 검증(중요)**: [회원 프로필]의 "성별"과 명백히 맞지 않는 서비스는 절대 안내하지
  마세요 (예: 성별이 "남"인 회원에게 임신·출산·산모 관련 서비스, 또는 그 반대의
  경우를 추천하지 마세요). 검색 자료에 그런 서비스가 있어도 언급하지 마세요.
<<<<<<< HEAD
- **자격요건 대조(중요)**: 각 서비스의 "지원대상"·"선정기준"을 [회원 프로필]과 실제로
  하나씩 비교하세요. 특정 질병, 특정 출신/국적, 특정 학력·재학 상태 등 [회원 프로필]에
  없는 특수 조건을 요구하는 서비스는, 회원이 그 조건에 해당한다는 근거가 없으면
  추천 목록에서 제외하거나 "해당 여부 확인 필요"라고 분명히 표시하세요. 단순히 검색
  자료에 포함되어 있다는 이유만으로 나열하지 마세요.
- **나이 조건 확인(중요)**: 서비스에 "65세 이상", "만 18세 미만" 등 나이 조건이 있으면,
  [회원 프로필]의 "나이"가 그 조건을 실제로 충족하는지 반드시 확인하세요. 충족하지
  않으면 그 서비스는 절대 추천하지 마세요 (예: 41세 회원에게 "65세 이상" 대상
  노인 서비스를 추천하지 마세요).
- **이미 보유한 자격 재추천 금지(중요)**: [회원 프로필]의 "회원 구분"이 이미
  "수급자"라면, 그 자체가 이미 국민기초생활보장제도 대상자라는 뜻입니다. "기초생활
  보장제도", "수급자 지정" 같이 이미 확정된 자격 자체를 새로운 추천으로 안내하지
  마세요. "차상위"인 경우도 마찬가지로, 이미 그 자격을 갖추고 있다는 전제 하에,
  그 자격으로 "추가로" 받을 수 있는 다른 서비스만 안내하세요.
=======
>>>>>>> 67b0a7c47b78cc77f311af5fc21155672fdd4bff
- 서비스를 안내할 때는 "서비스명 (전국 대상 / 지역: OO) / 자격요건 / 신청방법 / 출처"
  형식으로, 전국 대상인지 특정 지역 대상인지를 서비스명 옆에 꼭 표시하세요.
- 검색 자료로도 확실하지 않은 내용은 "확인 필요"라고 표시하세요.
- 답변 끝에는 "정확한 자격 요건은 반드시 해당 기관에 재확인이 필요합니다"라는
  문구를 꼭 포함하세요.
- 전체 한국어로, 사회복지사가 회원에게 바로 설명해줄 수 있을 정도로 간결하고
  이해하기 쉽게 작성하세요.
"""


def chat_turn(messages: list[dict], max_tool_rounds: int = 3) -> tuple[str, list[dict], list[dict]]:
    """
    대화 한 턴을 처리합니다. GPT가 필요하다고 판단하면 search_web 도구를
    최대 max_tool_rounds번까지 스스로 반복 호출한 뒤, 최종 답변을 만듭니다.

    messages: 지금까지의 전체 대화 (system, user, assistant, tool 메시지 포함)
    반환값: (최종 답변 텍스트, 이번 턴에서 새로 검색된 자료 목록, 갱신된 전체 대화)
    """
    client, model_name = get_client()
    working_messages = list(messages)
    all_search_results = []

    for _ in range(max_tool_rounds):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=working_messages,
                tools=SEARCH_TOOL,
                temperature=0.3,
            )
        except Exception as e:
            raise AIRecommendError(f"AI 응답 생성 중 오류가 발생했습니다: {e}") from e

        message = response.choices[0].message

        if not message.tool_calls:
            # 아주 드물지만 GPT가 빈 응답(None)을 줄 수 있습니다. None인 채로 화면에
            # st.markdown(None)을 넘기면 에러가 나므로, 안전한 문구로 대체합니다.
            answer = message.content or "(응답을 생성하지 못했습니다. 다시 시도해주세요.)"
            working_messages.append({"role": "assistant", "content": answer})
            return answer, all_search_results, working_messages

        working_messages.append(message.model_dump(exclude_none=True))

        for tool_call in message.tool_calls:
            if tool_call.function.name == "search_web":
                try:
                    args = json.loads(tool_call.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                query = args.get("query", "")

                try:
                    results = welfare_search.search_web(query, max_results=4) if query else []
                except welfare_search.WelfareSearchError:
                    results = []

                all_search_results.extend(results)

                tool_content = "\n\n".join(
                    f"[{r['title']}]({r['url']})\n{r['content'][:MAX_CONTENT_CHARS]}" for r in results
                ) or "(검색 결과가 없습니다.)"
            else:
                tool_content = "(지원하지 않는 도구입니다.)"

            working_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_content,
            })

    try:
        final_response = client.chat.completions.create(
            model=model_name, messages=working_messages, temperature=0.3,
        )
    except Exception as e:
        raise AIRecommendError(f"AI 응답 생성 중 오류가 발생했습니다: {e}") from e

    final_answer = final_response.choices[0].message.content or "(응답을 생성하지 못했습니다. 다시 시도해주세요.)"
    return final_answer, all_search_results, working_messages + [
        {"role": "assistant", "content": final_answer}
    ]