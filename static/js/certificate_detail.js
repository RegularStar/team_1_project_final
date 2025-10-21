(function () {
  const infoButton = document.querySelector(".difficulty-info");
  const popover = document.getElementById("difficulty-popover");

  if (infoButton && popover) {
    const hide = () => {
      if (popover.hasAttribute("hidden")) return;
      popover.setAttribute("hidden", "");
      infoButton.setAttribute("aria-expanded", "false");
    };

    const toggle = () => {
      const isHidden = popover.hasAttribute("hidden");
      if (isHidden) {
        popover.removeAttribute("hidden");
        infoButton.setAttribute("aria-expanded", "true");
      } else {
        hide();
      }
    };

    infoButton.addEventListener("click", (event) => {
      event.stopPropagation();
      toggle();
    });

    document.addEventListener("click", (event) => {
      if (!popover || popover.hasAttribute("hidden")) return;
      if (popover.contains(event.target) || event.target === infoButton) return;
      hide();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hide();
      }
    });
  }

<<<<<<< HEAD
  document.querySelectorAll('input[type="range"][data-slider-target]').forEach((slider) => {
    const targetSelector = slider.getAttribute("data-slider-target");
    const output = targetSelector ? document.querySelector(targetSelector) : null;
    if (!output) return;

    const update = () => {
      output.textContent = slider.value;
=======
  const clamp = (value) => {
    if (!Number.isFinite(value)) {
      return 0;
    }
    if (value < 0) return 0;
    if (value > 10) return 10;
    return value;
  };

  const applyGaugeValue = (gauge, rawValue) => {
    if (!gauge) return;
    const numeric = clamp(Number(rawValue));
    const normalized = numeric / 10;
    const percent = `${normalized * 100}%`;
    let indicatorPercent;
    let indicatorOffset = 0;
    if (normalized <= 0.001) {
      indicatorPercent = "0%";
      indicatorOffset = 10;
    } else if (normalized >= 0.999) {
      indicatorPercent = "100%";
      indicatorOffset = -10;
    } else {
      const indicatorBound = Math.min(Math.max(normalized, 0.04), 0.96);
      indicatorPercent = `${indicatorBound * 100}%`;
    }
    const hue = 120 - normalized * 120;
    const cappedHue = Math.max(0, Math.min(120, hue));
    const color = `hsl(${cappedHue}, 85%, 55%)`;
    gauge.dataset.difficulty = String(numeric);
    gauge.style.setProperty("--difficulty-percent", percent);
    gauge.style.setProperty("--difficulty-indicator", indicatorPercent);
    gauge.style.setProperty("--difficulty-indicator-offset", `${indicatorOffset}px`);
    gauge.style.setProperty("--difficulty-color", color);
  };

  document.querySelectorAll("[data-role=\"difficulty-gauge\"]").forEach((gauge) => {
    const rawValue = parseFloat(gauge.dataset.difficulty || "0");
    applyGaugeValue(gauge, rawValue);
  });

  document.querySelectorAll('input[type="range"][data-slider-target]').forEach((slider) => {
    const targetSelector = slider.getAttribute("data-slider-target");
    const output = targetSelector ? document.querySelector(targetSelector) : null;
    const gauge = slider.closest("[data-role=\"difficulty-gauge\"]");

    const update = () => {
      if (output) {
        output.textContent = slider.value;
      }
      if (gauge) {
        applyGaugeValue(gauge, slider.value);
      }
>>>>>>> seil2
    };

    slider.addEventListener("input", update);
    update();
  });

<<<<<<< HEAD
=======
  const collapsibleCards = Array.from(document.querySelectorAll("[data-role=\"collapsible-card\"]"));
  if (collapsibleCards.length) {
    collapsibleCards.forEach((card) => {
      const content = card.querySelector(".summary-card__content");
      const toggle = card.querySelector("[data-role=\"collapsible-toggle\"]");
      if (!content || !toggle) {
        return;
      }

      let expanded = false;

      const setExpanded = (next) => {
        expanded = Boolean(next);
        card.classList.toggle("is-expanded", expanded);
        card.classList.toggle("is-collapsed", !expanded);
        toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
        toggle.textContent = expanded ? "접기" : "펼쳐보기";
        content.hidden = !expanded;
      };

      toggle.addEventListener("click", () => {
        setExpanded(!expanded);
      });

      setExpanded(false);
    });
  }

>>>>>>> seil2
  const tooltipButtons = document.querySelectorAll(".info-tooltip[data-tip]");
  tooltipButtons.forEach((btn) => {
    const text = btn.dataset.tip;
    if (!text) return;

    let tooltipEl;

    const create = () => {
      tooltipEl = document.createElement("div");
      tooltipEl.className = "tooltip-popover";
      tooltipEl.textContent = text;
      document.body.appendChild(tooltipEl);
    };

    const show = () => {
      if (!tooltipEl) create();
      const rect = btn.getBoundingClientRect();
      tooltipEl.style.left = `${rect.left + rect.width / 2}px`;
      tooltipEl.style.top = `${rect.top + window.scrollY - 8}px`;
      tooltipEl.classList.add("visible");
    };

    const hideTooltip = () => {
      if (tooltipEl) tooltipEl.classList.remove("visible");
    };

    btn.addEventListener("mouseenter", show);
    btn.addEventListener("focus", show);
    btn.addEventListener("mouseleave", hideTooltip);
    btn.addEventListener("blur", hideTooltip);
  });
<<<<<<< HEAD
=======

  const reviewMenus = Array.from(document.querySelectorAll("[data-role=\"review-menu\"]"));
  const closeMenu = (menu) => {
    const trigger = menu.querySelector(".review-menu__trigger");
    const popover = menu.querySelector(".review-menu__popover");
    if (!trigger || !popover) return;
    trigger.setAttribute("aria-expanded", "false");
    popover.hidden = true;
  };

  const closeAllMenus = () => {
    reviewMenus.forEach((menu) => closeMenu(menu));
  };

  reviewMenus.forEach((menu) => {
    const trigger = menu.querySelector(".review-menu__trigger");
    const popover = menu.querySelector(".review-menu__popover");
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
    if (!reviewMenus.length) return;
    const target = event.target;
    const menu = reviewMenus.find((candidate) => candidate.contains(target));
    if (!menu) {
      closeAllMenus();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAllMenus();
    }
  });

  const sliderInput =
    document.getElementById("perceived-difficulty") ||
    document.getElementById("reviews-perceived-difficulty");
  const feedbackComment =
    document.getElementById("feedback-comment") ||
    document.getElementById("reviews-feedback-comment");
  const feedbackTitle =
    document.getElementById("difficulty-feedback-title") ||
    document.getElementById("reviews-feedback-title");

  const applyEditPayload = (difficulty, comment) => {
    if (sliderInput) {
      const min = Number(sliderInput.min || 0);
      const max = Number(sliderInput.max || 10);
      const safeValue = Math.min(Math.max(difficulty, min || 0), max || 10);
      sliderInput.value = String(safeValue);
      sliderInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
    if (feedbackComment != null) {
      feedbackComment.value = comment;
      feedbackComment.focus();
    }
    if (feedbackTitle) {
      feedbackTitle.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  document.querySelectorAll('.review-menu__item[data-action="edit"]').forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      const difficulty = Number.parseFloat(button.dataset.difficulty || "0") || 0;
      const comment = button.dataset.comment || "";
      closeAllMenus();
      applyEditPayload(clamp(difficulty), comment);
    });
  });
>>>>>>> seil2
})();
