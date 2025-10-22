(function () {
  const form = document.getElementById("job-rec-form");
  if (!form) {
    return;
  }

  const modeInputs = form.querySelectorAll("input[name='mode']");
  const modeContainers = {
    text: form.querySelector('[data-mode="text"]'),
    image: form.querySelector('[data-mode="image"]'),
  };
  const textArea = document.getElementById("job-rec-text");
  const imageInput = document.getElementById("job-rec-image");
  const maxSelect = document.getElementById("job-rec-max-results");
  const submitButton = form.querySelector(".job-rec__submit");
  const statusBox = document.getElementById("job-rec-status");
  const resultSection = document.getElementById("job-rec-result");
  const noticeBox = resultSection?.querySelector('[data-role="notice"]');
  const analysisBox = resultSection?.querySelector('[data-role="analysis"]');
  const recommendationsBox = resultSection?.querySelector('[data-role="recommendations"]');
  const contributionBox = resultSection?.querySelector('[data-role="contribution"]');
  const keywordSuggestionsBox = contributionBox?.querySelector('[data-role="keyword-suggestions"]');
  const selectedTagsBox = contributionBox?.querySelector('[data-role="selected-tags"]');
  const tagInput = document.getElementById("job-rec-contrib-tag");
  const tagAddButton = document.getElementById("job-rec-tag-add");
  const certQueryInput = document.getElementById("job-rec-contrib-cert-query");
  const certSearchButton = document.getElementById("job-rec-contrib-cert-search");
  const certResultsBox = contributionBox?.querySelector('[data-role="cert-results"]');
  const selectedCertificatesBox = contributionBox?.querySelector('[data-role="selected-certificates"]');
  const contributionSubmitButton = document.getElementById("job-rec-contrib-submit");
  const contributionStatusBox = contributionBox?.querySelector('[data-role="contrib-status"]');
  const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
  const apiEndpoint = form.dataset.apiEndpoint;
  const feedbackEndpoint = contributionBox?.dataset.feedbackEndpoint || "/api/ai/job-certificates/feedback/";
  const certificateSearchEndpoint = "/api/certificates/";
  const originalSubmitText = submitButton ? submitButton.textContent : "";

  const selectedCertificates = new Map();
  const selectedTags = new Map();
  let suggestionKeywords = [];
  let lastJobExcerpt = "";
  let lastKeywordSuggestions = [];

  function setStatus(message, type) {
    if (!statusBox) return;
    if (!message) {
      statusBox.textContent = "";
      statusBox.classList.add("hidden");
      statusBox.classList.remove("error");
      return;
    }
    statusBox.textContent = message;
    statusBox.classList.remove("hidden");
    if (type === "error") {
      statusBox.classList.add("error");
    } else {
      statusBox.classList.remove("error");
    }
  }

  function setLoading(isLoading) {
    if (!submitButton) return;
    submitButton.disabled = isLoading;
    submitButton.textContent = isLoading ? "추천 생성 중..." : originalSubmitText;
  }

  function resetContributionState(options = {}) {
    const preserveStatus = Boolean(options.preserveStatus);
    selectedCertificates.clear();
    updateSelectedCertificates();
    selectedTags.clear();
    renderSelectedTags();
    if (certResultsBox) {
      certResultsBox.innerHTML = "";
    }
    if (certQueryInput) {
      certQueryInput.value = "";
    }
    if (tagInput) {
      tagInput.value = "";
    }
    renderKeywordSuggestions();
    if (!preserveStatus) {
      setContributionStatus("");
    }
  }

  function setContributionStatus(message, type, options = {}) {
    if (!contributionStatusBox) return;
    if (!message) {
      contributionStatusBox.textContent = "";
      contributionStatusBox.innerHTML = "";
      contributionStatusBox.classList.add("hidden");
      contributionStatusBox.classList.remove("error");
      return;
    }
    const { html = false } = options;
    if (html) {
      contributionStatusBox.innerHTML = message;
    } else {
      contributionStatusBox.textContent = message;
    }
    contributionStatusBox.classList.remove("hidden");
    if (type === "error") {
      contributionStatusBox.classList.add("error");
    } else {
      contributionStatusBox.classList.remove("error");
    }
  }

  function normalizeTag(value) {
    return (value || "").trim().replace(/\s+/g, " ");
  }

  function addSelectedTag(rawValue) {
    const normalized = normalizeTag(rawValue);
    if (!normalized) {
      return false;
    }
    const key = normalized.toLowerCase();
    if (selectedTags.has(key)) {
      return false;
    }
    selectedTags.set(key, normalized);
    renderSelectedTags();
    renderKeywordSuggestions();
    return true;
  }

  function removeSelectedTag(key) {
    if (!selectedTags.has(key)) return;
    selectedTags.delete(key);
    renderSelectedTags();
    renderKeywordSuggestions();
  }

  function toggleSelectedTag(rawValue) {
    const normalized = normalizeTag(rawValue);
    if (!normalized) {
      return;
    }
    const key = normalized.toLowerCase();
    if (selectedTags.has(key)) {
      removeSelectedTag(key);
    } else {
      addSelectedTag(normalized);
    }
  }

  function renderSelectedTags() {
    if (!selectedTagsBox) return;
    selectedTagsBox.innerHTML = "";

    if (!selectedTags.size) {
      const empty = document.createElement("p");
      empty.className = "job-rec__hint";
      empty.textContent = "선택된 태그가 없습니다. 키워드를 선택하거나 직접 추가해보세요.";
      selectedTagsBox.appendChild(empty);
      return;
    }

    selectedTags.forEach((label, key) => {
      const chip = document.createElement("span");
      chip.className = "job-rec__tag-chip";

      const text = document.createElement("span");
      text.textContent = label;
      chip.appendChild(text);

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.setAttribute("aria-label", `${label} 태그 제거`);
      removeButton.textContent = "×";
      removeButton.addEventListener("click", () => removeSelectedTag(key));
      chip.appendChild(removeButton);

      selectedTagsBox.appendChild(chip);
    });
  }

  function renderKeywordSuggestions() {
    if (!keywordSuggestionsBox) return;
    keywordSuggestionsBox.innerHTML = "";

    if (!suggestionKeywords.length) {
      const info = document.createElement("p");
      info.className = "job-rec__empty";
      info.textContent = "추가할 만한 키워드를 찾지 못했어요. 직접 입력해주세요.";
      keywordSuggestionsBox.appendChild(info);
      return;
    }

    suggestionKeywords.forEach((keyword) => {
      const button = document.createElement("button");
      button.type = "button";
      const key = keyword.toLowerCase();
      const isActive = selectedTags.has(key);
      button.className = `job-rec__keyword-pill${isActive ? " job-rec__keyword-pill--active" : ""}`;
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
      button.textContent = keyword;
      button.addEventListener("click", () => toggleSelectedTag(keyword));
      keywordSuggestionsBox.appendChild(button);
    });
  }

  function handleManualTagAdd() {
    if (!tagInput) return;
    const rawValue = tagInput.value;
    const added = addSelectedTag(rawValue);
    if (added) {
      tagInput.value = "";
    } else if (rawValue && rawValue.trim()) {
      tagInput.select();
    }
  }

  function updateSelectedCertificates() {
    if (!selectedCertificatesBox) return;
    selectedCertificatesBox.innerHTML = "";

    if (!selectedCertificates.size) {
      const hint = document.createElement("p");
      hint.className = "job-rec__hint";
      hint.textContent = "연결할 자격증을 추가해주세요.";
      selectedCertificatesBox.appendChild(hint);
      return;
    }

    selectedCertificates.forEach((certificate, id) => {
      const item = document.createElement("div");
      item.className = "job-rec__selected-item";
      item.innerHTML = `
        <span>${certificate.name}</span>
        <button type="button" data-cert-id="${id}">제거</button>
      `;
      const removeButton = item.querySelector("button");
      if (removeButton) {
        removeButton.addEventListener("click", () => {
          selectedCertificates.delete(id);
          updateSelectedCertificates();
        });
      }
      selectedCertificatesBox.appendChild(item);
    });
  }

  function renderCertificateResults(results) {
    if (!certResultsBox) return;
    certResultsBox.innerHTML = "";

    if (!Array.isArray(results) || !results.length) {
      const empty = document.createElement("p");
      empty.className = "job-rec__empty";
      empty.textContent = "검색 결과가 없습니다.";
      certResultsBox.appendChild(empty);
      return;
    }

    results.forEach((certificate) => {
      const id = certificate.id;
      const item = document.createElement("div");
      item.className = "job-rec__cert-result-item";
      const disabled = selectedCertificates.has(id);
      item.innerHTML = `
        <span>${certificate.name}</span>
        <button type="button" data-cert-id="${id}" ${disabled ? "disabled" : ""}>추가</button>
      `;
      const addButton = item.querySelector("button");
      if (addButton && !disabled) {
        addButton.addEventListener("click", () => {
          selectedCertificates.set(id, certificate);
          updateSelectedCertificates();
          addButton.disabled = true;
        });
      }
      certResultsBox.appendChild(item);
    });
  }

  async function searchCertificates(query) {
    if (!certResultsBox) return;
    const trimmed = (query || "").trim();
    if (!trimmed) {
      renderCertificateResults([]);
      return;
    }

    certResultsBox.innerHTML = '<p class="job-rec__hint">검색 중...</p>';
    try {
      const url = `${certificateSearchEndpoint}?search=${encodeURIComponent(trimmed)}&ordering=name`;
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`검색에 실패했습니다 (${response.status})`);
      }
      const payload = await response.json();
      const results = Array.isArray(payload.results) ? payload.results : payload;
      renderCertificateResults(results.slice(0, 10));
    } catch (error) {
      certResultsBox.innerHTML = `<p class="job-rec__empty">${error.message || "검색 중 오류가 발생했어요."}</p>`;
    }
  }

  function renderContributionPrompt(primaryKeywords, matchedKeywords) {
    if (!contributionBox) return;

    selectedCertificates.clear();
    updateSelectedCertificates();
    selectedTags.clear();
    renderSelectedTags();
    if (certResultsBox) {
      certResultsBox.innerHTML = "";
    }
    if (certQueryInput) {
      certQueryInput.value = "";
    }
    if (tagInput) {
      tagInput.value = "";
    }
    const collected = new Map();

    const pushAll = (source) => {
      if (!Array.isArray(source)) return;
      source.forEach((item) => {
        if (typeof item !== "string") return;
        const text = item.trim();
        if (!text) return;
        const lowered = text.toLowerCase();
        if (collected.has(lowered)) return;
        collected.set(lowered, text);
      });
    };

    pushAll(primaryKeywords);
    pushAll(matchedKeywords);
    pushAll(lastKeywordSuggestions);

    suggestionKeywords = Array.from(collected.values());
    renderKeywordSuggestions();

    setContributionStatus("");
    contributionBox.classList.remove("hidden");
  }

  function hideContributionPrompt() {
    if (!contributionBox) return;
    suggestionKeywords = [];
    selectedTags.clear();
    renderSelectedTags();
    renderKeywordSuggestions();
    resetContributionState();
  }

  async function submitContribution() {
    if (!feedbackEndpoint) {
      setContributionStatus("태그 제안 API 경로가 설정되지 않았습니다.", "error");
      return;
    }

    const tagNames = Array.from(selectedTags.values());
    if (!tagNames.length) {
      setContributionStatus("연결할 태그를 선택하거나 직접 추가해주세요.", "error");
      if (tagInput) {
        tagInput.focus({ preventScroll: true });
      }
      return;
    }

    const certificateIds = Array.from(selectedCertificates.keys());
    if (!certificateIds.length) {
      setContributionStatus("연결할 자격증을 최소 한 개 이상 선택해주세요.", "error");
      return;
    }

    const headers = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (csrfInput?.value) {
      headers["X-CSRFToken"] = csrfInput.value;
    }

    if (contributionSubmitButton) {
      contributionSubmitButton.disabled = true;
    }
    setContributionStatus("선택한 태그를 연결하는 중입니다...", "info");

    try {
      const submittedKeys = new Set(tagNames.map((name) => name.toLowerCase()));
      const successfulTags = [];
      const duplicateTags = [];
      for (let index = 0; index < tagNames.length; index += 1) {
        const tagName = tagNames[index];
        setContributionStatus(`(${index + 1}/${tagNames.length}) '${tagName}' 태그를 연결하는 중입니다...`, "info");

        const payload = {
          tag_name: tagName,
          certificate_ids: certificateIds,
          job_excerpt: lastJobExcerpt || (textArea?.value || ""),
        };

        const response = await fetch(feedbackEndpoint, {
          method: "POST",
          headers,
          credentials: "include",
          body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => null);
        if (!response.ok || !data) {
          const detail = data?.detail
            || (Array.isArray(data?.non_field_errors) ? data.non_field_errors[0] : null)
            || (Array.isArray(data?.certificate_ids) ? data.certificate_ids[0] : null)
            || (Array.isArray(data?.tag_name) ? data.tag_name[0] : null)
            || "태그 제안 중 오류가 발생했습니다.";
          throw new Error(`'${tagName}' 처리 실패: ${detail}`);
        }

        const addedCount = Array.isArray(data.added_certificate_ids) ? data.added_certificate_ids.length : 0;
        const alreadyCount = Array.isArray(data.already_linked_ids) ? data.already_linked_ids.length : 0;
        if (addedCount > 0) {
          successfulTags.push(tagName);
        } else if (alreadyCount > 0 || !addedCount) {
          duplicateTags.push(tagName);
        }
      }

      const parts = [];
      if (successfulTags.length) {
        const tagList = successfulTags.map((name) => `<strong>${escapeHtml(name)}</strong>`).join(", ");
        parts.push(`<p class="job-rec__status-line job-rec__status-line--success">${tagList} 태그를 자격증과 연결했어요.</p>`);
      }
      if (duplicateTags.length) {
        const tagList = duplicateTags.map((name) => `<strong>${escapeHtml(name)}</strong>`).join(", ");
        parts.push(`<p class="job-rec__status-line job-rec__status-line--neutral">${tagList} 태그는 이미 연결되어 있었어요.</p>`);
      }
      const statusHtml = parts.join("");
      setContributionStatus(statusHtml || "처리할 태그가 없습니다.", successfulTags.length ? "info" : "error", {
        html: true,
      });
      resetContributionState({ preserveStatus: true });
      suggestionKeywords = suggestionKeywords.filter((keyword) => !submittedKeys.has(keyword.toLowerCase()));
      selectedTags.clear();
      renderSelectedTags();
      renderKeywordSuggestions();
      setTimeout(() => {
        form.requestSubmit();
      }, 400);
    } catch (error) {
      setContributionStatus(error.message || "태그 제안에 실패했습니다.", "error");
    } finally {
      if (contributionSubmitButton) {
        contributionSubmitButton.disabled = false;
      }
    }
  }

  function switchMode(mode) {
    Object.entries(modeContainers).forEach(([key, element]) => {
      if (!element) return;
      if (key === mode) {
        element.classList.remove("hidden");
      } else {
        element.classList.add("hidden");
      }
    });

    if (mode === "text" && textArea) {
      textArea.focus({ preventScroll: true });
    }
    if (mode === "image" && imageInput) {
      imageInput.focus({ preventScroll: true });
    }
  }

  modeInputs.forEach((input) => {
    input.addEventListener("change", () => switchMode(input.value));
  });
  switchMode(form.elements.mode?.value || "text");

  function escapeHtml(value) {
    if (value == null) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function truncate(text, maxLength) {
    if (!text) return "";
    const trimmed = text.trim();
    if (trimmed.length <= maxLength) return trimmed;
    return `${trimmed.slice(0, Math.max(0, maxLength - 1))}…`;
  }

  function renderNotice(text) {
    if (!noticeBox) return;
    if (!text) {
      noticeBox.textContent = "";
      noticeBox.classList.add("hidden");
      return;
    }
    noticeBox.textContent = text;
    noticeBox.classList.remove("hidden");
  }

  function renderAnalysis(analysis) {
    if (!analysisBox) return;
    const recommended = Array.isArray(analysis?.recommended_tags) ? analysis.recommended_tags : [];
    const expanded = Array.isArray(analysis?.expanded_keywords) ? analysis.expanded_keywords : [];
    const focus = Array.isArray(analysis?.focus_keywords) ? analysis.focus_keywords : [];
    const essential = Array.isArray(analysis?.essential_skills) ? analysis.essential_skills : [];
    const preferred = Array.isArray(analysis?.preferred_skills) ? analysis.preferred_skills : [];
    const newKeywords = Array.isArray(analysis?.new_keywords) ? analysis.new_keywords : [];
    const goalTitle = typeof analysis?.job_title === "string" ? analysis.job_title.trim() : "";
    const hasContent =
      recommended.length
      || expanded.length
      || focus.length
      || essential.length
      || preferred.length
      || newKeywords.length
      || goalTitle;

    if (!hasContent) {
      analysisBox.innerHTML = "";
      analysisBox.classList.add("hidden");
      return;
    }

    function renderList(items) {
      if (!items.length) {
        return '<p class="job-rec__empty">데이터가 없어요.</p>';
      }
      return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    const goalLine = goalTitle
      ? `<p class="job-rec__hint">AI가 파악한 핵심 목표: <strong>${escapeHtml(goalTitle)}</strong></p>`
      : "";

    const recommendedBlock = `
      <div class="job-rec__analysis-block">
        <h4>AI 추천 태그</h4>
        ${renderList(recommended)}
        ${recommended.length ? '<p class="job-rec__hint">이 태그를 기반으로 자격증을 우선 추천했어요.</p>' : ""}
      </div>
    `;

    const focusBlock = `
      <div class="job-rec__analysis-block">
        <h4>핵심 키워드</h4>
        ${renderList(focus)}
      </div>
    `;

    const essentialBlock = `
      <div class="job-rec__analysis-block">
        <h4>필수 역량</h4>
        ${renderList(essential)}
      </div>
    `;

    const preferredBlock = `
      <div class="job-rec__analysis-block">
        <h4>확장 역량</h4>
        ${renderList(preferred)}
      </div>
    `;

    const newKeywordBlock = `
      <div class="job-rec__analysis-block">
        <h4>새로 제안된 키워드</h4>
        ${
          newKeywords.length
            ? `${renderList(newKeywords)}<p class="job-rec__hint">DB에 없는 키워드예요. 태그로 등록하면 다음 추천에 반영돼요.</p>`
            : '<p class="job-rec__empty">추가 제안이 없어요.</p>'
        }
      </div>
    `;

    const expandedBlock = `
      <div class="job-rec__analysis-block">
        <h4>연관 키워드</h4>
        ${renderList(expanded)}
      </div>
    `;

    analysisBox.innerHTML = `
      <h3>AI 분석 결과</h3>
      ${goalLine}
      <div class="job-rec__analysis-grid">
        ${recommendedBlock}
        ${expandedBlock}
        ${focusBlock}
        ${essentialBlock}
        ${preferredBlock}
        ${newKeywordBlock}
      </div>
    `;
    analysisBox.classList.remove("hidden");
  }

  function renderRecommendations(recommendations, missingKeywords, matchedKeywords) {
    if (!recommendationsBox) return;
    recommendationsBox.innerHTML = "";

    if (!recommendations || !recommendations.length) {
      const empty = document.createElement("p");
      empty.className = "job-rec__empty";
      empty.textContent = "추천 가능한 자격증을 찾지 못했어요.";
      recommendationsBox.appendChild(empty);
    }

    renderContributionPrompt(missingKeywords || [], matchedKeywords || []);

    recommendations.forEach((entry) => {
      const certificate = entry.certificate || {};
      const reasons = Array.isArray(entry.reasons) ? entry.reasons : [];
      const hasLink = certificate.id != null;
      const linkTarget = hasLink
        ? `/certificates/${encodeURIComponent(String(certificate.id))}/`
        : null;
      const overview = truncate(certificate.overview || "", 220);

      const card = document.createElement(hasLink ? "a" : "article");
      card.className = "job-rec__recommendation-card";
      if (hasLink) {
        card.href = linkTarget;
      }

      card.innerHTML = `
        <header>
          <h4>${escapeHtml(certificate.name || "이름 미상")}</h4>
          <span class="job-rec__score">점수 ${escapeHtml(String(entry.score ?? "—"))}</span>
        </header>
        ${overview ? `<p>${escapeHtml(overview)}</p>` : '<p class="job-rec__empty">요약 정보가 없습니다.</p>'}
        ${reasons.length ? `<ul class="job-rec__reasons">${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>` : ""}
      `;
      recommendationsBox.appendChild(card);
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!apiEndpoint) {
      setStatus("API 경로가 설정되지 않았습니다.", "error");
      return;
    }

    const mode = form.elements.mode?.value || "text";
    const content = textArea?.value.trim() || "";
    const file = imageInput?.files?.[0];

    if (mode === "text" && !content) {
      setStatus("추천받고 싶은 내용을 입력해주세요.", "error");
      if (textArea) textArea.focus();
      return;
    }

    if (mode === "image" && !file) {
      setStatus("텍스트가 담긴 이미지를 업로드해주세요.", "error");
      if (imageInput) imageInput.focus();
      return;
    }

    setStatus("추천을 준비 중이에요...", "info");
    resultSection.hidden = true;
    setLoading(true);

    const payload = new FormData();
    payload.append("max_results", maxSelect?.value || "5");
    if (content) {
      payload.append("content", content);
    }
    if (mode === "image" && file) {
      payload.append("image", file);
    }

    const headers = {};
    if (csrfInput?.value) {
      headers["X-CSRFToken"] = csrfInput.value;
    }

    try {
      const response = await fetch(apiEndpoint, {
        method: "POST",
        headers,
        credentials: "include",
        body: payload,
      });

      const data = await response.json().catch(() => null);

      if (!response.ok || !data) {
        const detail = data?.detail
          || (Array.isArray(data?.non_field_errors) ? data.non_field_errors[0] : null)
          || "추천 요청 중 오류가 발생했습니다.";
        throw new Error(detail);
      }

      setStatus("", "info");
      lastKeywordSuggestions = Array.isArray(data.keyword_suggestions)
        ? data.keyword_suggestions.filter((item) => typeof item === "string" && item.trim())
        : [];
      lastJobExcerpt = data.job_text || data.job_excerpt || data.raw_text || (textArea?.value || "");
      renderNotice(data.notice);
      renderAnalysis(data.analysis);
      renderRecommendations(data.recommendations, data.missing_keywords, data.matched_keywords);
      resultSection.hidden = false;
      resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      setStatus(error.message || "추천 생성에 실패했습니다.", "error");
    } finally {
      setLoading(false);
    }
  }

  form.addEventListener("submit", handleSubmit);

  if (certSearchButton) {
    certSearchButton.addEventListener("click", () => {
      searchCertificates(certQueryInput?.value || "");
    });
  }

  if (certQueryInput) {
    certQueryInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        searchCertificates(certQueryInput.value || "");
      }
    });
  }

  if (contributionSubmitButton) {
    contributionSubmitButton.addEventListener("click", submitContribution);
  }

  if (tagAddButton) {
    tagAddButton.addEventListener("click", handleManualTagAdd);
  }

  if (tagInput) {
    tagInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        if (event.isComposing || event.keyCode === 229) {
          return;
        }
        event.preventDefault();
        handleManualTagAdd();
      }
    });
  }

  renderContributionPrompt([], []);
})();
