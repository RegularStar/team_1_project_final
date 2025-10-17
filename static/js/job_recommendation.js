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
  const summaryBox = resultSection?.querySelector('[data-role="summary"]');
  const noticeBox = resultSection?.querySelector('[data-role="notice"]');
  const analysisBox = resultSection?.querySelector('[data-role="analysis"]');
  const recommendationsBox = resultSection?.querySelector('[data-role="recommendations"]');
  const contributionBox = resultSection?.querySelector('[data-role="contribution"]');
  const keywordSuggestionsBox = contributionBox?.querySelector('[data-role="keyword-suggestions"]');
  const tagInput = document.getElementById("job-rec-contrib-tag");
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
  let lastMissingKeywords = [];
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
    submitButton.textContent = isLoading ? "분석 중..." : originalSubmitText;
  }

  function resetContributionState(options = {}) {
    const preserveStatus = Boolean(options.preserveStatus);
    selectedCertificates.clear();
    updateSelectedCertificates();
    if (certResultsBox) {
      certResultsBox.innerHTML = "";
    }
    if (certQueryInput) {
      certQueryInput.value = "";
    }
    if (!preserveStatus) {
      setContributionStatus("");
    }
  }

  function setContributionStatus(message, type) {
    if (!contributionStatusBox) return;
    if (!message) {
      contributionStatusBox.textContent = "";
      contributionStatusBox.classList.add("hidden");
      contributionStatusBox.classList.remove("error");
      return;
    }
    contributionStatusBox.textContent = message;
    contributionStatusBox.classList.remove("hidden");
    if (type === "error") {
      contributionStatusBox.classList.add("error");
    } else {
      contributionStatusBox.classList.remove("error");
    }
  }

  function renderKeywordSuggestions() {
    if (!keywordSuggestionsBox) return;
    keywordSuggestionsBox.innerHTML = "";

    if (!lastMissingKeywords.length) {
      const info = document.createElement("p");
      info.className = "job-rec__empty";
      info.textContent = "추가할 만한 키워드를 찾지 못했어요. 직접 입력해주세요.";
      keywordSuggestionsBox.appendChild(info);
      return;
    }

    lastMissingKeywords.forEach((keyword) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "job-rec__keyword-pill";
      button.textContent = keyword;
      button.addEventListener("click", () => {
        if (tagInput) {
          tagInput.value = keyword;
          tagInput.focus({ preventScroll: true });
        }
      });
      keywordSuggestionsBox.appendChild(button);
    });
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
    if (certResultsBox) {
      certResultsBox.innerHTML = "";
    }
    if (certQueryInput) {
      certQueryInput.value = "";
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

    lastMissingKeywords = Array.from(collected.values());
    renderKeywordSuggestions();

    if (tagInput && (!tagInput.value || !tagInput.value.trim()) && lastMissingKeywords.length) {
      tagInput.value = lastMissingKeywords[0];
    }

    setContributionStatus("");
    contributionBox.classList.remove("hidden");
  }

  function hideContributionPrompt() {
    if (!contributionBox) return;
    lastMissingKeywords = [];
    resetContributionState();
  }

  async function submitContribution() {
    if (!feedbackEndpoint) {
      setContributionStatus("태그 제안 API 경로가 설정되지 않았습니다.", "error");
      return;
    }

    const tagName = (tagInput?.value || "").trim();
    if (!tagName) {
      setContributionStatus("추가할 태그 이름을 입력해주세요.", "error");
      tagInput?.focus({ preventScroll: true });
      return;
    }

    const certificateIds = Array.from(selectedCertificates.keys());
    if (!certificateIds.length) {
      setContributionStatus("연결할 자격증을 최소 한 개 이상 선택해주세요.", "error");
      return;
    }

    const payload = {
      tag_name: tagName,
      certificate_ids: certificateIds,
      job_excerpt: lastJobExcerpt || (textArea?.value || ""),
    };

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
    setContributionStatus("태그 제안을 전송하는 중입니다...", "info");

    try {
      const response = await fetch(feedbackEndpoint, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => null);
      if (!response.ok || !data) {
        const detail = data?.detail
          || (Array.isArray(data?.non_field_errors) ? data.non_field_errors[0] : null)
          || (Array.isArray(data?.certificate_ids) ? data.certificate_ids[0] : null)
          || (Array.isArray(data?.tag_name) ? data.tag_name[0] : null)
          || "태그 제안 중 오류가 발생했습니다.";
        throw new Error(detail);
      }

      const addedIds = Array.isArray(data.added_certificate_ids) ? data.added_certificate_ids : [];
      const alreadyLinkedIds = Array.isArray(data.already_linked_ids) ? data.already_linked_ids : [];
      const tagCreated = Boolean(data.tag_created);

      const hasUpdates = tagCreated || addedIds.length > 0;
      const message = data.message || (hasUpdates
        ? "태그 제안을 반영했습니다."
        : "이미 연결된 태그와 자격증입니다.");
      const statusType = hasUpdates ? "info" : "error";
      setContributionStatus(message, statusType);

      if (tagInput && data.tag && data.tag.name) {
        tagInput.value = data.tag.name;
      }

      resetContributionState({ preserveStatus: true });

      if (hasUpdates) {
        setTimeout(() => {
          form.requestSubmit();
        }, 400);
      }
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

  function renderSummary(payload) {
    if (!summaryBox) return;
    const excerpt = payload.job_excerpt || payload.job_text || "";
    const fullText = payload.job_text || payload.job_excerpt || payload.raw_text || "";
    const summaryParts = [];
    lastJobExcerpt = fullText;
    summaryParts.push("<h3>채용공고 요약</h3>");
    if (excerpt) {
      summaryParts.push(`<p>${escapeHtml(excerpt)}</p>`);
    } else {
      summaryParts.push('<p class="job-rec__empty">요약 정보를 찾지 못했어요.</p>');
    }
    if (fullText) {
      summaryParts.push(
        `<details><summary>전체 텍스트 보기</summary><pre>${escapeHtml(fullText)}</pre></details>`
      );
    }
    summaryBox.innerHTML = summaryParts.join("\n");
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
    const focus = analysis?.focus_keywords || [];
    const essential = analysis?.essential_skills || [];
    const preferred = analysis?.preferred_skills || [];
    const hasContent = analysis && (analysis.job_title || focus.length || essential.length || preferred.length);

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

    const titleLine = analysis.job_title
      ? `<p class="job-rec__hint">추정 직무: <strong>${escapeHtml(analysis.job_title)}</strong></p>`
      : "";

    analysisBox.innerHTML = `
      <h3>분석된 키워드</h3>
      ${titleLine}
      <div class="job-rec__analysis-grid">
        <div class="job-rec__analysis-block">
          <h4>주요 키워드</h4>
          ${renderList(focus)}
        </div>
        <div class="job-rec__analysis-block">
          <h4>필수 역량</h4>
          ${renderList(essential)}
        </div>
        <div class="job-rec__analysis-block">
          <h4>우대 사항</h4>
          ${renderList(preferred)}
        </div>
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
      const linkTarget = certificate.id != null
        ? `/certificates/${encodeURIComponent(String(certificate.id))}/`
        : "#";
      const overview = truncate(certificate.overview || "", 220);

      const card = document.createElement("article");
      card.className = "job-rec__recommendation-card";
      card.innerHTML = `
        <header>
          <h4>${escapeHtml(certificate.name || "이름 미상")}</h4>
          <span class="job-rec__score">점수 ${escapeHtml(String(entry.score ?? "—"))}</span>
        </header>
        ${overview ? `<p>${escapeHtml(overview)}</p>` : '<p class="job-rec__empty">요약 정보가 없습니다.</p>'}
        ${reasons.length ? `<ul class="job-rec__reasons">${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>` : ""}
        <div class="job-rec__actions">
          <a class="btn secondary" href="${linkTarget}">자격증 상세 보기</a>
          <span class="job-rec__hint">난이도 ${escapeHtml(certificate.rating != null ? `${certificate.rating}/10` : "정보 없음")}</span>
        </div>
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
      setStatus("채용공고 본문을 입력해주세요.", "error");
      if (textArea) textArea.focus();
      return;
    }

    if (mode === "image" && !file) {
      setStatus("채용공고 이미지를 업로드해주세요.", "error");
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
      renderSummary(data);
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

  renderContributionPrompt([], []);
})();
