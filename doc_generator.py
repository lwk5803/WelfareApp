"""
doc_generator.py
-----------------
기관 양식(.docx) 템플릿에 대상자 데이터를 자동으로 채워 넣는 함수들을 모아둔 파일입니다.

동작 원리:
    양식 워드 파일 안에 {{성명}}, {{생년월일}} 처럼 이중 중괄호로 태그를 적어두면,
    docxtpl 라이브러리가 그 자리를 실제 데이터로 바꿔서 새 문서를 만들어줍니다.
    기관마다 양식이 달라도, 태그 이름만 아래 context 딕셔너리 키와 맞으면
    코드를 전혀 고치지 않고 그대로 사용할 수 있습니다.
"""

from io import BytesIO
from docxtpl import DocxTemplate


def get_template_tags(template_bytes: BytesIO) -> set:
    """업로드된 템플릿 안에 어떤 {{태그}}들이 들어있는지 찾아서 돌려줍니다."""
    doc = DocxTemplate(template_bytes)
    return doc.get_undeclared_template_variables()


def render_document(template_bytes: BytesIO, context: dict) -> BytesIO:
    """템플릿에 context 데이터를 채워서, 완성된 문서를 메모리 안에 만들어 돌려줍니다."""
    doc = DocxTemplate(template_bytes)
    doc.render(context)

    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output


def build_context(client: dict) -> dict:
    """
    DB에서 가져온 대상자 정보(client)를, 문서 템플릿에서 쓸 수 있는
    태그 딕셔너리로 바꿔줍니다.

    한글 태그({{성명}})와 영문 태그({{name}})를 모두 지원하도록
    두 가지 이름을 다 넣어뒀습니다. 기관 양식에서 어느 쪽 태그를 써도 채워집니다.
    """
    return {
        "id": client["id"],
        "name": client["name"],
        "성명": client["name"],
        "birth_date": client["birth_date"],
        "생년월일": client["birth_date"],
        "address": client["address"],
        "주소": client["address"],
        "phone": client["phone"],
        "연락처": client["phone"],
        "welfare_type": client["welfare_type"],
        "복지유형": client["welfare_type"],
        "manager": client["manager"],
        "담당자": client["manager"],
        "note": client["note"],
        "비고": client["note"],
    }
