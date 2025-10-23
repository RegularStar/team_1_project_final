(function () {
  const picker = document.querySelector('[data-role="global-board-picker"]');
  if (!picker) {
    return;
  }

  const endpoint = picker.dataset.endpoint;
  const template = picker.dataset.boardUrlTemplate;
  if (!endpoint || !template) {
    return;
  }

  const openBtn = picker.querySelector('[data-role="board-picker-open"]');
  const selectedLabel = picker.querySelector('[data-role="board-picker-selected"]');
  const modal = document.querySelector('[data-role="board-picker-modal"]');

  if (!openBtn || !modal) {
    return;
  }

  const closeElements = Array.from(modal.querySelectorAll('[data-role="board-picker-close"]'));
  const searchInput = modal.querySelector('[data-role="board-picker-search"]');
  const resultsBox = modal.querySelector('[data-role="board-picker-results"]');
  const backdrop = modal.querySelector('.tag-modal__backdrop');

  if (!searchInput || !resultsBox) {
    return;
  }

  let debounceId = null;
  let latestQuery = "";
  let currentResults = [];
  let lastFocused = null;

  function updateSelectedLabel(name) {
    if (!selectedLabel) {
      return;
    }
    selectedLabel.textContent = name ? `${name} 게시판` : "전체 게시판";
  }

  function openModal() {
    lastFocused = document.activeElement;
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    searchInput.value = "";
    latestQuery = "";
    currentResults = [];
    renderMessage("자격증을 검색해보세요.");
    fetchResults("");
    requestAnimationFrame(() => {
      searchInput.focus({ preventScroll: true });
    });
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

  function renderMessage(message) {
    resultsBox.innerHTML = "";
    const paragraph = document.createElement("p");
    paragraph.className = "tag-picker__empty";
    paragraph.textContent = message;
    resultsBox.appendChild(paragraph);
  }

  function renderResults(items) {
    resultsBox.innerHTML = "";

    if (!items.length) {
      if (latestQuery) {
        renderMessage("일치하는 자격증이 없습니다.");
      } else {
        renderMessage("자격증을 검색해보세요.");
      }
      return;
    }

    items.forEach((item) => {
      if (!item || item.id == null) {
        return;
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = "tag-modal__result";

      const label = document.createElement("span");
      label.textContent = item.name || String(item.id);
      button.appendChild(label);

      const action = document.createElement("span");
      action.className = "tag-modal__result-add";
      action.textContent = "이동";
      button.appendChild(action);

      button.addEventListener("click", () => {
        redirectToBoard(item);
      });

      resultsBox.appendChild(button);
    });
  }

  function redirectToBoard(item) {
    const slugValue = item.slug || item.id;
    const slug = slugValue != null ? String(slugValue) : "";
    const targetUrl = template.replace("__slug__", encodeURIComponent(slug));
    updateSelectedLabel(item.name);
    window.location.href = targetUrl;
  }

  async function fetchResults(query) {
    const trimmed = String(query || "").trim();
    latestQuery = trimmed;

    const params = new URLSearchParams();
    if (trimmed) {
      params.set("search", trimmed);
    }
    params.set("ordering", "name");
    params.set("page_size", "30");

    renderMessage("검색 중...");

    try {
      const queryString = params.toString();
      const requestUrl = queryString ? `${endpoint}?${queryString}` : endpoint;
      const response = await fetch(requestUrl, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`자격증 목록을 불러오지 못했어요. (${response.status})`);
      }
      const payload = await response.json();
      const results = Array.isArray(payload?.results)
        ? payload.results
        : Array.isArray(payload)
        ? payload
        : [];
      currentResults = results
        .map((entry) => ({
          id: entry?.id,
          slug: entry?.slug ?? entry?.id,
          name: entry?.name ? String(entry.name) : String(entry?.id ?? ""),
        }))
        .filter((entry) => entry.id != null && entry.name);
      renderResults(currentResults);
    } catch (error) {
      renderMessage(error.message || "자격증 목록을 불러오지 못했어요.");
    }
  }

  function scheduleFetch(value) {
    if (debounceId) {
      clearTimeout(debounceId);
    }
    debounceId = setTimeout(() => {
      fetchResults(value);
    }, 200);
  }

  openBtn.addEventListener("click", openModal);
  closeElements.forEach((element) => {
    element.addEventListener("click", closeModal);
  });
  if (backdrop) {
    backdrop.addEventListener("click", closeModal);
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      event.preventDefault();
      closeModal();
    }
  });
  searchInput.addEventListener("input", (event) => {
    scheduleFetch(event.target.value || "");
  });
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (currentResults.length) {
        redirectToBoard(currentResults[0]);
      }
    }
  });
})();
