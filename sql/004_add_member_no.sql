-- 회원번호 (예: "2026-0001") 자동 부여
-- 화면에 보이는 목록의 "연번"(1, 2, 3...)은 저장할 필요 없이 화면에서 매번 계산하면
-- 되므로 DB 변경이 필요 없습니다 (app_frontend.py에서 처리). 여기서는 서류/출력물에
-- 찍힐 "영구 회원번호"만 다룹니다 - 한 번 부여되면 그 회원을 삭제해도 재사용하지 않습니다.

alter table clients add column if not exists member_no text unique;

-- 등록 시 회원번호가 비어있으면(=신규 등록이면) "등록연도-4자리일련번호" 형식으로
-- 자동으로 채워주는 트리거입니다. 일련번호는 그 해에 지금까지 부여된 가장 큰 번호에 1을
-- 더한 값이라, 중간에 회원이 삭제돼도 이미 나간 번호를 다시 쓰지 않습니다.
create or replace function public.set_member_no()
returns trigger as $$
declare
  yr text := to_char(now(), 'YYYY');
  next_seq int;
begin
  if new.member_no is null then
    select coalesce(max(substring(member_no from 6)::int), 0) + 1
      into next_seq
      from clients
      where member_no like yr || '-%';
    new.member_no := yr || '-' || lpad(next_seq::text, 4, '0');
  end if;
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_set_member_no on clients;
create trigger trg_set_member_no
  before insert on clients
  for each row execute procedure public.set_member_no();

-- 이미 등록된 기존 회원들에게도 소급 적용: created_at 순서대로 회원번호를 매깁니다.
with numbered as (
  select id, extract(year from created_at)::text as yr,
         row_number() over (partition by extract(year from created_at) order by created_at) as rn
  from clients
  where member_no is null
)
update clients c
set member_no = numbered.yr || '-' || lpad(numbered.rn::text, 4, '0')
from numbered
where c.id = numbered.id;
