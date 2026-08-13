-- 로그인/권한 관리 (외부 테스트 피드백 #2)
-- Supabase Auth(auth.users)는 이메일/비밀번호 로그인 자체를 대신 처리해줍니다.
-- 여기서는 "이 사용자가 일반 직원(staff)인지 관리자(admin)인지"만 별도 테이블에 저장합니다.
-- role 기준: staff = 등록/수정 가능, 삭제 불가. admin = 등록/수정/삭제 모두 가능.

create table if not exists profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text,
    role text not null default 'staff' check (role in ('staff', 'admin')),
    created_at timestamptz not null default now()
);

-- Authentication > Users에서 새 계정을 만들면(=auth.users에 새 행이 생기면) 자동으로
-- profiles에도 기본 role('staff')로 같이 만들어줍니다. 관리자로 올리려면 이후 아래처럼
-- role을 'admin'으로 직접 업데이트하면 됩니다:
--   update profiles set role = 'admin' where email = '담당자 이메일';
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, role)
  values (new.id, new.email, 'staff');
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
