/*
 * member-search.js
 * -----------------
 * "회원목록에서 바로 골라 선택" + "이름으로 검색" 공용 위젯입니다. 페이지에 들어오면
 * 검색어를 치지 않아도 전체 회원이 회원 목록 화면과 같은 카드 모양으로 바로 보이고,
 * 그 중 하나를 클릭해서 고를 수 있습니다(카드 내용은 member-card.js가 공통으로 만듭니다).
 * 회원이 많아지는 경우를 대비해 이름 검색으로 좁혀볼 수도 있습니다(목록 영역은 세로
 * 스크롤이 생겨서 화면이 무한정 길어지지 않습니다).
 * 정보수정/회원삭제/서류출력/맞춤형 복지서비스 추천 화면에서 공통으로 씁니다.
 *
 * 사용법:
 *   initMemberSearch({ inputId: "search-input", resultsId: "search-results", onSelect: (client) => {...} })
 */
function initMemberSearch({ inputId, resultsId, onSelect }) {
  let clients = [];
  const input = document.getElementById(inputId);
  const resultsEl = document.getElementById(resultsId);
  const MAX_SHOWN = 60;

  function render(list) {
    if (list.length === 0) {
      resultsEl.innerHTML = `<p class="text-sm text-muted px-1 py-2">일치하는 회원이 없습니다.</p>`;
      return;
    }
    const shown = list.slice(0, MAX_SHOWN);
    resultsEl.innerHTML = shown.map((c) => `
      <button type="button" class="entity-card member-search-result" data-id="${c.id}">
        ${memberCardInnerHtml(c)}
      </button>
    `).join("") + (list.length > MAX_SHOWN
      ? `<p class="text-xs text-muted px-1 py-1 col-span-full">그 외 ${list.length - MAX_SHOWN}명 더 있습니다 - 검색으로 좁혀보세요.</p>`
      : "");
    resultsEl.querySelectorAll(".member-search-result").forEach((btn) => {
      btn.addEventListener("click", () => {
        const c = list.find((x) => String(x.id) === btn.dataset.id);
        onSelect(c);
      });
    });
    lucide.createIcons();
  }

  input.addEventListener("input", () => {
    const kw = input.value.trim();
    render(kw ? clients.filter((c) => (c.name || "").includes(kw)) : clients);
  });

  (async () => {
    try {
      clients = await apiJson("/api/clients");
      render(clients);
    } catch (e) {
      resultsEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>회원 목록을 불러오지 못했습니다: ${e.message}</span></div>`;
      if (window.lucide) lucide.createIcons();
    }
  })();

  return {
    getClients: () => clients,
  };
}
