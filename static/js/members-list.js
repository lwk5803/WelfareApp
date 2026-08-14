/*
 * members-list.js
 * -----------------
 * 회원 목록 화면. 카드형 목록 렌더링(공용 카드는 member-card.js) + 이름 검색(클라이언트 필터)
 * + 정렬(최근등록순/이름순).
 */
let allClients = [];

function renderCards(clients) {
  const grid = document.getElementById("list-grid");
  document.getElementById("count-caption").textContent = `총 ${clients.length}명`;

  if (clients.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full flex flex-col items-center justify-center gap-3 py-12 text-center">
        <div class="w-14 h-14 rounded-full bg-primary-light flex items-center justify-center text-primary-dark">
          <i data-lucide="users" class="w-7 h-7"></i>
        </div>
        <p class="text-muted text-sm">등록된 회원이 없습니다.</p>
      </div>`;
    lucide.createIcons();
    return;
  }

  grid.innerHTML = clients.map((c) => `
    <a class="entity-card" href="/members/${c.id}/edit">
      ${memberCardInnerHtml(c)}
    </a>
  `).join("");
  lucide.createIcons();
}

function sortClients(clients, mode) {
  const sorted = [...clients];
  if (mode === "name") {
    sorted.sort((a, b) => (a.name || "").localeCompare(b.name || "", "ko"));
  } else {
    sorted.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  }
  return sorted;
}

function applyFilters() {
  const kw = document.getElementById("search-input").value.trim();
  const mode = document.getElementById("sort-select").value;
  const filtered = kw ? allClients.filter((c) => (c.name || "").includes(kw)) : allClients;
  renderCards(sortClients(filtered, mode));
}

async function loadClients() {
  try {
    allClients = await apiJson("/api/clients");
    applyFilters();
  } catch (e) {
    document.getElementById("list-error").innerHTML =
      `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>회원 목록을 불러오지 못했습니다: ${e.message}</span></div>`;
    lucide.createIcons();
  }
}

document.getElementById("search-input").addEventListener("input", applyFilters);
document.getElementById("sort-select").addEventListener("change", applyFilters);

loadClients();
