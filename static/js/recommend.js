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
let memberInfoWarnings = [];
let chatBusy = false;

initMemberSearch({
  inputId: "member-search-input",
  resultsId: "member-search-results",
  onSelect: (c) => { window.location.href = `/recommend/${c.id}`; },
});

if (CLIENT_ID) {
  apiJson(`/api/clients/${CLIENT_ID}`).then((c) => {
    document.getElementById("member-search-input").value = c.name;
    renderMemberInfoCheck(c);
  }).catch(() => {});
}

// ---------- 회원 정보 확인 패널 ----------
// 외부 테스트 피드백: "입력된 회원 정보가 제대로 되어 있는지 확인이 필요함" +
// "100세 넘는 회원에게 아이돌봄서비스를 추천함" - 추천을 돌리기 전에 어떤 정보로
// 검색하는지 화면에 먼저 보여주고, 나이가 비정상적이면(100세 이상/계산 불가 등)
// 직원이 인지하고 넘어가도록 확인 절차를 넣습니다.
function renderMemberInfoCheck(c) {
  const el = document.getElementById("member-info-check");
  if (!el) return;

  const age = computeAge(c.birth_date);
  const warnings = [];
  if (age === null) {
    warnings.push("생년월일이 없거나 형식을 인식할 수 없어 나이를 계산하지 못했습니다. 나이 조건 필터링이 제대로 안 될 수 있습니다.");
  } else if (age >= 100) {
    warnings.push(`나이가 ${age}세로 계산됩니다. 실제로 맞는 나이인지 확인해주세요 (생년월일 오타로 나이가 이상하게 계산되면 서비스 추천도 엉뚱하게 나올 수 있습니다).`);
  } else if (age < 0) {
    warnings.push("생년월일이 오늘보다 미래로 되어 있어 나이 계산이 이상합니다.");
  }
  if (!c.gender) warnings.push("성별이 입력되어 있지 않습니다.");
  if (!c.address) warnings.push("주소가 입력되어 있지 않아 지역(지자체) 기반 서비스는 찾을 수 없습니다.");

  memberInfoWarnings = warnings;

  const rows = [
    ["이름", c.name || "-"],
    ["성별", c.gender || "미입력"],
    ["나이", age !== null ? `${age}세` : "계산 불가"],
    ["거주지", c.address || "미입력"],
    ["회원 구분", c.welfare_type || "-"],
  ];

  el.innerHTML = `
    <div class="card mb-4">
      <div class="text-sm font-semibold text-primary-dark mb-2 flex items-center gap-1.5">
        <i data-lucide="clipboard-check" class="w-4 h-4"></i>이 정보로 추천을 진행합니다
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
        ${rows.map(([k, v]) => `
          <div>
            <div class="text-xs text-muted">${escapeHtml(k)}</div>
            <div class="font-semibold text-sm truncate">${escapeHtml(v)}</div>
          </div>`).join("")}
      </div>
      ${warnings.length ? `
        <div class="alert alert-warning mt-3">
          <i data-lucide="alert-triangle" class="w-4 h-4 mt-0.5 shrink-0"></i>
          <div>
            ${warnings.map((w) => `<div>${escapeHtml(w)}</div>`).join("")}
            <a href="/members/${CLIENT_ID}/edit" class="btn btn-outline btn-sm mt-2"><i data-lucide="edit-3" class="w-3.5 h-3.5"></i>회원정보 수정하러 가기</a>
          </div>
        </div>` : ""}
    </div>`;
  lucide.createIcons();
}

// ---------- 채팅 렌더링 ----------
function chatRowHtml(role, innerHtml) {
  const icon = role === "user" ? "user" : "sparkles";
  return `
    <div class="chat-row ${role}">
      <div class="chat-avatar"><i data-lucide="${icon}"></i></div>
      <div class="chat-msg ${role}">${innerHtml}</div>
    </div>`;
}

function isHttpUrl(url) {
  return typeof url === "string" && /^https?:\/\//.test(url);
}

function serviceCardHtml(s) {
  const desc = (s["설명"] || "").trim();
  const descShort = desc.length > 90 ? desc.slice(0, 90) + "…" : desc;
  const inner = `
    <div class="entity-card-title">${escapeHtml(s["서비스명"] || "")}</div>
    <div class="flex gap-1.5 flex-wrap"><span class="badge badge-primary">${escapeHtml(s["구분"] || "")}</span></div>
    <div class="entity-card-body">
      ${descShort ? `<div class="service-card-desc">${escapeHtml(descShort)}</div>` : ""}
      <div class="flex items-center gap-1.5"><i data-lucide="building-2" class="w-3.5 h-3.5"></i>${escapeHtml(s["주관기관"] || "확인 필요")}</div>
      ${s["문의처"] ? `<div class="flex items-center gap-1.5"><i data-lucide="phone" class="w-3.5 h-3.5"></i>${escapeHtml(s["문의처"])}</div>` : ""}
    </div>
    ${isHttpUrl(s["링크"]) ? `<div class="service-card-link">자세히 보기 →</div>` : ""}
  `;
  return isHttpUrl(s["링크"])
    ? `<a class="entity-card" href="${encodeURI(s["링크"])}" target="_blank" rel="noopener noreferrer">${inner}</a>`
    : `<div class="entity-card" style="cursor:default;">${inner}</div>`;
}

function renderChat() {
  const area = document.getElementById("recommend-area");
  if (!area) return;
  const chatHtml = messages
    .filter((m, i) => i !== 1 && !["system", "tool"].includes(m.role) && m.content)
    .map((m) => chatRowHtml(m.role === "user" ? "user" : "assistant", renderChatMarkdown(m.content)))
    .join("");

  const govHtml = govServices.length
    ? `<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">${govServices.map(serviceCardHtml).join("")}</div>`
    : "";

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
          <input type="text" id="chat-input" placeholder="추가로 궁금한 점을 물어보세요 (예: 소득 기준이 어떻게 되나요?)" class="flex-1" autocomplete="off">
          <button type="submit" class="btn" id="chat-send-btn"><i data-lucide="send" class="w-4 h-4"></i>보내기</button>
        </form>
        <button type="button" class="btn btn-ghost btn-sm mt-2" id="reset-btn"><i data-lucide="rotate-ccw" class="w-4 h-4"></i>대화 초기화 (새로 검색)</button>
      </div>`;
    document.getElementById("chat-form").addEventListener("submit", onChatSubmit);
    document.getElementById("reset-btn").addEventListener("click", startJob);
    const chatBox = area.querySelector(".chat-box");
    chatBox.scrollTop = chatBox.scrollHeight;
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
    <div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>추천 조회 중 오류가 발생했습니다: ${escapeHtml(detail)}</span></div>
    <button type="button" class="btn mt-3" id="retry-btn"><i data-lucide="refresh-cw" class="w-4 h-4"></i>다시 시도</button>`;
  document.getElementById("retry-btn").addEventListener("click", startJob);
  lucide.createIcons();
}

async function startJob() {
  // 외부 테스트 피드백: 나이가 100세 이상으로 계산되는 등 회원 정보에 확인이 필요한
  // 부분이 있으면, 검색을 실제로 시작하기 전에 한 번 더 확인을 받습니다.
  if (memberInfoWarnings.length) {
    const proceed = confirm(
      "회원 정보에 확인이 필요한 부분이 있습니다:\n\n- " +
      memberInfoWarnings.join("\n- ") +
      "\n\n그래도 이 정보로 계속 진행하시겠습니까?"
    );
    if (!proceed) return;
  }

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
        const warnHtml = status.result.warnings.map((w) => `<div class="alert alert-warning mb-2"><i data-lucide="alert-triangle" class="w-4 h-4 mt-0.5"></i><span>${escapeHtml(w)}</span></div>`).join("");
        document.getElementById("recommend-area").insertAdjacentHTML("afterbegin", warnHtml);
        lucide.createIcons();
      }
    }
  } catch (e) {
    clearInterval(pollTimer);
    document.getElementById("recommend-area").innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>${escapeHtml(e.message)}</span></div>`;
    lucide.createIcons();
  }
}

// "생각 중..." 표시는 실제 메시지 배열에 넣지 않고 렌더링 직후 DOM에 직접 붙였다 뗍니다
// (messages 배열에 넣으면 서버에 다시 보낼 대화 기록에도 섞여 들어가기 때문입니다).
function showTypingIndicator() {
  const box = document.querySelector("#recommend-area .chat-box");
  if (!box) return;
  box.insertAdjacentHTML("beforeend", `
    <div class="chat-row assistant" id="typing-row">
      <div class="chat-avatar"><i data-lucide="sparkles"></i></div>
      <div class="chat-msg assistant"><span class="chat-typing"><span></span><span></span><span></span></span></div>
    </div>`);
  lucide.createIcons();
  box.scrollTop = box.scrollHeight;
}

function setChatBusy(busy) {
  chatBusy = busy;
  const input = document.getElementById("chat-input");
  const btn = document.getElementById("chat-send-btn");
  if (input) input.disabled = busy;
  if (btn) btn.disabled = busy;
}

async function onChatSubmit(e) {
  e.preventDefault();
  if (chatBusy) return;
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;
  messages.push({ role: "user", content: text });
  input.value = "";
  renderChat();
  showTypingIndicator();
  setChatBusy(true);
  try {
    const turn = await apiPostJson("/api/recommend/chat_turn", { client_id: CLIENT_ID, messages });
    messages = turn.updated_messages;
  } catch (err) {
    messages.push({ role: "assistant", content: `(오류: ${err.message})` });
  } finally {
    setChatBusy(false);
    renderChat();
    document.getElementById("chat-input")?.focus();
  }
}

if (CLIENT_ID) pollStatus();
