/*
 * api.js
 * ------
 * 화면(JS)에서 /api/* 를 호출할 때 쓰는 공통 fetch 도우미입니다.
 * 로그인 유지는 httpOnly 쿠키(access_token/refresh_token)로 서버가 관리하므로,
 * 이 파일은 토큰을 직접 다루지 않습니다. 대신 access_token이 만료돼 401이 오면
 * /api/session/refresh를 한 번 호출해 쿠키를 갱신하고, 원래 요청을 한 번만 재시도합니다.
 * 그래도 401이면 로그인이 완전히 끊긴 것이니 /login으로 이동시킵니다.
 */
/*
 * 회원 이름/주소/전화번호 등은 직원이 자유 입력한 텍스트라, innerHTML로 그대로
 * 꽂으면 "<img src=x onerror=...>" 같은 값이 저장됐을 때 다른 직원이 화면을
 * 볼 때 그대로 실행되는 저장형 XSS가 됩니다. 사용자 입력을 HTML로 조합하는
 * 곳에서는 반드시 이 함수로 이스케이프한 뒤 끼워 넣어야 합니다.
 */
function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

/*
 * AI 추천 답변은 "## 소제목", "**굵게**" 같은 마크다운 기호가 섞여 나오는데, 그냥
 * 텍스트로 보여주면 "##", "**" 기호가 그대로 보여서 지저분합니다. 전체를 먼저
 * escapeHtml로 이스케이프한 뒤, 그 위에서 제목/굵게/링크 세 가지 패턴만 안전하게
 * 실제 HTML 태그로 바꿔줍니다(그 외 텍스트는 손대지 않습니다).
 */
function renderChatMarkdown(value) {
  const escaped = escapeHtml(value);
  return escaped
    .split("\n")
    .map((line) => {
      const heading = line.match(/^##\s+(.+)$/);
      if (heading) return `<div class="chat-h2">${heading[1]}</div>`;
      if (line.startsWith("   - ")) return `<div class="chat-subline">${line.trim()}</div>`;
      return line;
    })
    .join("\n")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (m, text, url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${text}</a>`);
}

async function apiFetch(url, options = {}) {
  const opts = { credentials: "same-origin", ...options };
  let res = await fetch(url, opts);

  if (res.status === 401) {
    const refreshRes = await fetch("/api/session/refresh", {
      method: "POST",
      credentials: "same-origin",
    });
    if (refreshRes.ok) {
      res = await fetch(url, opts);
    }
  }

  if (res.status === 401) {
    window.location.href = "/login";
    return res;
  }
  return res;
}

async function apiJson(url, options = {}) {
  const res = await apiFetch(url, options);
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    data = null;
  }
  if (!res.ok) {
    const message = (data && data.detail) || `서버 오류 (${res.status})`;
    throw new Error(message);
  }
  return data;
}

function apiPostJson(url, body) {
  return apiJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function apiPutJson(url, body) {
  return apiJson(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
