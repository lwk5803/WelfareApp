/*
 * api.js
 * ------
 * 화면(JS)에서 /api/* 를 호출할 때 쓰는 공통 fetch 도우미입니다.
 * 로그인 유지는 httpOnly 쿠키(access_token/refresh_token)로 서버가 관리하므로,
 * 이 파일은 토큰을 직접 다루지 않습니다. 대신 access_token이 만료돼 401이 오면
 * /api/session/refresh를 한 번 호출해 쿠키를 갱신하고, 원래 요청을 한 번만 재시도합니다.
 * 그래도 401이면 로그인이 완전히 끊긴 것이니 /login으로 이동시킵니다.
 */
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
