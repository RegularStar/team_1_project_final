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

  document.querySelectorAll('input[type="range"][data-slider-target]').forEach((slider) => {
    const targetSelector = slider.getAttribute("data-slider-target");
    const output = targetSelector ? document.querySelector(targetSelector) : null;
    if (!output) return;

    const update = () => {
      output.textContent = slider.value;
    };

    slider.addEventListener("input", update);
    update();
  });

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
})();
