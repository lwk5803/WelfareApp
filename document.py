"""
document.py
------------
회원 등록 서류를 인쇄용 HTML로 만듭니다. PDF 라이브러리를 새로 설치하지 않고,
직원이 다운받은 HTML 파일을 브라우저에서 열어 인쇄(Ctrl+P) → "PDF로 저장"을
누르면 그대로 종이 서류/PDF가 됩니다.
"""
from jinja2 import Template

_TEMPLATE = Template("""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{{ client.name }} 회원등록서류</title>
<style>
  body { font-family: "맑은 고딕", "Malgun Gothic", sans-serif; padding: 40px; color: #222; }
  h1 { text-align: center; font-size: 22px; margin-bottom: 30px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
  td, th { border: 1px solid #999; padding: 8px 10px; font-size: 14px; text-align: left; }
  th { background: #f2f2f2; width: 110px; white-space: nowrap; }
  .photo-wrap { float: right; margin-left: 16px; text-align: center; }
  .photo { width: 120px; height: 150px; object-fit: cover; border: 1px solid #999; }
  .photo-empty { width: 120px; height: 150px; border: 1px dashed #999; display: flex;
                 align-items: center; justify-content: center; color: #999; font-size: 12px; }
  .consent { margin-top: 8px; font-size: 13px; line-height: 1.9; clear: both; }
  .sign-area { margin-top: 60px; text-align: right; font-size: 14px; }
  .print-btn { margin-bottom: 20px; }
  @media print { .print-btn { display: none; } body { padding: 0; } }
</style>
</head>
<body>
  <div class="print-btn"><button onclick="window.print()">인쇄 / PDF로 저장</button></div>
  <h1>회원 등록 서류</h1>

  <div class="photo-wrap">
    {% if photo_data_uri %}
      <img class="photo" src="{{ photo_data_uri }}">
    {% else %}
      <div class="photo-empty">사진 없음</div>
    {% endif %}
  </div>

  <table>
    <tr><th>회원번호</th><td>{{ client.member_no or '-' }}</td><th>등록일</th><td>{{ (client.created_at or '')[:10] or '-' }}</td></tr>
    <tr><th>성명</th><td>{{ client.name }}</td><th>성별</th><td>{{ client.gender }}</td></tr>
    <tr><th>생년월일</th><td>{{ client.birth_date }}</td><th>전화번호</th><td>{{ client.phone }}</td></tr>
    <tr><th>주소</th><td colspan="3">{{ client.address }}</td></tr>
    <tr><th>회원 구분</th><td>{{ client.welfare_type }}</td><th>장애 여부</th>
        <td>{{ client.has_disability }}{% if client.disability_type %} ({{ client.disability_type }}){% endif %}</td></tr>
    <tr><th>가구 유형</th><td colspan="3">{{ client.household_types or '-' }}</td></tr>
    <tr><th>비고</th><td colspan="3">{{ client.note or '-' }}</td></tr>
  </table>

  <div class="consent">
    <strong>개인정보 수집 및 이용 동의 현황</strong><br>
    - 개인정보 수집·이용: {{ client.consent_personal or '-' }}<br>
    - 민감정보 수집·이용: {{ client.consent_sensitive or '-' }}<br>
    - 제3자 제공: {{ client.consent_third_party or '-' }}<br>
    - 초상권(사진·영상): {{ client.consent_portrait or '-' }}<br>
    - 동의 확인일시: {{ (client.consent_signed_at or '')[:19] or '-' }}
  </div>

  <div class="sign-area">담당자 서명: ____________________</div>
</body>
</html>
""")


def build_registration_document(client: dict) -> str:
    """회원 한 명의 정보(dict, get_client() 결과)로 인쇄용 HTML 문서를 만듭니다."""
    photo_data_uri = ""
    if client.get("photo_data"):
        photo_data_uri = f"data:image/jpeg;base64,{client['photo_data']}"
    return _TEMPLATE.render(client=client, photo_data_uri=photo_data_uri)
