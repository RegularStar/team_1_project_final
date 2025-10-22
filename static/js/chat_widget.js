(function () {
  const widget = document.getElementById("chatbot-widget");
  if (!widget) {
    return;
  }

  const launcher = widget.querySelector("[data-role='launcher']");
  const panel = widget.querySelector("[data-role='panel']");
  const closeButton = widget.querySelector("[data-role='close']");
  const messagesBox = widget.querySelector("[data-role='messages']");
  const form = widget.querySelector("[data-role='form']");
  const textarea = widget.querySelector("[data-role='input']");
  const sendButton = widget.querySelector("[data-role='send']");
  const adminPrompt = widget.querySelector("[data-role='admin-prompt']");
  const adminPromptText = widget.querySelector("[data-role='prompt-text']");
  const confirmButton = adminPrompt.querySelector("[data-action='confirm']");
  const cancelButton = adminPrompt.querySelector("[data-action='cancel']");

  const chatEndpoint = widget.dataset.chatEndpoint || "";
  const inquiryEndpoint = widget.dataset.inquiryEndpoint || "";
  const isAuthenticated = widget.dataset.authenticated === "true";

  const DEFAULT_GREETING =
    "안녕하세요! SkillBridge AI 상담이에요. 자격증 추가 요청, 정보 수정, 통계 자료 등 필요한 내용을 말씀해 주세요.";
  const OUT_OF_SCOPE_REPLY =
    "죄송하지만, 자격증 및 커리어와 직접 관련된 질문에 대해서만 도와드릴 수 있어요.";

  const state = {
    history: [],
    isSending: false,
    pendingAdmin: null,
    greeted: false,
  };

  function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function createMessageElement(role, content) {
    const wrapper = document.createElement("div");
    wrapper.className = `chatbot__message chatbot__message--${role}`;
    wrapper.innerHTML = escapeHtml(content);
    return wrapper;
  }

  function addMessage(role, content) {
    const el = createMessageElement(role, content);
    messagesBox.appendChild(el);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  function addSystemMessage(content) {
    const el = document.createElement("div");
    el.className = "chatbot__message chatbot__message--system";
    el.innerHTML = escapeHtml(content);
    messagesBox.appendChild(el);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  function togglePanel(show) {
    if (show) {
      panel.classList.remove("chatbot__panel--hidden");
      textarea?.focus();
      if (!state.greeted) {
        addMessage("assistant", DEFAULT_GREETING);
        state.history.push({ role: "assistant", content: DEFAULT_GREETING });
        state.greeted = true;
      }
    } else {
      panel.classList.add("chatbot__panel--hidden");
    }
  }

  function setSending(isSending) {
    state.isSending = isSending;
    if (sendButton) {
      sendButton.disabled = isSending || !isAuthenticated;
    }
    if (textarea) {
      textarea.disabled = isSending || !isAuthenticated;
    }
  }

  function resetAdminPrompt() {
    state.pendingAdmin = null;
    adminPrompt.classList.add("hidden");
    adminPromptText.textContent = "";
  }

  function showAdminPrompt(summaryText, metadata) {
    state.pendingAdmin = metadata;
    adminPromptText.textContent = summaryText;
    adminPrompt.classList.remove("hidden");
  }

  function composeConversationDetail() {
    return state.history
      .map((item) => {
        const speaker = item.role === "assistant" ? "AI" : "사용자";
        return `${speaker}: ${item.content}`;
      })
      .join("\n");
  }

  function handleSendMessage(event) {
    event.preventDefault();
    if (!isAuthenticated) {
      addSystemMessage("로그인 후 상담을 이용하실 수 있어요.");
      return;
    }
    if (state.isSending) {
      return;
    }

    const value = textarea.value.trim();
    if (!value) {
      return;
    }

    addMessage("user", value);
    state.history.push({ role: "user", content: value });
    textarea.value = "";
    resetAdminPrompt();
    sendToAssistant(value);
  }

  async function sendToAssistant(message) {
    if (!chatEndpoint) {
      addSystemMessage("챗봇 서비스가 준비되지 않았습니다.");
      return;
    }

    setSending(true);
    try {
      const response = await fetch(chatEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        credentials: "include",
        body: JSON.stringify({
          message,
          history: state.history.slice(0, -1), // exclude the latest user entry duplicated later
        }),
      });

      if (!response.ok) {
        throw new Error("response-error");
      }

      const data = await response.json();
      const reply = data.reply || OUT_OF_SCOPE_REPLY;
      const metadata = data.metadata || {};
      const history = Array.isArray(data.history) ? data.history : null;

      addMessage("assistant", reply);
      state.history = history || [...state.history, { role: "assistant", content: reply }];

      if (metadata.needs_admin) {
        const summary = metadata.admin_summary || "해당 문의를 운영자에게 전달할까요?";
        showAdminPrompt(summary, {
          intent: metadata.intent || "general_help",
          summary,
        });
      } else {
        resetAdminPrompt();
      }
    } catch (error) {
      console.error("chatbot error", error);
      addSystemMessage("죄송하지만 지금은 응답할 수 없어요. 잠시 후 다시 시도해주세요.");
      if (state.history.length && state.history[state.history.length - 1].role === "user") {
        state.history.pop();
      }
    } finally {
      setSending(false);
    }
  }

  async function submitInquiry() {
    if (!state.pendingAdmin || !inquiryEndpoint) {
      return;
    }
    const payload = {
      intent: state.pendingAdmin.intent || "general_help",
      summary: state.pendingAdmin.summary || "사용자 문의",
      detail: composeConversationDetail(),
      conversation: state.history,
    };

    setSending(true);
    try {
      const response = await fetch(inquiryEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error("submit-error");
      }

      const confirmMessage = "요청을 운영자에게 전달했습니다. 빠르게 확인해드릴게요!";
      addMessage("assistant", confirmMessage);
      state.history.push({ role: "assistant", content: confirmMessage });
    } catch (error) {
      console.error("chatbot submission error", error);
      addSystemMessage("전송 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      resetAdminPrompt();
      setSending(false);
    }
  }

  function declineInquiry() {
    resetAdminPrompt();
    const message = "알겠습니다. 도움이 필요하시면 언제든 말씀해주세요.";
    addMessage("assistant", message);
    state.history.push({ role: "assistant", content: message });
  }

  launcher?.addEventListener("click", () => togglePanel(true));
  closeButton?.addEventListener("click", () => togglePanel(false));
  form?.addEventListener("submit", handleSendMessage);

  confirmButton?.addEventListener("click", () => {
    if (!isAuthenticated) {
      addSystemMessage("로그인 후 상담을 이용하실 수 있어요.");
      return;
    }
    submitInquiry();
  });

  cancelButton?.addEventListener("click", declineInquiry);

  if (!isAuthenticated) {
    textarea.placeholder = "로그인 후 이용 가능합니다.";
    textarea.disabled = true;
    sendButton.disabled = true;
  }
})();
