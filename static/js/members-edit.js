/*
 * members-edit.js
 * ----------------
 * "회원 수정" 화면. 기존 값을 불러와 폼에 채우고, 새로 입력한 값으로 PUT 요청을 보냅니다.
 * 사진/서명은 새로 찍거나 그리지 않으면 payload에 아예 포함하지 않습니다 - 예전 Streamlit
 * 버전은 빈 문자열을 그대로 보내서 기존 사진/서명이 지워지는 문제가 있었는데, 그 버그를 고친 것입니다.
 */

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

document.getElementById("e-photo").addEventListener("change", (e) => {
  const file = e.target.files[0];
  const preview = document.getElementById("e-photo-preview");
  if (!file) { preview.style.display = "none"; return; }
  const reader = new FileReader();
  reader.onload = () => { preview.src = reader.result; preview.style.display = "block"; };
  reader.readAsDataURL(file);
});

function wireToggle(radioName, activeValue, targets) {
  document.querySelectorAll(`input[name="${radioName}"]`).forEach((radio) => {
    radio.addEventListener("change", () => {
      const checked = document.querySelector(`input[name="${radioName}"]:checked`);
      const active = checked && checked.value === activeValue;
      targets.forEach((el) => { el.disabled = !active; });
    });
  });
}
wireToggle("e-disability", "예", [document.getElementById("e-disability-type")]);
wireToggle("e-illness", "있다", [
  ...document.querySelectorAll("#e-illness-types input"),
  document.getElementById("e-illness-etc"),
]);
wireToggle("e-career", "있다", [
  ...document.querySelectorAll("#e-career-types input"),
  document.getElementById("e-career-etc"),
]);

const KNOWN_ILLNESS = ["고혈압", "당뇨", "관절염", "치매", "심장질환", "뇌졸중"];
const KNOWN_CAREER = ["가사", "공직", "사무직", "자영업", "교직", "전문직", "기술직", "단순노동직"];

function fillMultiPlusEtc(commaValue, groupSelector, etcSelector, knownList) {
  const parts = (commaValue || "").split(",").map((s) => s.trim()).filter(Boolean);
  document.querySelectorAll(`${groupSelector} input`).forEach((cb) => {
    cb.checked = parts.includes(cb.value);
    cb.disabled = false;
  });
  const etc = parts.filter((p) => !knownList.includes(p)).join(", ");
  const etcEl = document.querySelector(etcSelector);
  etcEl.value = etc;
  etcEl.disabled = false;
}

async function loadClient() {
  try {
    const c = await apiJson(`/api/clients/${CLIENT_ID}`);
    document.getElementById("e-name").value = c.name || "";
    document.querySelector(`input[name="e-gender"][value="${c.gender === "남" ? "남" : "여"}"]`).checked = true;
    document.getElementById("e-birth").value = c.birth_date || "";
    document.getElementById("e-phone").value = c.phone || "";
    document.getElementById("e-address").value = c.address || "";
    document.getElementById("e-ec-name").value = c.emergency_contact_name || "";
    document.getElementById("e-ec-rel").value = c.emergency_contact_relation || "";
    document.getElementById("e-ec-phone").value = c.emergency_contact_phone || "";
    if (["일반", "차상위", "수급자"].includes(c.welfare_type)) {
      document.getElementById("e-welfare-type").value = c.welfare_type;
    }
    document.getElementById("e-counselor").value = c.counselor || "";
    const baseRoute = (c.join_route || "").split("(")[0];
    if (["자진", "관공서 의뢰", "주민 추천", "기타"].includes(baseRoute)) {
      document.getElementById("e-join-route").value = baseRoute;
    }
    const householdList = (c.household_types || "").split(",").map((s) => s.trim());
    document.querySelectorAll("#e-household-types input").forEach((cb) => {
      cb.checked = householdList.includes(cb.value);
    });

    const hasDisability = c.has_disability === "예" ? "예" : "아니오";
    document.querySelector(`input[name="e-disability"][value="${hasDisability}"]`).checked = true;
    document.getElementById("e-disability-type").disabled = hasDisability !== "예";
    document.getElementById("e-disability-type").value = c.disability_type || "";

    const hasIllness = c.has_illness === "있다" ? "있다" : "없다";
    document.querySelector(`input[name="e-illness"][value="${hasIllness}"]`).checked = true;
    if (hasIllness === "있다") {
      fillMultiPlusEtc(c.illness_type, "#e-illness-types", "#e-illness-etc", KNOWN_ILLNESS);
    }

    const hasCareer = c.has_career === "있다" ? "있다" : "없다";
    document.querySelector(`input[name="e-career"][value="${hasCareer}"]`).checked = true;
    if (hasCareer === "있다") {
      fillMultiPlusEtc(c.career_type, "#e-career-types", "#e-career-etc", KNOWN_CAREER);
    }

    document.getElementById("e-note").value = c.note || "";

    if (c.photo_data) {
      const img = document.getElementById("e-photo-current");
      img.src = `data:image/jpeg;base64,${c.photo_data}`;
      img.style.display = "block";
    }
    if (c.signature_data) {
      const img = document.getElementById("e-signature-current");
      img.src = `data:image/png;base64,${c.signature_data}`;
      img.style.display = "block";
    }

    const consentBadge = (label, value) =>
      `<span class="badge ${value === "동의함" ? "badge-secondary" : "badge-danger"}">${label} ${value === "동의함" ? "동의함" : "동의안함"}</span>`;
    document.getElementById("e-consent-info").innerHTML =
      consentBadge("개인정보", c.consent_personal) +
      consentBadge("민감정보", c.consent_sensitive) +
      consentBadge("제3자제공", c.consent_third_party) +
      consentBadge("초상권", c.consent_portrait) +
      (c.consent_signed_at
        ? `<span class="text-xs text-muted">동의일시: ${c.consent_signed_at.slice(0, 16).replace("T", " ")}</span>`
        : "");

    document.getElementById("edit-loading").style.display = "none";
    document.getElementById("edit-form").classList.remove("hidden");
    lucide.createIcons();
  } catch (e) {
    document.getElementById("edit-loading").innerHTML =
      `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>회원 정보를 불러오지 못했습니다: ${e.message}</span></div>`;
    lucide.createIcons();
  }
}
loadClient();

document.getElementById("edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("edit-error");
  errorEl.innerHTML = "";

  const name = document.getElementById("e-name").value.trim();
  if (!name) {
    errorEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>성명은 필수입니다.</span></div>`;
    lucide.createIcons();
    return;
  }

  const householdTypes = Array.from(document.querySelectorAll("#e-household-types input:checked")).map((c) => c.value);
  const hasIllness = document.querySelector('input[name="e-illness"]:checked').value;
  const illnessPicked = Array.from(document.querySelectorAll("#e-illness-types input:checked")).map((c) => c.value);
  const illnessEtc = document.getElementById("e-illness-etc").value.trim();
  const illnessType = hasIllness === "있다" ? [...illnessPicked, ...(illnessEtc ? [illnessEtc] : [])].join(",") : "";

  const hasCareer = document.querySelector('input[name="e-career"]:checked').value;
  const careerPicked = Array.from(document.querySelectorAll("#e-career-types input:checked")).map((c) => c.value);
  const careerEtc = document.getElementById("e-career-etc").value.trim();
  const careerType = hasCareer === "있다" ? [...careerPicked, ...(careerEtc ? [careerEtc] : [])].join(",") : "";

  const hasDisability = document.querySelector('input[name="e-disability"]:checked').value;

  const submitBtn = e.target.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  try {
    const payload = {
      name, gender: document.querySelector('input[name="e-gender"]:checked').value,
      birth_date: document.getElementById("e-birth").value.trim(),
      address: document.getElementById("e-address").value.trim(),
      phone: document.getElementById("e-phone").value.trim(),
      welfare_type: document.getElementById("e-welfare-type").value,
      note: document.getElementById("e-note").value,
      household_types: householdTypes.join(","),
      has_disability: hasDisability,
      disability_type: hasDisability === "예" ? document.getElementById("e-disability-type").value.trim() : "",
      emergency_contact_name: document.getElementById("e-ec-name").value.trim(),
      emergency_contact_relation: document.getElementById("e-ec-rel").value.trim(),
      emergency_contact_phone: document.getElementById("e-ec-phone").value.trim(),
      join_route: document.getElementById("e-join-route").value,
      has_illness: hasIllness, illness_type: illnessType,
      has_career: hasCareer, career_type: careerType,
      counselor: document.getElementById("e-counselor").value.trim(),
    };

    const photoData = await encodePhotoFile(document.getElementById("e-photo").files[0]);
    if (photoData) payload.photo_data = photoData;

    const signatureDataUrl = document.getElementById("e-signature").value;
    if (signatureDataUrl.includes(",")) payload.signature_data = signatureDataUrl.split(",", 2)[1];

    const res = await apiPutJson(`/api/clients/${CLIENT_ID}`, payload);
    errorEl.innerHTML = `<div class="alert alert-success"><i data-lucide="check-circle" class="w-4 h-4 mt-0.5"></i><span>${escapeHtml(res.message)}</span></div>`;
    lucide.createIcons();
  } catch (err) {
    errorEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>${err.message}</span></div>`;
    lucide.createIcons();
  } finally {
    submitBtn.disabled = false;
  }
});

document.getElementById("e-doc-btn").addEventListener("click", async () => {
  const resultEl = document.getElementById("e-doc-result");
  resultEl.innerHTML = `<p class="text-sm text-muted">만드는 중...</p>`;
  try {
    const res = await apiFetch(`/api/clients/${CLIENT_ID}/document`);
    if (!res.ok) throw new Error("서류를 만드는 중 오류가 발생했습니다.");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${document.getElementById("e-name").value || CLIENT_ID}_등록서류.docx`;
    a.className = "btn btn-outline btn-sm";
    a.innerHTML = `<i data-lucide="download" class="w-4 h-4"></i>서류 다운로드 (.docx)`;
    resultEl.innerHTML = "";
    resultEl.appendChild(a);
    lucide.createIcons();
  } catch (e) {
    resultEl.innerHTML = `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>서류 생성 오류: ${e.message}</span></div>`;
    lucide.createIcons();
  }
});
