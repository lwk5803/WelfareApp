-- 정보 수정 시각 기록 (등록 후 1년 넘게 정보가 갱신 안 된 회원을 화면에서 안내하기 위함)
-- created_at은 "처음 등록한 날"만 나타내서, 중간에 정보를 고친 적이 있어도 알 수가 없었습니다.
-- 이 컬럼을 새로 추가해서, 등록 시에는 created_at과 같은 값으로 채워두고 수정할 때마다
-- 현재 시각으로 갱신합니다 - "정보 갱신 필요" 판단 기준을 created_at 대신 이 값(없으면
-- created_at)으로 삼습니다.
alter table clients add column if not exists updated_at timestamptz;
update clients set updated_at = created_at where updated_at is null;
