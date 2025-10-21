(function () {
<<<<<<< HEAD
  const API_ENDPOINT = "/api/certificates/rankings/?limit=10";
=======
  const MAX_VISIBLE = 30;
  const PAGE_SIZE = 10;
  const API_ENDPOINT = `/api/certificates/rankings/?limit=${MAX_VISIBLE}`;
>>>>>>> seil2
  const datasets = {
    hot: [],
    pass: [],
    pass_low: [],
<<<<<<< HEAD
    hard: [],
    easy: [],
  };
  let isLoaded = false;
  let hasError = false;
=======
    hard_official: [],
    easy_official: [],
    hard_user: [],
    easy_user: [],
    difficulty_gap: [],
    hell_cards: [],
    applicant_surge: [],
    stage_pass_gap: [],
    insight_groups: [],
    badge_groups: [],
  };
  const MAX_INSIGHT_ITEMS = 8;
  const DEFAULT_RANK_TOOLTIP = "차수별 통계는 최근 공개된 데이터를 기준으로 했어요. 응시자 수 1,000명 이상만 보여줘요.";
  let isLoaded = false;
  let hasError = false;
  let visibleCount = PAGE_SIZE;
>>>>>>> seil2

  const listRoot = document.getElementById("list");
  if (!listRoot) {
    return;
  }
<<<<<<< HEAD
=======
  const badgeList = document.getElementById("badge-list");
  const badgeStatus = document.getElementById("badge-status");
  const badgeSelect = document.getElementById("badge-filter");
  const insightTrack = document.getElementById("insight-track");
  const insightStatus = document.getElementById("insight-status");
  const insightDots = document.getElementById("insight-dots");
  const insightPrev = document.querySelector('[data-role="insight-prev"]');
  const insightNext = document.querySelector('[data-role="insight-next"]');
  const insightNav = document.getElementById("insight-nav");
  const insightCarousel = document.querySelector(".insight-carousel");
  const loadMoreButton = document.getElementById("rank-load-more");
  const loadMoreContainer = loadMoreButton ? loadMoreButton.parentElement : null;

  const rankTip = document.querySelector('[data-role="rank-tooltip"]');
  if (rankTip) {
    rankTip.setAttribute("data-tip", rankTip.getAttribute("data-tip") || DEFAULT_RANK_TOOLTIP);
  }
>>>>>>> seil2

  const tabs = {
    hot: document.getElementById("tab-hot"),
    pass: document.getElementById("tab-pass"),
    pass_low: document.getElementById("tab-pass-low"),
<<<<<<< HEAD
    hard: document.getElementById("tab-hard"),
    easy: document.getElementById("tab-easy"),
  };

  let activeKey = "hot";
=======
    hard_official: document.getElementById("tab-hard-official"),
    easy_official: document.getElementById("tab-easy-official"),
    hard_user: document.getElementById("tab-hard-user"),
    easy_user: document.getElementById("tab-easy-user"),
  };

  let activeKey = "hot";
  const difficultyContexts = new Set(["hard_official", "easy_official", "hard_user", "easy_user"]);
  let insightSlides = [];
  let activeInsightIndex = 0;
  let activeBadgeKey = null;
>>>>>>> seil2

  const TOOLTIP_TEXTS = {
    "difficulty-scale": `난이도 안내\n1. 아주 쉬움. 기초 개념 위주라 단기간 준비로 누구나 합격 가능한 수준.\n2. 쉬움. 기본 지식이 있으면 무난히 도전할 수 있는 입문 수준.\n3. 보통. 일정한 학습이 필요하지만 꾸준히 준비하면 충분히 합격 가능한 수준.\n4. 다소 어려움. 이론과 실무를 균형 있게 요구하며, 준비 기간이 다소 긴 수준.\n5. 중상 난이도. 전공지식과 응용력이 필요해 체계적 학습이 요구되는 수준.\n6. 어려움. 합격률이 낮고 심화 학습이 필요해 전공자도 부담되는 수준.\n7. 매우 어려움. 방대한 범위와 높은 난이도로 전공자도 장기간 학습이 필수인 수준.\n8. 극히 어려움. 전문성·응용력·실무 경험이 모두 요구되는 최상위권 자격 수준.\n9. 최상 난이도. 전문지식과 실무를 총망라하며, 합격자가 극소수에 불과한 수준.\n10. 극한 난이도. 수년간 전념해도 합격을 장담할 수 없는, 최고 난도의 자격 수준.`
  };

<<<<<<< HEAD
=======
  const difficultyLegend = document.querySelector('[data-role="difficulty-legend"]');
  if (difficultyLegend) {
    difficultyLegend.setAttribute("data-tip", TOOLTIP_TEXTS["difficulty-scale"]);
  }

>>>>>>> seil2
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

<<<<<<< HEAD
  function renderMetric(metric, seen) {
    if (!metric || !metric.value || metric.value === "—") {
=======
  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatNumber(value) {
    if (value == null || Number.isNaN(Number(value))) {
      return "―";
    }
    return Number(value).toLocaleString();
  }

  function formatRate(value) {
    if (value == null || Number.isNaN(Number(value))) {
      return "―";
    }
    return `${Number(value).toFixed(1)}%`;
  }

  function formatYearDisplay(value, fallback = "최근 통계") {
    if (value == null || value === "") {
      return fallback;
    }
    const match = String(value).match(/\d{4}/);
    if (match) {
      return `${match[0]}년`;
    }
    const trimmed = String(value).trim();
    return trimmed || fallback;
  }

  function formatStageLabelText(value) {
    if (value == null || value === "") {
      return "";
    }
    let text = String(value).trim();
    if (!text) {
      return "";
    }
    if (/^\d+$/.test(text)) {
      return `${text}차`;
    }
    if (/^\d+차$/.test(text)) {
      return text;
    }
    return text;
  }

  function certificateLink(item) {
    if (!item) {
      return "#";
    }
    const slugSource =
      typeof item.slug === "string" && item.slug.trim()
        ? item.slug.trim()
        : item.id != null
          ? String(item.id)
          : "";
    if (!slugSource) {
      return "#";
    }
    return `/certificates/${encodeURIComponent(slugSource)}/`;
  }

  function renderMetric(metric, seen) {
    if (!metric) {
      return "";
    }
    const value = metric.value;
    if (value == null) {
>>>>>>> seil2
      return "";
    }
    const tooltipKey = metric.tooltipKey && TOOLTIP_TEXTS[metric.tooltipKey];
    const tooltipText = tooltipKey || metric.tooltip;
<<<<<<< HEAD
    const tooltipAttr = tooltipText ? ` data-tip="${escapeAttr(tooltipText)}"` : "";
    const tooltipButton = tooltipText
      ? `<span class="metric-tip" aria-hidden="true">!</span>`
=======
    const useInfoButton = Boolean(metric.infoButton && tooltipText);
    const tooltipAttr = tooltipText
      ? useInfoButton
        ? ` data-tip="${escapeAttr(tooltipText)}"`
        : ` title="${escapeAttr(tooltipText)}"`
>>>>>>> seil2
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
<<<<<<< HEAD
    return `<span class="metric-info"${tooltipAttr}>${tooltipButton}<span>${metric.label ?? ""}${metric.label ? " " : ""}<b class="${rateClass}">${metric.value}</b></span></span>`;
  }

  function makeRow(item, contextKey) {
    const row = document.createElement("div");
    row.className = "row";
=======
    const labelText = metric.label ? `${escapeHtml(metric.label)} ` : "";
    const classAttr = rateClass ? ` class="${rateClass}"` : "";
    const infoButton = useInfoButton
      ? `<button type="button" class="metric-tip" aria-label="${escapeAttr(
          metric.label ? `${metric.label} 안내 보기` : "도움말 보기",
        )}" aria-expanded="false">!</button>`
      : "";
    return `<span class="metric-info"${tooltipAttr}>${infoButton}<span>${labelText}<b${classAttr}>${escapeHtml(
      value,
    )}</b></span></span>`;
  }

  function stageText(item) {
    if (!item || item.stage_label == null) {
      return "";
    }
    if (item.stage_label === "") {
      return "";
    }
    if (item.is_overall_stage) {
      return "전체";
    }
    let text = String(item.stage_label);
    const numericStage = Number(item.stage);
    if (/^\d+$/.test(text)) {
      text = `${text}차`;
    } else if (
      Number.isFinite(numericStage) &&
      numericStage !== 10 &&
      text === String(numericStage) &&
      !/차$/.test(text)
    ) {
      text = `${numericStage}차`;
    }
    return text;
  }

  function closeAllTooltips(except) {
    const openTips = document.querySelectorAll("[data-tip].is-tip-open");
    openTips.forEach((node) => {
      if (node === except) {
        return;
      }
      node.classList.remove("is-tip-open");
      const button = node.querySelector(".metric-tip");
      if (button) {
        button.setAttribute("aria-expanded", "false");
      }
    });
  }

  let tooltipsInitialized = false;

  function setupTooltipInteractions() {
    if (tooltipsInitialized) {
      return;
    }
    tooltipsInitialized = true;

    document.addEventListener("click", (event) => {
      const trigger = event.target.closest(".metric-tip");
      if (trigger) {
        const container = trigger.closest("[data-tip]");
        if (!container) {
          return;
        }
        const willOpen = !container.classList.contains("is-tip-open");
        if (willOpen) {
          closeAllTooltips(container);
        } else {
          closeAllTooltips();
        }
        container.classList.toggle("is-tip-open", willOpen);
        trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
        event.preventDefault();
        event.stopPropagation();
        return;
      }

      if (!event.target.closest("[data-tip]")) {
        closeAllTooltips();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeAllTooltips();
        return;
      }

      if (event.key === " " || event.key === "Enter") {
        const active = document.activeElement;
        if (active && active.classList && active.classList.contains("metric-tip")) {
          event.preventDefault();
          active.click();
        }
      }
    });
  }

  setupTooltipInteractions();

  function setupTabTooltips() {
    const tabButtons = document.querySelectorAll(".tab[data-role=\"tab-tip\"]");
    tabButtons.forEach((button) => {
      if (button.classList.contains("tab--with-tip")) {
        return;
      }
      const tip = button.getAttribute("data-tip");
      if (!tip) {
        return;
      }
      const labelText = button.textContent.trim();
      button.classList.add("tab--with-tip");
      const tooltipContainer = document.createElement("span");
      tooltipContainer.className = "metric-info tab-tip";
      tooltipContainer.setAttribute("data-tip", tip);
      const trigger = document.createElement("span");
      trigger.className = "metric-tip";
      trigger.setAttribute("role", "button");
      trigger.setAttribute("tabindex", "0");
      trigger.setAttribute("aria-expanded", "false");
      trigger.setAttribute("aria-label", `${labelText} 안내 보기`);
      trigger.textContent = "!";
      tooltipContainer.appendChild(trigger);
      button.insertAdjacentElement("afterbegin", tooltipContainer);
    });
  }

  setupTabTooltips();

  function makeRow(item, contextKey) {
    const row = document.createElement("div");
    const isHell = Boolean(item.is_hell);
    row.className = "row";
    if (isHell) {
      row.classList.add("row--hell");
    }
>>>>>>> seil2
    const slugSource = item.id != null ? item.id : (item.slug || item.name);
    const link = slugSource
      ? `/certificates/${encodeURIComponent(String(slugSource).toLowerCase())}/`
      : "#";
<<<<<<< HEAD
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
=======
    const metricParts = [];
    const seen = new Set();
    const isDifficultyContext = difficultyContexts.has(contextKey);

    const pushMetric = (metric) => {
      const rendered = renderMetric(metric, seen);
      if (rendered) {
        metricParts.push(rendered);
      }
    };

    if (isDifficultyContext) {
      pushMetric(item.metric);
      pushMetric(item.secondary);
    } else {
      pushMetric(item.metric);
      pushMetric(item.secondary);
      pushMetric(item.tertiary);
    }

    let tags = Array.isArray(item.tags) ? item.tags.slice(0, 10) : [];
    if (!tags.length && item.tag) {
      tags = [item.tag];
    }
    const hasTags = tags.length > 0;
    const chips = hasTags
      ? tags.map((tag) => `<span class="tag-chip">${escapeHtml(tag)}</span>`).join("")
      : "";
    const tagContent = hasTags
      ? `<span class="tag-chip-list">${chips}</span>`
      : '<span class="tag-chip-empty">아직 등록된 관련 태그가 없어요.</span>';
    const tagsBlock = `<div class="tag-block${hasTags ? "" : " tag-block--empty"}"><span class="tag-chip-label">관련 태그:</span>${tagContent}</div>`;
    const stageLabelText = !isDifficultyContext ? stageText(item) : "";
    let stageMarkup = "";
    if (stageLabelText) {
      const stageClasses = ["title-stage"];
      if (item.is_overall_stage) {
        stageClasses.push("title-stage--overall");
      }
      stageMarkup = `<span class="${stageClasses.join(" ")}">${escapeHtml(stageLabelText)}</span>`;
    }
    const badgeLabels = [];
    if (item.is_hell) {
      badgeLabels.push('<span class="title-hell">지옥의 자격증</span>');
    }
    if (item.is_elite_profession) {
      badgeLabels.push('<span class="title-elite">8대 전문직</span>');
    }
    const badgeMarkup = badgeLabels.length ? badgeLabels.join("") : "";
    const nameAttr = escapeAttr(item.name);
    const nameText = escapeHtml(item.name);
    const nameMarkup = `<span class="title-name" title="${nameAttr}">${nameText}</span>`;
>>>>>>> seil2
    row.innerHTML = `
      <div class="left">
        <div class="rank">#${item.rank}</div>
        <div>
<<<<<<< HEAD
          <div class="title" title="${item.name}">${item.name}</div>
          <div class="meta">
            ${metricParts.join("\n")}
          </div>
=======
          <div class="title-block">
            <div class="title">
              ${nameMarkup}${stageMarkup}${badgeMarkup}
            </div>
          </div>
          <div class="meta">
            ${metricParts.join("\n")}
          </div>
          ${tagsBlock}
>>>>>>> seil2
        </div>
      </div>
      <div class="right">
        <a class="detail-btn" href="${link}">상세 보기</a>
      </div>
    `;
    return row;
  }

<<<<<<< HEAD
  function render() {
    if (hasError) {
      listRoot.innerHTML = '<div class="state error">랭킹 정보를 불러오지 못했어요.</div>';
=======
  function updateInsightStatus(message) {
    if (!insightStatus) {
      return;
    }
    if (!message) {
      insightStatus.textContent = "";
      insightStatus.hidden = true;
      return;
    }
    insightStatus.textContent = message;
    insightStatus.hidden = false;
  }

  function createDifficultyGapCard(item) {
    const card = document.createElement("a");
    card.className = "insight-card insight-card--link";
    card.href = certificateLink(item);
    card.setAttribute("aria-label", `${item.name} 상세 페이지로 이동`);
    const official = item.rating != null ? `${item.rating}/10` : "―";
    const userValue =
      item.user_difficulty != null ? `${Number(item.user_difficulty).toFixed(1)}/10.0` : "―";
    const userCount = item.user_difficulty_count || 0;
    const userDisplay = userCount ? `${userValue} (${formatNumber(userCount)}명 평가)` : userValue;
    const diffDisplay =
      item.difference != null ? `${Number(item.difference).toFixed(1)}점 차이` : null;
    const diffSigned = Number(item.difference_signed);
    let perceptionMessage = "";
    if (Number.isFinite(diffSigned) && Math.abs(diffSigned) >= 0.1) {
      const absValue = Math.abs(diffSigned).toFixed(1);
      perceptionMessage =
        diffSigned > 0
          ? `실제 응시자들이 ${absValue}점 더 어렵게 느꼈어요.`
          : `실제 응시자들이 ${absValue}점 더 쉽게 느꼈어요.`;
    } else {
      perceptionMessage = "체감 난이도는 공식 난이도와 거의 같았어요.";
    }
    card.innerHTML = `
      <header class="insight-card__header">
        <h4 class="insight-card__title">
          <span class="insight-card__name">${escapeHtml(item.name)}</span>
        </h4>
      </header>
      <div class="insight-card__metrics">
        <div><span class="insight-card__metric-label">공식 난이도</span><span class="insight-card__metric-value">${escapeHtml(official)}</span></div>
        <div><span class="insight-card__metric-label">사용자 난이도</span><span class="insight-card__metric-value">${escapeHtml(userDisplay)}</span></div>
        ${
          diffDisplay
            ? `<div><span class="insight-card__metric-label">체감 차이</span><span class="insight-card__difference">${escapeHtml(diffDisplay)}</span></div>`
            : ""
        }
      </div>
      <p class="insight-card__note">${escapeHtml(perceptionMessage)}</p>
    `;
    return card;
  }

  function createApplicantSurgeCard(item) {
    const card = document.createElement("a");
    card.className = "insight-card insight-card--link";
    card.href = certificateLink(item);
    card.setAttribute("aria-label", `${item.name} 상세 페이지로 이동`);
    const stageLabelText = formatStageLabelText(item.stage_label);
    const stageKey = Number(item.stage_order) === 10 || (!item.stage_key && Number(item.stage_label) === 10) || (item.stage_key && item.stage_key === 'total') ? 'total' : item.stage_key;
    const metricLabel = item.participant_source === "registered" ? "접수 인원" : "응시자 수";
    const recentLabel = item.recent_year_label || formatYearDisplay(item.recent_year, "최근");
    const previousLabel =
      item.previous_year_label || formatYearDisplay(item.previous_year, "이전");
    const recentValue =
      item.recent_applicants != null ? `${formatNumber(item.recent_applicants)}명` : "―";
    const previousValue =
      item.previous_applicants != null ? `${formatNumber(item.previous_applicants)}명` : "―";
    const rawDifference = Number(item.difference);
    const diffValue = Number.isFinite(rawDifference) ? rawDifference : 0;
    const diffAbs = Math.abs(diffValue);
    const rawRatio = Number(item.difference_ratio);
    const ratioValue = Number.isFinite(rawRatio) ? rawRatio : null;
    let diffDisplay;
    let diffClass = "insight-card__difference";
    if (diffValue > 0) {
      diffDisplay = `+${formatNumber(diffAbs)}명`;
      diffClass += " insight-card__difference--up";
    } else if (diffValue < 0) {
      diffDisplay = `-${formatNumber(diffAbs)}명`;
      diffClass += " insight-card__difference--down";
    } else {
      diffDisplay = "변화 없음";
    }
    if (ratioValue != null && diffValue !== 0) {
      const ratioSign = ratioValue > 0 ? "+" : "";
      diffDisplay = `${diffDisplay} (${ratioSign}${ratioValue.toFixed(1)}%)`;
    }
    let changeMessage = "";
    if (diffValue > 0) {
      changeMessage = `${recentLabel} 응시자 수가 ${formatNumber(diffAbs)}명 더 많아졌어요.`;
    } else if (diffValue < 0) {
      changeMessage = `${recentLabel} 응시자 수가 ${formatNumber(diffAbs)}명 줄어들었어요.`;
    } else {
      changeMessage = "응시자 수 변동이 거의 없었어요.";
    }
    card.innerHTML = `
      <header class="insight-card__header">
        <h4 class="insight-card__title">
          <span class="insight-card__name">${escapeHtml(item.name)}</span>
          ${stageLabelText ? `<span class="insight-card__stage ${stageKey === 'total' ? 'insight-card__stage--overall' : ''}">${escapeHtml(stageLabelText)}</span>` : ""}
        </h4>
      </header>
      <div class="insight-card__metrics">
        <div><span class="insight-card__metric-label">${escapeHtml(
          `${recentLabel} ${metricLabel}`,
        )}</span><span class="insight-card__metric-value">${escapeHtml(recentValue)}</span></div>
        <div><span class="insight-card__metric-label">${escapeHtml(
          `${previousLabel} ${metricLabel}`,
        )}</span><span class="insight-card__metric-value">${escapeHtml(previousValue)}</span></div>
        <div><span class="insight-card__metric-label">응시자수 변화</span><span class="${diffClass}">${escapeHtml(diffDisplay)}</span></div>
      </div>
      <p class="insight-card__note">${escapeHtml(changeMessage)}</p>
    `;
    return card;
  }

  function createStagePassGapCard(item) {
    const card = document.createElement("a");
    card.className = "insight-card insight-card--link";
    card.href = certificateLink(item);
    card.setAttribute("aria-label", `${item.name} 상세 페이지로 이동`);
    const stage1Label = formatStageLabelText(item.stage1_label || "1차");
    const stage2Label = formatStageLabelText(item.stage2_label || "2차");
    const stage1Rate =
      item.stage1_pass_rate != null ? formatRate(item.stage1_pass_rate) : "―";
    const stage2Rate =
      item.stage2_pass_rate != null ? formatRate(item.stage2_pass_rate) : "―";
    const yearLabel = item.year_label || formatYearDisplay(item.year, "최근 통계");
    const stage1RateNumber = Number(item.stage1_pass_rate);
    const stage2RateNumber = Number(item.stage2_pass_rate);
    let differenceMessage = "합격률 차이가 거의 없어요.";
    if (
      Number.isFinite(stage1RateNumber) &&
      Number.isFinite(stage2RateNumber) &&
      stage1RateNumber !== stage2RateNumber
    ) {
      const isStage1Higher = stage1RateNumber > stage2RateNumber;
      const higherLabel = isStage1Higher ? stage1Label : stage2Label;
      const diffValue = Math.abs(stage1RateNumber - stage2RateNumber);
      differenceMessage = `${higherLabel}가 ${diffValue.toFixed(1)}%p 높아요`;
    }
    card.innerHTML = `
      <header class="insight-card__header">
        <h4 class="insight-card__title">
          <span class="insight-card__name">${escapeHtml(item.name)}</span>
        </h4>
      </header>
      <div class="insight-card__metrics">
        <div><span class="insight-card__metric-label">기준년도</span><span class="insight-card__metric-value">${escapeHtml(yearLabel)}</span></div>
        <div><span class="insight-card__metric-label">${escapeHtml(`${stage1Label} 합격률`)}</span><span class="insight-card__metric-value">${escapeHtml(stage1Rate)}</span></div>
      <div><span class="insight-card__metric-label">${escapeHtml(`${stage2Label} 합격률`)}</span><span class="insight-card__metric-value">${escapeHtml(stage2Rate)}</span></div>
      </div>
      <p class="insight-card__note">${escapeHtml(differenceMessage)}</p>
    `;
    return card;
  }

  function createInsightCard(groupKey, item) {
    if (!item) {
      return null;
    }
    if (groupKey === "applicant_surge") {
      return createApplicantSurgeCard(item);
    }
    if (groupKey === "stage_pass_gap") {
      return createStagePassGapCard(item);
    }
    return createDifficultyGapCard(item);
  }

  function buildInsightSlide(group, index) {
    const slide = document.createElement("section");
    slide.className = "insight-slide";
    slide.dataset.insightKey = group.key || `insight-${index}`;
    slide.setAttribute("role", "group");
    slide.setAttribute("aria-hidden", "true");
    const header = document.createElement("header");
    header.className = "insight-slide__head";
    const title = document.createElement("h4");
    title.className = "insight-slide__title";
    title.textContent = group.title || `인사이트 ${index + 1}`;
    const heading = document.createElement("div");
    heading.className = "insight-slide__heading";
    heading.appendChild(title);
    if (group.subtitle) {
      const subtitle = document.createElement("p");
      subtitle.className = "insight-slide__subtitle";
      subtitle.textContent = group.subtitle;
      heading.appendChild(subtitle);
    }
    header.appendChild(heading);
    slide.appendChild(header);
    const cardsContainer = document.createElement("div");
    cardsContainer.className = "insight-cards insight-cards--carousel";
    const items = Array.isArray(group.items) ? group.items.slice(0, MAX_INSIGHT_ITEMS) : [];
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "insight-empty";
      empty.textContent = "아직 해당 통계를 준비 중이에요.";
      cardsContainer.appendChild(empty);
    } else {
      items.forEach((item) => {
        const card = createInsightCard(group.key, item);
        if (card) {
          cardsContainer.appendChild(card);
        }
      });
    }
    slide.appendChild(cardsContainer);
    return slide;
  }

  function setActiveInsight(index) {
    if (!insightSlides.length) {
      activeInsightIndex = 0;
      updateInsightNavState();
      attachInsightNav();
      return;
    }
    const clamped = Math.max(0, Math.min(index, insightSlides.length - 1));
    activeInsightIndex = clamped;
    insightSlides.forEach((slide, idx) => {
      const isActive = idx === clamped;
      slide.classList.toggle("is-active", isActive);
      slide.setAttribute("aria-hidden", isActive ? "false" : "true");
    });
    if (insightDots) {
      Array.from(insightDots.children).forEach((dot, idx) => {
        const isActive = idx === clamped;
        dot.classList.toggle("is-active", isActive);
        dot.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    }
    updateInsightNavState();
    attachInsightNav();
  }

  function attachInsightNav() {
    if (!insightNav) {
      return;
    }
    const total = insightSlides.length;
    const shouldShowNav = total > 1;
    if (!shouldShowNav) {
      insightNav.hidden = true;
      if (insightCarousel && insightNav.parentElement !== insightCarousel) {
        insightCarousel.appendChild(insightNav);
      }
      return;
    }
    const activeSlide = insightSlides[activeInsightIndex];
    if (!activeSlide) {
      insightNav.hidden = true;
      if (insightCarousel && insightNav.parentElement !== insightCarousel) {
        insightCarousel.appendChild(insightNav);
      }
      return;
    }
    const head = activeSlide.querySelector(".insight-slide__head");
    if (!head) {
      insightNav.hidden = true;
      if (insightCarousel && insightNav.parentElement !== insightCarousel) {
        insightCarousel.appendChild(insightNav);
      }
      return;
    }
    if (insightNav.parentElement !== head) {
      head.appendChild(insightNav);
    }
    insightNav.hidden = false;
  }

  function updateInsightNavState() {
    const total = insightSlides.length;
    const hasSlides = total > 0;
    if (insightDots) {
      insightDots.hidden = total <= 1;
    }
    if (insightPrev) {
      insightPrev.disabled = !hasSlides || activeInsightIndex <= 0;
    }
    if (insightNext) {
      insightNext.disabled = !hasSlides || activeInsightIndex >= total - 1;
    }
  }

  function renderInsights() {
    if (!insightTrack) {
      return;
    }
    if (hasError) {
      insightTrack.innerHTML = "";
      insightSlides = [];
      if (insightDots) {
        insightDots.innerHTML = "";
      }
      updateInsightStatus("데이터를 불러오지 못했어요.");
      updateInsightNavState();
      attachInsightNav();
      return;
    }
    if (!isLoaded) {
      insightTrack.innerHTML = "";
      insightSlides = [];
      if (insightDots) {
        insightDots.innerHTML = "";
      }
      updateInsightStatus("데이터를 불러오는 중이에요.");
      updateInsightNavState();
      attachInsightNav();
      return;
    }
    const groups = Array.isArray(datasets.insight_groups) ? datasets.insight_groups : [];
    insightTrack.innerHTML = "";
    insightSlides = [];
    if (!groups.length) {
      if (insightDots) {
        insightDots.innerHTML = "";
      }
      updateInsightStatus("새로운 통계를 준비하고 있어요.");
      updateInsightNavState();
      attachInsightNav();
      return;
    }
    updateInsightStatus(null);
    groups.forEach((group, index) => {
      const slide = buildInsightSlide(group, index);
      insightTrack.appendChild(slide);
      insightSlides.push(slide);
    });
    if (insightDots) {
      insightDots.innerHTML = "";
      insightSlides.forEach((_, index) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "insight-dot";
        dot.setAttribute("data-index", String(index));
        const label =
          groups[index] && groups[index].title
            ? `${groups[index].title} 보기`
            : `인사이트 ${index + 1} 보기`;
        dot.setAttribute("aria-label", label);
        dot.addEventListener("click", () => setActiveInsight(index));
        insightDots.appendChild(dot);
      });
    }
    const initialIndex = Math.min(Math.max(activeInsightIndex, 0), insightSlides.length - 1);
    setActiveInsight(initialIndex);
  }

  function populateBadgeOptions(groups) {
    if (!badgeSelect) {
      return;
    }
    const existingValue = badgeSelect.value;
    badgeSelect.innerHTML = "";
    groups.forEach((group, index) => {
      const option = document.createElement("option");
      option.value = group.key;
      option.textContent = group.title || `그룹 ${index + 1}`;
      badgeSelect.appendChild(option);
    });
    const hasGroups = groups.length > 0;
    if (badgeSelect.parentElement) {
      badgeSelect.parentElement.classList.toggle("badge-select--hidden", !hasGroups);
    }
    if (hasGroups) {
      const nextValue = groups.some((group) => group.key === existingValue)
        ? existingValue
        : groups[0].key;
      badgeSelect.value = nextValue;
      activeBadgeKey = nextValue;
    } else {
      activeBadgeKey = null;
    }
    badgeSelect.disabled = !hasGroups || groups.length <= 1;
  }

  function buildBadgeStageStatsMarkup(item) {
    const stageStats = Array.isArray(item.stage_statistics) ? item.stage_statistics.filter(Boolean) : [];
    if (!stageStats.length) {
      return "";
    }
    const parseYear = (value) => {
      if (value == null) {
        return null;
      }
      const match = String(value).match(/\d{4}/);
      return match ? Number(match[0]) : null;
    };
    const latestYear = stageStats.reduce((acc, stat) => {
      const yearNum = parseYear(stat.year);
      if (yearNum == null) {
        return acc;
      }
      if (acc == null || yearNum > acc) {
        return yearNum;
      }
      return acc;
    }, null);
    const statsForDisplay = [...stageStats]
      .filter((stat) => latestYear == null || parseYear(stat.year) === latestYear)
      .sort((a, b) => {
        const stageA = Number(a.stage);
        const stageB = Number(b.stage);
        if (Number.isFinite(stageA) && Number.isFinite(stageB)) {
          return stageA - stageB;
        }
        return String(a.stage_label || "").localeCompare(String(b.stage_label || ""));
      });
    const yearLine =
      latestYear != null ? `<p class="badge-stats__note">기준년도: ${latestYear}년</p>` : "";
    const stageStatsItems = statsForDisplay
      .map((stat) => {
        const numericStage = Number(stat.stage);
        const rawLabel =
          stat.stage_label ||
          (Number.isFinite(numericStage) ? String(numericStage) : null) ||
          "―";
        let stageLabel = rawLabel;
        if (/^\d+$/.test(stageLabel)) {
          stageLabel = `${stageLabel}차`;
        } else if (Number.isFinite(numericStage) && !/차$/.test(stageLabel)) {
          stageLabel = `${numericStage}차`;
        }
        const rateText = stat.pass_rate != null ? formatRate(stat.pass_rate) : "―";
        return `<li>
            <span class="badge-stat__stage">${escapeHtml(stageLabel)}</span>
            <span class="badge-stat__metric">합격률 ${escapeHtml(rateText)}</span>
          </li>`;
      })
      .join("");
    if (!stageStatsItems) {
      return "";
    }
    return `<div class="badge-stats">
        <p class="badge-stats__title">최근 공개된 합격률</p>
        ${yearLine}
        <ul class="badge-stats__list">${stageStatsItems}</ul>
      </div>`;
  }

  function createBadgeCard(item, group) {
    const variant = item.badge_variant || group.variant || "default";
    const ribbonText = item.badge_label || group.ribbon || group.title;
    const card = document.createElement("a");
    card.className = `insight-card insight-card--badge badge-variant-${variant}`;
    card.href = certificateLink(item);
    card.setAttribute("aria-label", `${item.name} 상세 페이지로 이동`);
    const official = item.rating != null ? `${item.rating}/10` : "―";
    const userValue =
      item.user_difficulty != null ? `${Number(item.user_difficulty).toFixed(1)}/10.0` : "―";
    const userCount = item.user_difficulty_count || 0;
    const userDisplay = userCount ? `${userValue} (${formatNumber(userCount)}명 평가)` : userValue;
    const stageStatsMarkup = buildBadgeStageStatsMarkup(item);
    card.innerHTML = `
      ${ribbonText ? `<span class="badge-ribbon badge-ribbon--${variant}">${escapeHtml(ribbonText)}</span>` : ""}
      <h4 class="insight-card__title">
        <span class="insight-card__name">${escapeHtml(item.name)}</span>
      </h4>
      <div class="insight-card__metrics">
        <div><span class="insight-card__metric-label">공식 난이도</span><span class="insight-card__metric-value">${escapeHtml(official)}</span></div>
        <div><span class="insight-card__metric-label">사용자 난이도</span><span class="insight-card__metric-value">${escapeHtml(userDisplay)}</span></div>
      </div>
      ${stageStatsMarkup}
    `;
    return card;
  }

  function renderBadgeCards() {
    if (!badgeList || !badgeStatus) {
      return;
    }
    if (hasError) {
      badgeStatus.textContent = "도장깨기 데이터를 불러오지 못했어요.";
      badgeStatus.hidden = false;
      badgeList.hidden = true;
      badgeList.innerHTML = "";
      return;
    }
    if (!isLoaded) {
      badgeStatus.textContent = "데이터를 불러오는 중이에요.";
      badgeStatus.hidden = false;
      badgeList.hidden = true;
      badgeList.innerHTML = "";
      return;
    }
    const groups = Array.isArray(datasets.badge_groups) ? datasets.badge_groups : [];
    if (!groups.length) {
      badgeStatus.textContent = "표시할 도장깨기 자격증이 아직 없어요.";
      badgeStatus.hidden = false;
      badgeList.hidden = true;
      badgeList.innerHTML = "";
      return;
    }
    if (!activeBadgeKey || !groups.some((group) => group.key === activeBadgeKey)) {
      activeBadgeKey = groups[0].key;
    }
    if (badgeSelect) {
      const currentOptions = Array.from(badgeSelect.options).map((option) => option.value);
      const targetOptions = groups.map((group) => group.key);
      if (currentOptions.length !== targetOptions.length || currentOptions.some((value, index) => value !== targetOptions[index])) {
        populateBadgeOptions(groups);
      } else if (badgeSelect.value !== activeBadgeKey) {
        badgeSelect.value = activeBadgeKey;
      }
      if (badgeSelect.parentElement) {
        badgeSelect.parentElement.classList.toggle("badge-select--hidden", groups.length <= 1);
      }
      badgeSelect.disabled = groups.length <= 1;
    }
    const activeGroup = groups.find((group) => group.key === activeBadgeKey) || groups[0];
    const items = Array.isArray(activeGroup.items) ? activeGroup.items : [];
    if (!items.length) {
      badgeStatus.textContent = "표시할 자격증이 아직 없어요.";
      badgeStatus.hidden = false;
      badgeList.hidden = true;
      badgeList.innerHTML = "";
      return;
    }
    badgeStatus.hidden = true;
    badgeList.hidden = false;
    badgeList.removeAttribute("hidden");
    badgeList.innerHTML = "";
    items.forEach((item) => {
      const card = createBadgeCard(item, activeGroup);
      badgeList.appendChild(card);
    });
  }

  function updateLoadMoreState(items) {
    if (!loadMoreButton) {
      return;
    }
    const total = Array.isArray(items) ? items.length : 0;
    const effectiveVisible = Math.min(MAX_VISIBLE, visibleCount);
    const hasMore = total > effectiveVisible && effectiveVisible < MAX_VISIBLE;
    if (!hasMore) {
      if (loadMoreContainer) {
        loadMoreContainer.style.display = "none";
      }
      loadMoreButton.style.display = "none";
      loadMoreButton.disabled = true;
    } else {
      if (loadMoreContainer) {
        loadMoreContainer.style.display = "flex";
      }
      loadMoreButton.style.display = "inline-flex";
      loadMoreButton.disabled = false;
    }
  }

  function render() {
    if (hasError) {
      listRoot.innerHTML = '<div class="state error">랭킹 정보를 불러오지 못했어요.</div>';
      updateLoadMoreState([]);
>>>>>>> seil2
      return;
    }

    if (!isLoaded) {
      listRoot.innerHTML = '<div class="state">랭킹을 불러오는 중...</div>';
<<<<<<< HEAD
=======
      updateLoadMoreState([]);
>>>>>>> seil2
      return;
    }

    listRoot.innerHTML = "";
<<<<<<< HEAD
    const items = (datasets[activeKey] || []).slice(0, 10);
    if (!items.length) {
      listRoot.innerHTML = '<div class="state empty">표시할 랭킹이 없어요.</div>';
      return;
    }
    items.forEach((item) => listRoot.appendChild(makeRow(item, activeKey)));
  }

  function selectTab(key) {
    activeKey = key;
=======
    const items = datasets[activeKey] || [];
    const allowedVisible = Math.min(MAX_VISIBLE, visibleCount);
    const sliceCount = Math.min(items.length, allowedVisible);
    const visibleItems = items.slice(0, sliceCount);
    if (!visibleItems.length) {
      listRoot.innerHTML = '<div class="state empty">표시할 랭킹이 없어요.</div>';
      updateLoadMoreState(items);
      return;
    }
    visibleItems.forEach((item) => listRoot.appendChild(makeRow(item, activeKey)));
    updateLoadMoreState(items);
  }

  function selectTab(key) {
    closeAllTooltips();
    activeKey = key;
    visibleCount = PAGE_SIZE;
>>>>>>> seil2
    Object.entries(tabs).forEach(([name, element]) => {
      if (!element) return;
      element.setAttribute("aria-selected", name === key ? "true" : "false");
    });
    render();
<<<<<<< HEAD
=======
    renderInsights();
    renderBadgeCards();
>>>>>>> seil2
  }

  Object.entries(tabs).forEach(([name, element]) => {
    if (!element) return;
    element.addEventListener("click", () => selectTab(name));
  });

<<<<<<< HEAD
  async function loadRankings() {
    render();
=======
  if (badgeSelect) {
    badgeSelect.addEventListener("change", (event) => {
      activeBadgeKey = event.target.value;
      renderBadgeCards();
    });
  }

  if (insightPrev) {
    insightPrev.addEventListener("click", () => setActiveInsight(activeInsightIndex - 1));
  }

  if (insightNext) {
    insightNext.addEventListener("click", () => setActiveInsight(activeInsightIndex + 1));
  }

  if (loadMoreButton) {
    if (loadMoreContainer) {
      loadMoreContainer.style.display = "none";
    }
    loadMoreButton.style.display = "none";
    loadMoreButton.disabled = true;
    loadMoreButton.addEventListener("click", () => {
      const items = datasets[activeKey] || [];
      const maxAvailable = Math.min(MAX_VISIBLE, items.length);
      if (visibleCount >= maxAvailable) {
        updateLoadMoreState(items);
        return;
      }
      visibleCount = Math.min(MAX_VISIBLE, visibleCount + PAGE_SIZE);
      render();
    });
  }

  async function loadRankings() {
    render();
    renderInsights();
    renderBadgeCards();
>>>>>>> seil2
    try {
      const response = await fetch(API_ENDPOINT, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      const payload = await response.json();
<<<<<<< HEAD
      Object.assign(datasets, payload);
=======
      Object.keys(datasets).forEach((key) => {
        const incoming = payload[key];
        if (!Array.isArray(incoming)) {
          datasets[key] = [];
          return;
        }
        if (key === "badge_groups" || key === "insight_groups") {
          datasets[key] = incoming.map((group) => ({
            ...group,
            items: Array.isArray(group.items)
              ? group.items.map((item) => ({ ...item }))
              : [],
          }));
        } else {
          datasets[key] = incoming.map((item) => ({ ...item }));
        }
      });

      const hellIds = new Set();
      const eliteIds = new Set();

      datasets.badge_groups = (datasets.badge_groups || []).map((group) => {
        const variant = group.variant || group.badge_variant;
        const items = Array.isArray(group.items) ? group.items : [];
        const mappedItems = items.map((item) => {
          const isHell = Boolean(item.badge_variant === "hell" || variant === "hell" || item.is_hell);
          const isElite = Boolean(item.badge_variant === "elite" || variant === "elite" || item.is_elite_profession);
          if (item.id != null) {
            if (isHell) hellIds.add(item.id);
            if (isElite) eliteIds.add(item.id);
          }
          return {
            ...item,
            is_hell: isHell,
            is_elite_profession: isElite,
          };
        });
        return {
          ...group,
          items: mappedItems,
        };
      });

      const applyBadgeFlags = (items) => {
        if (!Array.isArray(items)) {
          return [];
        }
        return items.map((item) => {
          if (!item || typeof item !== "object") {
            return item;
          }
          const id = item.id;
          const isHell = Boolean(item.is_hell) || (id != null && hellIds.has(id));
          const isElite = Boolean(item.is_elite_profession) || (id != null && eliteIds.has(id));
          return {
            ...item,
            is_hell: isHell,
            is_elite_profession: isElite,
          };
        });
      };

      Object.keys(datasets).forEach((key) => {
        if (key === "badge_groups") {
          return;
        }
        const value = datasets[key];
        if (!Array.isArray(value)) {
          return;
        }
        if (value.length && value[0] && typeof value[0] === "object" && Array.isArray(value[0].items)) {
          datasets[key] = value.map((group) => ({
            ...group,
            items: applyBadgeFlags(group.items),
          }));
        } else {
          datasets[key] = applyBadgeFlags(value);
        }
      });
      if (rankTip) {
        const tooltipFromData = [
          "hot",
          "pass",
          "pass_low",
          "hard_official",
          "easy_official",
          "hard_user",
          "easy_user",
        ].reduce((acc, key) => {
          if (acc) {
            return acc;
          }
          const list = payload[key] || [];
          const found = list.find((entry) => entry.rank_tooltip);
          return found ? found.rank_tooltip : null;
        }, null);
        rankTip.setAttribute("data-tip", tooltipFromData || DEFAULT_RANK_TOOLTIP);
      }
>>>>>>> seil2
      hasError = false;
    } catch (error) {
      console.error("Failed to load rankings", error);
      hasError = true;
    }
    isLoaded = true;
<<<<<<< HEAD
    render();
=======
    visibleCount = PAGE_SIZE;
    render();
    renderInsights();
    renderBadgeCards();
>>>>>>> seil2
  }

  loadRankings();
})();
