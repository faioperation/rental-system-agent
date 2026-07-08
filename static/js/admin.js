// ---------- Admin Auth ----------
const adminAuth = localStorage.getItem("admin_auth");
const loginPanel = document.getElementById("login-panel");
const adminContent = document.getElementById("admin-content");

if (adminAuth !== "true") {
  loginPanel.style.display = "flex";
  adminContent.style.display = "none";
} else {
  loginPanel.style.display = "none";
  adminContent.style.display = "block";
}

document.getElementById("login-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const pass = document.getElementById("login-password").value.trim();
  
  if (email === "admin@fireai.com" && pass === "1234") {
    localStorage.setItem("admin_auth", "true");
    loginPanel.style.display = "none";
    adminContent.style.display = "block";
    loadTickets();
  } else {
    document.getElementById("login-error").style.display = "block";
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  localStorage.removeItem("admin_auth");
  window.location.reload();
});

// ---------- Admin dashboard: Leads / Properties / Viewings — no chat here ----------
const railItems = document.querySelectorAll(".rail-item");
railItems.forEach((btn) => {
  btn.addEventListener("click", () => {
    railItems.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    document.getElementById("view-" + btn.dataset.view).classList.remove("hidden");
    if (btn.dataset.view === "tickets") loadTickets();
    if (btn.dataset.view === "properties") loadProperties();
    if (btn.dataset.view === "kb") loadKbDocuments();
    if (btn.dataset.view === "viewings") loadViewings();
  });
});

// ---------- leads ----------
async function loadTickets() {
  const status = document.getElementById("filter-status").value;
  const priority = document.getElementById("filter-priority").value;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (priority) params.set("priority", priority);

  const resp = await fetch("/api/tickets?" + params.toString());
  const tickets = await resp.json();

  const list = document.getElementById("ticket-list");
  list.innerHTML = "";
  if (!tickets.length) {
    list.innerHTML = '<div class="a-sub">No leads yet.</div>';
    return;
  }

  tickets.forEach((t) => {
    const row = document.createElement("div");
    row.className = "ticket-row priority-" + t.priority;
    row.innerHTML = `
      <div class="ticket-row-top">
        <span>${t.category} · ${t.status}</span>
        <span>${new Date(t.created_at).toLocaleString()}</span>
      </div>
      <div class="ticket-row-summary">${t.summary || ""}</div>
    `;
    list.appendChild(row);
  });
}

document.getElementById("refresh-tickets").addEventListener("click", loadTickets);
document.getElementById("filter-status").addEventListener("change", loadTickets);
document.getElementById("filter-priority").addEventListener("change", loadTickets);

// ---------- properties ----------
document.getElementById("property-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const statusEl = document.getElementById("property-status");
  statusEl.textContent = "Embedding & saving…";

  const features = document
    .getElementById("prop-features")
    .value.split(",")
    .map((f) => f.trim())
    .filter(Boolean);

  const payload = {
    title: document.getElementById("prop-title").value.trim(),
    listing_type: document.getElementById("prop-listing-type").value,
    address: document.getElementById("prop-address").value.trim(),
    city: document.getElementById("prop-city").value.trim(),
    neighborhood: document.getElementById("prop-neighborhood").value.trim(),
    price: parseFloat(document.getElementById("prop-price").value) || null,
    bedrooms: parseInt(document.getElementById("prop-bedrooms").value) || null,
    bathrooms: parseFloat(document.getElementById("prop-bathrooms").value) || null,
    sqft: parseInt(document.getElementById("prop-sqft").value) || null,
    features,
    description: document.getElementById("prop-description").value.trim(),
  };

  const resp = await fetch("/api/properties", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (resp.ok) {
    statusEl.textContent = "Property added and embedded for search.";
    document.getElementById("property-form").reset();
    loadProperties();
  } else {
    statusEl.textContent = "Something went wrong — check the console.";
  }
});

// ---------- CSV bulk import ----------
document.getElementById("csv-upload-btn").addEventListener("click", async () => {
  const fileInput = document.getElementById("csv-file-input");
  const statusEl = document.getElementById("csv-status");

  if (!fileInput.files.length) {
    statusEl.textContent = "Choose a CSV file first.";
    return;
  }

  statusEl.textContent = "Uploading & embedding rows…";

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const resp = await fetch("/api/properties/bulk-csv", {
    method: "POST",
    body: formData,
  });
  const result = await resp.json();

  statusEl.textContent = `Imported ${result.inserted} listing(s).` +
    (result.failed.length ? ` ${result.failed.length} row(s) failed — check row numbers: ${result.failed.map((f) => f.row).join(", ")}` : "");

  fileInput.value = "";
  loadProperties();
});

async function loadProperties() {
  const resp = await fetch("/api/properties");
  let properties = await resp.json();

  const cityFilter = document.getElementById("filter-city").value.trim().toLowerCase();
  if (cityFilter) {
    properties = properties.filter((p) => (p.city || "").toLowerCase().includes(cityFilter));
  }

  const list = document.getElementById("property-list");
  list.innerHTML = "";
  if (!properties.length) {
    list.innerHTML = '<div class="a-sub">No properties found.</div>';
    return;
  }

  const houseIcon = `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-6h6v6"/></svg>`;

  properties.forEach((p) => {
    const row = document.createElement("div");
    row.className = "property-card";
    row.innerHTML = `
      <div class="property-card-main">
        <div class="property-icon">${houseIcon}</div>
        <div class="property-card-text">
          <div class="property-card-title">${p.title}</div>
          <div class="property-card-meta">${p.listing_type === "rent" ? "For rent" : "For sale"} · ${p.city || ""}${p.neighborhood ? " / " + p.neighborhood : ""} · ${p.bedrooms ?? "?"} bed · ${p.bathrooms ?? "?"} bath · ${p.status}</div>
        </div>
      </div>
      <div class="property-card-price">$${p.price ?? "?"}${p.listing_type === "rent" ? "/mo" : ""}</div>
      <button data-id="${p.id}">Generate slots</button>
    `;
    row.querySelector("button").addEventListener("click", async (e) => {
      e.target.textContent = "Generating…";
      await fetch("/api/viewings/generate-slots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ property_id: p.id }),
      });
      e.target.textContent = "Slots ready ✓";
    });
    list.appendChild(row);
  });
}

document.getElementById("refresh-properties").addEventListener("click", loadProperties);
document.getElementById("filter-city").addEventListener("input", loadProperties);

// ---------- knowledge base ----------
document.getElementById("kb-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = document.getElementById("kb-title").value.trim();
  const content = document.getElementById("kb-content").value.trim();
  if (!title || !content) return;

  const statusEl = document.getElementById("kb-status");
  statusEl.textContent = "Embedding & saving…";

  const resp = await fetch("/api/kb", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content }),
  });
  const result = await resp.json();
  statusEl.textContent = `Saved (${result.chunks_added} chunk(s) added).`;

  document.getElementById("kb-form").reset();
  loadKbDocuments();
});

document.getElementById("kb-upload-btn").addEventListener("click", async () => {
  const fileInput = document.getElementById("kb-file-input");
  const statusEl = document.getElementById("kb-file-status");

  if (!fileInput.files.length) {
    statusEl.textContent = "Choose a .txt or .md file first.";
    return;
  }

  statusEl.textContent = "Uploading & embedding…";

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const resp = await fetch("/api/kb/upload", { method: "POST", body: formData });
  const result = await resp.json();
  statusEl.textContent = `Saved (${result.chunks_added} chunk(s) added).`;

  fileInput.value = "";
  loadKbDocuments();
});

async function loadKbDocuments() {
  const resp = await fetch("/api/kb");
  const docs = await resp.json();

  const list = document.getElementById("kb-list");
  list.innerHTML = "";
  if (!docs.length) {
    list.innerHTML = '<div class="a-sub">No knowledge base entries yet.</div>';
    return;
  }

  docs.forEach((d) => {
    const row = document.createElement("div");
    row.className = "ticket-row";
    row.innerHTML = `
      <div class="ticket-row-top">
        <span>${d.title}</span>
        <span>${new Date(d.created_at).toLocaleDateString()}</span>
      </div>
      <div class="ticket-row-summary">Source: ${d.source}</div>
    `;
    list.appendChild(row);
  });
}

// ---------- viewings ----------
async function loadViewings() {
  const resp = await fetch("/api/viewings/");
  const viewings = await resp.json();

  const list = document.getElementById("viewing-list");
  list.innerHTML = "";
  if (!viewings.length) {
    list.innerHTML = '<div class="a-sub">No viewings booked yet.</div>';
    return;
  }

  let lastDate = "";
  viewings.forEach((v) => {
    const prop = v.properties || {};
    const cust = v.customers || {};
    const dateObj = new Date(v.scheduled_start);
    const dateKey = dateObj.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });

    if (dateKey !== lastDate) {
      const header = document.createElement("div");
      header.className = "viewing-date-header";
      header.textContent = dateKey;
      list.appendChild(header);
      lastDate = dateKey;
    }

    const row = document.createElement("div");
    row.className = "viewing-row";
    row.innerHTML = `
      <div class="ticket-row-top">
        <span>${prop.title || "Property"} · ${v.status}</span>
        <span>${dateObj.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      </div>
      <div class="ticket-row-summary">${cust.name || cust.email || "Customer"} — ${prop.address || ""}</div>
      <a href="/api/viewings/${v.id}/ics" target="_blank">Download calendar invite (.ics)</a>
    `;
    list.appendChild(row);
  });
}

document.getElementById("refresh-viewings").addEventListener("click", loadViewings);

// Load leads by default on page open
loadTickets();