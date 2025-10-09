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

  const quickTagContainer = form.querySelector(".quick-tags");
  const keywordBucket = form.querySelector('[data-role="selected-tags-display"]');
  const hiddenTagInputs = form.querySelector('[data-role="selected-tag-inputs"]');

  if (!quickTagContainer || !keywordBucket || !hiddenTagInputs) {
    return;
  }

  const tagMeta = {};

  function registerTag(id, label) {
    if (!id) return;
    const trimmed = (label || "").trim();
    if (trimmed) {
      tagMeta[id] = trimmed;
    } else if (!(id in tagMeta)) {
      tagMeta[id] = `태그 ${id}`;
    }
  }

  quickTagContainer
    .querySelectorAll('.chip[data-tag-id]')
    .forEach((button) => {
      registerTag(button.dataset.tagId, button.dataset.tagLabel || button.textContent);
    });

  hiddenTagInputs
    .querySelectorAll('input[name="tag"]')
    .forEach((input) => {
      registerTag(input.value, input.dataset.tagLabel);
    });

  keywordBucket
    .querySelectorAll('[data-tag-id]')
    .forEach((node) => {
      registerTag(node.dataset.tagId, node.dataset.tagLabel || node.textContent);
    });

  const selectedSet = new Set(
    Array.from(hiddenTagInputs.querySelectorAll('input[name="tag"]')).map(
      (input) => input.value
    )
  );

  function syncHiddenInputs(ids) {
    hiddenTagInputs.innerHTML = "";
    ids.forEach((id) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "tag";
      input.value = id;
      const label = tagMeta[id];
      if (label) {
        input.dataset.tagLabel = label;
      }
      hiddenTagInputs.appendChild(input);
    });
  }

  function renderSelectedTags(ids) {
    keywordBucket.innerHTML = "";
    ids.forEach((id) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chip selected";
      button.dataset.tagId = id;
      button.dataset.tagLabel = tagMeta[id] || `태그 ${id}`;
      button.textContent = tagMeta[id] || `태그 ${id}`;
      keywordBucket.appendChild(button);
    });
  }

  function syncQuickTagState(ids) {
    const active = new Set(ids);
    quickTagContainer.querySelectorAll('.chip[data-tag-id]').forEach((button) => {
      const id = button.dataset.tagId;
      button.classList.toggle("active", active.has(id));
    });
  }

  function commit() {
    const ids = Array.from(selectedSet);
    syncHiddenInputs(ids);
    renderSelectedTags(ids);
    syncQuickTagState(ids);
  }

  commit();

  quickTagContainer.addEventListener("click", (event) => {
    const button = event.target.closest('.chip[data-tag-id]');
    if (!button || button.classList.contains("disabled")) {
      return;
    }
    const id = button.dataset.tagId;
    registerTag(id, button.dataset.tagLabel || button.textContent);
    if (selectedSet.has(id)) {
      selectedSet.delete(id);
    } else {
      selectedSet.add(id);
    }
    commit();
  });

  keywordBucket.addEventListener("click", (event) => {
    const tagItem = event.target.closest('.chip[data-tag-id]');
    if (!tagItem) {
      return;
    }
    const id = tagItem.dataset.tagId;
    if (selectedSet.has(id)) {
      selectedSet.delete(id);
      commit();
    }
  });
})();
