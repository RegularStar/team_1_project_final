(function () {
  const panel = document.querySelector('[data-role="interest-tags-panel"]');
  if (!panel) {
    return;
  }

  const form = panel.querySelector('[data-role="interest-tag-form"]');
  const hiddenInput = form ? form.querySelector('[data-role="tag-input"]') : null;
  const openButton = panel.querySelector('[data-role="open-tag-modal"]');
  const modal = panel.querySelector('[data-role="tag-modal"]');
  const searchInput = modal ? modal.querySelector('[data-role="tag-search-input"]') : null;
  const resultsBox = modal ? modal.querySelector('[data-role="tag-modal-results"]') : null;
  const closeElements = modal ? Array.from(modal.querySelectorAll('[data-role="tag-modal-close"]')) : [];
  const backdrop = modal ? modal.querySelector('.tag-modal__backdrop') : null;
  const endpoint = panel.dataset.tagsEndpoint || "";

  if (!form || !hiddenInput || !openButton || !modal || !searchInput || !resultsBox || !endpoint) {
    return;
  }

  const selectedTags = new Set();

  function normalizeName(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function keyFor(value) {
    return normalizeName(value).toLowerCase();
  }

  panel.querySelectorAll("[data-tag-name]").forEach((node) => {
    const label = node.getAttribute("data-tag-name") || node.textContent;
    const key = keyFor(label);
    if (key) {
      selectedTags.add(key);
    }
  });

  let lastFocused = null;
  let debounceTimer = null;
  let latestQuery = "";
  let currentResults = [];

  function isModalOpen() {
    return !modal.classList.contains("hidden");
  }

  function focusSearchInput() {
    requestAnimationFrame(() => {
      searchInput.focus({ preventScroll: true });
    });
  }

  function openModal() {
    lastFocused = document.activeElement;
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    searchInput.value = "";
    latestQuery = "";
    currentResults = [];
    renderResults([]);
    fetchResults("");
    focusSearchInput();
  }

  function closeModal() {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    searchInput.value = "";
    latestQuery = "";
    currentResults = [];
    resultsBox.innerHTML = "";
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
  }

  function showMessage(message) {
    resultsBox.innerHTML = "";
    const paragraph = document.createElement("p");
    paragraph.className = "tag-picker__empty";
    paragraph.textContent = message;
    resultsBox.appendChild(paragraph);
  }

  function renderResults(items) {
    resultsBox.innerHTML = "";

    const hasQuery = Boolean(normalizeName(latestQuery));

    if (!items.length && !hasQuery) {
      showMessage("추가할 태그를 검색해보세요.");
      return;
    }

    if (!items.length && hasQuery) {
      const info = document.createElement("p");
      info.className = "tag-picker__empty";
      info.textContent = "일치하는 태그가 없습니다.";
      resultsBox.appendChild(info);
    }

    items.forEach((item) => {
      const label = normalizeName(item.name || "");
      if (!label) {
        return;
      }
      const key = keyFor(label);
      const isSelected = selectedTags.has(key);

      const button = document.createElement("button");
      button.type = "button";
      button.className = "tag-modal__result";
      if (isSelected) {
        button.classList.add("is-selected");
      }

      const labelSpan = document.createElement("span");
      labelSpan.textContent = label;
      button.appendChild(labelSpan);

      const actionSpan = document.createElement("span");
      actionSpan.className = "tag-modal__result-add";
      actionSpan.textContent = isSelected ? "추가됨" : "+ 추가";
      button.appendChild(actionSpan);

      if (!isSelected) {
        button.addEventListener("click", () => {
          handleSelect(label);
        });
      }

      resultsBox.appendChild(button);
    });

    const normalizedQuery = keyFor(latestQuery);
    if (
      normalizedQuery &&
      !selectedTags.has(normalizedQuery) &&
      !items.some((item) => keyFor(item.name || "") === normalizedQuery)
    ) {
      const createButton = document.createElement("button");
      createButton.type = "button";
      createButton.className = "tag-modal__result";

      const labelSpan = document.createElement("span");
      labelSpan.textContent = `새 태그 \"${normalizeName(latestQuery)}\" 추가`;
      createButton.appendChild(labelSpan);

      const actionSpan = document.createElement("span");
      actionSpan.className = "tag-modal__result-add";
      actionSpan.textContent = "+ 추가";
      createButton.appendChild(actionSpan);

      createButton.addEventListener("click", () => {
        handleSelect(latestQuery);
      });

      resultsBox.appendChild(createButton);
    }
  }

  async function fetchResults(query) {
    const trimmed = normalizeName(query);
    latestQuery = query;

    const params = new URLSearchParams();
    if (trimmed) {
      params.set("search", trimmed);
    }
    params.set("ordering", "name");
    params.set("page_size", "30");

    showMessage("검색 중...");

    try {
      const response = await fetch(`${endpoint}?${params.toString()}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`태그 목록을 불러오지 못했어요. (${response.status})`);
      }
      const payload = await response.json();
      const results = Array.isArray(payload?.results)
        ? payload.results
        : Array.isArray(payload)
        ? payload
        : [];
      currentResults = results
        .filter((item) => item && item.id != null)
        .map((item) => ({ id: item.id, name: item.name || String(item.id) }));
      renderResults(currentResults);
    } catch (error) {
      currentResults = [];
      showMessage(error.message || "태그 목록을 불러오지 못했어요.");
    }
  }

  function scheduleFetch(query) {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(() => {
      fetchResults(query);
    }, 200);
  }

  function handleSelect(name) {
    const normalized = normalizeName(name);
    if (!normalized) {
      return;
    }
    const key = keyFor(normalized);
    if (selectedTags.has(key)) {
      closeModal();
      return;
    }
    hiddenInput.value = normalized;
    form.submit();
  }

  openButton.addEventListener("click", () => {
    openModal();
  });

  closeElements.forEach((element) => {
    element.addEventListener("click", () => {
      closeModal();
    });
  });

  if (backdrop) {
    backdrop.addEventListener("click", () => {
      closeModal();
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isModalOpen()) {
      event.preventDefault();
      closeModal();
    }
  });

  searchInput.addEventListener("input", (event) => {
    scheduleFetch(event.target.value);
  });

  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (currentResults.length) {
        const first = currentResults.find((item) => !selectedTags.has(keyFor(item.name || "")));
        if (first) {
          handleSelect(first.name);
          return;
        }
      }
      if (normalizeName(latestQuery)) {
        handleSelect(latestQuery);
      }
    }
  });
})();
