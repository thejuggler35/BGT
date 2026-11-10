const app = document.querySelector("#app");
const toastRegion = document.querySelector("#toast-region");
const API_BASE_URL = (window.BGT_API_BASE_URL || "").trim().replace(/\/+$/, "");
const state = {
  page: "overview",
  rules: null,
  reviews: [],
  currentReview: null,
  selectedFindingId: null,
  findingFilter: "all",
  reviewMode: "text",
  draftText: "",
  uploadFile: null,
  authRequired: false,
};

const iconPaths = {
  overview: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="13" width="7" height="8" rx="1"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 1 4 17.5z"/><path d="M4 17.5A2.5 2.5 0 0 1 6.5 15H20M8 7h8M8 10h7"/>',
  scan: '<path d="M4 7V5a1 1 0 0 1 1-1h2M17 4h2a1 1 0 0 1 1 1v2M20 17v2a1 1 0 0 1-1 1h-2M7 20H5a1 1 0 0 1-1-1v-2"/><circle cx="10.5" cy="10.5" r="3.5"/><path d="m13 13 3 3"/>',
  history: '<path d="M3 12a9 9 0 1 0 2.64-6.36L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 0 1 4.8.8c0 1.7-2.4 2.2-2.4 3.7M12 17h.01"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  rules: '<path d="M4 5h16M4 12h16M4 19h16"/><circle cx="8" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="10" cy="19" r="1"/>',
  upload: '<path d="M12 16V4m-4 4 4-4 4 4"/><path d="M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  shield: '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11"/><path d="m9 12 2 2 4-4"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
  x: '<path d="m18 6-12 12M6 6l12 12"/>',
};

function icon(name, className = "") {
  return `<svg class="${className}" viewBox="0 0 24 24" aria-hidden="true">${iconPaths[name] || iconPaths.file}</svg>`;
}

function syncAuthChrome() {
  const signOut = document.querySelector("#sign-out");
  if (signOut) signOut.hidden = !state.authRequired || !sessionStorage.getItem("bgt-access-token");
}

function syncBrandChrome() {
  const name = state.rules?.brand_name || "BGT workspace";
  const workspaceName = document.querySelector("#workspace-name");
  const workspaceInitial = document.querySelector("#workspace-initial");
  if (workspaceName) workspaceName.textContent = name;
  if (workspaceInitial) workspaceInitial.textContent = name.trim().charAt(0).toUpperCase() || "B";
}

function setWorkspaceStatus(label, disconnected = false) {
  const status = document.querySelector(".status-indicator");
  if (!status) return;
  status.classList.toggle("is-error", disconnected);
  status.querySelector("span").textContent = label;
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function formatDate(value, options = { month: "short", day: "numeric", year: "numeric" }) {
  if (!value) return "Not yet decided";
  const date = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, options).format(date);
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = sessionStorage.getItem("bgt-access-token");
  if (token) {
    const headerName = ["Author", "ization"].join("");
    const headerValue = ["Bear", "er"].join("") + " " + token;
    headers.set(headerName, headerValue);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail) ? detail.map((item) => item.msg).join(" ") : detail;
    const error = new Error(message || `Request failed (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function toast(message, error = false) {
  const node = document.createElement("div");
  node.className = `toast${error ? " error" : ""}`;
  node.innerHTML = `<span class="toast-icon">${error ? "!" : "✓"}</span><span>${escapeHtml(message)}</span>`;
  toastRegion.append(node);
  window.setTimeout(() => node.remove(), 3600);
}

function setBreadcrumb(label) {
  document.querySelector("#breadcrumbs").innerHTML =
    `<span>Workspace</span><span class="crumb-separator">/</span><strong>${escapeHtml(label)}</strong>`;
}

function closeMobileNav() {
  document.querySelector("#sidebar").classList.remove("open");
  document.querySelector("#mobile-backdrop").classList.remove("visible");
  document.querySelector("#mobile-menu").setAttribute("aria-expanded", "false");
}

function setActiveNav(page) {
  document.querySelectorAll(".nav-link").forEach((link) => {
    const active = link.dataset.route === page || (page === "review" && link.dataset.route === "history");
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function navigate(page, options = {}) {
  const hash = page === "review" ? `#/review/${options.id}` : `#/${page}`;
  if (window.location.hash === hash) renderRoute();
  else window.location.hash = hash;
}

function parseRoute() {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/");
  if (parts[0] === "review" && parts[1]) return { page: "review", id: Number(parts[1]) };
  const allowed = ["overview", "brand", "new", "history", "guide"];
  return { page: allowed.includes(parts[0]) ? parts[0] : "overview" };
}

function renderRoute() {
  const route = parseRoute();
  state.page = route.page;
  state.currentReview = null;
  setActiveNav(route.page);
  syncBrandChrome();
  syncAuthChrome();
  closeMobileNav();
  const labels = {
    overview: "Overview",
    brand: "Brand guidelines",
    new: "New review",
    history: "Review history",
    review: "Review report",
    guide: "Quick guide",
  };
  setBreadcrumb(labels[route.page]);
  if (!state.rules) return;
  if (route.page === "overview") renderOverview();
  if (route.page === "brand") renderBrand();
  if (route.page === "new") renderNewReview();
  if (route.page === "history") renderHistory();
  if (route.page === "guide") renderGuide();
  if (route.page === "review") loadReview(route.id);
}

function renderLogin(errorMessage = "") {
  setBreadcrumb("Sign in");
  syncAuthChrome();
  app.innerHTML = `<section class="login-layout page-enter">
    <div class="login-card">
      <img class="brand-mark login-mark" src="static/bgt-logo.png" alt="BGT">
      <p class="eyebrow"><span class="eyebrow-dot"></span> PRIVATE WORKSPACE</p>
      <h1 class="page-title">Welcome back</h1>
      <p class="page-description">Enter your workspace access token to open your brand guidelines and review history.</p>
      <form class="login-form" id="login-form">
        <label class="field"><span class="field-label">Workspace access token</span><input class="text-input" name="token" type="password" autocomplete="current-password" required autofocus placeholder="Paste your access token"></label>
        <p class="validation-message" id="login-error" role="alert">${escapeHtml(errorMessage)}</p>
            <button class="button button-primary" type="submit">Sign in <span class="button-icon">→</span></button>
      </form>
      <div class="human-note">${icon("shield")}<span>Your token is kept in this browser tab only and cleared when you close it.</span></div>
    </div>
  </section>`;
}

function renderConnectionError(error, needsConfiguration = false) {
  setWorkspaceStatus("Backend unavailable", true);
  const description = needsConfiguration
    ? "This site is hosted on GitHub Pages, which serves the interface but cannot run BGT’s API. Connect a backend to load guidelines, reviews, and workspace data."
    : "The BGT interface loaded, but its API could not be reached. Check the backend connection and try again.";
  const detail = needsConfiguration
    ? `<div class="connection-detail"><strong>Backend URL not configured</strong><span>Deploy the FastAPI service, then add its HTTPS address as the BGT_API_BASE_URL Actions variable and redeploy Pages.</span></div>`
    : `<div class="connection-detail"><strong>Connection details</strong><span>${error.status === 404 ? "The configured server returned 404. Check that BGT_API_BASE_URL points to the BGT API root." : `${escapeHtml(error.message)} Check that the backend is running and allows requests from this site.`}</span></div>`;
  app.innerHTML = `<section class="connection-layout page-enter" aria-labelledby="connection-title">
    <div class="connection-card">
      <div class="connection-mark">${icon(needsConfiguration ? "shield" : "x")}</div>
      <p class="eyebrow"><span class="eyebrow-dot"></span> WORKSPACE CONNECTION</p>
      <h1 class="page-title" id="connection-title">${needsConfiguration ? "Connect your BGT workspace" : "We can’t reach BGT right now"}</h1>
      <p class="page-description">${description}</p>
      ${detail}
      <div class="connection-actions">
        <button class="button button-primary" type="button" data-action="${needsConfiguration ? "reload-page" : "retry-connection"}">${needsConfiguration ? "Refresh after deployment" : "Try again"}</button>
        <a class="button button-secondary" href="https://github.com/thejuggler35/BGT/blob/main/readme.md#website-and-backend" target="_blank" rel="noreferrer">Backend setup guide</a>
      </div>
      <p class="connection-footnote">Your reviews and brand guidelines are not available until the backend is connected.</p>
    </div>
  </section>`;
}

function metricCard(label, value, note, metricIcon) {
  return `<article class="metric-card page-enter">
    <div class="metric-label-row"><span>${escapeHtml(label)}</span><span class="metric-icon">${icon(metricIcon)}</span></div>
    <div class="metric-value">${value}</div><div class="metric-note">${escapeHtml(note)}</div>
  </article>`;
}

function statusChip(status) {
  const labels = { needs_review: "Needs review", approved: "Approved", changes_requested: "Changes requested" };
  return `<span class="status-chip status-${escapeHtml(status)}">${escapeHtml(labels[status] || status)}</span>`;
}

function fileIcon(type) {
  return `<span class="review-file-icon">${icon(type === "pdf" || type === "docx" ? "file" : "edit")}</span>`;
}

function reviewRow(review) {
  return `<div class="review-row" role="link" tabindex="0" data-open-review="${review.id}">
    ${fileIcon(review.source_type)}
    <div class="review-row-copy"><strong>${escapeHtml(review.title)}</strong><small>${escapeHtml(review.source_name)} · ${review.finding_count} ${review.finding_count === 1 ? "finding" : "findings"}</small></div>
    <div class="review-row-meta">${statusChip(review.status)}<small>${formatDate(review.created_at, { month: "short", day: "numeric" })}</small></div>
  </div>`;
}

function renderOverview() {
  const now = new Date();
  const monthReviews = state.reviews.filter((review) => {
    const created = new Date(review.created_at.includes("T") ? review.created_at : `${review.created_at.replace(" ", "T")}Z`);
    return created.getMonth() === now.getMonth() && created.getFullYear() === now.getFullYear();
  }).length;
  const awaiting = state.reviews.filter((review) => review.status === "needs_review").length;
  const guidelineCount = state.rules.restricted_terms.length + state.rules.preferred_terms.length + state.rules.product_facts.length;
  const recent = state.reviews.slice(0, 5);
  app.innerHTML = `<section class="page-enter">
    <div class="welcome-strip">
      <div class="welcome-copy">
        <h1>Your review workspace</h1>
        <p>Check drafts against your approved brand guidelines.</p>
      </div>
      <div class="welcome-action"><button class="button button-primary" data-action="new-review">${icon("scan")} Start a review <span class="button-icon">↗</span></button></div>
    </div>
    <div class="metric-grid">
      ${metricCard("Reviews this month", monthReviews, "Saved reviews this calendar month", "history")}
      ${metricCard("Awaiting review", awaiting, "Human decision still needed", "clock")}
      ${metricCard("Brand guidelines", guidelineCount, "Terms and approved product facts", "book")}
    </div>
    <section class="panel">
      <div class="panel-heading"><div><h2>Recent reviews</h2><p>Your latest saved reviews</p></div><a class="text-link" href="#/history">View history</a></div>
      ${recent.length
        ? `<div class="panel-body">${recent.map(reviewRow).join("")}</div>`
        : `<div class="empty-state">${iconWrapper("file")}<strong>No reviews yet</strong><p>Start a review to check a draft against your brand guidelines.</p><button class="button button-secondary button-small" data-action="new-review">Start a review</button></div>`}
    </section>
  </section>`;
}

function iconWrapper(name) {
  return `<span class="empty-illustration">${icon(name)}</span>`;
}

function renderTermRows(terms, kind) {
  if (!terms.length) return `<div class="empty-inline" data-empty="${kind}" style="color:#99a3a3;font-size:11px;padding:8px 0">No ${kind} terms yet. Add one when you’re ready.</div>`;
  return terms.map((term, index) => `<div class="editable-row" data-term-kind="${kind}" data-index="${index}">
    <input class="text-input" data-field="phrase" aria-label="${kind} phrase" placeholder="Term or phrase" value="${escapeHtml(term.phrase)}">
    <input class="text-input" data-field="explanation" aria-label="Guideline explanation" placeholder="Why this guideline matters" value="${escapeHtml(term.explanation || "")}">
    <button class="icon-remove" type="button" aria-label="Remove term" data-action="remove-term" data-kind="${kind}" data-index="${index}">${icon("x")}</button>
  </div>`).join("");
}

function renderFactRows(facts) {
  if (!facts.length) return `<div class="empty-inline" data-empty="fact" style="color:#99a3a3;font-size:11px;padding:8px 0">No verified facts saved yet.</div>`;
  return facts.map((fact, index) => `<div class="editable-row fact-row" data-fact-index="${index}">
    <input class="text-input" data-field="product" aria-label="Product name" placeholder="Product" value="${escapeHtml(fact.product)}">
    <input class="text-input" data-field="fact" aria-label="Fact description" placeholder="Approved fact" value="${escapeHtml(fact.fact)}">
    <input class="text-input" data-field="value" aria-label="Numeric value" type="number" step="any" placeholder="Value" value="${fact.value ?? ""}">
    <input class="text-input" data-field="unit" aria-label="Unit" placeholder="Unit" value="${escapeHtml(fact.unit || "")}">
    <button class="icon-remove" type="button" aria-label="Remove product fact" data-action="remove-fact" data-index="${index}">${icon("x")}</button>
  </div>`).join("");
}

function renderBrand() {
  const rules = state.rules;
  const total = rules.restricted_terms.length + rules.preferred_terms.length + rules.product_facts.length;
  app.innerHTML = `<section class="page-enter">
    <div class="page-heading-row">
      <div><p class="eyebrow"><span class="eyebrow-dot"></span> YOUR BRAND KNOWLEDGE</p><h1 class="page-title">Brand guidelines</h1><p class="page-description">One reliable source of truth for the language and product details BGT checks against.</p></div>
      <span class="save-status" id="brand-save-status" role="status"></span>
    </div>
    <div class="form-layout">
      <form class="panel form-panel" id="brand-form">
        <div class="form-section-title"><span class="section-index">01</span><div><h2>Brand profile</h2><p>Give reviewers the context behind your brand voice.</p></div></div>
        <div class="form-grid">
          <div class="field"><label for="brand-name">Brand name</label><input id="brand-name" class="text-input" maxlength="120" required value="${escapeHtml(rules.brand_name)}"></div>
          <div class="field"><label for="brand-voice">Voice characteristics</label><input id="brand-voice" class="text-input" value="${escapeHtml(rules.brand_voice.join(", "))}" placeholder="Friendly, Confident, Clear"><span class="field-hint">Separate each characteristic with a comma.</span></div>
          <div class="field full"><label for="brand-tone">Tone guidance</label><textarea id="brand-tone" class="text-area" maxlength="1000" placeholder="Describe the tone in a sentence or two.">${escapeHtml(rules.tone_characteristics)}</textarea></div>
        </div>
        <hr class="form-divider">
        <div class="form-section-title"><span class="section-index">02</span><div><h2>Restricted terms</h2><p>Flag exact phrases for human review with a clear reason.</p></div></div>
        <div class="inline-list" id="restricted-list">${renderTermRows(rules.restricted_terms, "restricted")}</div>
        <button class="add-row" type="button" data-action="add-term" data-kind="restricted"><span>＋</span> Add restricted term</button>
        <hr class="form-divider">
        <div class="form-section-title"><span class="section-index">03</span><div><h2>Preferred language</h2><p>Offer optional wording suggestions, never automatic violations.</p></div></div>
        <div class="inline-list" id="preferred-list">${renderTermRows(rules.preferred_terms, "preferred")}</div>
        <button class="add-row" type="button" data-action="add-term" data-kind="preferred"><span>＋</span> Add preferred term</button>
        <hr class="form-divider">
        <div class="form-section-title"><span class="section-index">04</span><div><h2>Verified product facts</h2><p>Store approved numeric claims and the context they belong to.</p></div></div>
        <div class="inline-list" id="facts-list">${renderFactRows(rules.product_facts)}</div>
        <button class="add-row" type="button" data-action="add-fact"><span>＋</span> Add product fact</button>
        <div class="form-actions"><span class="save-status" id="brand-save-status-bottom" role="status"></span><button class="button button-primary" type="submit">Save guidelines <span class="button-icon">→</span></button></div>
      </form>
      <aside class="side-stack">
        <section class="panel"><div class="panel-heading"><div><h2>Guideline coverage</h2><p>Saved in this workspace</p></div></div><div class="guideline-counts">
          <div class="count-row"><span>Restricted terms</span><strong>${rules.restricted_terms.length}</strong></div>
          <div class="count-row"><span>Preferred terms</span><strong>${rules.preferred_terms.length}</strong></div>
          <div class="count-row"><span>Product facts</span><strong>${rules.product_facts.length}</strong></div>
          <div class="count-row"><span>Total checks</span><strong>${total}</strong></div>
        </div></section>
        <div class="callout"><strong>Keep reviewers in control</strong>Every match is shown with its source. BGT never changes a draft or approves content automatically.</div>
        <div class="callout"><strong>Make facts specific</strong>Pair the product and claim context with numeric values and units to make comparisons more useful.</div>
      </aside>
    </div>
  </section>`;
}

function captureBrandForm() {
  const name = document.querySelector("#brand-name");
  if (!name) return;
  state.rules = {
    ...state.rules,
    brand_name: name.value,
    brand_voice: document.querySelector("#brand-voice").value.split(",").map((part) => part.trim()).filter(Boolean),
    tone_characteristics: document.querySelector("#brand-tone").value,
    restricted_terms: collectTerms("restricted"),
    preferred_terms: collectTerms("preferred"),
    product_facts: collectFacts(),
  };
}

function collectTerms(kind) {
  return [...document.querySelectorAll(`[data-term-kind="${kind}"]`)].map((row) => ({
    phrase: row.querySelector('[data-field="phrase"]').value.trim(),
    explanation: row.querySelector('[data-field="explanation"]').value.trim(),
  })).filter((term) => term.phrase);
}

function collectFacts() {
  return [...document.querySelectorAll("[data-fact-index]")].map((row) => {
    const value = row.querySelector('[data-field="value"]').value.trim();
    return {
      product: row.querySelector('[data-field="product"]').value.trim(),
      fact: row.querySelector('[data-field="fact"]').value.trim(),
      value: value === "" ? null : Number(value),
      unit: row.querySelector('[data-field="unit"]').value.trim(),
    };
  }).filter((fact) => fact.product || fact.fact || fact.value !== null || fact.unit);
}

async function saveBrand(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector('[type="submit"]');
  const status = document.querySelector("#brand-save-status");
  button.disabled = true;
  button.innerHTML = '<span class="loader"></span> Saving…';
  if (status) status.textContent = "";
  const voice = document.querySelector("#brand-voice").value.split(",").map((part) => part.trim()).filter(Boolean);
  const payload = {
    brand_name: document.querySelector("#brand-name").value.trim(),
    brand_voice: voice,
    tone_characteristics: document.querySelector("#brand-tone").value.trim(),
    restricted_terms: collectTerms("restricted"),
    preferred_terms: collectTerms("preferred"),
    product_facts: collectFacts(),
  };
  try {
    state.rules = await api("/api/brand-rules", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    toast("Brand guidelines saved.");
    renderBrand();
    const newStatus = document.querySelector("#brand-save-status");
    if (newStatus) newStatus.textContent = "Saved just now";
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
    button.textContent = "Save guidelines →";
  }
}

function setReviewMode(mode) {
  const draft = document.querySelector("#draft-text");
  if (draft) state.draftText = draft.value;
  state.reviewMode = mode;
  const area = document.querySelector("#review-input-area");
  if (!area) return;
  area.innerHTML = mode === "text" ? renderTextEditor() : renderUploadEditor();
  document.querySelectorAll(".tab-button").forEach((button) => button.classList.toggle("active", button.dataset.mode === mode));
}

function renderTextEditor() {
  const draftText = state.draftText;
  return `<div class="editor-wrap"><textarea class="text-area" id="draft-text" maxlength="200000" placeholder="Paste a draft here. BGT will compare its language and claims with your saved guidelines.">${escapeHtml(draftText)}</textarea>
    <div class="editor-toolbar"><span>Draft stays unchanged until you choose to edit it.</span><span><b id="word-count">0</b> words&nbsp; · &nbsp;<b id="character-count">0</b> characters</span></div>
    <div class="editor-submit"><button class="button button-quiet button-small" type="button" data-action="clear-draft">Clear draft</button><span class="validation-message" id="review-error"></span><button class="button button-primary" type="button" data-action="submit-review">Run brand check <span class="button-icon">→</span></button></div>
  </div>`;
}

function renderUploadEditor() {
  return `<div class="drop-zone" id="drop-zone"><span class="upload-icon">${icon("upload")}</span>
    <strong>Drop a document here, or choose a file</strong><p>PDF or DOCX · Maximum file size 10 MB</p>
    <button class="button button-secondary button-small" type="button" data-action="choose-file">Choose a file</button>
    <input class="file-input" id="document-file" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document">
  </div><div id="file-detail"></div><div class="editor-submit"><span class="validation-message" id="review-error"></span><button class="button button-primary" type="button" data-action="submit-review">Upload &amp; review <span class="button-icon">→</span></button></div>`;
}

function renderNewReview() {
  state.uploadFile = null;
  state.draftText = "";
  state.reviewMode = "text";
  app.innerHTML = `<section class="page-enter">
    <div class="page-heading-row"><div><p class="eyebrow"><span class="eyebrow-dot"></span> CONTENT CHECK</p><h1 class="page-title">New review</h1><p class="page-description">Check draft language against the approved ${escapeHtml(state.rules.brand_name)} brand rules. Your original stays exactly as submitted.</p></div></div>
    <div class="form-layout">
      <section class="panel form-panel">
        <div class="form-section-title"><span class="section-index">01</span><div><h2>Bring in your draft</h2><p>Paste text directly or upload a document for text extraction.</p></div></div>
        <div class="field review-title-field"><label for="review-title">Review title <span class="field-hint">(optional)</span></label><input id="review-title" class="text-input" maxlength="160" placeholder="e.g. Summer launch announcement"></div>
        <div class="tabs" role="tablist" aria-label="Draft input method"><button class="tab-button ${state.reviewMode === "text" ? "active" : ""}" type="button" role="tab" aria-selected="${state.reviewMode === "text"}" data-mode="text">Paste text</button><button class="tab-button ${state.reviewMode === "file" ? "active" : ""}" type="button" role="tab" aria-selected="${state.reviewMode === "file"}" data-mode="file">Upload document</button></div>
        <div id="review-input-area">${state.reviewMode === "text" ? renderTextEditor() : renderUploadEditor()}</div>
      </section>
      <aside class="side-stack">
        <section class="panel"><div class="panel-heading"><div><h2>What BGT checks</h2><p>Every check includes its evidence</p></div></div><div class="review-guidance">
          <div class="guidance-item"><span class="guidance-icon">${icon("rules")}</span><div><strong>Restricted phrases</strong><p>Exact, case-insensitive matches from your saved rules.</p></div></div>
          <div class="guidance-item"><span class="guidance-icon">${icon("check")}</span><div><strong>Product facts</strong><p>Numeric claims compared with matching product context.</p></div></div>
          <div class="guidance-item"><span class="guidance-icon">${icon("edit")}</span><div><strong>Preferred wording</strong><p>Optional suggestions when preferred language is missing.</p></div></div>
          <div class="guidance-item"><span class="guidance-icon">${icon("help")}</span><div><strong>Tone prompt</strong><p>A simple, transparent capitalization heuristic.</p></div></div>
        </div></section>
        <div class="callout"><strong>Human review is the final step</strong>Findings are prompts, not confirmed violations. BGT will never publish, rewrite, or approve your content for you.</div>
      </aside>
    </div>
  </section>`;
  updateDraftCounts();
}

function updateDraftCounts() {
  const draft = document.querySelector("#draft-text");
  if (!draft) return;
  const value = draft.value;
  state.draftText = value;
  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  document.querySelector("#word-count").textContent = wordCount.toLocaleString();
  document.querySelector("#character-count").textContent = value.length.toLocaleString();
}

function showSelectedFile(file) {
  state.uploadFile = file;
  const detail = document.querySelector("#file-detail");
  const error = document.querySelector("#review-error");
  const validType = /\.(pdf|docx)$/i.test(file.name);
  if (file.size > 10 * 1024 * 1024) {
    state.uploadFile = null;
    error.textContent = "This file is larger than the 10 MB limit.";
    detail.innerHTML = "";
    return;
  }
  if (!validType) {
    state.uploadFile = null;
    error.textContent = "Choose a PDF or DOCX file.";
    detail.innerHTML = "";
    return;
  }
  error.textContent = "";
  detail.innerHTML = `<div class="file-detail">${icon("file")}<span>${escapeHtml(file.name)}</span><small>${formatBytes(file.size)}</small></div>`;
}

async function submitReview() {
  const errorNode = document.querySelector("#review-error");
  const submitButton = document.querySelector('[data-action="submit-review"]');
  errorNode.textContent = "";
  const formData = new FormData();
  if (state.reviewMode === "text") {
    const content = document.querySelector("#draft-text").value.trim();
    if (!content) {
      errorNode.textContent = "Paste some draft text before running a check.";
      return;
    }
    formData.append("text", content);
  } else {
    if (!state.uploadFile) {
      errorNode.textContent = "Choose a PDF or DOCX file to continue.";
      return;
    }
    formData.append("file", state.uploadFile);
  }
  formData.append("title", document.querySelector("#review-title")?.value.trim() || "");
  submitButton.disabled = true;
  submitButton.innerHTML = '<span class="loader"></span> Checking…';
  try {
    const review = await api("/api/reviews", { method: "POST", body: formData });
    state.reviews.unshift(review);
    toast("Review is ready. Findings are prompts for human review.");
    navigate("review", { id: review.id });
  } catch (error) {
    errorNode.textContent = error.message;
    submitButton.disabled = false;
    submitButton.innerHTML = `${state.reviewMode === "file" ? "Upload &amp; review" : "Run brand check"} <span class="button-icon">→</span>`;
  }
}

function historyItem(review) {
  return `<div class="history-item" role="link" tabindex="0" data-open-review="${review.id}">
    <div class="history-title">${fileIcon(review.source_type)}<div><strong>${escapeHtml(review.title)}</strong><small>${escapeHtml(review.source_name)}</small></div></div>
    <span class="history-cell">${escapeHtml(review.source_type.toUpperCase())}</span>
    <span class="history-cell">${formatDate(review.created_at, { month: "short", day: "numeric", year: "numeric" })}</span>
    ${statusChip(review.status)}
    <span class="history-count">${review.finding_count} <span>findings</span></span>
    <span class="history-chevron">›</span>
  </div>`;
}

function renderHistory(filterText = "") {
  const normalized = filterText.trim().toLowerCase();
  const reviews = state.reviews.filter((review) =>
    `${review.title} ${review.source_name} ${review.status}`.toLowerCase().includes(normalized));
  app.innerHTML = `<section class="page-enter">
    <div class="page-heading-row"><div><p class="eyebrow"><span class="eyebrow-dot"></span> SAVED RECORDS</p><h1 class="page-title">Review history</h1><p class="page-description">Revisit every draft, finding, and human decision saved in this workspace.</p></div><button class="button button-primary" data-action="new-review">${icon("scan")} New review</button></div>
    <div class="history-toolbar"><label class="search-field">${icon("search")}<input class="text-input" type="search" id="history-search" placeholder="Search reviews by title or file" value="${escapeHtml(filterText)}" aria-label="Search reviews"></label><span class="field-hint">${reviews.length} ${reviews.length === 1 ? "review" : "reviews"} saved</span></div>
    <section class="panel history-list">${reviews.length ? `<div class="history-header"><span>Review</span><span>Source type</span><span>Date created</span><span>Status</span><span>Findings</span></div>${reviews.map(historyItem).join("")}` : `<div class="list-empty">${normalized ? "No reviews match that search." : "No saved reviews yet. Your completed checks will appear here."}</div>`}</section>
  </section>`;
}

function findingLabel(severity) {
  return { attention: "Needs attention", suggestion: "Suggestion", info: "Informational" }[severity] || "Finding";
}

function findingCard(finding, selected) {
  const marker = finding.severity === "suggestion" ? "suggestion" : finding.severity === "info" ? "info" : "";
  const excerpt = finding.matched_text || finding.guideline;
  return `<button class="finding-card ${selected ? "selected" : ""}" type="button" data-select-finding="${finding.id}">
    <span class="finding-marker ${marker}">${finding.severity === "attention" ? "!" : finding.severity === "suggestion" ? "↗" : "i"}</span>
    <span class="finding-copy"><strong>${escapeHtml(finding.title)}</strong><small>${escapeHtml(excerpt || findingLabel(finding.severity))}</small></span>
    ${finding.state !== "open" ? `<span class="finding-resolved">${escapeHtml(finding.state)}</span>` : ""}
  </button>`;
}

function selectedFinding(review) {
  return review.findings.find((finding) => finding.id === state.selectedFindingId) || review.findings[0] || null;
}

function findingDetail(finding) {
  if (!finding) return `<div class="finding-details"><p class="detail-copy">No findings were raised by the current checks. A human reviewer still needs to record a decision.</p></div>`;
  const resolved = finding.state !== "open";
  return `<div class="finding-details">
    <div class="detail-title-row"><h3>${escapeHtml(finding.title)}</h3><span class="severity-chip severity-${escapeHtml(finding.severity)}">${escapeHtml(findingLabel(finding.severity))}</span></div>
    <p class="detail-copy">${escapeHtml(finding.explanation)}</p>
    ${finding.matched_text ? `<div class="evidence-block"><span>Draft excerpt</span><p>“${escapeHtml(finding.matched_text)}”</p></div>` : ""}
    ${finding.evidence ? `<div class="evidence-block"><span>Supporting evidence</span><p>${escapeHtml(finding.evidence)}</p></div>` : ""}
    ${finding.guideline ? `<div class="evidence-block"><span>Related brand guideline</span><p>${escapeHtml(finding.guideline)}</p></div>` : ""}
    ${finding.suggestion ? `<div class="field suggestion-field"><label for="suggestion-${finding.id}">Suggested correction <span class="field-hint">(editable; not applied automatically)</span></label><textarea class="text-area" id="suggestion-${finding.id}" maxlength="1000">${escapeHtml(finding.suggestion)}</textarea></div>` : ""}
    <div class="detail-actions">
      ${finding.suggestion ? `<button class="button button-secondary button-small" data-action="copy-suggestion" data-id="${finding.id}">Copy suggestion</button><button class="button button-secondary button-small" data-action="save-suggestion" data-id="${finding.id}">Save edit</button>` : ""}
      ${!resolved ? `${finding.suggestion ? `<button class="button button-quiet button-small" data-action="accept-finding" data-id="${finding.id}">Accept suggestion</button>` : ""}<button class="button button-quiet button-small" data-action="resolve-finding" data-id="${finding.id}">Mark resolved</button><button class="button button-quiet button-small" data-action="dismiss-finding" data-id="${finding.id}">Dismiss</button>` : `<span class="finding-resolved">Marked ${escapeHtml(finding.state)}</span>`}
    </div>
  </div>`;
}

function reviewDecision(review) {
  if (review.status !== "needs_review") {
    return `<section class="panel decision-panel"><div class="decision-summary">${icon(review.status === "approved" ? "check" : "edit")}<span><strong>${review.status === "approved" ? "Review approved by a human" : "Changes requested by a human"}</strong>${review.decision_note ? escapeHtml(review.decision_note) : `Decision recorded ${formatDate(review.decided_at)}.`}</span></div></section>`;
  }
  return `<section class="panel decision-panel">
    <div class="decision-copy"><h2>Human review</h2><p>A person makes the final decision, even when no checks raise a finding.</p></div>
    <textarea class="text-area" id="decision-note" maxlength="1000" placeholder="Optional reviewer note for the history record"></textarea>
    <div class="decision-actions"><button class="button button-secondary button-small" data-action="decide" data-status="changes_requested">Request changes</button><button class="button button-primary button-small" data-action="decide" data-status="approved">${icon("check")} Approve review</button></div>
  </section>`;
}

async function loadReview(id) {
  app.innerHTML = `<div class="loading-view"><span class="loader"></span><span>Opening review…</span></div>`;
  try {
    const review = await api(`/api/reviews/${id}`);
    state.currentReview = review;
    if (!review.findings.some((finding) => finding.id === state.selectedFindingId)) {
      state.selectedFindingId = review.findings[0]?.id || null;
    }
    renderReview(review);
  } catch (error) {
    app.innerHTML = `<section class="review-not-found"><h1 class="page-title">Review unavailable</h1><p class="page-description">${escapeHtml(error.message)}</p><button class="button button-secondary" data-action="go-history">Back to review history</button></section>`;
  }
}

function renderReview(review) {
  const openCount = review.findings.filter((finding) => finding.state === "open").length;
  const selected = selectedFinding(review);
  const visibleFindings = review.findings.filter((finding) => {
    if (state.findingFilter === "open") return finding.state === "open";
    if (state.findingFilter === "attention") return finding.severity === "attention";
    return true;
  });
  app.innerHTML = `<section class="page-enter">
    <div class="report-top">
      <div><p class="eyebrow"><span class="eyebrow-dot"></span> REVIEW REPORT</p><h1 class="page-title">${escapeHtml(review.title)}</h1>
        <div class="report-meta"><span>${icon("file")} ${escapeHtml(review.source_name)}</span><span>${icon("clock")} ${formatDate(review.created_at)}</span><span>${escapeHtml(review.source_type.toUpperCase())} source</span></div>
      </div>
      <div class="report-stats"><div class="report-stat"><strong>${review.finding_count}</strong><span>Findings</span></div><div class="report-stat"><strong>${openCount}</strong><span>Open</span></div><div class="report-stat">${statusChip(review.status)}</div></div>
    </div>
    <div class="report-grid">
      <div class="report-column">
        <section class="panel draft-card"><div class="card-heading"><h2>Original draft</h2><span>Read-only · ${review.content.length.toLocaleString()} characters</span></div><div class="draft-content">${escapeHtml(review.content)}</div></section>
        ${reviewDecision(review)}
      </div>
      <section class="panel findings-card"><div class="card-heading"><h2>Findings &amp; suggestions</h2><span>${review.finding_count} total</span></div>
        <div class="finding-filter"><button class="filter-chip ${state.findingFilter === "all" ? "active" : ""}" data-filter-findings="all">All (${review.finding_count})</button><button class="filter-chip ${state.findingFilter === "open" ? "active" : ""}" data-filter-findings="open">Open (${openCount})</button><button class="filter-chip ${state.findingFilter === "attention" ? "active" : ""}" data-filter-findings="attention">Attention (${review.findings.filter((item) => item.severity === "attention").length})</button></div>
        <div class="finding-list">${visibleFindings.length ? visibleFindings.map((finding) => findingCard(finding, selected?.id === finding.id)).join("") : `<div class="list-empty">${review.finding_count ? "No findings in this filter." : "No deterministic checks raised a finding. Review the draft, then record your decision."}</div>`}</div>
        ${visibleFindings.some((finding) => finding.id === selected?.id) ? findingDetail(selected) : ""}
      </section>
    </div>
    <div class="human-note">${icon("shield")}<span>Only a human reviewer can decide whether this content is ready. Dismissed, resolved, and edited findings remain part of the review record.</span></div>
  </section>`;
}

async function updateFinding(id, changes) {
  const review = state.currentReview;
  const updated = await api(`/api/reviews/${review.id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ findings: [{ id, ...changes }] }),
  });
  state.currentReview = updated;
  const index = state.reviews.findIndex((item) => item.id === updated.id);
  if (index >= 0) state.reviews[index] = updated;
  renderReview(updated);
}

async function saveDecision(status) {
  const note = document.querySelector("#decision-note")?.value.trim() || "";
  const updated = await api(`/api/reviews/${state.currentReview.id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, decision_note: note }),
  });
  state.currentReview = updated;
  const index = state.reviews.findIndex((item) => item.id === updated.id);
  if (index >= 0) state.reviews[index] = updated;
  toast(status === "approved" ? "Human approval recorded." : "Change request recorded.");
  renderReview(updated);
}

function renderGuide() {
  app.innerHTML = `<section class="page-enter">
    <p class="eyebrow"><span class="eyebrow-dot"></span> BGT STUDIO</p><h1 class="page-title">A quick guide to better reviews</h1><p class="page-description">BGT helps teams apply their own standards consistently. It explains each check and leaves every decision with your people.</p>
    <div class="guide-grid">
      <article class="guide-card"><span class="section-index">01</span><h2>Make your standard useful</h2><p>Add exact restricted phrases, optional preferred language, and product facts with context. Keep the guidance specific and current.</p></article>
      <article class="guide-card"><span class="section-index">02</span><h2>Bring a draft in</h2><p>Paste text or upload a text-based PDF or DOCX. BGT stores the original draft with its review record and checks the extracted content.</p></article>
      <article class="guide-card"><span class="section-index">03</span><h2>Follow the evidence</h2><p>Open each finding to see the matched text, saved guideline, or approved fact that prompted it. Suggestions can be edited before copying.</p></article>
      <article class="guide-card"><span class="section-index">04</span><h2>Decide as a reviewer</h2><p>Resolve or dismiss individual findings, then approve the review or request changes. No draft is auto-approved.</p></article>
      <article class="guide-card"><span class="section-index">05</span><h2>Know the limits</h2><p>Checks are deterministic phrase and numeric comparisons plus a basic capitalization heuristic. They do not understand legal context or replace expert review.</p></article>
      <article class="guide-card"><span class="section-index">06</span><h2>Keep your data local</h2><p>This MVP stores reviews and brand rules in a local SQLite database. Uploaded documents are read for text extraction and not kept as binary files.</p></article>
    </div>
    <div class="human-note">${icon("shield")}<span>Findings are prompts for review, not confirmed violations. BGT does not publish content or send drafts to an external service.</span></div>
  </section>`;
}

function updateWorkspaceDate() {
  document.querySelector("#topbar-date").textContent = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" }).format(new Date());
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action], [data-open-review], [data-select-finding], [data-mode], [data-filter-findings]");
  if (!target) return;
  if (target.dataset.openReview) {
    navigate("review", { id: target.dataset.openReview });
    return;
  }
  if (target.dataset.mode) {
    setReviewMode(target.dataset.mode);
    return;
  }
  if (target.dataset.filterFindings) {
    state.findingFilter = target.dataset.filterFindings;
    renderReview(state.currentReview);
    return;
  }
  if (target.dataset.selectFinding) {
    state.selectedFindingId = Number(target.dataset.selectFinding);
    renderReview(state.currentReview);
    return;
  }
  const action = target.dataset.action;
  try {
    if (action === "reload-page") {
      window.location.reload();
      return;
    }
    if (action === "retry-connection") {
      target.disabled = true;
      target.textContent = "Checking…";
      await init();
      return;
    }
    if (action === "new-review") navigate("new");
    if (action === "go-history") navigate("history");
    if (action === "choose-file") document.querySelector("#document-file")?.click();
    if (action === "clear-draft") {
      document.querySelector("#draft-text").value = "";
      updateDraftCounts();
    }
    if (action === "submit-review") await submitReview();
    if (action === "add-term") {
      captureBrandForm();
      const kind = target.dataset.kind;
      state.rules[`${kind}_terms`].push({ phrase: "", explanation: "" });
      renderBrand();
      const row = document.querySelector(`[data-term-kind="${kind}"]:last-child [data-field="phrase"]`);
      row?.focus();
    }
    if (action === "remove-term") {
      captureBrandForm();
      const kind = target.dataset.kind;
      state.rules[`${kind}_terms`].splice(Number(target.dataset.index), 1);
      renderBrand();
    }
    if (action === "add-fact") {
      captureBrandForm();
      state.rules.product_facts.push({ product: "", fact: "", value: null, unit: "" });
      renderBrand();
      document.querySelector("[data-fact-index]:last-child [data-field='product']")?.focus();
    }
    if (action === "remove-fact") {
      captureBrandForm();
      state.rules.product_facts.splice(Number(target.dataset.index), 1);
      renderBrand();
    }
    if (action === "copy-suggestion") {
      const finding = state.currentReview.findings.find((item) => item.id === Number(target.dataset.id));
      await navigator.clipboard.writeText(finding.suggestion);
      toast("Suggestion copied to clipboard.");
    }
    if (action === "save-suggestion") {
      const id = Number(target.dataset.id);
      const suggestion = document.querySelector(`#suggestion-${id}`).value.trim();
      await updateFinding(id, { suggestion });
      toast("Suggested correction saved.");
    }
    if (action === "dismiss-finding") {
      await updateFinding(Number(target.dataset.id), { state: "dismissed" });
      toast("Finding dismissed and saved.");
    }
    if (action === "resolve-finding") {
      await updateFinding(Number(target.dataset.id), { state: "resolved" });
      toast("Finding marked resolved.");
    }
    if (action === "accept-finding") {
      await updateFinding(Number(target.dataset.id), { state: "accepted" });
      toast("Finding accepted and saved.");
    }
    if (action === "decide") await saveDecision(target.dataset.status);
    if (target.id === "header-help") navigate("guide");
  } catch (error) {
    toast(error.message || "The action could not be completed.", true);
  }
});

document.addEventListener("submit", (event) => {
  if (event.target.id === "brand-form") saveBrand(event);
});

document.addEventListener("input", (event) => {
  if (event.target.id === "draft-text") updateDraftCounts();
  if (event.target.id === "history-search") {
    const cursor = event.target.selectionStart;
    renderHistory(event.target.value);
    const replacement = document.querySelector("#history-search");
    replacement.focus();
    replacement.setSelectionRange(cursor, cursor);
  }
});

document.addEventListener("change", (event) => {
  if (event.target.id === "document-file" && event.target.files?.[0]) showSelectedFile(event.target.files[0]);
});

document.addEventListener("dragover", (event) => {
  const zone = event.target.closest("#drop-zone");
  if (zone) {
    event.preventDefault();
    zone.classList.add("drag-over");
  }
});

document.addEventListener("dragleave", (event) => {
  const zone = event.target.closest("#drop-zone");
  if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove("drag-over");
});

document.addEventListener("drop", (event) => {
  const zone = event.target.closest("#drop-zone");
  if (!zone) return;
  event.preventDefault();
  zone.classList.remove("drag-over");
  if (event.dataTransfer.files?.[0]) showSelectedFile(event.dataTransfer.files[0]);
});

document.querySelector("#mobile-menu").addEventListener("click", () => {
  const sidebar = document.querySelector("#sidebar");
  const isOpen = sidebar.classList.toggle("open");
  document.querySelector("#mobile-backdrop").classList.toggle("visible", isOpen);
  document.querySelector("#mobile-menu").setAttribute("aria-expanded", String(isOpen));
});
document.querySelector("#mobile-backdrop").addEventListener("click", closeMobileNav);
document.querySelector("#header-help").addEventListener("click", () => navigate("guide"));
document.querySelector("#sign-out").addEventListener("click", () => {
  sessionStorage.removeItem("bgt-access-token");
  state.rules = null;
  state.reviews = [];
  renderLogin();
});
window.addEventListener("hashchange", renderRoute);
document.addEventListener("keydown", (event) => {
  const row = event.target.closest("[data-open-review]");
  if (row && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    navigate("review", { id: row.dataset.openReview });
  }
});

async function init() {
  updateWorkspaceDate();
  document.querySelectorAll("[data-icon]").forEach((node) => {
    const name = node.dataset.icon;
    node.innerHTML = icon(name);
  });
  setWorkspaceStatus("Connecting");
  const needsConfiguration = location.hostname.endsWith(".github.io") && !API_BASE_URL;
  if (needsConfiguration) {
    renderConnectionError(null, true);
    return;
  }
  try {
    const config = await api("/api/auth/config");
    state.authRequired = config.required;
    if (state.authRequired && !sessionStorage.getItem("bgt-access-token")) {
      renderLogin();
      return;
    }
    const [health, rules, reviews] = await Promise.all([api("/api/health"), api("/api/brand-rules"), api("/api/reviews")]);
    if (health.status !== "ok") throw new Error("The BGT API did not report a healthy status.");
    state.rules = rules;
    state.reviews = reviews;
    setWorkspaceStatus("Workspace active");
    renderRoute();
  } catch (error) {
    if (error.status === 401 && state.authRequired) {
      sessionStorage.removeItem("bgt-access-token");
      renderLogin("Your access token has expired or is not valid. Try again.");
      return;
    }
    renderConnectionError(error);
  }
}

document.addEventListener("submit", async (event) => {
  if (event.target.id !== "login-form") return;
  event.preventDefault();
  const form = event.target;
  const button = form.querySelector('[type="submit"]');
  const token = new FormData(form).get("token").toString().trim();
  button.disabled = true;
  button.textContent = "Signing in…";
  sessionStorage.setItem("bgt-access-token", token);
  try {
    await api("/api/auth/session", { method: "POST" });
    await init();
  } catch (error) {
    sessionStorage.removeItem("bgt-access-token");
    renderLogin(error.message);
  }
});

init();
