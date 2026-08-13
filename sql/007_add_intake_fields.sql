-- 오프라인 "이용신청서" 서식을 온라인 등록 절차로 옮기면서 필요해진 항목들.
-- (기존 이용신청서 종이 양식 참고: 비상연락망 / 가입경로 / 질병유무 / 경력(전직업) / 상담자)

alter table clients
    add column if not exists emergency_contact_name text not null default '',
    add column if not exists emergency_contact_relation text not null default '',
    add column if not exists emergency_contact_phone text not null default '',
    add column if not exists join_route text not null default '',
    add column if not exists has_illness text not null default '없다',
    add column if not exists illness_type text not null default '',
    add column if not exists has_career text not null default '없다',
    add column if not exists career_type text not null default '',
    add column if not exists counselor text not null default '';
