/*
 * stats.js
 * --------
 * 통계 화면. /api/stats/summary + /api/stats/charts를 불러와 카드/차트/기간별 현황을 그립니다.
 * 차트는 Chart.js(CDN)를 씁니다 - 따로 빌드가 필요 없는 가벼운 의존성입니다. 분포(성별/구분/
 * 연령/가구유형 등) 차트는 꽉 찬 원형(파이) 차트로, 월별 현황은 막대 차트로 그립니다. 값은
 * chartjs-plugin-datalabels로 조각 위에 직접 숫자를 표시해 눈으로 바로 확인할 수 있게 했습니다.
 * 모든 차트는 .chart-box(고정 높이 컨테이너) + maintainAspectRatio:false 조합으로
 * 항목 개수/라벨 길이와 상관없이 항상 같은 크기로 보이게 했습니다.
 */
if (window.ChartDataLabels) Chart.register(ChartDataLabels);

// 데이터 레이블(조각/막대 위에 뜨는 숫자) 글자색은 흰색 대신 진한 잉크색을 씁니다 - 파이 조각
// 색을 연하게 바꾸면서 흰 글씨는 대비가 약해져 잘 안 보이는 색 조합이 생길 수 있어서입니다.
// 굵게(bold)도 빼고 medium 정도로만 - 요청대로 너무 튀지 않게.
const LABEL_COLOR = "#3A3A3A";
const LABEL_FONT = { weight: "500", size: 13 };

const ACCENT = "#FB923C";
// 기존보다 한 단계씩 밝은 톤으로(오렌지/그린 계열은 유지) 가독성을 살짝 높였습니다.
const PALETTE = ["#FB923C", "#4ADE80", "#F97316", "#22C55E", "#FED7AA", "#BBF7D0", "#F59E0B", "#93C5FD"];

function pieChart(canvasId, dict, label) {
  const entries = Object.entries(dict || {});
  if (entries.length === 0) return;
  const total = entries.reduce((sum, e) => sum + e[1], 0);
  new Chart(document.getElementById(canvasId), {
    type: "pie",
    data: {
      labels: entries.map((e) => e[0]),
      datasets: [{ label, data: entries.map((e) => e[1]), backgroundColor: PALETTE, borderWidth: 2, borderColor: "#fff" }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 13, font: { size: 13, weight: "600" } } },
        datalabels: {
          color: LABEL_COLOR,
          font: LABEL_FONT,
          formatter: (value) => (total ? `${value}\n(${Math.round((value / total) * 100)}%)` : value),
        },
      },
    },
  });
}

function barChart(canvasId, dict, label) {
  const entries = Object.entries(dict || {}).sort((a, b) => a[0].localeCompare(b[0]));
  if (entries.length === 0) return;
  new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: {
      labels: entries.map((e) => e[0]),
      // maxBarThickness/barPercentage: 데이터(월 수)가 적을 때 막대 하나가 화면을 꽉 채워
      // 지나치게 커 보이지 않도록 최대 두께를 제한합니다. 데이터가 늘어나 막대가 많아지면
      // Chart.js가 알아서 폭을 좁혀 자동으로 맞춰줍니다(이 설정과 상관없이 항상 그렇습니다).
      datasets: [{
        label, data: entries.map((e) => e[1]), backgroundColor: ACCENT, borderRadius: 6,
        maxBarThickness: 56, barPercentage: 0.5, categoryPercentage: 0.7,
      }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        datalabels: { anchor: "end", align: "top", offset: 4, color: LABEL_COLOR, font: LABEL_FONT },
      },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0, font: { size: 12 } } },
        x: { ticks: { font: { size: 12 } } },
      },
    },
  });
}

function renderPeriodStrip(rows) {
  const strip = document.getElementById("period-strip");
  if (rows.length === 0) {
    strip.innerHTML = `<p class="text-sm text-muted">데이터가 없습니다.</p>`;
    return;
  }
  strip.innerHTML = rows.map((row) => `
    <div class="period-card">
      <div class="period-label">${row["기간"]}</div>
      <div class="period-count">${row["신규가입"]}명</div>
      <div class="period-detail">남 ${row["남"]} · 여 ${row["여"]}</div>
      <div class="period-detail">일반 ${row["일반"]} · 차상위 ${row["차상위"]} · 수급자 ${row["수급자"]}</div>
    </div>
  `).join("");
}

let periodRowsCache = [];
let currentPeriod = "월";

async function loadPeriod(period) {
  currentPeriod = period;
  document.querySelectorAll(".period-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.period === period);
  });
  document.getElementById("date-filter-wrap").classList.toggle("hidden", period !== "일");

  try {
    periodRowsCache = await apiJson(`/api/stats/period/${encodeURIComponent(period)}`);
    applyDateFilter();
  } catch (e) {
    document.getElementById("period-strip").innerHTML =
      `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>${e.message}</span></div>`;
    lucide.createIcons();
  }
}

function applyDateFilter() {
  if (currentPeriod !== "일") {
    renderPeriodStrip(periodRowsCache);
    return;
  }
  const picked = document.getElementById("date-filter").value;
  const rows = picked ? periodRowsCache.filter((r) => r["기간"] === picked) : periodRowsCache;
  renderPeriodStrip(rows);
}

document.querySelectorAll(".period-tab").forEach((btn) => {
  btn.addEventListener("click", () => loadPeriod(btn.dataset.period));
});
document.getElementById("date-filter").addEventListener("change", applyDateFilter);

function setAsOfCaption(elId) {
  const el = document.getElementById(elId);
  if (!el) return;
  const now = new Date();
  el.textContent = `현재 기준: ${now.toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" })}`;
}

async function loadStats() {
  setAsOfCaption("stats-asof");
  try {
    const [summary, charts] = await Promise.all([
      apiJson("/api/stats/summary"),
      apiJson("/api/stats/charts"),
    ]);

    document.getElementById("metric-grid").innerHTML = `
      <div class="card text-center"><div class="text-xl font-bold text-primary-dark">${summary.total}명</div><div class="text-xs text-muted mt-1">전체 회원수</div></div>
      <div class="card text-center"><div class="text-xl font-bold text-primary-dark">${summary.today}명</div><div class="text-xs text-muted mt-1">오늘 신규가입</div></div>
      <div class="card text-center"><div class="text-xl font-bold text-primary-dark">${summary.this_month}명</div><div class="text-xs text-muted mt-1">이번 달 신규가입</div></div>
      <div class="card text-center"><div class="text-xl font-bold text-primary-dark">${summary.male} / ${summary.female}</div><div class="text-xs text-muted mt-1">남 / 여</div></div>
      <div class="card text-center"><div class="text-xl font-bold text-primary-dark">${summary.recipient}명</div><div class="text-xs text-muted mt-1">수급자</div></div>
    `;

    barChart("chart-monthly", charts.monthly_trend, "신규가입");
    pieChart("chart-gender", charts.gender_distribution, "인원");
    pieChart("chart-welfare-type", charts.welfare_type_distribution, "인원");
    pieChart("chart-age", charts.age_distribution, "인원");
    pieChart("chart-household", charts.household_type_distribution, "인원");
    pieChart("chart-disability", charts.disability_distribution, "인원");
    pieChart("chart-illness", charts.illness_distribution, "인원");
    pieChart("chart-career", charts.career_distribution, "인원");
    pieChart("chart-join-route", charts.join_route_distribution, "인원");

    await loadPeriod("월");
  } catch (e) {
    document.getElementById("stats-error").innerHTML =
      `<div class="alert alert-danger"><i data-lucide="alert-circle" class="w-4 h-4 mt-0.5"></i><span>통계를 불러오지 못했습니다: ${e.message}</span></div>`;
    lucide.createIcons();
  }
}
loadStats();
