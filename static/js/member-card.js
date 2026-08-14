/*
 * member-card.js
 * ---------------
 * 회원 한 명을 카드로 보여줄 때 쓰는 공용 조각들입니다. 회원 목록 화면(members-list.js)과
 * 회원 선택 위젯(member-search.js)이 똑같은 카드 모양을 쓰도록 여기 한 곳에 모아뒀습니다 -
 * "같은 정보인데 화면마다 다르게 보이는" 문제를 피하기 위함입니다.
 */

function avatarInitial(name) {
  return (name || "?").trim().slice(0, 1);
}

function welfareBadgeClass(type) {
  if (type === "수급자") return "badge badge-warning";
  if (type === "차상위") return "badge badge-primary";
  return "badge";
}

/** 생년월일("YYYY-MM-DD")로 만 나이를 계산합니다. 형식이 이상하면 null. */
function computeAge(birthDateStr) {
  if (!birthDateStr) return null;
  const birth = new Date(birthDateStr);
  if (isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const hadBirthdayThisYear =
    today.getMonth() > birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() >= birth.getDate());
  if (!hadBirthdayThisYear) age -= 1;
  return age >= 0 ? age : null;
}

/** 마지막으로 정보가 갱신된 지 1년(365일)이 넘었으면 true. updated_at이 없으면 created_at 기준. */
function needsInfoUpdate(client) {
  const ref = client.updated_at || client.created_at;
  if (!ref) return false;
  const refDate = new Date(ref);
  if (isNaN(refDate.getTime())) return false;
  const oneYearAgo = new Date();
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
  return refDate < oneYearAgo;
}

/**
 * 회원 카드 안쪽 내용(HTML)을 만듭니다. 감싸는 태그(<a>든 <button>이든)는 호출하는 쪽에서
 * class="entity-card"를 붙여 직접 만들어야 합니다 - 화면마다 클릭했을 때 하는 일이 달라서입니다.
 */
function memberCardInnerHtml(c) {
  const age = computeAge(c.birth_date);
  const genderAgeParts = [c.gender, age !== null ? `${age}세` : null].filter(Boolean);
  const genderAgeStr = genderAgeParts.length ? ` (${genderAgeParts.join(" / ")})` : "";

  const badges = [
    c.welfare_type ? `<span class="${welfareBadgeClass(c.welfare_type)}">${escapeHtml(c.welfare_type)}</span>` : "",
    c.has_disability === "예" ? `<span class="badge badge-secondary">장애</span>` : "",
    needsInfoUpdate(c) ? `<span class="badge badge-warning"><i data-lucide="refresh-cw" class="w-3 h-3"></i>정보 갱신 필요</span>` : "",
  ].join("");

  // 이름/주소/전화번호/회원번호는 직원이 자유 입력한 값이라 반드시 escapeHtml을 거칩니다
  // (그대로 꽂으면 저장형 XSS로 이어질 수 있습니다 - api.js의 escapeHtml 주석 참고).
  return `
    <div class="flex items-center gap-3">
      <div class="avatar">${escapeHtml(avatarInitial(c.name))}</div>
      <div class="min-w-0">
        <div class="entity-card-title truncate">${c.name ? escapeHtml(c.name) : "(이름 없음)"}<span class="font-normal text-muted">${escapeHtml(genderAgeStr)}</span></div>
        <div class="entity-card-sub">${escapeHtml(c.member_no || "")}</div>
      </div>
    </div>
    <div class="flex gap-1.5 flex-wrap">${badges}</div>
    <div class="entity-card-body">
      ${c.address ? `<div class="flex items-center gap-1.5"><i data-lucide="map-pin" class="w-3.5 h-3.5"></i>${escapeHtml(c.address)}</div>` : ""}
      ${c.phone ? `<div class="flex items-center gap-1.5"><i data-lucide="phone" class="w-3.5 h-3.5"></i>${escapeHtml(c.phone)}</div>` : ""}
      ${c.created_at ? `<div class="flex items-center gap-1.5"><i data-lucide="calendar" class="w-3.5 h-3.5"></i>가입일 ${escapeHtml((c.created_at || "").slice(0, 10))}</div>` : ""}
    </div>
  `;
}
