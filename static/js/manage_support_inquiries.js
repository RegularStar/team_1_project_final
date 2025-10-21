(function () {
  const toggles = document.querySelectorAll("[data-role='toggle-detail']");
  toggles.forEach((button) => {
    const targetId = button.dataset.target;
    const panel = document.getElementById(targetId);
    if (!panel) return;

    button.addEventListener("click", () => {
      const isHidden = panel.hasAttribute("hidden");
      if (isHidden) {
        panel.removeAttribute("hidden");
        panel.classList.remove("hidden");
        button.textContent = "상세 대화 닫기";
        button.setAttribute("aria-expanded", "true");
      } else {
        panel.setAttribute("hidden", "hidden");
        panel.classList.add("hidden");
        button.textContent = "상세 대화 보기";
        button.setAttribute("aria-expanded", "false");
      }
    });
  });
})();
