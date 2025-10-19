(function () {
  const MAX_VISIBLE = 30;
  const PAGE_SIZE = 10;
  const API_ENDPOINT = `/api/certificates/rankings/?limit=${MAX_VISIBLE}`;
  const datasets = {
    hot: [],
    pass: [],
    pass_low: [],
    hard_official: [],
    easy_official: [],
    hard_user: [],
    easy_user: [],
  };
  const DEFAULT_RANK_TOOLTIP = "차수별 통계는 최근 공개된 데이터를 기준으로 했어요. 응시자 수 1,000명 이상만 보여줘요.";
  let isLoaded = false;
  let hasError = false;
  let visibleCount = PAGE_SIZE;

  const listRoot = document.getElementById("list");
  if (!listRoot) {
    return;
  }
  const loadMoreButton = document.getElementById("rank-load-more");
  const loadMoreContainer = loadMoreButton ? loadMoreButton.parentElement : null;

  const rankTip = document.querySelector('[data-role="rank-tooltip"]');
  if (rankTip) {
    rankTip.setAttribute("data-tip", rankTip.getAttribute("data-tip") || DEFAULT_RANK_TOOLTIP);
  }

  const tabs = {
    hot: document.getElementById("tab-hot"),
    pass: document.getElementById("tab-pass"),
    pass_low: document.getElementById("tab-pass-low"),
    hard_official: document.getElementById("tab-hard-official"),
    easy_official: document.getElementById("tab-easy-official"),
    hard_user: document.getElementById("tab-hard-user"),
    easy_user: document.getElementById("tab-easy-user"),
  };

  let activeKey = "hot";
  const difficultyContexts = new Set(["hard_official", "easy_official", "hard_user", "easy_user"]);

  const TOOLTIP_TEXTS = {
    "difficulty-scale": `난이도 안내\n1. 아주 쉬움. 기초 개념 위주라 단기간 준비로 누구나 합격 가능한 수준.\n2. 쉬움. 기본 지식이 있으면 무난히 도전할 수 있는 입문 수준.\n3. 보통. 일정한 학습이 필요하지만 꾸준히 준비하면 충분히 합격 가능한 수준.\n4. 다소 어려움. 이론과 실무를 균형 있게 요구하며, 준비 기간이 다소 긴 수준.\n5. 중상 난이도. 전공지식과 응용력이 필요해 체계적 학습이 요구되는 수준.\n6. 어려움. 합격률이 낮고 심화 학습이 필요해 전공자도 부담되는 수준.\n7. 매우 어려움. 방대한 범위와 높은 난이도로 전공자도 장기간 학습이 필수인 수준.\n8. 극히 어려움. 전문성·응용력·실무 경험이 모두 요구되는 최상위권 자격 수준.\n9. 최상 난이도. 전문지식과 실무를 총망라하며, 합격자가 극소수에 불과한 수준.\n10. 극한 난이도. 수년간 전념해도 합격을 장담할 수 없는, 최고 난도의 자격 수준.`
  };

  const difficultyLegend = document.querySelector('[data-role="difficulty-legend"]');
  if (difficultyLegend) {
    difficultyLegend.setAttribute("data-tip", TOOLTIP_TEXTS["difficulty-scale"]);
  }

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

  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderMetric(metric, seen) {
    if (!metric) {
      return "";
    }
    const value = metric.value;
    if (value == null) {
      return "";
    }
    const tooltipKey = metric.tooltipKey && TOOLTIP_TEXTS[metric.tooltipKey];
    const tooltipText = tooltipKey || metric.tooltip;
    const useInfoButton = Boolean(metric.infoButton && tooltipText);
    const tooltipAttr = tooltipText
      ? useInfoButton
        ? ` data-tip="${escapeAttr(tooltipText)}"`
        : ` title="${escapeAttr(tooltipText)}"`
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
    row.className = "row";
    const slugSource = item.id != null ? item.id : (item.slug || item.name);
    const link = slugSource
      ? `/certificates/${encodeURIComponent(String(slugSource).toLowerCase())}/`
      : "#";
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
    const nameAttr = escapeAttr(item.name);
    const nameText = escapeHtml(item.name);
    const nameMarkup = `<span class="title-name" title="${nameAttr}">${nameText}</span>`;
    row.innerHTML = `
      <div class="left">
        <div class="rank">#${item.rank}</div>
        <div>
          <div class="title-block">
            <div class="title">
              ${nameMarkup}${stageMarkup}
            </div>
          </div>
          <div class="meta">
            ${metricParts.join("\n")}
          </div>
          ${tagsBlock}
        </div>
      </div>
      <div class="right">
        <a class="detail-btn" href="${link}">상세 보기</a>
      </div>
    `;
    return row;
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
      return;
    }

    if (!isLoaded) {
      listRoot.innerHTML = '<div class="state">랭킹을 불러오는 중...</div>';
      updateLoadMoreState([]);
      return;
    }

    listRoot.innerHTML = "";
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
    try {
      const response = await fetch(API_ENDPOINT, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      const payload = await response.json();
      Object.keys(datasets).forEach((key) => {
        const incoming = payload[key];
        datasets[key] = Array.isArray(incoming) ? incoming : [];
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
      hasError = false;
    } catch (error) {
      console.error("Failed to load rankings", error);
      hasError = true;
    }
    isLoaded = true;
    visibleCount = PAGE_SIZE;
    render();
  }

  loadRankings();
})();
