// ---------- Customer-facing chat with LocalStorage Sessions & Files ----------

function uuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// 1. Identity & Sessions in LocalStorage
let customerId = localStorage.getItem("aria_customer_id");
if (!customerId) {
  customerId = "web-" + uuid();
  localStorage.setItem("aria_customer_id", customerId);
}

// Array of { conversationId, title, timestamp }
let savedSessions = JSON.parse(localStorage.getItem("aria_sessions") || "[]");
let currentConversationId = null;
let currentSessionFiles = []; // { name, content }

function saveSessions() {
  localStorage.setItem("aria_sessions", JSON.stringify(savedSessions));
  renderSessionList();
}

// 2. UI Elements
const chatScroll = document.getElementById("chat-scroll");
const composer = document.getElementById("composer");
const composerInput = document.getElementById("composer-input");
const sessionListEl = document.getElementById("session-list");
const newSessionBtn = document.getElementById("new-session-btn");
const errorBanner = document.getElementById("error-banner");

const fileInput = document.getElementById("chat-file-input");
const uploadBtn = document.getElementById("chat-upload-btn");
const fileStatus = document.getElementById("file-upload-status");
const fileListEl = document.getElementById("session-files-list");

// 3. Render Session List
function renderSessionList() {
  sessionListEl.innerHTML = "";
  if (savedSessions.length === 0) {
    sessionListEl.innerHTML = '<div class="a-sub" style="padding: 10px;">No recent chats.</div>';
    return;
  }

  // Sort newest first
  const sorted = [...savedSessions].sort((a, b) => b.timestamp - a.timestamp);

  sorted.forEach(sess => {
    const item = document.createElement("div");
    item.className = "session-item";

    const btn = document.createElement("button");
    btn.className = "rail-item" + (sess.conversationId === currentConversationId ? " active" : "");
    btn.innerHTML = `<span class="rail-dot"></span> ${sess.title}`;
    btn.onclick = () => loadSession(sess.conversationId);

    const delBtn = document.createElement("button");
    delBtn.className = "delete-btn";
    delBtn.innerHTML = "×";
    delBtn.title = "Delete chat";
    delBtn.onclick = (e) => {
      e.stopPropagation();
      deleteSession(sess.conversationId);
    };

    item.appendChild(btn);
    item.appendChild(delBtn);
    sessionListEl.appendChild(item);
  });
}

function deleteSession(convId) {
  savedSessions = savedSessions.filter(s => s.conversationId !== convId);
  saveSessions();
  if (currentConversationId === convId) {
    startNewSession();
  }
}

// 4. Load / Start Session
async function loadSession(convId) {
  currentConversationId = convId;
  currentSessionFiles = []; // Reset files on switch
  renderFiles();
  renderSessionList();
  errorBanner.style.display = "none";

  chatScroll.innerHTML = '<div class="a-sub" style="text-align: center;">Loading history...</div>';

  try {
    const resp = await fetch(`/api/conversations/${convId}/history`);
    const history = await resp.json();
    
    chatScroll.innerHTML = "";
    if (history.length === 0) {
      chatScroll.innerHTML = '<div class="msg agent"><div class="msg-bubble">Hi, I\'m Aria 👋 Let\'s pick up where we left off.</div></div>';
    } else {
      history.forEach(turn => {
        addBubble(turn.role, turn.content);
      });
    }
  } catch (err) {
    chatScroll.innerHTML = '<div class="msg agent"><div class="msg-bubble">Error loading history.</div></div>';
  }
}

function startNewSession() {
  currentConversationId = null;
  currentSessionFiles = [];
  renderFiles();
  renderSessionList();
  errorBanner.style.display = "none";
  chatScroll.innerHTML = '<div class="msg agent"><div class="msg-bubble">Hi, I\'m Aria 👋 Tell me what you\'re looking for — buying or renting, city, budget, bedrooms — and I\'ll find suitable listings and can schedule a viewing for you.</div></div>';
}

newSessionBtn.addEventListener("click", startNewSession);

// 5. Chat Bubbles
function addBubble(role, text) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + (role === "user" ? "user" : "agent");
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  chatScroll.appendChild(wrap);
  chatScroll.scrollTop = chatScroll.scrollHeight;
  return bubble;
}

// 6. Sending Messages & Streaming
async function sendMessage(message) {
  errorBanner.style.display = "none";
  addBubble("user", message);
  const agentBubble = addBubble("agent", "");
  agentBubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

  // Attach file contents if any
  let finalMessage = message;
  if (currentSessionFiles.length > 0) {
    let fileContext = "[The user has shared the following documents for context]\n\n";
    currentSessionFiles.forEach(f => {
      fileContext += `--- BEGIN FILE: ${f.name} ---\n${f.content}\n--- END FILE ---\n\n`;
    });
    finalMessage = fileContext + "User Message:\n" + message;
  }

  try {
    const resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: finalMessage,
        conversation_id: currentConversationId,
        customer_external_id: customerId,
        channel: "web",
      }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let isRateLimited = false;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

      const blocks = buffer.split("\n\n");
      buffer = blocks.pop();

      for (const block of blocks) {
        const lines = block.split("\n");
        let event = "message";
        let data = "";
        for (const line of lines) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        const parsed = JSON.parse(data);

        if (event === "analysis") {
          if (parsed.conversation_id) {
            currentConversationId = parsed.conversation_id;
            
            // Check if we need to save this new session
            const existing = savedSessions.find(s => s.conversationId === currentConversationId);
            if (!existing) {
              savedSessions.push({
                conversationId: currentConversationId,
                title: message.substring(0, 30) + (message.length > 30 ? "..." : ""),
                timestamp: Date.now()
              });
              saveSessions();
            }
          }
        } else if (event === "token") {
          if (parsed.content.includes("Limit reached. Wait for sometime.")) {
            isRateLimited = true;
          }
          if (agentBubble.querySelector('.typing-indicator')) {
            agentBubble.innerHTML = '';
          }
          agentBubble.textContent += parsed.content;
          chatScroll.scrollTop = chatScroll.scrollHeight;
        }
      }
    }

    if (isRateLimited) {
      errorBanner.textContent = "Rate limit reached. Please wait for some time before sending more messages.";
      errorBanner.style.display = "block";
    }

  } catch (err) {
    errorBanner.textContent = "A network error occurred.";
    errorBanner.style.display = "block";
  }
}

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = composerInput.value.trim();
  if (!text) return;
  composerInput.value = "";
  sendMessage(text);
});

// Allow Enter to submit in textarea, Shift+Enter for new line
composerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composer.dispatchEvent(new Event("submit"));
  }
});


// 7. File Upload Logic
fileInput.addEventListener("change", () => {
  if (!fileInput.files.length) return;
  
  const file = fileInput.files[0];
  fileStatus.style.display = "block";
  fileStatus.textContent = "Reading file...";

  const reader = new FileReader();
  reader.onload = (e) => {
    const content = e.target.result;
    currentSessionFiles.push({ name: file.name, content: content });
    fileStatus.textContent = `Attached ${file.name}`;
    setTimeout(() => { fileStatus.style.display = "none"; }, 3000);
    fileInput.value = "";
    renderFiles();
  };
  reader.onerror = () => {
    fileStatus.textContent = "Error reading file.";
  };
  reader.readAsText(file);
});

function renderFiles() {
  fileListEl.innerHTML = "";
  if (currentSessionFiles.length === 0) {
    fileListEl.innerHTML = '<div class="a-sub">No files shared yet.</div>';
    return;
  }
  currentSessionFiles.forEach((f, idx) => {
    const row = document.createElement("div");
    row.className = "ticket-row";
    row.style.display = "flex";
    row.style.justifyContent = "space-between";
    row.style.alignItems = "center";
    row.style.padding = "10px";
    row.innerHTML = `<span style="font-size: 13px; font-weight: 500;">📄 ${f.name}</span>`;
    
    const delBtn = document.createElement("button");
    delBtn.className = "delete-btn";
    delBtn.style = "background: none; border: none; color: var(--accent-danger); cursor: pointer; font-size: 13px;";
    delBtn.textContent = "Remove";
    delBtn.onclick = () => {
      currentSessionFiles.splice(idx, 1);
      renderFiles();
    };
    
    row.appendChild(delBtn);
    fileListEl.appendChild(row);
  });
}

// Init
startNewSession();