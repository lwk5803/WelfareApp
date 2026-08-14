-- 서명 (외부 테스트 피드백 - 태블릿/모바일에서 캔버스로 서명 받기)
-- photo_data와 같은 방식: 별도 파일 저장소 없이 base64 PNG로 DB에 바로 저장합니다.
-- 서명 여부는 별도 컬럼을 안 두고, signature_data가 채워져 있는지로 판단합니다
-- (값이 있으면 "서명함", 비어있으면 "서명 안 함") - 같은 사실을 두 컬럼에 나눠
-- 저장하면 나중에 서로 어긋날 수 있어서, 한 컬럼만 두는 게 더 안전합니다.
alter table clients add column if not exists signature_data text;
