(function () {
  const form = document.getElementById("search-form");
  if (!form) {
    return;
  }

  form.addEventListener("submit", () => {
    const keywordInput = form.querySelector("input[name='q']");
    if (keywordInput) {
      keywordInput.value = keywordInput.value.trim();
    }
  });

  const hiddenTagInputs = form.querySelector('[data-role="selected-tag-inputs"]');
  const filterTagContainer = form.querySelector('[data-role="selected-tags-display"]');
  const heroTagContainer = form.querySelector('[data-role="hero-selected-tags"]');
  const openTagModalButton = form.querySelector('[data-role="open-tag-modal"]');
  const tagModal = form.querySelector('[data-role="tag-modal"]');
  const tagModalCloseElements = tagModal ? Array.from(tagModal.querySelectorAll('[data-role="tag-modal-close"]')) : [];
  const tagSearchInput = document.getElementById("tag-modal-search-input");
  const tagResultsBox = tagModal ? tagModal.querySelector('[data-role="tag-modal-results"]') : null;
  const resetFiltersButton = form.querySelector('[data-role="reset-filters"]');

  if (!hiddenTagInputs || !filterTagContainer || !tagModal || !tagResultsBox) {
    return;
  }

  const resultCards = form.querySelectorAll(".result-card[data-detail-url]");
  resultCards.forEach((card) => {
    card.addEventListener("click", () => {
      const url = card.dataset.detailUrl;
      if (url) {
        window.location.href = url;
      }
    });
    card.addEventListener("keypress", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        const url = card.dataset.detailUrl;
        if (url) {
          window.location.href = url;
        }
      }
    });
  });

  if (resetFiltersButton) {
    resetFiltersButton.addEventListener("click", () => {
      form.querySelectorAll("input[type='number']").forEach((input) => {
        if (input.hasAttribute("data-default")) {
          input.value = input.dataset.default;
        } else {
          input.value = "";
        }
      });
      form.querySelectorAll("select").forEach((select) => {
        const original = select.getAttribute("data-default") ?? "";
        select.value = original;
      });
      const url = new URL(window.location.href);
      url.search = "";
      window.location.href = url.toString();
    });
  }

  const TAG_SEARCH_DEBOUNCE = 180;
  const tagEndpoint = form.dataset.tagsEndpoint || "/api/tags/";
  const tagMeta = new Map();
  const selectedSet = new Set();
  let debounceTimer = null;
  let currentResults = [];
  let lastFocusedBeforeModal = null;
  let latestQuery = "";

  function registerTag(id, label) {
    if (id == null) return null;
    const idStr = String(id);
    const trimmed = (label || "").trim();
    if (trimmed) {
      tagMeta.set(idStr, trimmed);
    } else if (!tagMeta.has(idStr)) {
      tagMeta.set(idStr, `태그 ${idStr}`);
    }
    return idStr;
  }

  function getTagLabel(id) {
    const idStr = String(id);
    return tagMeta.get(idStr) || `태그 ${idStr}`;
  }

  function syncHiddenInputs(ids) {
    hiddenTagInputs.innerHTML = "";
    ids.forEach((id) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "tag";
      input.value = id;
      const label = getTagLabel(id);
      if (label) {
        input.dataset.tagLabel = label;
      }
      hiddenTagInputs.appendChild(input);
    });
  }

  function createChip(id) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip selected";
    button.dataset.tagId = id;
    button.dataset.tagLabel = getTagLabel(id);
    button.textContent = getTagLabel(id);
    return button;
  }

  function renderFilterTags(ids) {
    filterTagContainer.innerHTML = "";
    if (!ids.length) {
      const empty = document.createElement("p");
      empty.className = "empty-copy";
      empty.textContent = "선택된 키워드가 없습니다.";
      filterTagContainer.appendChild(empty);
      return;
    }
    ids.forEach((id) => {
      filterTagContainer.appendChild(createChip(id));
    });
  }

  function renderHeroTags(ids) {
    if (!heroTagContainer) {
      return;
    }
    heroTagContainer.innerHTML = "";
    if (!ids.length) {
      const empty = document.createElement("p");
      empty.className = "tag-picker__empty";
      empty.textContent = "선택한 키워드가 없습니다.";
      heroTagContainer.appendChild(empty);
      return;
    }
    ids.forEach((id) => {
      heroTagContainer.appendChild(createChip(id));
    });
  }

  function commit() {
    const ids = Array.from(selectedSet);
    syncHiddenInputs(ids);
    renderFilterTags(ids);
    renderHeroTags(ids);
    renderResults(currentResults);
  }

  function removeTag(id) {
    const idStr = String(id);
    if (!selectedSet.has(idStr)) {
      return;
    }
    selectedSet.delete(idStr);
    commit();
  }

  function addTag(id, label) {
    const idStr = registerTag(id, label);
    if (!idStr) return;
    if (!selectedSet.has(idStr)) {
      selectedSet.add(idStr);
      commit();
    }
  }

  function renderResults(items) {
    if (!tagResultsBox) return;
    tagResultsBox.innerHTML = "";

    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "tag-picker__empty";
      empty.textContent = latestQuery ? "일치하는 태그가 없습니다." : "추천 태그가 아직 없어요.";
      tagResultsBox.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const idStr = registerTag(item.id, item.name);
      if (!idStr) {
        return;
      }
      const isSelected = selectedSet.has(idStr);

      const button = document.createElement("button");
      button.type = "button";
      button.className = "tag-modal__result";
      if (isSelected) {
        button.classList.add("is-selected");
      }
      button.dataset.tagId = idStr;

      const labelSpan = document.createElement("span");
      labelSpan.textContent = getTagLabel(idStr);
      button.appendChild(labelSpan);

      const actionSpan = document.createElement("span");
      actionSpan.className = "tag-modal__result-add";
      actionSpan.textContent = isSelected ? "추가됨" : "+ 추가";
      button.appendChild(actionSpan);

      button.addEventListener("click", () => {
        if (selectedSet.has(idStr)) {
          return;
        }
        selectedSet.add(idStr);
        commit();
        if (tagSearchInput) {
          tagSearchInput.focus({ preventScroll: true });
        }
      });

      tagResultsBox.appendChild(button);
    });
  }

  async function fetchTagResults(query) {
    const trimmed = (query || "").trim();
    latestQuery = trimmed;
    const params = new URLSearchParams();
    if (trimmed) {
      params.set("search", trimmed);
    }
    params.set("ordering", "name");
    params.set("page_size", "30");

    const url = `${tagEndpoint}?${params.toString()}`;
    if (tagResultsBox) {
      tagResultsBox.innerHTML = '<p class="tag-picker__empty">검색 중...</p>';
    }

    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`태그 검색에 실패했습니다 (${response.status})`);
      }
      const payload = await response.json();
      const items = Array.isArray(payload?.results) ? payload.results : Array.isArray(payload) ? payload : [];
      currentResults = items
        .filter((item) => item && item.id != null)
        .map((item) => ({ id: item.id, name: item.name || `태그 ${item.id}` }));
      renderResults(currentResults);
    } catch (error) {
      currentResults = [];
      tagResultsBox.innerHTML = "";
      const message = document.createElement("p");
      message.className = "tag-picker__empty";
      message.textContent = error.message || "태그 목록을 불러오지 못했어요.";
      tagResultsBox.appendChild(message);
    }
  }

  function loadInitialSuggestions() {
    const node = document.getElementById("tag-suggestions-data");
    if (!node) {
      currentResults = [];
      renderResults(currentResults);
      fetchTagResults("");
      return;
    }
    try {
      const parsed = JSON.parse(node.textContent || "[]");
      const items = Array.isArray(parsed) ? parsed : [];
      currentResults = items
        .filter((item) => item && item.id != null)
        .map((item) => ({ id: item.id, name: item.name || `태그 ${item.id}` }));
      renderResults(currentResults);
      if (!currentResults.length) {
        fetchTagResults("");
      }
    } catch (error) {
      currentResults = [];
      renderResults(currentResults);
      fetchTagResults("");
    }
  }

  function openTagModal() {
    if (!tagModal || !tagResultsBox) return;
    if (!tagModal.classList.contains("hidden")) {
      return;
    }
    lastFocusedBeforeModal = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    tagModal.classList.remove("hidden");
    tagModal.setAttribute("aria-hidden", "false");
    if (!latestQuery) {
      renderResults(currentResults);
    }
    requestAnimationFrame(() => {
      if (tagSearchInput) {
        tagSearchInput.focus({ preventScroll: true });
        tagSearchInput.select();
      }
    });
  }

  function closeTagModal(options = {}) {
    if (!tagModal) return;
    if (tagModal.classList.contains("hidden")) {
      return;
    }
    const { restoreFocus = true, clearSearch = false } = options;
    tagModal.classList.add("hidden");
    tagModal.setAttribute("aria-hidden", "true");
    if (clearSearch && tagSearchInput) {
      tagSearchInput.value = "";
      latestQuery = "";
      loadInitialSuggestions();
    }
    if (restoreFocus && lastFocusedBeforeModal && typeof lastFocusedBeforeModal.focus === "function") {
      lastFocusedBeforeModal.focus({ preventScroll: true });
    }
    lastFocusedBeforeModal = null;
  }

  function handleChipContainerClick(event) {
    const chip = event.target.closest('.chip[data-tag-id]');
    if (!chip) {
      return;
    }
    removeTag(chip.dataset.tagId);
  }

  function handleSearchInputChange() {
    if (!tagSearchInput) return;
    const value = tagSearchInput.value;
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(() => {
      fetchTagResults(value);
    }, TAG_SEARCH_DEBOUNCE);
  }

  function initSelectedTags() {
    hiddenTagInputs
      .querySelectorAll('input[name="tag"]')
      .forEach((input) => {
        const idStr = registerTag(input.value, input.dataset.tagLabel);
        if (idStr) {
          selectedSet.add(idStr);
        }
      });

    filterTagContainer
      .querySelectorAll('.chip[data-tag-id]')
      .forEach((chip) => {
        const idStr = registerTag(chip.dataset.tagId, chip.dataset.tagLabel || chip.textContent);
        if (idStr) {
          selectedSet.add(idStr);
        }
      });

    if (heroTagContainer) {
      heroTagContainer
        .querySelectorAll('.chip[data-tag-id]')
        .forEach((chip) => {
          const idStr = registerTag(chip.dataset.tagId, chip.dataset.tagLabel || chip.textContent);
          if (idStr) {
            selectedSet.add(idStr);
          }
        });
    }

    commit();
  }

  initSelectedTags();
  loadInitialSuggestions();

  if (heroTagContainer) {
    heroTagContainer.addEventListener("click", handleChipContainerClick);
  }
  filterTagContainer.addEventListener("click", handleChipContainerClick);

  if (openTagModalButton) {
    openTagModalButton.addEventListener("click", () => {
      openTagModal();
    });
  }

  tagModalCloseElements.forEach((element) => {
    element.addEventListener("click", () => {
      closeTagModal({ clearSearch: true });
    });
  });

  if (tagSearchInput) {
    tagSearchInput.addEventListener("input", handleSearchInputChange);
    tagSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeTagModal({ clearSearch: true });
      }
      if (event.key === "Enter") {
        event.preventDefault();
        const first = tagResultsBox.querySelector('.tag-modal__result:not(.is-selected)');
        if (first) {
          const id = first.dataset.tagId;
          addTag(id);
          if (tagSearchInput) {
            tagSearchInput.focus({ preventScroll: true });
          }
        }
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && tagModal && !tagModal.classList.contains("hidden")) {
      event.preventDefault();
      closeTagModal({ clearSearch: true });
    }
  });
})();
