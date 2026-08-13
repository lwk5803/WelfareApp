-- 회원 사진 (외부 테스트 피드백 #8 - 서류 작성용 사진 촬영)
-- 별도 파일 저장소(Storage) 없이, 리사이즈된 JPEG를 base64 텍스트로 DB에 바로
-- 저장합니다. 이 앱 규모(직원 몇 명, 회원 수백 명)에서는 이 방식이 가장 단순하고,
-- 민감한 개인 사진을 별도 공개 URL 없이 기존 DB 접근 권한 그대로 보호할 수 있습니다.
alter table clients add column if not exists photo_data text;
