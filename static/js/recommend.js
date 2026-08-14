/*
 * recommend.js
 * -------------
 * AI 복지서비스 추천 화면. 조회 자체는 서버 백그라운드 스레드에서 돌고(다른 메뉴로
 * 이동해도 안 끊김), 이 화면은 2초 간격으로 상태를 물어보는 방식(폴링)으로 진행 상황을
 * 보여줍니다. 예전 Streamlit 버전의 time.sleep(2)+rerun 방식을 setInterval로 대체한 것입니다.
 */
let pollTimer = null;
let messages = [];
let govServices = [];

initMemberSearch({
  inputId: "member-search-input",
  resultsId: "member-search-results",
  onSelect: (c) => { window.location.href = `/recommend/${c.id}`; },
});

if (CLIENT_ID) {
  apiJson(`/api/clients/${CLIENT_ID}`).then((c) => {
    document.getElementById("member-search-input").value = c.name;
  }).catch(() => {});
}

function renderChat() {
  const area = document.getElementById("recommend-area");
  if (!area) return;
  const chatHtml = messages
    .filter((m, i) => i !== 1 && !["system", "tool"].includes(m.role) && m.content)
    .map((m) => `<div class="chat-msg ${m.role === "user" ? "user" : "assistant"}">${m.content}</div>`)
    .join("");

  const govHtml = govServices.length ? `
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
      ${govServices.map((s) => `
        <div class="entity-card" style="cursor:default;">
          <div class="entity-card-title">${s["서비스명"]}</div>
          <div class="flex gap-1.5"><span class="badge badge-primary">${s["구분"]}</span></div>
          <div class="entity-card-body">${s["주관기관"]}</div>
        </div>`).join("")}
    </div>` : "";

  const existing = area.querySelector(".chat-box");
  if (existing) {
    existing.innerHTML = chatHtml;
    existing.scrollTop = existing.scrollHeight;
    const govArea = area.querySelector(".gov-services-area");
    if (govArea) govArea.innerHTML = govHtml;
  } else {
    area.innerHTML = `
      <div class="card">
        <div class="chat-box">${chatHtml}</div>
        <div class="gov-services-area">${govHtml}</div>
        <form id="chat-form" class="flex gap-3 mt-3">
          <input type="text" id="chat-input" placeholder="추가로 궁금한 점을 물어보세요" class="flex-1">
          <button type="submit" class="btn"><i data-lucide="send" class="w-4 h-4"></i>보내기</button>
        </form>
        <button type="button" class="btn btn-ghost btn-sm mt-2" id="reset-btn"><i data-lucide="rotate-ccw" class="w-4 h-4"></i>대화 초기화 (새로 검색)</button>
      </div>`;
    document.getElementById("chat-form").addEventListener("submit", onChatSubmit);
    document.getElementById("reset-btn").addEventListener("click", startJob);
  }
  lucide.createIcons();
}

function renderStart() {
  document.getElementById("recommend-area").innerHTML = `
    <div class="card">
      <button type="button" class="btn" id="start-btn"><i data-lucide="sparkles" class="w-4 h-4"></i>복지서비스 검색 및 추천 받기</button>
    </div>`;
  document.getElementById("start-btn").addEventListener("click", startJob);
  lucide.createIcons();
}

function renderRunning() {
  document.getElementById("recommend-area").innerHTML = `
    <div class="alert alert-info"><i data-lucide="loader-circle" class="w-4 h-4 mt-0.5 animate-spin"></i><span>공공데이터 및 AI 분석 중입니다... (잠시만 기다려주세요)</span></div>`;
  lucide.createIcons();
}

function renderError(detail) {
  document.getElementById("recommend-area").innerHTML = `
    <div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>추천 조회 중 오류가 발생했습니다: ${detail}</span></div>
    <button type="button" class="btn mt-3" id="retry-btn"><i data-lucide="refresh-cw" class="w-4 h-4"></i>다시 시도</button>`;
  document.getElementById("retry-btn").addEventListener("click", startJob);
  lucide.createIcons();
}

async function startJob() {
  clearInterval(pollTimer);
  messages = [];
  govServices = [];
  await apiPostJson(`/api/recommend/start?client_id=${CLIENT_ID}`, {});
  renderRunning();
  pollStatus();
  pollTimer = setInterval(pollStatus, 2000);
}

async function pollStatus() {
  try {
    const status = await apiJson(`/api/recommend/status/${CLIENT_ID}`);
    if (status.status === "none") {
      clearInterval(pollTimer);
      renderStart();
    } else if (status.status === "running") {
      renderRunning();
    } else if (status.status === "error") {
      clearInterval(pollTimer);
      renderError(status.detail);
    } else if (status.status === "done") {
      clearInterval(pollTimer);
      messages = status.result.updated_messages;
      govServices = status.result.gov_services;
      renderChat();
      if (status.result.warnings && status.result.warnings.length) {
        const warnHtml = status.result.warnings.map((w) => `<div class="alert alert-warning mb-2"><i data-lucide="alert-triangle" class="w-4 h-4 mt-0.5"></i><span>${w}</span></div>`).join("");
        document.getElementById("recommend-area").insertAdjacentHTML("afterbegin", warnHtml);
        lucide.createIcons();
      }
    }
  } catch (e) {
    clearInterval(pollTimer);
    document.getElementById("recommend-area").innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>${e.message}</span></div>`;
    lucide.createIcons();
  }
}

async function onChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;
  messages.push({ role: "user", content: text });
  input.value = "";
  renderChat();
  try {
    const turn = await apiPostJson("/api/recommend/chat_turn", { client_id: CLIENT_ID, messages });
    messages = turn.updated_messages;
    renderChat();
  } catch (err) {
    messages.push({ role: "assistant", content: `(오류: ${err.message})` });
    renderChat();
  }
}

if (CLIENT_ID) pollStatus();
