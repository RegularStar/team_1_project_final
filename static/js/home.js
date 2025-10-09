(function () {
  const API_ENDPOINT = "/api/certificates/rankings/?limit=10";
  const datasets = {
    hot: [],
    pass: [],
    pass_low: [],
    hard: [],
    easy: [],
  };
  let isLoaded = false;
  let hasError = false;

  const listRoot = document.getElementById("list");
  if (!listRoot) {
    return;
  }

  const tabs = {
    hot: document.getElementById("tab-hot"),
    pass: document.getElementById("tab-pass"),
    pass_low: document.getElementById("tab-pass-low"),
    hard: document.getElementById("tab-hard"),
    easy: document.getElementById("tab-easy"),
  };

  let activeKey = "hot";

  const TOOLTIP_TEXTS = {
    "difficulty-scale": `난이도 안내\n1. 아주 쉬움. 기초 개념 위주라 단기간 준비로 누구나 합격 가능한 수준.\n2. 쉬움. 기본 지식이 있으면 무난히 도전할 수 있는 입문 수준.\n3. 보통. 일정한 학습이 필요하지만 꾸준히 준비하면 충분히 합격 가능한 수준.\n4. 다소 어려움. 이론과 실무를 균형 있게 요구하며, 준비 기간이 다소 긴 수준.\n5. 중상 난이도. 전공지식과 응용력이 필요해 체계적 학습이 요구되는 수준.\n6. 어려움. 합격률이 낮고 심화 학습이 필요해 전공자도 부담되는 수준.\n7. 매우 어려움. 방대한 범위와 높은 난이도로 전공자도 장기간 학습이 필수인 수준.\n8. 극히 어려움. 전문성·응용력·실무 경험이 모두 요구되는 최상위권 자격 수준.\n9. 최상 난이도. 전문지식과 실무를 총망라하며, 합격자가 극소수에 불과한 수준.\n10. 극한 난이도. 수년간 전념해도 합격을 장담할 수 없는, 최고 난도의 자격 수준.`
  };

  function badgeClass(rate) {
    if (rate == null || Number.isNaN(rate)) return "";
    if (rate >= 65) return "ok";
    if (rate <= 15) return "danger";
    return "warn";
  }

  function escapeAttr(text) {
    if (!text) return "";
    return String(text).replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderMetric(metric, seen) {
    if (!metric || !metric.value || metric.value === "—") {
      return "";
    }
    const tooltipKey = metric.tooltipKey && TOOLTIP_TEXTS[metric.tooltipKey];
    const tooltipText = tooltipKey || metric.tooltip;
    const tooltipAttr = tooltipText ? ` data-tip="${escapeAttr(tooltipText)}"` : "";
    const tooltipButton = tooltipText
      ? `<span class="metric-tip" aria-hidden="true">!</span>`
      : "";
    const rateClass = metric.label && metric.label.includes("합격률")
      ? badgeClass(Number(metric.raw))
      : "";
    const labelKey = (metric.label || "") + (metric.tooltipKey || "") + (metric.tooltip || "");
    if (seen && labelKey && seen.has(labelKey)) {
      return "";
    }
    if (seen && labelKey) {
      seen.add(labelKey);
    }
    return `<span class="metric-info"${tooltipAttr}>${tooltipButton}<span>${metric.label ?? ""}${metric.label ? " " : ""}<b class="${rateClass}">${metric.value}</b></span></span>`;
  }

  function makeRow(item, contextKey) {
    const row = document.createElement("div");
    row.className = "row";
    const slugSource = item.slug || item.id || item.name;
    const link = slugSource
      ? `/certificates/${encodeURIComponent(String(slugSource).toLowerCase())}/`
      : "#";
    const ratingDisplay = item.rating != null ? item.rating : "—";
    const metricParts = [];
    const seen = new Set();
    const difficultyMetric = item.difficulty ? { ...item.difficulty, value: ratingDisplay !== "—" ? `${ratingDisplay}/10` : null } : null;

    if (contextKey === "hard" || contextKey === "easy") {
      const primary = renderMetric(item.metric, seen);
      if (primary) metricParts.push(primary);
      const secondary = renderMetric(item.secondary, seen);
      if (secondary) metricParts.push(secondary);
      const tertiary = renderMetric(item.tertiary, seen);
      if (tertiary) metricParts.push(tertiary);
      const difficulty = renderMetric(difficultyMetric, seen);
      if (difficulty) metricParts.unshift(difficulty);
    } else {
      const primary = renderMetric(item.metric, seen);
      if (primary) metricParts.push(primary);
      const secondary = renderMetric(item.secondary, seen);
      if (secondary) metricParts.push(secondary);
      const tertiary = renderMetric(item.tertiary, seen);
      if (tertiary) metricParts.push(tertiary);
      const difficulty = renderMetric(difficultyMetric, seen);
      if (difficulty) metricParts.push(difficulty);
    }
    if (item.tag) {
      metricParts.push(`<span class="tag-text">${item.tag}</span>`);
    }
    row.innerHTML = `
      <div class="left">
        <div class="rank">#${item.rank}</div>
        <div>
          <div class="title" title="${item.name}">${item.name}</div>
          <div class="meta">
            ${metricParts.join("\n")}
          </div>
        </div>
      </div>
      <div class="right">
        <a class="detail-btn" href="${link}">상세 보기</a>
      </div>
    `;
    return row;
  }

  function render() {
    if (hasError) {
      listRoot.innerHTML = '<div class="state error">랭킹 정보를 불러오지 못했어요.</div>';
      return;
    }

    if (!isLoaded) {
      listRoot.innerHTML = '<div class="state">랭킹을 불러오는 중...</div>';
      return;
    }

    listRoot.innerHTML = "";
    const items = (datasets[activeKey] || []).slice(0, 10);
    if (!items.length) {
      listRoot.innerHTML = '<div class="state empty">표시할 랭킹이 없어요.</div>';
      return;
    }
    items.forEach((item) => listRoot.appendChild(makeRow(item, activeKey)));
  }

  function selectTab(key) {
    activeKey = key;
    Object.entries(tabs).forEach(([name, element]) => {
      if (!element) return;
      element.setAttribute("aria-selected", name === key ? "true" : "false");
    });
    render();
  }

  Object.entries(tabs).forEach(([name, element]) => {
    if (!element) return;
    element.addEventListener("click", () => selectTab(name));
  });

  async function loadRankings() {
    render();
    try {
      const response = await fetch(API_ENDPOINT, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      const payload = await response.json();
      Object.assign(datasets, payload);
      hasError = false;
    } catch (error) {
      console.error("Failed to load rankings", error);
      hasError = true;
    }
    isLoaded = true;
    render();
  }

  loadRankings();
})();
