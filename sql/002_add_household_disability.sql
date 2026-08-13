-- 회원 등록 정보 세분화 (외부 테스트 피드백 #3)
-- household_types: 가구 유형/대상자 구분. 한 사람이 여러 유형에 해당할 수 있어(예: 독거노인이면서
--   장애인가구) 콤마로 구분된 여러 값을 저장합니다. 예: "독거노인,장애인가구"
--   허용 값: 독거노인 / 노인부부 / 조손가정 / 한부모가정 / 다문화가정 / 장애인가구 / 일반가구
-- has_disability: 장애 여부. "예" 또는 "아니오".
-- disability_type: 장애 유형/정도를 자유 텍스트로 기록 (등급제 폐지 이후 공식 등급이 없어
--   자유 입력이 현실적입니다). has_disability가 "아니오"면 보통 빈 문자열입니다.

alter table clients
    add column if not exists household_types text not null default '',
    add column if not exists has_disability text not null default '아니오',
    add column if not exists disability_type text not null default '';
