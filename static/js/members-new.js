/*
 * members-new.js
 * ---------------
 * "신규 회원 등록" 화면의 모든 상호작용을 담당합니다: 기존 이력 확인, 주소 검색,
 * 사진 촬영(리사이즈), 장애/질병/경력의 "있다/없다"에 따른 입력칸 활성화-비활성화,
 * 서명, 동의 검증, 등록 제출, 그리고 엑셀 일괄등록까지.
 */

// ---------- 사진: 800x800 이하로 축소 + JPEG 품질 80%로 압축 (base64) ----------
function encodePhotoFile(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve("");
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const maxSize = 800;
        let { width, height } = img;
        if (width > maxSize || height > maxSize) {
          const scale = maxSize / Math.max(width, height);
          width = Math.round(width * scale);
          height = Math.round(height * scale);
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        canvas.getContext("2d").drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", 0.8).split(",", 2)[1]);
      };
      img.onerror = () => reject(new Error("사진을 읽지 못했습니다."));
      img.src = reader.result;
    };
    reader.onerror = () => reject(new Error("사진을 읽지 못했습니다."));
    reader.readAsDataURL(file);
  });
}

document.getElementById("reg-photo").addEventListener("change", (e) => {
  const file = e.target.files[0];
  const preview = document.getElementById("reg-photo-preview");
  if (!file) {
    preview.style.display = "none";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    preview.src = reader.result;
    preview.style.display = "block";
  };
  reader.readAsDataURL(file);
});

// ---------- 장애/질병/경력: "있다/예" 선택 시에만 하위 입력 활성화 ----------
function wireToggle(radioName, activeValue, targets) {
  document.querySelectorAll(`input[name="${radioName}"]`).forEach((radio) => {
    radio.addEventListener("change", () => {
      const active = document.querySelector(`input[name="${radioName}"]:checked`).value === activeValue;
      targets.forEach((el) => { el.disabled = !active; });
    });
  });
}
wireToggle("f-disability", "예", [document.getElementById("f-disability-type")]);
wireToggle("f-illness", "있다", [
  ...document.querySelectorAll("#f-illness-types input"),
  document.getElementById("f-illness-etc"),
]);
wireToggle("f-career", "있다", [
  ...document.querySelectorAll("#f-career-types input"),
  document.getElementById("f-career-etc"),
]);

// ---------- 가입경로: "관공서 의뢰"/"기타"일 때만 상세 사유 입력칸 노출 ----------
const joinRouteSelect = document.getElementById("f-join-route");
const joinRouteDetail = document.getElementById("f-join-route-detail");
joinRouteSelect.addEventListener("change", () => {
  const needsDetail = ["관공서 의뢰", "기타"].includes(joinRouteSelect.value);
  joinRouteDetail.style.display = needsDetail ? "block" : "none";
  if (!needsDetail) joinRouteDetail.value = "";
});

// ---------- 기존 등록 이력 확인 ----------
document.getElementById("check-btn").addEventListener("click", async () => {
  const name = document.getElementById("check-name").value.trim();
  const birth = document.getElementById("check-birth").value.trim();
  const resultsEl = document.getElementById("check-results");
  if (!name) {
    resultsEl.innerHTML = `<div class="alert alert-warning"><i data-lucide="alert-triangle" class="w-4 h-4 mt-0.5"></i><span>성명을 입력해주세요.</span></div>`;
    lucide.createIcons();
    return;
  }
  try {
    const results = await apiPostJson("/api/clients/check_duplicates", { name, birth_date: birth, phone: "" });
    if (results.length === 0) {
      resultsEl.innerHTML = `<p class="text-sm text-muted">일치하는 기록이 없습니다.</p>`;
      return;
    }
    const active = results.filter((r) => !r.deleted_at);
    const deleted = results.filter((r) => r.deleted_at);
    let html = "";
    active.forEach((r) => {
      html += `<div class="alert alert-warning mb-2"><i data-lucide="alert-triangle" class="w-4 h-4 mt-0.5"></i><span>이미 등록되어 있는 회원입니다 (회원번호: ${r.member_no}). 중복 등록에 주의하세요.</span></div>`;
    });
    deleted.forEach((r) => {
      html += `<div class="alert alert-info mb-2">
        <i data-lucide="info" class="w-4 h-4 mt-0.5"></i>
        <div>
          회원번호: ${r.member_no} / 등록일: ${(r.created_at || "").slice(0, 10)} / 탈퇴일: ${(r.deleted_at || "").slice(0, 10)}
          <div class="mt-1.5"><button type="button" class="btn btn-outline btn-sm load-prefill-btn" data-id="${r.id}">이 정보 불러오기 (${r.member_no})</button></div>
        </div>
      </div>`;
    });
    resultsEl.innerHTML = html;
    lucide.createIcons();
    resultsEl.querySelectorAll(".load-prefill-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const record = results.find((r) => String(r.id) === btn.dataset.id);
        applyPrefill(record);
        resultsEl.innerHTML = "";
      });
    });
  } catch (e) {
    resultsEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>조회 실패: ${e.message}</span></div>`;
    lucide.createIcons();
  }
});

function applyPrefill(r) {
  document.getElementById("f-name").value = r.name || "";
  document.querySelector(`input[name="f-gender"][value="${r.gender === "남" ? "남" : "여"}"]`).checked = true;
  document.getElementById("f-birth").value = r.birth_date || "";
  document.getElementById("f-phone").value = r.phone || "";
  document.getElementById("f-address").value = r.address || "";
  document.getElementById("f-ec-name").value = r.emergency_contact_name || "";
  document.getElementById("f-ec-rel").value = r.emergency_contact_relation || "";
  document.getElementById("f-ec-phone").value = r.emergency_contact_phone || "";
  document.getElementById("f-welfare-type").value = r.welfare_type || "일반";
  document.getElementById("f-counselor").value = r.counselor || "";
  const baseRoute = (r.join_route || "").split("(")[0];
  if (["자진", "관공서 의뢰", "주민 추천", "기타"].includes(baseRoute)) {
    joinRouteSelect.value = baseRoute;
    joinRouteSelect.dispatchEvent(new Event("change"));
  }
  const householdList = (r.household_types || "").split(",").map((s) => s.trim());
  document.querySelectorAll("#f-household-types input").forEach((cb) => {
    cb.checked = householdList.includes(cb.value);
  });
  document.querySelector(`input[name="f-disability"][value="${r.has_disability === "예" ? "예" : "아니오"}"]`).checked = true;
  document.getElementById("f-disability-type").disabled = r.has_disability !== "예";
  document.getElementById("f-disability-type").value = r.disability_type || "";
  document.getElementById("f-note").value = r.note || "";

  document.getElementById("prefill-banner").innerHTML =
    `<div class="alert alert-success">
       <i data-lucide="check-circle" class="w-4 h-4 mt-0.5"></i>
       <div>'${r.member_no}' 회원의 예전 정보를 불러왔습니다. 필요한 부분만 고쳐서 등록하세요.
       <button type="button" class="btn btn-ghost btn-sm ml-2" id="clear-prefill-btn">불러온 정보 지우기</button></div>
     </div>`;
  lucide.createIcons();
  document.getElementById("clear-prefill-btn").addEventListener("click", () => {
    document.getElementById("reg-form").reset();
    document.getElementById("prefill-banner").innerHTML = "";
  });
}

// ---------- 주소 검색 (주소 입력창 자체를 검색어로 씀 - 검색창을 따로 안 둠) ----------
document.getElementById("addr-search-btn").addEventListener("click", async () => {
  const kw = document.getElementById("f-address").value.trim();
  const resultsEl = document.getElementById("addr-results");
  if (!kw) return;
  resultsEl.innerHTML = `<p class="text-sm text-muted">검색 중...</p>`;
  try {
    const results = await apiJson(`/api/address/search?keyword=${encodeURIComponent(kw)}`);
    if (results.length === 0) {
      resultsEl.innerHTML = `<p class="text-sm text-muted">검색 결과가 없습니다. 다른 검색어(건물명, 도로명 등)로 시도해보세요.</p>`;
      return;
    }
    resultsEl.innerHTML = `
      <div class="flex flex-wrap gap-3 mt-3">
        <div class="flex-[3] min-w-[200px]">
          <select id="addr-pick">
            ${results.map((r, i) => {
              const label = `${r.place_name ? r.place_name + " - " : ""}${r.road_address}${r.zip_code ? " (" + r.zip_code + ")" : ""}`;
              return `<option value="${i}">${label}</option>`;
            }).join("")}
          </select>
        </div>
        <div class="flex-1 min-w-[120px]">
          <button type="button" class="btn btn-outline btn-block" id="addr-fill-btn">이 주소로 채우기</button>
        </div>
      </div>`;
    document.getElementById("addr-fill-btn").addEventListener("click", () => {
      const idx = document.getElementById("addr-pick").value;
      document.getElementById("f-address").value = results[idx].road_address;
      resultsEl.innerHTML = "";
    });
  } catch (e) {
    resultsEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>주소 검색 실패: ${e.message}</span></div>`;
    lucide.createIcons();
  }
});

// ---------- 등록 제출 ----------
document.getElementById("reg-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("reg-error");
  errorEl.innerHTML = "";

  const name = document.getElementById("f-name").value.trim();
  const consentPersonal = document.getElementById("c-personal").checked;
  const consentSensitive = document.getElementById("c-sensitive").checked;
  const consentThirdParty = document.getElementById("c-third-party").checked;
  const consentPortrait = document.getElementById("c-portrait").checked;

  if (!name) {
    errorEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>성명은 필수입니다.</span></div>`;
    lucide.createIcons();
    return;
  }
  if (!(consentPersonal && consentSensitive && consentThirdParty)) {
    errorEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>필수 동의 항목(개인정보 / 민감정보 / 제3자 제공)에 모두 동의해야 등록할 수 있습니다.</span></div>`;
    lucide.createIcons();
    return;
  }

  const householdTypes = Array.from(document.querySelectorAll("#f-household-types input:checked")).map((c) => c.value);
  const hasIllness = document.querySelector('input[name="f-illness"]:checked').value;
  const illnessPicked = Array.from(document.querySelectorAll("#f-illness-types input:checked")).map((c) => c.value);
  const illnessEtc = document.getElementById("f-illness-etc").value.trim();
  const illnessType = hasIllness === "있다" ? [...illnessPicked, ...(illnessEtc ? [illnessEtc] : [])].join(",") : "";

  const hasCareer = document.querySelector('input[name="f-career"]:checked').value;
  const careerPicked = Array.from(document.querySelectorAll("#f-career-types input:checked")).map((c) => c.value);
  const careerEtc = document.getElementById("f-career-etc").value.trim();
  const careerType = hasCareer === "있다" ? [...careerPicked, ...(careerEtc ? [careerEtc] : [])].join(",") : "";

  const hasDisability = document.querySelector('input[name="f-disability"]:checked').value;
  const joinRouteDetailVal = joinRouteDetail.value.trim();
  const joinRoute = joinRouteDetailVal ? `${joinRouteSelect.value}(${joinRouteDetailVal})` : joinRouteSelect.value;

  const submitBtn = e.target.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  try {
    const photoData = await encodePhotoFile(document.getElementById("reg-photo").files[0]);
    const signatureDataUrl = document.getElementById("f-signature").value;
    const payload = {
      name, gender: document.querySelector('input[name="f-gender"]:checked').value,
      birth_date: document.getElementById("f-birth").value.trim(),
      address: document.getElementById("f-address").value.trim(),
      phone: document.getElementById("f-phone").value.trim(),
      welfare_type: document.getElementById("f-welfare-type").value,
      note: document.getElementById("f-note").value,
      household_types: householdTypes.join(","),
      has_disability: hasDisability,
      disability_type: hasDisability === "예" ? document.getElementById("f-disability-type").value.trim() : "",
      photo_data: photoData,
      signature_data: signatureDataUrl.includes(",") ? signatureDataUrl.split(",", 2)[1] : "",
      emergency_contact_name: document.getElementById("f-ec-name").value.trim(),
      emergency_contact_relation: document.getElementById("f-ec-rel").value.trim(),
      emergency_contact_phone: document.getElementById("f-ec-phone").value.trim(),
      join_route: joinRoute,
      has_illness: hasIllness, illness_type: illnessType,
      has_career: hasCareer, career_type: careerType,
      counselor: document.getElementById("f-counselor").value.trim(),
      consent_personal: consentPersonal ? "동의함" : "동의안함",
      consent_sensitive: consentSensitive ? "동의함" : "동의안함",
      consent_third_party: consentThirdParty ? "동의함" : "동의안함",
      consent_portrait: consentPortrait ? "동의함" : "동의안함",
    };
    const res = await apiPostJson("/api/clients", payload);
    errorEl.innerHTML = `<div class="alert alert-success"><i data-lucide="check-circle" class="w-4 h-4 mt-0.5"></i><span>${escapeHtml(res.message)}</span></div>`;
    lucide.createIcons();
    document.getElementById("reg-form").reset();
    document.getElementById("reg-photo-preview").style.display = "none";
    document.getElementById("prefill-banner").innerHTML = "";
    document.querySelectorAll(".signature-pad-clear").forEach((btn) => btn.click());
  } catch (err) {
    errorEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>${err.message}</span></div>`;
    lucide.createIcons();
  } finally {
    submitBtn.disabled = false;
  }
});

// ---------- 엑셀 일괄등록 ----------
const FIELD_LABELS = {
  name: "성명 *", gender: "성별", birth_date: "생년월일",
  address: "주소", phone: "전화번호", welfare_type: "회원 구분", note: "비고",
};
let bulkColumns = [];

function guessColumn(field, columns) {
  const norm = (s) => s.replace(/[\s*]/g, "");
  const target = norm(FIELD_LABELS[field]);
  return columns.find((c) => norm(c) === norm(field) || norm(c) === target) || "(사용 안 함)";
}

document.getElementById("bulk-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  const previewEl = document.getElementById("bulk-preview");
  const mappingEl = document.getElementById("bulk-mapping");
  if (!file) return;
  previewEl.innerHTML = `<p class="text-sm text-muted">읽는 중...</p>`;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const res = await apiFetch("/api/bulk/preview", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "미리보기 실패");
    bulkColumns = data.columns;

    previewEl.innerHTML = `
      <p class="text-sm text-muted">미리보기 (총 ${data.total_rows}행)</p>
      <div class="table-wrap"><table>
        <thead><tr>${data.columns.map((c) => `<th>${c}</th>`).join("")}</tr></thead>
        <tbody>${data.preview_rows.map((row) =>
          `<tr>${data.columns.map((c) => `<td>${row[c] ?? ""}</td>`).join("")}</tr>`
        ).join("")}</tbody>
      </table></div>`;

    const options = ["(사용 안 함)", ...data.columns];
    mappingEl.innerHTML = `<div class="text-sm font-semibold text-primary-dark uppercase tracking-wide mb-3 pt-4 border-t border-dashed border-primary-light">컬럼 매칭</div><div class="flex flex-wrap gap-4">` +
      Object.keys(FIELD_LABELS).map((field) => `
        <div class="flex-1 min-w-[160px]">
          <label>${FIELD_LABELS[field]}</label>
          <select class="bulk-map-select" data-field="${field}">
            ${options.map((c) => `<option value="${c}" ${c === guessColumn(field, data.columns) ? "selected" : ""}>${c}</option>`).join("")}
          </select>
        </div>`).join("") + `</div>`;

    document.getElementById("bulk-consent-field").style.display = "block";
    document.getElementById("bulk-submit-btn").style.display = "inline-flex";
  } catch (err) {
    previewEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>${err.message}</span></div>`;
    lucide.createIcons();
  }
});

document.getElementById("bulk-submit-btn").addEventListener("click", async () => {
  const resultEl = document.getElementById("bulk-result");
  const file = document.getElementById("bulk-file").files[0];
  const mapping = {};
  document.querySelectorAll(".bulk-map-select").forEach((sel) => { mapping[sel.dataset.field] = sel.value; });

  if (mapping.name === "(사용 안 함)") {
    resultEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>성명 컬럼은 반드시 매칭해야 합니다.</span></div>`;
    lucide.createIcons();
    return;
  }
  if (!document.getElementById("bulk-consent").checked) {
    resultEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>동의 확인 체크박스에 체크해야 등록할 수 있습니다.</span></div>`;
    lucide.createIcons();
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("mapping", JSON.stringify(mapping));
  resultEl.innerHTML = `<p class="text-sm text-muted">등록 중입니다. 잠시만 기다려주세요...</p>`;
  try {
    const res = await apiFetch("/api/clients/bulk", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "일괄 등록 실패");
    let html = `<div class="alert alert-success"><i data-lucide="check-circle" class="w-4 h-4 mt-0.5"></i><span>${data.success}건 등록 완료 (건너뜀 ${data.skipped}건)</span></div>`;
    if (data.warnings.length) {
      html += `<details class="mt-2"><summary class="cursor-pointer text-sm text-warning font-medium">경고 ${data.warnings.length}건</summary><ul class="text-sm text-muted list-disc pl-5 mt-1">${data.warnings.map((w) => `<li>${w}</li>`).join("")}</ul></details>`;
    }
    if (data.failed.length) {
      html += `<details class="mt-2"><summary class="cursor-pointer text-sm text-danger font-medium">실패 ${data.failed.length}건</summary><ul class="text-sm text-muted list-disc pl-5 mt-1">${data.failed.map((f) => `<li>${f}</li>`).join("")}</ul></details>`;
    }
    resultEl.innerHTML = html;
    lucide.createIcons();
  } catch (err) {
    resultEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>${err.message}</span></div>`;
    lucide.createIcons();
  }
});
