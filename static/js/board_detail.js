(() => {
  const commentMenus = Array.from(document.querySelectorAll('[data-role="comment-menu"]'));

  const closeMenu = (menu) => {
    const trigger = menu.querySelector(".comment-menu__trigger");
    const popover = menu.querySelector(".comment-menu__popover");
    if (!trigger || !popover) return;
    trigger.setAttribute("aria-expanded", "false");
    popover.hidden = true;
  };

  const closeAllMenus = () => {
    commentMenus.forEach((menu) => closeMenu(menu));
  };

  commentMenus.forEach((menu) => {
    const trigger = menu.querySelector(".comment-menu__trigger");
    const popover = menu.querySelector(".comment-menu__popover");
    if (!trigger || !popover) return;
    closeMenu(menu);
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const isExpanded = trigger.getAttribute("aria-expanded") === "true";
      closeAllMenus();
      if (!isExpanded) {
        trigger.setAttribute("aria-expanded", "true");
        popover.hidden = false;
      }
    });
  });

  document.addEventListener("click", (event) => {
    if (!commentMenus.length) return;
    const target = event.target;
    const activeMenu = commentMenus.find((menu) => menu.contains(target));
    if (!activeMenu) {
      closeAllMenus();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAllMenus();
    }
  });

  const form = document.querySelector('[data-role="comment-form"]');
  if (!form) return;

  const textarea = form.querySelector("textarea[name='body']");
  const commentIdField = form.querySelector('input[name="comment_id"]');
  const submitButton = form.querySelector('[data-role="comment-submit"]');
  const cancelButton = form.querySelector('[data-role="comment-cancel"]');
  const editHint = form.querySelector('[data-role="comment-edit-hint"]');

  if (!textarea || !commentIdField || !submitButton || !cancelButton) return;

  const defaultLabel = submitButton.dataset.defaultLabel || submitButton.textContent.trim();
  const editLabel = submitButton.dataset.editLabel || defaultLabel;

  let draftValue = commentIdField.value ? "" : textarea.value;

  const setEditingState = (isEditing) => {
    submitButton.textContent = isEditing ? editLabel : defaultLabel;
    cancelButton.hidden = !isEditing;
    if (editHint) {
      editHint.hidden = !isEditing;
    }
  };

  const startEditing = (commentId, body) => {
    if (!commentIdField.value) {
      draftValue = textarea.value;
    }
    commentIdField.value = commentId;
    textarea.value = body;
    setEditingState(true);
    closeAllMenus();
    textarea.focus();
    form.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const cancelEditing = () => {
    commentIdField.value = "";
    textarea.value = draftValue;
    setEditingState(false);
    textarea.focus();
  };

  if (commentIdField.value) {
    setEditingState(true);
  } else {
    setEditingState(false);
  }

  cancelButton.addEventListener("click", (event) => {
    event.preventDefault();
    cancelEditing();
  });

  textarea.addEventListener("input", () => {
    if (!commentIdField.value) {
      draftValue = textarea.value;
    }
  });

  document.querySelectorAll('.comment-menu__item[data-action="edit"]').forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      const commentId = button.dataset.commentId || "";
      const commentBody = button.dataset.commentBody || "";
      startEditing(commentId, commentBody);
    });
  });
})();
