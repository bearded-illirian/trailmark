// vschk-flow-ui — SPA hash router + tree navigation
// Consumes Block 3 endpoints; POST /api/access on file/artifact opens.

// ── i18n (namespace object — immune to variable shadowing) ────────────
window.i18n = {
  SUPPORTED: ["en", "ru"],
  DEFAULT: "en",
  dict: {},
  locale: "en",

  detect() {
    const stored = localStorage.getItem("flow_ui_locale");
    if (stored && this.SUPPORTED.includes(stored)) return stored;
    const browser = (navigator.language || "").toLowerCase();
    return browser.startsWith("ru") ? "ru" : "en";
  },

  async load(locale) {
    const res = await fetch(`/static/i18n/${locale}.json`);
    this.dict = await res.json();
    this.locale = locale;
    document.documentElement.lang = locale;
  },

  t(key, vars) {
    let s = this.dict[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
    return s;
  },

  async set(locale) {
    if (!this.SUPPORTED.includes(locale)) return;
    localStorage.setItem("flow_ui_locale", locale);
    await this.load(locale);
    document.querySelectorAll(".locale-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.locale === locale);
    });
    const badge = document.querySelector(".stats-badge");
    if (badge) badge.title = this.t("badge.tooltip");
    if (typeof applyHash === "function") applyHash();
  },
};

const ARTIFACT_CATEGORIES = {
  protocol: new Set([
    "flow-first", "library-first", "plan-first", "report",
    "idea-first", "smoke-verify", "migration",
  ]),
  thoughts: new Set([
    "note", "user-note", "user-note-final", "decision", "decision-first",
    "research-doc", "audit-doc", "handoff", "arch-doc", "habit-first",
  ]),
  audits: new Set([
    "atom-compliance", "ui-ai-first", "ui-ai-first-sub",
    "chain-doc", "chain-validation", "monitoring",
  ]),
};

const state = {
  projects: [],
  project: null,     // {id, name, path, ...}
  tab: "files",      // "files" | "tasks" | "deploys" | "skills"
  filesPath: "",     // subpath under project root
  taskId: null,      // opened task id (Tasks tab drilldown)
  artifactFilter: "all", // "all" | "protocol" | "thoughts" | "audits"
  accessed: new Set(), // dedup for POST /api/access
  expandedDeployGroups: new Set(), // task_ids of expanded groups in Deploys tab
  // Skills tab (block 404)
  skillFilter: { domain: "all", usage: "all" }, // usage: "all" | "used30d" | "unused90d"
  selectedSkill: null, // skill name when detail view active
  skillsCache: null,   // client-side memoization of GET /api/skills
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "on") for (const [ev, fn] of Object.entries(v)) node.addEventListener(ev, fn);
    else if (k.startsWith("data-")) node.setAttribute(k, v);
    else node[k] = v;
  }
  for (const c of children) node.append(c?.nodeType ? c : document.createTextNode(c ?? ""));
  return node;
};

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

async function logAccess(project, target_type, target_id) {
  const key = `${target_type}:${target_id}`;
  if (state.accessed.has(key)) return;
  state.accessed.add(key);
  try {
    await api("/api/access", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, target_type, target_id }),
    });
    refreshStats();
  } catch (e) {
    console.warn("access log failed:", e);
  }
}

async function refreshStats() {
  try {
    const s = await api("/api/stats");
    const label = document.querySelector(".stats-badge .badge-label");
    const today = document.querySelector(".stats-badge .today");
    if (label) label.textContent = i18n.t("badge.label");
    if (today) today.textContent = `· ${i18n.t("badge.today", { n: s.today_count })}`;
  } catch (e) {
    console.warn("stats refresh failed:", e);
  }
}

// ── Hash router ───────────────────────────────────────────
// /#/{project}/files/{subpath}   → Files tab, at subpath
// /#/{project}/tasks             → Tasks tab, list
// /#/{project}/tasks/{task_id}   → Tasks tab, drilled to task

function parseHash() {
  const raw = (location.hash || "#/").slice(2); // strip "#/"
  const parts = raw.split("/").filter(Boolean);
  // Empty hash (page refresh / initial load) → default to global stats
  if (parts.length === 0) {
    return { statsScope: "global" };
  }
  // /#/stats → global stats
  if (parts.length === 1 && parts[0] === "stats") {
    return { statsScope: "global" };
  }
  // /#/{project}/skills → skills list  (must come BEFORE stats fallback)
  if (parts.length === 2 && parts[1] === "skills") {
    return { project: parts[0], kind: "skills", target: "" };
  }
  // /#/{project}/skills/{name} → skill detail
  if (parts.length === 3 && parts[1] === "skills") {
    return { project: parts[0], kind: "skills", target: parts[2] };
  }
  // /#/{project}/stats → project stats
  if (parts.length === 2 && parts[1] === "stats") {
    return { statsScope: "project", project: parts[0] };
  }
  // /#/{project}/tasks/{task_id}/stats → task stats
  if (parts.length === 4 && parts[1] === "tasks" && parts[3] === "stats") {
    return { statsScope: "task", project: parts[0], taskId: parts[2] };
  }
  const [project, kind, ...rest] = parts;
  const target = rest.join("/");
  return { project, kind: kind || "files", target };
}

function setHash({ project, kind = "files", target = "" }) {
  const rest = target ? `/${target}` : "";
  location.hash = `#/${project}/${kind}${rest}`;
}

// ── Renderers ─────────────────────────────────────────────

function renderCrumbs() {
  const c = $("#crumbs");
  c.replaceChildren();
  if (!state.project) return;
  if (state.tab === "files") {
    const segs = ["", ...state.filesPath.split("/").filter(Boolean)];
    segs.forEach((seg, i) => {
      const path = segs.slice(1, i + 1).join("/");
      const link = el("a", {
        on: {
          click: () => {
            state.filesPath = path;
            setHash({ project: state.project.id, kind: "files", target: path });
          },
        },
      }, i === 0 ? state.project.id : seg);
      c.append(link);
      if (i < segs.length - 1) c.append(el("span", { class: "sep" }, "/"));
    });
  } else if (state.tab === "skills") {
    c.append(el("span", {}, `${state.project.id} · skills`));
    if (state.selectedSkill) c.append(el("span", { class: "sep" }, "/"), el("span", {}, state.selectedSkill));
  } else if (state.tab === "deploys") {
    c.append(el("span", {}, `${state.project.id} · deploys`));
  } else {
    c.append(el("span", {}, `${state.project.id} · tasks`));
    if (state.taskId) c.append(el("span", { class: "sep" }, "/"), el("span", {}, state.taskId));
  }
  // 📊 stats icon on the right — for project or task context
  const statsBtn = el("button", {
    class: "stats-icon-btn",
    title: state.taskId ? i18n.t("title.task_stats", { id: state.taskId }) : i18n.t("title.project_stats", { id: state.project.id }),
    on: { click: () => {
      if (state.taskId) location.hash = `#/${state.project.id}/tasks/${state.taskId}/stats`;
      else location.hash = `#/${state.project.id}/stats`;
    }},
  }, "📊");
  c.append(statsBtn);
}

function setContent(html) {
  const box = $("#content");
  box.replaceChildren();
  if (typeof html === "string") box.innerHTML = html;
  else box.append(html);
}

const CODE_EXTS = new Set([
  "py", "js", "ts", "tsx", "jsx", "css", "scss", "sh", "bash", "zsh",
  "sql", "html", "xml", "yml", "yaml", "json", "toml", "ini", "conf",
  "rb", "go", "rs", "java", "c", "cpp", "h", "swift", "kt", "php",
]);

function renderContent(text, filename) {
  const ext = (filename || "").split(".").pop().toLowerCase();
  if (ext === "md" || ext === "markdown") {
    const box = el("div", { class: "md-content" });
    box.innerHTML = window.marked ? marked.parse(text) : text;
    if (window.hljs) box.querySelectorAll("pre code").forEach(b => hljs.highlightElement(b));
    return box;
  }
  if (CODE_EXTS.has(ext)) {
    const code = el("code", { class: `language-${ext}` }, text);
    const pre = el("pre", {}, code);
    if (window.hljs) hljs.highlightElement(code);
    return pre;
  }
  return el("pre", {}, text);
}

async function renderFiles() {
  const t = $("#tree");
  t.replaceChildren(el("div", { class: "muted", style: "padding:12px" }, "Loading…"));
  try {
    const entries = await api(`/api/projects/${state.project.id}/tree?path=${encodeURIComponent(state.filesPath)}`);
    t.replaceChildren();
    if (state.filesPath) {
      t.append(el("div", {
        class: "tree-item", "data-type": "dir",
        on: { click: () => {
          const parent = state.filesPath.split("/").slice(0, -1).join("/");
          setHash({ project: state.project.id, kind: "files", target: parent });
        }},
      }, el("span", { class: "icon" }, ""), el("span", { class: "name" }, "..")));
    }
    for (const e of entries) {
      const item = el("div", {
        class: "tree-item", "data-type": e.type,
        on: { click: () => onFileClick(e) },
      },
        el("span", { class: "icon" }, ""),
        el("span", { class: "name" }, e.name),
        e.type === "file" ? el("span", { class: "meta" }, formatSize(e.size)) : "",
      );
      t.append(item);
    }
    if (!entries.length) t.append(el("div", { class: "muted", style: "padding:12px" }, "Empty."));
  } catch (e) {
    console.warn(e);
    t.replaceChildren(el("div", { class: "muted", style: "padding:12px" }, `Error: ${e.message}`));
  }
}

async function onFileClick(entry) {
  if (entry.type === "dir") {
    const next = state.filesPath ? `${state.filesPath}/${entry.name}` : entry.name;
    setHash({ project: state.project.id, kind: "files", target: next });
    return;
  }
  const path = state.filesPath ? `${state.filesPath}/${entry.name}` : entry.name;
  logAccess(state.project.id, "file", path);
  if (!entry.is_text) {
    setContent(`<div class="muted center">Binary file — preview not available.</div>`);
    return;
  }
  setContent(`<div class="muted center">Loading…</div>`);
  try {
    const data = await api(`/api/projects/${state.project.id}/file?path=${encodeURIComponent(path)}`);
    setContent(renderContent(data.content, path));
  } catch (e) {
    setContent(`<div class="muted center">Error: ${e.message}</div>`);
  }
}

function renderChips() {
  const row = el("div", { class: "filter-chips" });
  const chips = [
    ["all", i18n.t("filter.all")], ["protocol", i18n.t("filter.protocol")],
    ["thoughts", i18n.t("filter.thoughts")], ["audits", i18n.t("filter.audits")],
  ];
  for (const [key, label] of chips) {
    row.append(el("button", {
      class: `chip${state.artifactFilter === key ? " active" : ""}`,
      "data-filter": key,
      on: { click: () => {
        state.artifactFilter = key;
        renderTasks();
      }},
    }, label));
  }
  return row;
}

async function renderTasks() {
  const t = $("#tree");
  t.replaceChildren(el("div", { class: "muted", style: "padding:12px" }, "Loading tasks…"));
  try {
    if (state.taskId) {
      // drilled — show artifacts + fetch task meta for pin
      const [artifactsRaw, task] = await Promise.all([
        api(`/api/tasks/${state.taskId}/artifacts`),
        api(`/api/tasks/${state.taskId}`).catch(() => null),
      ]);
      let artifacts = artifactsRaw;
      // Pin task.md above chip filter — GitHub README-style
      // Primary source: task.file_path (from artifacts table); fallback: task_artifacts scan
      let taskMdPath = task && task.file_path ? task.file_path : null;
      let taskMdName = "task.md";
      if (!taskMdPath) {
        const found = artifacts.find(a => (a.file_name || "").toLowerCase() === "task.md");
        if (found) { taskMdPath = found.file_path; taskMdName = found.file_name; }
      }
      artifacts = artifacts.filter(a => (a.file_name || "").toLowerCase() !== "task.md");
      const cat = ARTIFACT_CATEGORIES[state.artifactFilter];
      if (cat) artifacts = artifacts.filter(a => cat.has(a.artifact_type));
      t.replaceChildren();
      if (taskMdPath) {
        t.append(el("div", {
          class: "task-pin-banner",
          on: { click: () => onArtifactClick({ file_path: taskMdPath, file_name: taskMdName }) },
        },
          el("span", { class: "task-pin-icon" }, "📋"),
          el("span", { class: "task-pin-title" }, taskMdName),
          el("span", { class: "task-pin-meta" }, i18n.t("task.description")),
        ));
      }
      t.append(renderChips());
      t.append(el("div", {
        class: "tree-item", "data-type": "dir",
        on: { click: () => {
          state.taskId = null;
          state.artifactFilter = "all";
          setHash({ project: state.project.id, kind: "tasks", target: "" });
        }},
      }, el("span", { class: "icon" }, ""), el("span", { class: "name" }, "..")));
      for (const a of artifacts) {
        const item = el("div", {
          class: "tree-item subitem", "data-type": "artifact",
          on: { click: () => onArtifactClick(a) },
        },
          el("span", { class: "icon" }, ""),
          el("span", { class: "name" }, a.file_name || a.file_path || "?"),
          el("span", { class: "meta" }, `${a.artifact_type ?? ""} #${a.block_num_raw ?? ""}`),
        );
        t.append(item);
      }
      if (!artifacts.length) t.append(el("div", { class: "muted", style: "padding:12px" }, "No artifacts matching filter."));
    } else {
      // list tasks
      const tasks = await api(`/api/projects/${state.project.id}/tasks`);
      t.replaceChildren();
      for (const task of tasks) {
        const item = el("div", {
          class: "tree-item", "data-type": "task",
          on: { click: () => {
            state.taskId = task.id;
            setHash({ project: state.project.id, kind: "tasks", target: task.id });
          }},
        },
          el("span", { class: "icon" }, ""),
          el("span", { class: "name" }, `#${task.number ?? "-"} ${task.title || task.id}`),
          el("span", { class: "meta" }, task.status || ""),
        );
        t.append(item);
      }
      if (!tasks.length) t.append(el("div", { class: "muted", style: "padding:12px" }, "No tasks."));
    }
  } catch (e) {
    console.warn(e);
    t.replaceChildren(el("div", { class: "muted", style: "padding:12px" }, `Error: ${e.message}`));
  }
}

async function onArtifactClick(a) {
  const path = a.file_path;
  if (!path) return;
  logAccess(state.project.id, "artifact", path);
  setContent(`<div class="muted center">Loading…</div>`);
  try {
    const data = await api(`/api/artifacts/read?path=${encodeURIComponent(path)}`);
    setContent(renderContent(data.content, a.file_name || path));
  } catch (e) {
    setContent(`<div class="muted center">Error: ${e.message}</div>`);
  }
}

// ── Deploys tab ───────────────────────────────────────────

function fmtDeployTime(iso) {
  // "2026-07-06T16:23:59Z" → "07-06 19:23" (MSK-adjusted display)
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mn}`;
}

function renderDeployRow(d) {
  const sha = (d.commit_sha || "").slice(0, 8);
  const block = d.block_num ? `block-${d.block_num}` : "";
  const msg = d.commit_msg || "(no message)";
  const row = el("div", {
    class: "deploy-row",
    on: { click: () => onDeployClick(d) },
  });
  row.append(
    el("span", { class: "deploy-icon" }, "📦"),
    el("span", { class: "deploy-time" }, fmtDeployTime(d.deployed_at)),
    el("span", { class: "deploy-sha" }, sha),
  );
  if (block) row.append(el("span", { class: "deploy-block-badge" }, block));
  row.append(el("span", { class: "deploy-msg" }, msg));
  return row;
}

function renderDeployGroup(group) {
  const isExpanded = state.expandedDeployGroups.has(group.id);
  const groupEl = el("div", { class: `deploy-task-group${isExpanded ? " expanded" : ""}` });
  // Mirror Tasks tab row exactly (tree-item[data-type=task]) — icon + #NNN title (N) + status
  const numberPrefix = group.number != null ? `#${group.number}` : (group.id === "__unlinked__" ? "" : "#-");
  const nameText = group.id === "__unlinked__"
    ? `${group.title} (${group.count})`
    : `${numberPrefix} ${group.title || group.id} (${group.count})`;
  const header = el("div", {
    class: "tree-item deploy-task-header",
    "data-type": group.id === "__unlinked__" ? "deploy-unlinked" : "task",
    on: { click: () => {
      // Local DOM toggle only — no re-fetch, no full tree rebuild.
      // state Set kept in sync so full re-render (project switch etc)
      // rehydrates the same expansion state.
      if (state.expandedDeployGroups.has(group.id)) {
        state.expandedDeployGroups.delete(group.id);
        groupEl.classList.remove("expanded");
      } else {
        state.expandedDeployGroups.add(group.id);
        groupEl.classList.add("expanded");
      }
    }},
  },
    el("span", { class: "icon" }, ""),
    el("span", { class: "name" }, nameText),
    el("span", { class: "meta" }, group.status || ""),
  );
  const list = el("div", { class: "deploy-list" });
  group.deploys.forEach(d => list.append(renderDeployRow(d)));
  groupEl.append(header, list);
  return groupEl;
}

async function renderDeploys() {
  const t = $("#tree");
  t.replaceChildren(el("div", { class: "muted", style: "padding:12px" }, "Loading deploys…"));
  try {
    const data = await api(`/api/projects/${state.project.id}/deploys`);
    t.replaceChildren();
    if (!data.tasks.length && !data.unlinked.length) {
      t.append(el("div", { class: "muted center", style: "padding:24px" }, "No deploys yet."));
      return;
    }
    const tree = el("div", { class: "deploys-tree" });
    data.tasks.forEach(g => tree.append(renderDeployGroup(g)));
    if (data.unlinked.length) {
      tree.append(el("div", { class: "deploy-unlinked-separator" }));
      const unlinkedGroup = {
        id: "__unlinked__",
        title: i18n.t("task.no_task"),
        count: data.unlinked.length,
        deploys: data.unlinked,
      };
      tree.append(renderDeployGroup(unlinkedGroup));
    }
    t.append(tree);
  } catch (e) {
    console.warn(e);
    t.replaceChildren(el("div", { class: "muted", style: "padding:12px" }, `Error: ${e.message}`));
  }
}

async function onDeployClick(deploy) {
  const sha8 = (deploy.commit_sha || "").slice(0, 8);
  const heading = `${sha8} · ${deploy.deployed_at}`;
  setContent(`<div class="muted center">Loading deploy…</div>`);
  // If linked to task+block, try loading latest user-note-{block}.{R}.md
  if (deploy.task_id && deploy.block_num !== null && deploy.block_num !== undefined) {
    try {
      const artifacts = await api(`/api/tasks/${deploy.task_id}/artifacts`);
      const candidates = artifacts.filter(a =>
        a.artifact_type === "user-note" && String(a.block_num_raw) === String(deploy.block_num)
      );
      candidates.sort((a, b) => (b.round_num || 0) - (a.round_num || 0));
      if (candidates.length && candidates[0].file_path) {
        const data = await api(`/api/artifacts/read?path=${encodeURIComponent(candidates[0].file_path)}`);
        setContent(renderContent(data.content, candidates[0].file_name || "user-note.md"));
        return;
      }
    } catch (e) { /* fall through to fallback */ }
  }
  // Fallback: simple commit_msg header
  const fallback = [
    `# Deploy ${sha8}`,
    "",
    `**Project:** ${deploy.project}`,
    `**Deployed at:** ${deploy.deployed_at}`,
    `**Status:** ${deploy.status}`,
    deploy.task_title ? `**Task:** ${deploy.task_title}` : "",
    deploy.block_num !== null && deploy.block_num !== undefined ? `**Block:** ${deploy.block_num}` : "",
    "",
    "## Commit message",
    "",
    deploy.commit_msg || "(no message)",
  ].filter(Boolean).join("\n");
  setContent(renderContent(fallback, "deploy.md"));
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}K`;
  return `${(bytes / 1024 / 1024).toFixed(1)}M`;
}

function fmtNum(n) { return (n ?? 0).toLocaleString("ru-RU"); }

// ── Date formatting (block 408) ──────────────────────────

function formatDateRu(iso) {
  if (!iso) return "—";
  const s = String(iso).slice(0, 10); // "yyyy-mm-dd"
  const parts = s.split("-");
  if (parts.length !== 3) return "—";
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
}

// ── Stats view ────────────────────────────────────────────

function renderTopNumbers(nums, order) {
  const grid = el("div", { class: "stats-numbers" });
  for (const [key, label] of order) {
    const value = nums[key];
    if (value === undefined) continue;
    grid.append(el("div", { class: "stats-number" },
      el("div", { class: "stats-number-big" }, fmtNum(value)),
      el("div", { class: "stats-number-label" }, label),
    ));
  }
  return grid;
}

function renderBars(bars, opts = {}) {
  if (!bars || !bars.length) return el("div", { class: "muted" }, i18n.t("empty.no_data"));
  const max = Math.max(...bars.map(b => b.value));
  const wrap = el("div", { class: "stats-bars" });
  const rows = opts.limit ? bars.slice(0, opts.limit) : bars;
  for (const b of rows) {
    const pct = max > 0 ? Math.max(4, Math.round((b.value / max) * 100)) : 0;
    wrap.append(el("div", { class: "stats-bar" },
      el("div", { class: "stats-bar-label", title: b.label }, b.label),
      el("div", { class: "stats-bar-track" },
        el("div", { class: "stats-bar-fill", style: `width: ${pct}%` }),
      ),
      el("div", { class: "stats-bar-value" }, fmtNum(b.value)),
    ));
  }
  return wrap;
}

function renderHeatmap(cells) {
  const map = new Map(cells.map(c => [c.date, c.count]));
  const grid = el("div", { class: "heatmap" });
  const today = new Date();
  // last 52 weeks + current — 371 days back from Sunday
  const dayCount = 371;
  for (let i = dayCount - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    const c = map.get(iso) || 0;
    let tier = 0;
    if (c > 0) tier = 1;
    if (c >= 3) tier = 2;
    if (c >= 6) tier = 3;
    if (c >= 12) tier = 4;
    grid.append(el("div", {
      class: `heatmap-cell tier-${tier}`,
      title: `${iso} — ${c} events`,
    }));
  }
  return grid;
}

function renderRecent(tasks) {
  const list = el("div", { class: "stats-recent" });
  if (!tasks || !tasks.length) {
    list.append(el("div", { class: "muted" }, i18n.t("empty.no_tasks")));
    return list;
  }
  for (const t of tasks) {
    const row = el("div", {
      class: "stats-recent-row",
      on: { click: () => setHash({ project: t.project, kind: "tasks", target: t.id }) },
    },
      el("div", { class: "stats-recent-num" }, `#${t.number ?? "-"}`),
      el("div", { class: "stats-recent-title" }, t.title || t.id),
      el("div", { class: "stats-recent-meta" }, `${t.project || ""} · ${t.status || ""}`),
    );
    list.append(row);
  }
  return list;
}

function renderBlocksTimeline(blocks) {
  const wrap = el("div", { class: "stats-timeline" });
  for (const b of blocks) {
    const dot = el("span", { class: `timeline-dot status-${b.status}` }, "");
    wrap.append(el("div", { class: `stats-timeline-row status-${b.status}` },
      dot,
      el("div", { class: "stats-recent-num" }, `#${b.block_num ?? "-"}`),
      el("div", { class: "stats-recent-title" }, b.title || "-"),
      el("div", { class: "stats-recent-meta" },
        b.commit_hash ? `${b.status} · ${b.commit_hash.slice(0, 7)}` : b.status,
      ),
    ));
  }
  return wrap;
}

function renderStats(data) {
  const v = el("div", { class: "stats-view" });

  if (data.scope === "global") {
    v.append(el("h2", { class: "stats-h" }, i18n.t("stats.global_title")));
    v.append(renderTopNumbers(data.top_numbers, [
      ["tasks_total", i18n.t("stats.tasks_total")],
      ["tasks_open", i18n.t("stats.tasks_open")],
      ["tasks_closed", i18n.t("stats.tasks_closed")],
      ["streak_days", "🔥 streak"],
      ["artifacts_total", i18n.t("stats.artifacts_total")],
      ["week_calendar", i18n.t("stats.week_calendar")],
      ["week_views", i18n.t("stats.week_views")],
      ["today_count", i18n.t("stats.today_count")],
    ]));
    if (data.deploys && Object.keys(data.deploys).length) {
      v.append(renderTopNumbers(data.deploys, [
        ["deploys_total", i18n.t("deploys.total")],
        ["deploys_week_calendar", i18n.t("deploys.week_calendar")],
        ["deploys_week_views", i18n.t("deploys.week_views")],
        ["deploys_today", i18n.t("deploys.today")],
      ]));
    }
    v.append(el("h3", { class: "stats-h3" }, i18n.t("stats.year_activity")));
    v.append(renderHeatmap(data.heatmap));
    const grid = el("div", { class: "stats-grid" });
    grid.append(el("div", { class: "stats-panel" },
      el("h3", { class: "stats-h3" }, i18n.t("stats.top_projects")),
      renderBars(data.top_projects)));
    grid.append(el("div", { class: "stats-panel" },
      el("h3", { class: "stats-h3" }, i18n.t("stats.task_types")),
      renderBars(data.types_tasks)));
    grid.append(el("div", { class: "stats-panel" },
      el("h3", { class: "stats-h3" }, i18n.t("stats.artifact_types")),
      renderBars(data.types_artifacts, { limit: 10 })));
    grid.append(el("div", { class: "stats-panel" },
      el("h3", { class: "stats-h3" }, i18n.t("stats.frequently_opened")),
      renderBars(data.top_accessed, { limit: 10 })));
    v.append(grid);
    v.append(el("h3", { class: "stats-h3" }, i18n.t("stats.recent_tasks")));
    v.append(renderRecent(data.recent));

    // Skills analytics section (block 405) — only for global scope
    if (data.skills_stats) {
      const s = data.skills_stats;
      const skillsSection = el("div", { class: "skills-analytics-section" });
      skillsSection.append(el("h3", { class: "stats-h3" }, i18n.t("methodology.title")));

      // 4th top_numbers row — skills coverage
      skillsSection.append(renderTopNumbers({
        total_registered: s.total_registered,
        used_30d: s.used_30d,
        unused_90d: s.unused_90d,
        domain_count: (s.domain_coverage || []).length,
      }, [
        ["total_registered", i18n.t("methodology.total_registered")],
        ["used_30d", i18n.t("methodology.used_30d")],
        ["unused_90d", i18n.t("methodology.unused_90d")],
        ["domain_count", i18n.t("methodology.domain_count")],
      ]));

      // Two-column: top-10 bars + unused list
      const grid2 = el("div", { class: "skills-analytics-grid" });

      const topBars = (s.top_used_30d || []).map(t => ({
        label: t.display_name || t.name,
        value: t.count,
      }));
      grid2.append(el("div", { class: "stats-panel" },
        el("h3", { class: "stats-h3" }, i18n.t("methodology.top_30d")),
        renderBars(topBars, { limit: 10 })));

      // Unused skills — take from usage_map inference: catalog names NOT in top_used_30d, up to first 15
      const usedNames = new Set((s.top_used_30d || []).map(t => t.name));
      const domainList = s.domain_coverage || [];
      const unusedCount = s.unused_90d;
      const unusedPanel = el("div", { class: "stats-panel" });
      unusedPanel.append(el("h3", { class: "stats-h3" }, i18n.t("methodology.dormant_skills", { n: unusedCount })));
      unusedPanel.append(el("div", { class: "muted", style: "font-size:11px; padding: 0 4px 8px" },
        i18n.t("methodology.dormant_desc")));
      grid2.append(unusedPanel);

      skillsSection.append(grid2);

      // Domain coverage bars
      const coverageBars = domainList.map(d => ({
        label: `${d.domain} (${d.used}/${d.total})`,
        value: d.used,
      }));
      skillsSection.append(el("h3", { class: "stats-h3" }, i18n.t("methodology.domain_coverage")));
      skillsSection.append(renderBars(coverageBars, { limit: 15 }));

      v.append(skillsSection);
    }

    return v;
  }

  if (data.scope === "project") {
    v.append(el("h2", { class: "stats-h" }, i18n.t("title.project_stats_full", { id: data.project_id })));
    v.append(renderTopNumbers(data.top_numbers, [
      ["tasks_total", i18n.t("project.tasks_total")],
      ["tasks_open", i18n.t("project.tasks_open")],
      ["tasks_closed", i18n.t("project.tasks_closed")],
      ["artifacts_total", i18n.t("project.artifacts_total")],
    ]));
    if (data.deploys && Object.keys(data.deploys).length) {
      v.append(renderTopNumbers(data.deploys, [
        ["deploys_total", i18n.t("deploys.total")],
        ["deploys_week_calendar", i18n.t("deploys.week_calendar")],
        ["deploys_week_views", i18n.t("deploys.week_views")],
        ["deploys_today", i18n.t("deploys.today")],
      ]));
    }
    v.append(el("h3", { class: "stats-h3" }, i18n.t("stats.year_activity")));
    v.append(renderHeatmap(data.heatmap));
    const grid = el("div", { class: "stats-grid" });
    grid.append(el("div", { class: "stats-panel" },
      el("h3", { class: "stats-h3" }, i18n.t("stats.task_types")),
      renderBars(data.types_tasks)));
    grid.append(el("div", { class: "stats-panel" },
      el("h3", { class: "stats-h3" }, i18n.t("stats.artifact_types")),
      renderBars(data.types_artifacts, { limit: 10 })));
    v.append(grid);
    v.append(el("h3", { class: "stats-h3" }, i18n.t("stats.recent_project_tasks")));
    v.append(renderRecent(data.recent));
    return v;
  }

  // task scope
  v.append(el("h2", { class: "stats-h" }, `#${data.task.number ?? "-"} ${data.task.title || data.task.id}`));
  v.append(renderTopNumbers(data.top_numbers, [
    ["blocks_total", i18n.t("task_stats.blocks_total")],
    ["blocks_done", i18n.t("task_stats.blocks_done")],
    ["blocks_pending", i18n.t("task_stats.blocks_pending")],
    ["artifacts_total", i18n.t("task_stats.artifacts_total")],
    ["commits_total", i18n.t("task_stats.commits_total")],
  ]));
  v.append(el("h3", { class: "stats-h3" }, i18n.t("task_stats.blocks_timeline")));
  v.append(renderBlocksTimeline(data.blocks_timeline));
  v.append(el("h3", { class: "stats-h3" }, i18n.t("task_stats.artifact_types")));
  v.append(renderBars(data.artifacts_by_type));
  if (data.commits.length) {
    v.append(el("h3", { class: "stats-h3" }, i18n.t("task_stats.commits")));
    const commitsWrap = el("div", { class: "stats-commits" });
    for (const c of data.commits) commitsWrap.append(el("code", { class: "commit" }, c));
    v.append(commitsWrap);
  }
  return v;
}

async function loadStats(scope, id, taskId) {
  let url = "/api/stats/global";
  if (scope === "project") url = `/api/stats/project/${encodeURIComponent(id)}`;
  if (scope === "task") url = `/api/stats/task/${encodeURIComponent(taskId)}`;
  setContent(`<div class="muted center">${i18n.t("state.loading_stats")}</div>`);
  try {
    // Global scope also fetches skills analytics (block 405) — parallel for speed
    if (scope === "global") {
      const [data, skills] = await Promise.all([api(url), api("/api/stats/skills").catch(() => null)]);
      if (skills) data.skills_stats = skills;
      setContent(renderStats(data));
    } else {
      const data = await api(url);
      setContent(renderStats(data));
    }
  } catch (e) {
    setContent(`<div class="muted center">${i18n.t("state.error_loading", { msg: e.message })}</div>`);
  }
}

// ── Tab switching ─────────────────────────────────────────

function activateTab(name) {
  state.tab = name;
  state.taskId = null; // reset drill on tab switch
  state.filesPath = "";
  state.artifactFilter = "all";
  state.selectedSkill = null; // reset skill detail on tab switch
  if (state.project) {
    setHash({ project: state.project.id, kind: name, target: "" });
  }
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  render();
}

// ── Main render dispatcher ────────────────────────────────

async function render() {
  renderCrumbs();
  if (!state.project) {
    $("#tree").replaceChildren(el("div", { class: "muted", style: "padding:12px" }, "Select a project."));
    return;
  }
  if (state.tab === "files") return renderFiles();
  if (state.tab === "deploys") return renderDeploys();
  if (state.tab === "skills") return renderSkills();
  return renderTasks();
}

async function applyHash() {
  const parsed = parseHash();

  if (parsed.statsScope) {
    if (parsed.statsScope === "global") {
      await loadStats("global");
    } else if (parsed.statsScope === "project") {
      const found = state.projects.find(p => p.id === parsed.project);
      if (found) {
        state.project = found;
        $("#project-selector").value = parsed.project;
      }
      await loadStats("project", parsed.project);
    } else if (parsed.statsScope === "task") {
      const found = state.projects.find(p => p.id === parsed.project);
      if (found) {
        state.project = found;
        $("#project-selector").value = parsed.project;
      }
      await loadStats("task", null, parsed.taskId);
    }
    return;
  }

  const { project, kind, target } = parsed;
  if (project) {
    const found = state.projects.find(p => p.id === project);
    if (found) {
      state.project = found;
      state.tab = ["tasks", "deploys", "skills"].includes(kind) ? kind : "files";
      const nextTaskId = (kind === "tasks") ? (target || null) : null;
      if (nextTaskId !== state.taskId) state.artifactFilter = "all"; // reset filter on task change
      if (state.tab === "files") { state.filesPath = target; state.taskId = null; state.selectedSkill = null; }
      else if (state.tab === "deploys") { state.taskId = null; state.filesPath = ""; state.selectedSkill = null; }
      else if (state.tab === "skills") { state.selectedSkill = target || null; state.taskId = null; state.filesPath = ""; }
      else { state.taskId = nextTaskId; state.filesPath = ""; state.selectedSkill = null; }
      $("#project-selector").value = project;
      document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === state.tab));
    } else {
      setContent(`<div class="muted center">Project not found: ${project}. Pick another from the top selector.</div>`);
    }
  } else if (state.projects.length && !state.project) {
    state.project = state.projects[0];
    $("#project-selector").value = state.project.id;
    setHash({ project: state.project.id, kind: "files" });
    return; // hashchange re-fires
  }
  await render();
}

async function init() {
  // Load i18n dictionary before any render
  await i18n.load(i18n.detect());

  // Locale switcher wiring (buttons in header)
  document.querySelectorAll(".locale-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.locale === i18n.locale);
    b.addEventListener("click", () => i18n.set(b.dataset.locale));
  });

  try {
    state.projects = await api("/api/projects");
  } catch (e) {
    $("#tree").replaceChildren(el("div", { class: "muted", style: "padding:12px" }, `Error loading projects: ${e.message}`));
    return;
  }
  const sel = $("#project-selector");
  sel.replaceChildren();
  for (const p of state.projects) {
    sel.append(el("option", { value: p.id }, `${p.name} (${p.id})`));
  }
  sel.addEventListener("change", () => {
    setHash({ project: sel.value, kind: state.tab });
  });
  document.querySelectorAll(".tab").forEach(b => {
    b.addEventListener("click", () => {
      setHash({ project: state.project?.id, kind: b.dataset.tab });
    });
  });
  window.addEventListener("hashchange", applyHash);

  // Badge click → global stats
  const badge = document.querySelector(".stats-badge");
  if (badge) {
    badge.style.cursor = "pointer";
    badge.title = i18n.t("badge.tooltip");
    badge.addEventListener("click", () => { location.hash = "#/stats"; });
  }

  await applyHash();
}

// ── Skills tab (block 404) ───────────────────────────────

async function loadSkillsCatalog() {
  if (state.skillsCache) return state.skillsCache;
  const data = await api("/api/skills");
  state.skillsCache = data.items || [];
  return state.skillsCache;
}

function skillDomain(item) {
  return item.category_slug || "uncategorized";
}

function renderSkillChips(catalog) {
  const domains = ["all", ...Array.from(new Set(catalog.map(skillDomain))).sort()];
  const usage = [["all", i18n.t("filter.usage_all")], ["used30d", i18n.t("filter.usage_used30d")], ["unused90d", i18n.t("filter.usage_unused90d")]];

  const domainRow = el("div", { class: "filter-chips" });
  domains.forEach(d => {
    const label = d === "all" ? i18n.t("filter.all_domains") : d;
    domainRow.append(el("button", {
      class: `chip${state.skillFilter.domain === d ? " active" : ""}`,
      on: { click: () => { state.skillFilter.domain = d; renderSkills(); } },
    }, label));
  });
  const usageRow = el("div", { class: "filter-chips" });
  usage.forEach(([key, label]) => {
    usageRow.append(el("button", {
      class: `chip${state.skillFilter.usage === key ? " active" : ""}`,
      on: { click: () => { state.skillFilter.usage = key; renderSkills(); } },
    }, label));
  });
  const wrap = el("div", { class: "skill-chips-wrap" });
  wrap.append(domainRow, usageRow);
  return wrap;
}

function filterSkills(catalog) {
  return catalog.filter(item => {
    if (state.skillFilter.domain !== "all" && skillDomain(item) !== state.skillFilter.domain) return false;
    if (state.skillFilter.usage === "used30d" && !(item.usage_30d > 0)) return false;
    if (state.skillFilter.usage === "unused90d") {
      const last = item.last_used_at;
      const total = item.usage_total || 0;
      if (total === 0) return true;
      // rough client-side check — accept never-used or 30d=0 as unused
      if (item.usage_30d > 0) return false;
    }
    return true;
  });
}

async function renderSkills() {
  const t = $("#tree");
  t.replaceChildren(el("div", { class: "muted", style: "padding:12px" }, "Loading skills…"));
  try {
    const catalog = await loadSkillsCatalog();
    const filtered = filterSkills(catalog);
    t.replaceChildren();
    t.append(renderSkillChips(catalog));

    // Group by domain
    const groups = {};
    filtered.forEach(item => {
      const d = skillDomain(item);
      (groups[d] = groups[d] || []).push(item);
    });
    const domainOrder = Object.keys(groups).sort();

    if (!domainOrder.length) {
      t.append(el("div", { class: "muted", style: "padding:12px" }, i18n.t("empty.no_skills")));
    }

    for (const domain of domainOrder) {
      t.append(el("div", { class: "tree-item", "data-type": "domain-header" }, `${domain} (${groups[domain].length})`));
      for (const item of groups[domain]) {
        const usage = item.usage_total || 0;
        const row = el("div", {
          class: `tree-item subitem${state.selectedSkill === item.name ? " active" : ""}`,
          "data-type": "skill",
          on: { click: () => {
            state.selectedSkill = item.name;
            setHash({ project: state.project.id, kind: "skills", target: item.name });
          }},
        },
          el("span", { class: "icon" }, ""),
          el("span", { class: "name" }, item.display_name || item.name),
          el("span", { class: "meta" }, `${usage} ×`),
        );
        t.append(row);
      }
    }

    if (state.selectedSkill) {
      renderSkillDetail(state.selectedSkill);
    } else {
      setContent(el("div", { class: "muted center" }, i18n.t("empty.select_skill")));
    }
  } catch (e) {
    console.warn(e);
    t.replaceChildren(el("div", { class: "muted", style: "padding:12px" }, i18n.t("state.error", { msg: e.message })));
  }
}

function worksWithPill(item) {
  const isString = typeof item === "string";
  const id = isString ? item : (item.id || item.name || "?");
  const why = isString ? "" : (item.why || "");
  return el("button", {
    class: "skill-pill",
    title: why,
    on: { click: () => {
      state.selectedSkill = id;
      setHash({ project: state.project.id, kind: "skills", target: id });
    }},
  }, id);
}

async function renderSkillDetail(name) {
  setContent(el("div", { class: "muted center" }, "Loading…"));
  logAccess(state.project.id, "skill", name);
  try {
    const [skill, examples] = await Promise.all([
      api(`/api/skills/${encodeURIComponent(name)}`),
      api(`/api/skills/${encodeURIComponent(name)}/examples`).catch(() => ({ items: [] })),
    ]);
    const box = el("div", { class: "skill-detail" });

    // Header
    const header = el("div", { class: "skill-detail-header" });
    header.append(el("div", { class: "skill-detail-title" }, skill.display_name || skill.name));
    const pillsRow = el("div", { class: "skill-detail-pills" });
    pillsRow.append(el("span", { class: "skill-pill" }, `v${skill.version || "1.0.0"}`));
    if (skill.pack_slug) pillsRow.append(el("span", { class: "skill-pill" }, skill.pack_slug));
    if (skill.category_slug) pillsRow.append(el("span", { class: "skill-pill" }, skill.category_slug));
    header.append(pillsRow);
    box.append(header);

    if (skill.pitch) {
      box.append(el("div", { class: "skill-detail-pitch" }, skill.pitch));
    }

    // Usage box
    const usageBox = el("div", { class: "skill-usage-box" });
    const cells = [
      [i18n.t("skill.total"), skill.usage_total ?? 0],
      [i18n.t("skill.30days"), skill.usage_30d ?? 0],
      [i18n.t("skill.7days"), skill.usage_7d ?? 0],
      [i18n.t("skill.last_used"), formatDateRu(skill.last_used_at)],
    ];
    cells.forEach(([label, value]) => {
      usageBox.append(el("div", { class: "skill-usage-cell" },
        el("div", { class: "skill-usage-value" }, String(value)),
        el("div", { class: "skill-usage-label" }, label),
      ));
    });
    box.append(usageBox);

    // Description MD
    if (skill.description_ru) {
      const descBox = el("div", { class: "md-content skill-detail-desc-md" });
      descBox.innerHTML = window.marked ? marked.parse(skill.description_ru) : skill.description_ru;
      if (window.hljs) descBox.querySelectorAll("pre code").forEach(b => hljs.highlightElement(b));
      box.append(descBox);
    }

    // Works with
    if (skill.works_with && skill.works_with.length) {
      const wwHeader = el("div", { class: "skill-section-header" }, i18n.t("skill.works_together"));
      const wwBox = el("div", { class: "skill-works-with" });
      skill.works_with.forEach(item => wwBox.append(worksWithPill(item)));
      box.append(wwHeader, wwBox);
    }

    // Examples
    if (examples.items && examples.items.length) {
      box.append(el("div", { class: "skill-section-header" }, i18n.t("skill.recent_uses")));
      const list = el("div", { class: "skill-examples-list" });
      examples.items.forEach(ex => {
        const item = el("div", {
          class: "skill-example-row",
          on: { click: async () => {
            try {
              const data = await api(`/api/artifacts/read?path=${encodeURIComponent(ex.file_path)}`);
              setContent(renderContent(data.content, ex.file_name));
            } catch (e) {
              setContent(`<div class="muted center">${i18n.t("state.error", { msg: e.message })}</div>`);
            }
          }},
        },
          el("div", { class: "skill-example-name" }, ex.file_name || "?"),
          el("div", { class: "skill-example-meta" }, `${ex.task_title || ex.task_id || ""} · ${formatDateRu(ex.created_at)}`),
        );
        list.append(item);
      });
      box.append(list);
    }

    setContent(box);
  } catch (e) {
    setContent(`<div class="muted center">${i18n.t("state.error", { msg: e.message })}</div>`);
  }
}

init();
