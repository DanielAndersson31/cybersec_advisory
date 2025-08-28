document.addEventListener("DOMContentLoaded", () => {
  // Wait for marked.js to be available before initializing
  const waitForMarked = (callback, maxAttempts = 50) => {
    let attempts = 0;

    const check = () => {
      attempts++;
      if (window.marked) {
        console.log("Marked.js found, initializing chat...");
        callback();
      } else if (attempts < maxAttempts) {
        setTimeout(check, 100); // Check again in 100ms
      } else {
        console.warn("Marked.js not found after", maxAttempts, "attempts, proceeding without it");
        callback();
      }
    };

    check();
  };
  // --- DOM Elements ---
  const chatContainer = document.getElementById("chat-container");
  const messageInput = document.getElementById("message-input");
  const sendBtn = document.getElementById("send-btn");
  const newChatBtn = document.getElementById("new-chat-btn");
  const chatList = document.getElementById("chat-list");
  const chatTitle = document.getElementById("chat-title");

  // --- State Management ---
  let state = {
    chats: {},
    activeChatId: null,
  };

  // --- Specialist Agent Definitions (for display only) ---
  const specialists = {
    "threat-analyst": { name: "Threat Analyst", color: "red" },
    "incident-responder": { name: "Incident Responder", color: "orange" },
    "compliance-advisor": { name: "Compliance Advisor", color: "blue" },
    "security-architect": { name: "Security Architect", color: "green" },
  };

  // Agent role mapping for display
  const agentRoleMapping = {
    incident_response: { name: "Incident Responder", abbreviation: "IR", color: "orange" },
    prevention: { name: "Prevention Specialist", abbreviation: "PS", color: "green" },
    threat_intel: { name: "Threat Analyst", abbreviation: "TA", color: "red" },
    compliance: { name: "Compliance Advisor", abbreviation: "CA", color: "blue" },
    coordinator: { name: "Team Coordinator", abbreviation: "TC", color: "slate" },
    team: { name: "Advisory Team", abbreviation: "AT", color: "purple" },
  };

  // --- Initialization ---
  function init() {
    // Wait for marked.js to load and configure it
    const initializeMarked = () => {
      if (window.marked) {
        console.log("Marked.js loaded successfully");

        // Configure marked.js options
        if (typeof window.marked.setOptions === "function") {
          window.marked.setOptions({
            breaks: true,
            gfm: true,
            sanitize: false,
            smartLists: true,
            smartypants: false,
          });
        } else if (window.marked.defaults) {
          // For newer versions of marked
          Object.assign(window.marked.defaults, {
            breaks: true,
            gfm: true,
            sanitize: false,
            smartLists: true,
            smartypants: false,
          });
        }
      } else {
        console.warn("Marked.js not found on window object");
      }
    };

    // Initialize marked after a short delay to ensure it's loaded
    setTimeout(initializeMarked, 100);

    const hasLoadedState = loadState();

    if (hasLoadedState && state.activeChatId && state.chats[state.activeChatId]) {
      renderChatList();
      renderActiveChat();
    } else {
      createNewChat();
    }

    setupEventListeners();
    messageInput.focus();
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    sendBtn.addEventListener("click", sendMessage);
    newChatBtn.addEventListener("click", createNewChat);

    messageInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    messageInput.addEventListener("input", handleTextareaResize);
    messageInput.addEventListener("input", updateSendButtonState);

    // Keyboard shortcuts
    document.addEventListener("keydown", handleKeyboardShortcuts);

    // Save state periodically and on unload
    setInterval(saveState, 30000);
    window.addEventListener("beforeunload", saveState);
  }
  // --- Rendering Functions ---
  function renderChatList() {
    const chatIds = Object.keys(state.chats).sort((a, b) => {
      return new Date(state.chats[b].lastActivity || 0) - new Date(state.chats[a].lastActivity || 0);
    });

    chatList.innerHTML = chatIds
      .map((chatId) => {
        const chat = state.chats[chatId];
        const isActive = state.activeChatId === chatId;

        return `
                <button data-id="${chatId}" class="chat-item w-full text-left py-3 px-4 rounded-lg transition ${
          isActive ? "active text-white" : "text-slate-700 hover:text-slate-900"
        }">
                    <div class="flex items-center justify-between">
                        <div class="flex-grow pr-2">
                            <div class="font-medium text-sm truncate">${chat.title}</div>
                            <div class="text-xs opacity-75 truncate">
                                ${chat.messages.length} messages
                            </div>
                        </div>
                        <span class="delete-chat-btn flex-shrink-0" data-id="${chatId}">×</span>
                    </div>
                </button>
            `;
      })
      .join("");

    chatList.querySelectorAll(".chat-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        if (e.target.classList.contains("delete-chat-btn")) {
          e.stopPropagation();
          deleteChat(e.target.dataset.id);
        } else {
          switchChat(item.dataset.id);
        }
      });
    });
  }

  function renderActiveChat() {
    const activeChat = state.chats[state.activeChatId];
    chatTitle.textContent = activeChat.title;

    // Debug: Check if marked is available
    if (!window.marked) {
      console.warn("Marked.js is not available during render");
    }

    chatContainer.innerHTML = activeChat.messages.map((msg) => createMessageHTML(msg)).join("");

    // Apply syntax highlighting to code blocks
    chatContainer.querySelectorAll("pre code").forEach((block) => {
      if (window.hljs) {
        hljs.highlightElement(block);
      }
    });

    // Smooth scroll to bottom
    setTimeout(() => {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }, 100);
  }

  function createMessageHTML({ role, content, specialist, agent_name, agent_role, sources }) {
    const isUser = role === "user";
    const isThinking = content === "...";

    let messageContent;
    if (isUser) {
      messageContent = `<div class="user-content">${content
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br>")}</div>`;
    } else if (isThinking) {
      messageContent =
        '<div class="thinking flex items-center"><svg class="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>Processing your request...</div>';
    } else {
      // Ensure marked is available and properly parse markdown
      try {
        if (typeof marked !== "undefined") {
          messageContent = `<div class="markdown-content">${marked.parse(content)}</div>`;
        } else {
          // Fallback: basic markdown parsing if marked isn't available
          let parsedContent = content
            // Headers
            .replace(/^### (.*$)/gm, "<h3>$1</h3>")
            .replace(/^## (.*$)/gm, "<h2>$1</h2>")
            .replace(/^# (.*$)/gm, "<h1>$1</h1>")
            // Bold and italic
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/__(.*?)__/g, "<strong>$1</strong>")
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            .replace(/_(.*?)_/g, "<em>$1</em>")
            // Inline code
            .replace(/`(.*?)`/g, "<code>$1</code>")
            // Code blocks
            .replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
            // Line breaks
            .replace(/\n\n/g, "</p><p>")
            .replace(/\n/g, "<br>")
            // Wrap in paragraphs
            .replace(/^/, "<p>")
            .replace(/$/, "</p>")
            // Fix empty paragraphs
            .replace(/<p><\/p>/g, "");

          // Handle lists separately
          parsedContent = parsedContent.replace(/(<br>- .*?(?=<br>[^-]|$))/gs, (match) => {
            const listItems = match
              .split("<br>- ")
              .filter((item) => item.trim())
              .map((item) => `<li>${item.replace(/^- /, "")}</li>`)
              .join("");
            return `<ul>${listItems}</ul>`;
          });

          messageContent = `<div class="markdown-content">${parsedContent}</div>`;
        }
      } catch (error) {
        console.error("Markdown parsing error:", error);
        messageContent = `<div class="markdown-content">${content.replace(/\n/g, "<br>")}</div>`;
      }
    }

    const specialistInfo = agent_role ? agentRoleMapping[agent_role] : null;

    // User and AI icons
    const userIcon = `
            <div class="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center ml-3">
                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                </svg>
            </div>
        `;

    const aiIcon = `
            <div class="flex-shrink-0 w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center mr-3">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-3z"></path></svg>
            </div>
        `;

    return `
            <div class="message flex items-start ${isUser ? "justify-end" : "justify-start"} group">
                ${!isUser ? aiIcon : ""}
                <div class="message-bubble px-5 py-4 rounded-lg max-w-4xl ${
                  isUser ? "user-message text-white" : `assistant-message ${isThinking ? "thinking" : ""}`
                }">
                   ${
                     !isUser && !isThinking
                       ? `<div class="font-bold mb-2 text-slate-700">${
                           agent_name && specialistInfo
                             ? `${agent_name} (${specialistInfo.abbreviation})`
                             : "Advisory Team"
                         }</div>`
                       : ""
                   }
                    ${messageContent}
                    ${
                      sources && sources.length > 0
                        ? `<div class="mt-4 pt-3 border-t border-slate-200/20 text-xs">
                             <h4 class="font-semibold mb-1 text-slate-600">Sources & Tools Used:</h4>
                             <ul class="list-disc pl-4 text-slate-500">
                               ${sources.map((source) => `<li>${source}</li>`).join("")}
                             </ul>
                           </div>`
                        : ""
                    }
                </div>
                ${isUser ? userIcon : ""}
            </div>
                `;
  }

  // --- State & Chat Logic ---
  function createNewChat() {
    const newChatId = `chat-${Date.now()}`;
    state.chats[newChatId] = {
      id: newChatId,
      threadId: `session-${crypto.randomUUID()}`,
      messages: [
        {
          role: "assistant",
          content:
            "Welcome to **CyberGuard Enterprise Security Advisory Platform**.\n\nI'm your cybersecurity consultant, ready to provide expert guidance on:\n\n- **Risk Assessment** - Identify and evaluate security vulnerabilities\n- **Incident Response** - Emergency response and containment strategies  \n- **Compliance & Governance** - Regulatory requirements and frameworks\n- **Security Architecture** - Infrastructure design and implementation\n\nOur system will automatically connect you with the most appropriate security specialist based on your inquiry. You can use **markdown formatting** in your questions for better structure.\n\n### Test Markdown\n\nTry asking: *What are common cybersecurity threats?*\n\nOr use `code formatting` and **bold text** in your messages!",
        },
      ],
      title: "New Security Consultation",
      lastActivity: new Date().toISOString(),
    };
    switchChat(newChatId);
  }

  function deleteChat(chatId) {
    const chat = state.chats[chatId];
    if (chat && chat.messages.length > 1) {
      if (!confirm(`Delete "${chat.title}"?\n\nThis security consultation will be permanently removed.`)) {
        return;
      }
    }

    delete state.chats[chatId];
    if (state.activeChatId === chatId) {
      const remainingChats = Object.keys(state.chats);
      const newActiveId = remainingChats.length > 0 ? remainingChats[0] : null;
      if (newActiveId) {
        switchChat(newActiveId);
      } else {
        createNewChat();
      }
    }
    renderChatList();
  }

  function switchChat(chatId) {
    state.activeChatId = chatId;
    const chat = state.chats[chatId];

    // Update last activity
    chat.lastActivity = new Date().toISOString();

    renderChatList();
    renderActiveChat();
    messageInput.focus();
  }

  function addMessageToActiveChat(message) {
    const activeChat = state.chats[state.activeChatId];
    activeChat.messages.push(message);
    activeChat.lastActivity = new Date().toISOString();
  }

  // --- Enhanced UI Functions ---
  function handleTextareaResize() {
    messageInput.style.height = "auto";
    const newHeight = Math.min(messageInput.scrollHeight, 120);
    messageInput.style.height = `${newHeight}px`;
  }

  function updateSendButtonState() {
    const hasContent = messageInput.value.trim().length > 0;
    sendBtn.style.opacity = hasContent ? "1" : "0.6";
    sendBtn.disabled = !hasContent;
  }

  function generateChatTitle(content) {
    const words = content.trim().split(" ");
    if (words.length <= 4) {
      return content;
    }

    // Cybersecurity keywords for intelligent titling
    const securityTerms = [
      "security",
      "threat",
      "vulnerability",
      "attack",
      "breach",
      "malware",
      "phishing",
      "firewall",
      "encryption",
      "compliance",
      "audit",
      "risk",
      "incident",
      "forensics",
      "penetration",
      "assessment",
      "gdpr",
      "hipaa",
    ];

    const foundTerms = words.filter((word) => securityTerms.includes(word.toLowerCase().replace(/[^a-zA-Z]/g, "")));

    if (foundTerms.length > 0) {
      const contextualWords = words.slice(0, 2).concat(foundTerms.slice(0, 2));
      const title = contextualWords.join(" ");
      return title.length > 35 ? title.slice(0, 32) + "..." : title;
    }

    const title = words.slice(0, 4).join(" ");
    return title.length > 35 ? title.slice(0, 32) + "..." : title;
  }

  function handleKeyboardShortcuts(e) {
    // Ctrl/Cmd + K to focus on input
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      messageInput.focus();
    }

    // Escape to blur input
    if (e.key === "Escape" && document.activeElement === messageInput) {
      messageInput.blur();
    }
  }

  // --- API Communication ---
  async function sendMessage() {
    const content = messageInput.value.trim();
    if (!content) return;

    // Disable send button during request
    sendBtn.disabled = true;
    sendBtn.style.opacity = "0.4";

    const activeChat = state.chats[state.activeChatId];

    // Generate intelligent chat title for first user message
    if (activeChat.messages.length === 1) {
      activeChat.title = generateChatTitle(content);
    }

    // Add user message
    const userMessage = { role: "user", content };
    addMessageToActiveChat(userMessage);
    renderActiveChat();
    renderChatList();

    // Clear and reset input
    messageInput.value = "";
    handleTextareaResize();
    updateSendButtonState();

    // Add thinking indicator
    const thinkingIndicator = { role: "assistant", content: "..." };
    addMessageToActiveChat(thinkingIndicator);
    renderActiveChat();

    try {
      const { threadId } = activeChat;

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          thread_id: threadId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Update the thinking indicator with response
      thinkingIndicator.content = data.response;
      thinkingIndicator.agent_name = data.agent_name;
      thinkingIndicator.agent_role = data.agent_role;
      thinkingIndicator.sources = data.tools_used; // Make sure backend sends this key

      // If backend indicates specialist, add that info
      if (data.specialist && specialists[data.specialist]) {
        thinkingIndicator.specialist = data.specialist;
      }
    } catch (error) {
      console.error("Error fetching chat response:", error);

      let errorMessage = "I apologize, but I'm experiencing technical difficulties. ";

      if (error.message.includes("Failed to fetch")) {
        errorMessage += "Please verify your network connection and try again.";
      } else if (error.message.includes("500")) {
        errorMessage += "Our security advisory service is temporarily unavailable. Please try again shortly.";
      } else if (error.message.includes("429")) {
        errorMessage += "Too many requests detected. Please wait a moment before continuing.";
      } else {
        errorMessage += "Please try again or contact your system administrator if the issue persists.";
      }

      thinkingIndicator.content = errorMessage;
    } finally {
      renderActiveChat();
      sendBtn.disabled = false;
      updateSendButtonState();
      messageInput.focus();
    }
  }

  // --- Local Storage for Persistence ---
  function saveState() {
    try {
      const stateToSave = {
        chats: state.chats,
        activeChatId: state.activeChatId,
        timestamp: Date.now(),
      };
      localStorage.setItem("cybersec-enterprise-state", JSON.stringify(stateToSave));
    } catch (error) {
      console.warn("Failed to save consultation state:", error);
    }
  }

  function loadState() {
    try {
      const savedState = localStorage.getItem("cybersec-enterprise-state");
      if (savedState) {
        const parsed = JSON.parse(savedState);
        // Load state if saved within last 30 days
        if (Date.now() - parsed.timestamp < 30 * 24 * 60 * 60 * 1000) {
          state.chats = parsed.chats || {};
          state.activeChatId = parsed.activeChatId;
          return Object.keys(state.chats).length > 0;
        }
      }
    } catch (error) {
      console.warn("Failed to load consultation state:", error);
    }
    return false;
  }

  // --- Start the professional advisory platform ---
  waitForMarked(() => {
    init();
  });
});
