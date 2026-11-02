(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const csrf = () => (document.cookie.split("; ").find((r) => r.startsWith("csrftoken=")) || "").split("=")[1] || "";

  function errText(d, status) {
    if (!d) return `Request failed (${status}).`;
    if (d.detail) return d.detail;
    return Object.entries(d).map(([k, v]) => `${k}: ${[].concat(v).join(" ")}`).join(" | ");
  }

  async function api(url, { method = "GET", json, form } = {}) {
    const opts = { method, credentials: "same-origin", headers: {} };
    if (method !== "GET") opts.headers["X-CSRFToken"] = csrf();
    if (json) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(json); }
    if (form) opts.body = form;
    const r = await fetch(url, opts);
    const data = r.status === 204 ? null : await r.json().catch(() => null);
    if (!r.ok) { const e = new Error(errText(data, r.status)); e.status = r.status; throw e; }
    return data;
  }

  function flash(msg, kind = "danger") {
    $("#alert").innerHTML = msg ? `<div class="alert alert-${kind} alert-dismissible">${esc(msg)}
      <button type="button" class="btn-close" data-bs-dismiss="alert" onclick="this.parentElement.remove()"></button></div>` : "";
  }

  const TABS = {
    Administrator: [["admin", "Manage manuals"], ["history", "All questions"]],
    Engineer: [["ask", "Ask a question"], ["history", "My history"]],
    Supervisor: [["history", "Question history"]],
  };
  let me = null, machines = [];

  function machineOptions(sel) {
    $(sel).innerHTML = machines.length
      ? machines.map((m) => `<option value="${m.id}">${esc(m.name)} (${esc(m.model_number)})</option>`).join("")
      : `<option value="">No machines registered yet</option>`;
  }

  async function loadMachines() {
    machines = await api("/api/machines/");
    if (me.role === "Administrator") machineOptions("#u-machine");
    if (me.role === "Engineer") machineOptions("#a-machine");
  }

  async function loadManuals() {
    const rows = await api("/api/manuals/");
    $("#manuals-body").innerHTML = rows.length ? rows.map((m) => `<tr>
      <td>${esc(m.machine_name)}</td><td>${esc(m.title)}</td><td>${esc(m.revision)}</td><td>${m.page_count}</td>
      <td><a href="${m.file_url}" target="_blank" rel="noopener">Open PDF</a></td></tr>`).join("")
      : `<tr><td colspan="5" class="text-muted">No manuals yet. Upload one to get started.</td></tr>`;
  }

  function renderQA(q, withMeta) {
    const sources = (q.sources || []).map((s) => `<div class="source">
      <strong>[${s.ref}] ${esc(s.manual_title)}</strong>, revision ${esc(s.revision)}, page ${s.page}
      &middot; <a href="${s.file_url}#page=${s.page}" target="_blank" rel="noopener">Open PDF at page ${s.page}</a>
      <blockquote>${esc(s.passage)}</blockquote></div>`).join("");
    return `<article class="qa ${q.answered ? "" : "unanswered"}">
      ${withMeta ? `<div class="meta mb-1">${esc(q.username)} &middot; ${esc(q.machine_name)} &middot; ${new Date(q.created_at).toLocaleString()}</div>` : ""}
      <div class="fw-semibold mb-2">${esc(q.text)}</div>
      <span class="badge ${q.answered ? "text-bg-success" : "text-bg-danger"} mb-2">${q.answered ? "Answered" : "Not enough information"}</span>
      <div class="answer">${esc(q.answer)}</div>${sources}</article>`;
  }

  async function loadHistory() {
    const unanswered = $("#h-unanswered").checked ? "?unanswered=1" : "";
    const rows = await api("/api/questions/" + unanswered);
    $("#history").innerHTML = rows.length
      ? rows.map((q) => renderQA(q, me.role !== "Engineer")).join("")
      : `<p class="text-muted">No questions to show.</p>`;
  }

  async function show(tab) {
    flash("");
    document.querySelectorAll(".tab").forEach((t) => t.classList.add("d-none"));
    $("#tab-" + tab).classList.remove("d-none");
    document.querySelectorAll("#tabs .nav-link").forEach((a) => a.classList.toggle("active", a.dataset.tab === tab));
    try {
      if (tab === "admin") { await loadMachines(); await loadManuals(); }
      if (tab === "ask") await loadMachines();
      if (tab === "history") await loadHistory();
    } catch (e) { flash(e.message); }
  }

  function start(user) {
    me = user;
    $("#login-view").classList.add("d-none");
    $("#session").classList.remove("d-none");
    $("#who").textContent = `${me.username} (${me.role || "no role"})`;
    const tabs = TABS[me.role] || [];
    if (!tabs.length) { $("#app-view").classList.add("d-none"); flash("Your account has no role yet. Ask an administrator."); return; }
    $("#app-view").classList.remove("d-none");
    $("#tabs").innerHTML = tabs.map(([id, label]) =>
      `<li class="nav-item"><a href="#" class="nav-link" data-tab="${id}">${label}</a></li>`).join("");
    $("#tabs").onclick = (e) => { const a = e.target.closest("[data-tab]"); if (a) { e.preventDefault(); show(a.dataset.tab); } };
    show(tabs[0][0]);
  }

  function showLogin() {
    me = null;
    $("#session").classList.add("d-none");
    $("#app-view").classList.add("d-none");
    $("#login-view").classList.remove("d-none");
  }

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault(); flash("");
    try {
      start(await api("/api/auth/login/", { method: "POST", json: { username: $("#username").value, password: $("#password").value } }));
      $("#password").value = "";
    } catch (err) { flash(err.message); }
  });

  $("#logout").addEventListener("click", async () => {
    try { await api("/api/auth/logout/", { method: "POST" }); } catch (e) { /* already signed out */ }
    flash(""); showLogin();
  });

  $("#machine-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/machines/", { method: "POST", json: { name: $("#m-name").value, model_number: $("#m-model").value } });
      e.target.reset(); await loadMachines(); flash("Machine added.", "success");
    } catch (err) { flash(err.message); }
  });

  $("#manual-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData();
    fd.append("machine", $("#u-machine").value);
    fd.append("title", $("#u-title").value);
    fd.append("revision", $("#u-rev").value);
    fd.append("file", $("#u-file").files[0]);
    $("#u-btn").disabled = true; $("#u-btn").textContent = "Indexing...";
    try {
      await api("/api/manuals/", { method: "POST", form: fd });
      e.target.reset(); await loadManuals(); flash("Manual uploaded and indexed.", "success");
    } catch (err) { flash(err.message); }
    finally { $("#u-btn").disabled = false; $("#u-btn").textContent = "Upload and index"; }
  });

  $("#ask-form").addEventListener("submit", async (e) => {
    e.preventDefault(); flash("");
    $("#a-btn").disabled = true; $("#a-btn").textContent = "Searching manuals...";
    try {
      const q = await api("/api/ask/", { method: "POST", json: { machine: Number($("#a-machine").value), question: $("#a-text").value } });
      $("#answer").innerHTML = renderQA(q, false);
    } catch (err) { flash(err.message); }
    finally { $("#a-btn").disabled = false; $("#a-btn").textContent = "Ask"; }
  });

  $("#h-unanswered").addEventListener("change", () => loadHistory().catch((e) => flash(e.message)));

  (async () => {
    try { start(await api("/api/auth/me/")); } catch (e) { showLogin(); }
  })();
})();
