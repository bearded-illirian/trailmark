/*
 * task-engine.js — reusable task-management widget
 * v1.2.0 · vschk-lab kit
 *
 * v1.2 features:
 *   - Unified task-detail slider (mode=create/edit) — replaces separate comments slider
 *   - config.filter.meetingId — frontend-side filter (from consumer sidebar navigation)
 *   - config.showAddButton — «+ Задача» button top-right → open create slider
 *   - config.availableAssignees — enum для assigned_to dropdown
 *   - Overdue deadline highlight (deadline < today → red text)
 *   - Click on task text → open edit slider
 *   - Click on 💬 icon → open edit slider + auto-scroll to comments section
 *
 * Public API: TaskEngine.mount(container, config)
 */

(function () {
  "use strict";

  const DEFAULT_COLUMNS = [
    { key: "text",           label: "Задача",     type: "text",  bold: true },
    { key: "assigned_to",    label: "Ответственный", type: "text" },
    { key: "status",         label: "Статус",     type: "badge" },
    { key: "deadline",       label: "Дедлайн",    type: "date" },
    { key: "comments_count", label: "💬",         type: "comments" }
  ];

  const DEFAULT_STATUSES = {
    "todo":  { label: "Открыта",  color: "var(--text-muted)" },
    "doing": { label: "В работе", color: "var(--link)" },
    "done":  { label: "Готово",   color: "var(--success)" }
  };

  function esc(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function apiFetch(base, path, opts) {
    opts = opts || {};
    const url = base.replace(/\/$/, "") + path;
    const init = { method: opts.method || "GET", headers: { "Content-Type": "application/json" } };
    if (opts.body !== undefined) init.body = JSON.stringify(opts.body);
    return fetch(url, init).then(function (r) {
      if (!r.ok) return r.json().catch(function () { return { detail: r.statusText }; })
        .then(function (err) { throw new Error(err.detail || "HTTP " + r.status); });
      return r.json();
    });
  }

  function isOverdue(deadline) {
    if (!deadline) return false;
    const today = new Date().toISOString().slice(0, 10);
    return deadline < today;
  }

  function renderStatusBadge(value, statuses) {
    const cfg = statuses[value] || { label: value, color: "var(--text-muted)" };
    return '<span class="te-badge" style="background:' + cfg.color + '22;color:' + cfg.color + ';border-color:' + cfg.color + '55">' + esc(cfg.label) + '</span>';
  }

  function defaultRenderCell(col, value, task, statuses) {
    if (col.type === "badge" && col.key === "status") return renderStatusBadge(value, statuses);
    if (col.type === "date") {
      if (!value) return '<span class="te-empty">—</span>';
      const cls = isOverdue(value) && task.status !== "done" ? "te-overdue" : "";
      return '<span class="' + cls + '">' + esc(value) + '</span>';
    }
    if (col.type === "comments") {
      const n = value || 0;
      return '<span class="te-comments-icon" title="Комментарии">💬 ' + n + '</span>';
    }
    const html = esc(value || "—");
    return col.bold ? "<strong>" + html + "</strong>" : html;
  }

  function mount(container, cfg) {
    if (!container) throw new Error("TaskEngine.mount: container required");
    if (!cfg || !cfg.apiBase) throw new Error("TaskEngine.mount: config.apiBase required");

    const columns  = cfg.columns  || DEFAULT_COLUMNS;
    const statuses = cfg.statuses || DEFAULT_STATUSES;
    const mode     = cfg.mode     || "embedded";
    const hooks    = cfg.hooks    || {};
    const groupBy  = (cfg.sections && cfg.sections.groupBy) || "flat";
    const showFilters = cfg.showFilters !== false;
    const filterMeetingId = (cfg.filter && cfg.filter.meetingId) || null;
    const showAddButton = cfg.showAddButton === true;
    // Пустой список, а не имена первого клиента: подставлять чужого человека в
    // чужой кабинет хуже, чем показать пустой выпадающий (задача 706, блок 234).
    let availableAssignees = cfg.availableAssignees || [];

    let tasks = [];
    let sources = [];
    let meetings = [];
    let activeStatus = "all";

    function filteredTasks() {
      let f = tasks;
      if (filterMeetingId != null) {
        f = f.filter(function (t) {
          if (filterMeetingId === "__none") return t.meeting_id == null;
          return t.meeting_id === filterMeetingId;
        });
      }
      if (activeStatus !== "all") f = f.filter(function (t) { return t.status === activeStatus; });
      return f;
    }

    function render() {
      let html = '<div class="te-root te-mode-' + mode + '">';
      if (mode === "standalone" && cfg.title) html += '<h1 class="te-title">' + esc(cfg.title) + '</h1>';
      // Unified toolbar: filter chips (wrap) + add-button anchored right
      if (showFilters || showAddButton) {
        html += '<div class="te-toolbar">';
        if (showFilters) {
          const scoped = filterMeetingId != null ? tasks.filter(function (t) {
            if (filterMeetingId === "__none") return t.meeting_id == null;
            return t.meeting_id === filterMeetingId;
          }) : tasks;
          const counts = { all: scoped.length };
          Object.keys(statuses).forEach(function (s) { counts[s] = 0; });
          scoped.forEach(function (t) { if (counts[t.status] !== undefined) counts[t.status]++; });
          html += '<div class="te-toolbar-filters">';
          html += '<button class="te-chip' + (activeStatus === "all" ? " active" : "") + '" data-filter="all">Все <span class="te-chip-count">' + counts.all + '</span></button>';
          Object.keys(statuses).forEach(function (s) {
            const active = activeStatus === s ? " active" : "";
            html += '<button class="te-chip' + active + '" data-filter="' + s + '">' + esc(statuses[s].label) + ' <span class="te-chip-count">' + (counts[s] || 0) + '</span></button>';
          });
          html += '</div>';
        } else {
          html += '<div class="te-toolbar-filters"></div>';
        }
        if (showAddButton) {
          html += '<div class="te-toolbar-actions"><button class="te-btn te-btn-primary" data-action="open-create">+ Задача</button></div>';
        }
        html += '</div>';
      }
      const list = filteredTasks();
      if (list.length === 0) {
        html += '<div class="te-empty-row">Задач нет</div>';
      } else if (groupBy === "meeting" && filterMeetingId == null) {
        html += renderGroupedByMeeting(list);
      } else {
        html += renderTable(list);
      }
      html += '</div>';
      container.innerHTML = html;
      attachHandlers();
    }

    function renderGroupedByMeeting(taskList) {
      const map = {};
      meetings.forEach(function (m) { map[m.id] = m; });
      const groups = {};
      taskList.forEach(function (t) {
        const key = t.meeting_id != null ? String(t.meeting_id) : "__none";
        (groups[key] = groups[key] || []).push(t);
      });
      // v1.2.3: __none (Без встречи) always pinned на top, meetings ниже по date DESC
      const meetingKeys = Object.keys(groups)
        .filter(function (k) { return k !== "__none"; })
        .sort(function (a, b) {
          const ma = map[a]; const mb = map[b];
          return (mb && mb.date ? mb.date : "").localeCompare(ma && ma.date ? ma.date : "");
        });
      const orderedKeys = [];
      if (groups["__none"]) orderedKeys.push("__none");
      orderedKeys.push.apply(orderedKeys, meetingKeys);
      let out = "";
      orderedKeys.forEach(function (key) {
        const gt = groups[key];
        const done = gt.filter(function (t) { return t.status === "done"; }).length;
        let title, sub = "";
        if (key === "__none") title = "Без встречи";
        else {
          const m = map[key];
          title = m ? m.title : "Встреча #" + key;
          if (m && m.date) sub = ' · ' + m.date;
        }
        // v1.2.3: smart default expand — если все задачи done → collapsed по default
        const allDone = gt.length > 0 && done === gt.length;
        const collapsedClass = allDone ? " te-section-collapsed" : "";
        const chevronChar = allDone ? "▸" : "▾";
        out += '<div class="te-section' + collapsedClass + '" data-section-key="' + esc(key) + '">';
        out += '<div class="te-section-header" data-action="toggle-section"><span class="te-chevron">' + chevronChar + '</span>' + esc(title) + '<span class="te-section-meta">' + sub + ' · ' + gt.length + ' задач' + (done > 0 ? ', ' + done + ' готово' : '') + '</span></div>';
        out += renderTable(gt);
        out += '</div>';
      });
      return out;
    }

    function renderTable(taskList) {
      let out = '<div class="te-table-wrap"><table class="te-table"><tbody>';
      taskList.forEach(function (task) {
        const sc = statuses[task.status] || { color: "var(--text-muted)" };
        out += '<tr class="te-row" data-task-id="' + task.id + '" style="border-left-color:' + sc.color + '">';
        columns.forEach(function (col) {
          let cell = null;
          if (hooks.renderCell) cell = hooks.renderCell(col.key, task[col.key], task);
          if (cell == null) cell = defaultRenderCell(col, task[col.key], task, statuses);
          const editable = task.writable && col.key === "status";
          const clickComm = col.key === "comments_count";
          const clickText = col.key === "text" && task.writable;
          const attrs = (editable ? ' data-editable="status"' : "") + (clickComm ? ' data-action="open-detail-comments"' : "") + (clickText ? ' data-action="open-detail-edit"' : "");
          out += '<td class="te-cell te-cell-' + col.key + '"' + attrs + '>' + cell + '</td>';
        });
        out += '</tr>';
      });
      out += '</tbody></table></div>';
      return out;
    }

    function attachHandlers() {
      container.querySelectorAll("[data-filter]").forEach(function (btn) {
        btn.addEventListener("click", function () { activeStatus = btn.dataset.filter; render(); });
      });
      container.querySelectorAll("[data-editable=\"status\"]").forEach(function (cell) {
        cell.addEventListener("click", function (e) { openStatusDropdown(cell, e); });
      });
      container.querySelectorAll("[data-action=\"open-detail-comments\"]").forEach(function (cell) {
        cell.addEventListener("click", function (e) {
          e.stopPropagation();
          const row = cell.closest(".te-row");
          const taskId = parseInt(row.dataset.taskId, 10);
          openDetailSlider("edit", taskId, { scrollToComments: true });
        });
      });
      container.querySelectorAll("[data-action=\"open-detail-edit\"]").forEach(function (cell) {
        cell.addEventListener("click", function (e) {
          e.stopPropagation();
          const row = cell.closest(".te-row");
          const taskId = parseInt(row.dataset.taskId, 10);
          openDetailSlider("edit", taskId);
        });
      });
      container.querySelectorAll("[data-action=\"open-create\"]").forEach(function (btn) {
        btn.addEventListener("click", function () { openDetailSlider("create"); });
      });
      // Accordion: toggle collapse/expand на section-header click
      container.querySelectorAll("[data-action=\"toggle-section\"]").forEach(function (hdr) {
        hdr.addEventListener("click", function () {
          const section = hdr.closest(".te-section");
          if (!section) return;
          section.classList.toggle("te-section-collapsed");
          const chevron = hdr.querySelector(".te-chevron");
          if (chevron) chevron.textContent = section.classList.contains("te-section-collapsed") ? "▸" : "▾";
        });
      });
    }

    function openStatusDropdown(cell, event) {
      event.stopPropagation();
      const row = cell.closest(".te-row");
      const taskId = parseInt(row.dataset.taskId, 10);
      const dd = document.createElement("div");
      dd.className = "te-dropdown";
      Object.keys(statuses).forEach(function (code) {
        const opt = document.createElement("div");
        opt.className = "te-dropdown-opt";
        opt.textContent = statuses[code].label;
        opt.addEventListener("click", function () {
          apiFetch(cfg.apiBase, "/task/" + taskId, { method: "PATCH", body: { status: code } })
            .then(function (r) {
              const idx = tasks.findIndex(function (t) { return t.id === taskId; });
              if (idx !== -1) tasks[idx] = r.task;
              render();
              if (hooks.onSave) hooks.onSave(r.task);
            })
            .catch(function (e) { alert("Ошибка: " + e.message); });
          dd.remove();
        });
        dd.appendChild(opt);
      });
      const rect = cell.getBoundingClientRect();
      dd.style.top = (rect.bottom + window.scrollY) + "px";
      dd.style.left = (rect.left + window.scrollX) + "px";
      document.body.appendChild(dd);
      const closer = function (e) { if (!dd.contains(e.target)) { dd.remove(); document.removeEventListener("click", closer); } };
      setTimeout(function () { document.addEventListener("click", closer); }, 0);
    }

    function openDetailSlider(sliderMode, taskId, opts) {
      opts = opts || {};
      document.querySelectorAll(".te-slider").forEach(function (s) { s.remove(); });
      const isEdit = sliderMode === "edit";
      const task = isEdit ? tasks.find(function (t) { return t.id === taskId; }) : {
        text: "", status: "todo", deadline: "", assigned_to: (availableAssignees[0] || ""),
        meeting_id: filterMeetingId && filterMeetingId !== "__none" ? filterMeetingId : null,
      };
      if (isEdit && !task) return;

      // Build meeting options
      const meetingOpts = ['<option value="">— Без встречи —</option>'].concat(
        meetings.map(function (m) {
          const sel = task.meeting_id === m.id ? " selected" : "";
          return '<option value="' + m.id + '"' + sel + '>' + esc(m.title) + (m.date ? ' · ' + m.date : '') + '</option>';
        })
      ).join("");
      const assigneeOpts = ['<option value="">— не назначен —</option>'].concat(
        availableAssignees.map(function (a) {
        return '<option value="' + esc(a) + '"' + (task.assigned_to === a ? " selected" : "") + '>' + esc(a) + '</option>';
        })
      ).join("");
      const statusOpts = Object.keys(statuses).map(function (s) {
        return '<option value="' + s + '"' + (task.status === s ? " selected" : "") + '>' + esc(statuses[s].label) + '</option>';
      }).join("");

      const slider = document.createElement("div");
      slider.className = "te-slider";
      slider.innerHTML =
        // Крестик слева, номер задачи справа — решение decision-18.
        '<div class="te-slider-header">' +
          '<button class="te-slider-close" data-slider="close">✕</button>' +
          '<div class="te-slider-num">' + (isEdit ? "#" + task.id : "новая") + '</div>' +
        '</div>' +
        '<div class="te-slider-cols">' +

        // ── Слева читают: название и описание, больше ничего ──
        '<div class="te-slider-main">' +
          '<h2 class="te-slider-name">' + esc(task.text || "Новая задача") + '</h2>' +
          '<div class="te-descr" data-descr-host></div>' +
        '</div>' +

        // ── Справа управляют: мета сверху, лента под ней ──
        '<aside class="te-slider-side">' +
          '<div class="te-slider-fields">' +
            '<div class="te-field-row"><label>Название:</label></div>' +
            '<textarea class="te-slider-text" placeholder="Текст задачи">' + esc(task.text || "") + '</textarea>' +
            '<div class="te-field-row"><label>Ответственный:</label><select class="te-slider-assigned">' + assigneeOpts + '</select></div>' +
            '<div class="te-field-row"><label>Встреча:</label><select class="te-slider-meeting">' + meetingOpts + '</select></div>' +
            '<div class="te-field-row"><label>Дедлайн:</label><input type="text" data-datepicker data-format="iso" placeholder="ГГГГ-ММ-ДД" class="te-slider-deadline" value="' + esc(task.deadline || "") + '"></div>' +
            '<div class="te-field-row"><label>Статус:</label><select class="te-slider-status">' + statusOpts + '</select></div>' +
            (isEdit ? (
              '<div class="te-field-row"><label>Описание:</label>' +
                '<button type="button" class="te-btn te-btn-ghost" data-slider="descr-toggle">Править разметку</button>' +
              '</div>' +
              '<textarea class="te-slider-descr" hidden placeholder="HTML-описание задачи">' + esc(task.description || "") + '</textarea>'
            ) : '') +
            '<div class="te-slider-actions">' +
              '<button class="te-btn te-btn-primary" data-slider="save">' + (isEdit ? "Сохранить" : "Создать") + '</button>' +
              (isEdit ? '<button class="te-btn te-btn-danger" data-slider="delete">🗑 Удалить</button>' : "") +
            '</div>' +
          '</div>' +
          (isEdit ? (
            '<div class="te-slider-comments-header">Комментарии</div>' +
            '<div class="te-slider-body"><div class="te-muted">Загрузка…</div></div>' +
            '<div class="te-slider-form">' +
              '<textarea class="te-slider-input" placeholder="Написать комментарий…"></textarea>' +
              '<button class="te-btn te-btn-primary" data-slider="comment-submit">Отправить</button>' +
            '</div>'
          ) : '') +
        '</aside>' +
        '</div>';
      document.body.appendChild(slider);

      // Описание рисуем ПОСЛЕ вставки: наблюдателю нужен узел, уже лежащий в
      // документе, иначе он не увидит, как фрейм оттуда исчезнет.
      const descrHost = slider.querySelector("[data-descr-host]");
      if (descrHost) {
        const html = (task.description || "").trim();
        if (html && typeof window.buildSandboxFrame === "function") {
          // Описание тоже может звать документ кабинета — портал даёт свой
          // обработчик через конфиг (задача 706, блок 226).
          descrHost.appendChild(window.buildSandboxFrame(
            html, slider, "te-descr-frame", cfg.onOpenDocument, openTaskById));
        } else if (html) {
          descrHost.innerHTML = '<div class="te-muted">Описание не показано: не подключён sandbox-frame.js</div>';
        } else if (isEdit) {
          // Пустая левая колонка выглядела бы поломкой. Приглашение делает из
          // пустого места вход в работу (decision-18, пункт 9).
          descrHost.innerHTML =
            '<div class="te-descr-empty">' +
              '<p class="te-muted">Описания пока нет</p>' +
              '<button type="button" class="te-btn te-btn-ghost" data-slider="descr-toggle">Добавить описание</button>' +
            '</div>';
        }
      }

      // Кнопок правки две — в мете и в приглашении, — а поле одно.
      slider.querySelectorAll('[data-slider="descr-toggle"]').forEach(function (btn) {
        btn.addEventListener("click", function () {
          const ta = slider.querySelector(".te-slider-descr");
          if (!ta) return;
          ta.hidden = false;
          ta.focus();
          const metaBtn = slider.querySelector('.te-slider-fields [data-slider="descr-toggle"]');
          if (metaBtn) metaBtn.textContent = "Скрыть разметку";
        });
      });

      // Снимок разметки на момент открытия: по нему решаем, есть ли что терять.
      const descrAtOpen = (task.description || "");
      function hasUnsavedDescr() {
        const ta = slider.querySelector(".te-slider-descr");
        return !!ta && !ta.hidden && ta.value !== descrAtOpen;
      }

      // Снять слушатели и убрать слой без вопросов. Нужен saveDetail и
      // deleteDetail: они лежат вне этой области, и правку там как раз сохраняют.
      slider._detach = function () {
        document.removeEventListener("keydown", onKey);
        document.removeEventListener("click", onOutside);
        slider.remove();
      };

      function closeSlider(force) {
        if (!force && hasUnsavedDescr()) return false;
        if (force && hasUnsavedDescr() &&
            !confirm("Разметка описания изменена и не сохранена. Закрыть и потерять правки?")) return false;
        slider._detach();
        return true;
      }

      const onKey = function (e) { if (e.key === "Escape") closeSlider(false); };
      // Задержка обязательна: без неё тот же клик, который открыл слайдер,
      // немедленно его закроет (приём из te-dropdown, task-engine.js:279).
      const onOutside = function (e) { if (!slider.contains(e.target)) closeSlider(false); };
      document.addEventListener("keydown", onKey);
      setTimeout(function () { document.addEventListener("click", onOutside); }, 0);

      slider.querySelector('[data-slider="close"]').addEventListener("click", function () { closeSlider(true); });
      slider.querySelector('[data-slider="save"]').addEventListener("click", function () { saveDetail(slider, isEdit, task); });
      if (isEdit) {
        const delBtn = slider.querySelector('[data-slider="delete"]');
        if (delBtn) delBtn.addEventListener("click", function () { deleteDetail(slider, task.id); });
        loadComments(slider, task.id);
        slider.querySelector('[data-slider="comment-submit"]').addEventListener("click", function () {
          submitComment(slider, task.id);
        });
        if (opts.scrollToComments) {
          setTimeout(function () {
            const body = slider.querySelector(".te-slider-body");
            if (body) body.scrollTop = body.scrollHeight;
          }, 150);
        }
      }
    }

    function saveDetail(slider, isEdit, task) {
      const text = slider.querySelector(".te-slider-text").value.trim();
      if (!text) { alert("Текст задачи обязателен"); return; }
      const assigned = slider.querySelector(".te-slider-assigned").value;
      const meetingVal = slider.querySelector(".te-slider-meeting").value;
      const deadline = slider.querySelector(".te-slider-deadline").value || null;
      const status = slider.querySelector(".te-slider-status").value;
      const meeting_id = meetingVal ? parseInt(meetingVal, 10) : null;
      const body = { text: text, status: status, deadline: deadline, assigned_to: assigned, meeting_id: meeting_id };
      // Поле есть только в режиме правки. Пустая строка — законное значение
      // «описания нет», поэтому шлём её, а не пропускаем.
      const descrField = slider.querySelector(".te-slider-descr");
      if (descrField) body.description = descrField.value;
      const req = isEdit
        ? apiFetch(cfg.apiBase, "/task/" + task.id, { method: "PATCH", body: body })
        : (function () { body.source_key = "personal"; return apiFetch(cfg.apiBase, "/task", { method: "POST", body: body }); })();
      req.then(function (r) {
        if (isEdit) {
          const idx = tasks.findIndex(function (t) { return t.id === task.id; });
          if (idx !== -1) tasks[idx] = r.task;
        } else {
          tasks.unshift(r.task);
        }
        (slider._detach || slider.remove.bind(slider))();
        render();
        if (isEdit && hooks.onSave) hooks.onSave(r.task);
        if (!isEdit && hooks.onCreate) hooks.onCreate(r.task);
      }).catch(function (e) { alert("Ошибка: " + e.message); });
    }

    function deleteDetail(slider, taskId) {
      if (!confirm("Удалить задачу безвозвратно?")) return;
      apiFetch(cfg.apiBase, "/task/" + taskId, { method: "DELETE" })
        .then(function () {
          tasks = tasks.filter(function (t) { return t.id !== taskId; });
          (slider._detach || slider.remove.bind(slider))();
          render();
          if (hooks.onDelete) hooks.onDelete(taskId);
        })
        .catch(function (e) { alert("Ошибка: " + e.message); });
    }

    // Реплику агента видно глазом: засечка слева и другое начертание имени.
    // Через месяц в ленте будет сорок записей, и без этого не отличить отчёт
    // цифрового сотрудника от слова человека (задача 706, decision-18 пункт 11).
    function renderComment(c) {
      const isAgent = c.author_kind === "agent";
      return '<div class="te-comment' + (isAgent ? " te-comment-agent" : "") + '">' +
        '<div class="te-comment-meta"><strong>' + esc(c.author) + '</strong>' +
        (isAgent ? '<span class="te-comment-badge">агент</span>' : '') +
        ' · ' + esc(c.created_at) + '</div>' +
        '<div class="te-comment-text">' + esc(c.text) + '</div></div>';
    }

    function loadComments(slider, taskId) {
      const body = slider.querySelector(".te-slider-body");
      apiFetch(cfg.apiBase, "/task/" + taskId + "/comments")
        .then(function (comments) {
          if (comments.length === 0) {
            body.innerHTML = '<div class="te-muted te-slider-empty">Комментариев пока нет</div>';
          } else {
            body.innerHTML = comments.map(renderComment).join("");
          }
        }).catch(function (e) { body.innerHTML = '<div class="te-error">Ошибка: ' + esc(e.message) + '</div>'; });
    }

    function submitComment(slider, taskId) {
      const input = slider.querySelector(".te-slider-input");
      const btn = slider.querySelector('[data-slider="comment-submit"]');
      const text = input.value.trim();
      if (!text) return;
      btn.disabled = true;
      apiFetch(cfg.apiBase, "/task/" + taskId + "/comment", { method: "POST", body: { text: text } })
        .then(function (r) {
          input.value = "";
          btn.disabled = false;
          const body = slider.querySelector(".te-slider-body");
          const empty = body.querySelector(".te-slider-empty");
          if (empty) body.innerHTML = "";
          body.insertAdjacentHTML("beforeend", renderComment(r.comment || r));
          body.scrollTop = body.scrollHeight;
          const t = tasks.find(function (x) { return x.id === taskId; });
          if (t) t.comments_count = (t.comments_count || 0) + 1;
          render();
          if (hooks.onCommentSubmit) hooks.onCommentSubmit(r.comment);
        })
        .catch(function (e) { btn.disabled = false; alert("Ошибка: " + e.message); });
    }

    function load() {
      return apiFetch(cfg.apiBase, "/tasks")
        .then(function (r) {
          tasks = r.tasks || []; sources = r.sources || []; meetings = r.meetings || [];
          // Участники приходят вместе с задачами: кит уже спрашивает этот адрес,
          // и отдельный запрос ради двух имён не нужен. Конфиг имеет приоритет —
          // он есть у consumer'ов, которые задают список сами.
          if (!cfg.availableAssignees && Array.isArray(r.participants)) {
            availableAssignees = r.participants;
          }
          render();
        })
        .catch(function (e) { container.innerHTML = '<div class="te-error">Ошибка загрузки: ' + esc(e.message) + '</div>'; });
    }

    /** Открыть задачу по номеру — для ссылок из документов кабинета.
     *
     *  Задача берётся из состояния кита, а не из базы: openDetailSlider уже так
     *  устроен. Нет такого номера — говорим об этом вслух, а не открываем пустой
     *  слайдер: молчаливый отказ читается как «кабинет сломался»
     *  (задача 706, блок 2371).
     */
    function openTaskById(taskId, isRetry) {
      // Ссылка из документа несёт либо номер задачи, либо стабильный ключ панели.
      // Номер свой в каждом кабинете, ключ один на всех — поэтому документ с ключом
      // работает в любом кабинете, а с номером только в своём (задача 721, блок 102).
      // Числовая ветка остаётся навсегда: пятнадцать существующих материалов
      // написаны номерами, и переписывать их незачем.
      const raw = String(taskId == null ? "" : taskId).trim();
      const id = /^\d+$/.test(raw) ? parseInt(raw, 10) : null;
      const task = id !== null
        ? tasks.find(function (t) { return t.id === id; })
        : tasks.find(function (t) { return t.panel_key && t.panel_key === raw; });
      if (!task) {
        // Кит монтируется при первом показе вкладки и грузит задачи запросом.
        // Ссылка из документа срабатывает раньше, чем приходит ответ, — список
        // ещё пуст, и задача «не найдена», хотя она есть. Одна попытка после
        // загрузки, и только потом отказ (задача 706, блок 2371).
        if (!isRetry) {
          load().then(function () { openTaskById(raw, true); });
          return;
        }
        alert("Задача " + (id !== null ? "#" + id : "«" + raw + "»") + " не найдена в этом кабинете.");
        return;
      }
      switchToTasksView();
      // Слайдер открывается по номеру найденной задачи, а не по тому, что пришло
      // в ссылке: при поиске по ключу номер известен только после находки.
      openDetailSlider("edit", task.id, {});
    }

    /** Кит может быть примонтирован на скрытой вкладке — показать её. */
    function switchToTasksView() {
      if (typeof cfg.onNeedTasksTab === "function") cfg.onNeedTasksTab();
    }

    // v1.4: openMeetingCreate — public method для consumer (например sidebar «+ Встреча» button)
    function openMeetingCreate() {
      document.querySelectorAll(".te-slider").forEach(function (s) { s.remove(); });
      const slider = document.createElement("div");
      slider.className = "te-slider";
      slider.innerHTML =
        '<div class="te-slider-header">' +
          '<div class="te-slider-title">Новая встреча</div>' +
          '<button class="te-slider-close" data-slider="close">✕</button>' +
        '</div>' +
        '<div class="te-slider-fields">' +
          '<div class="te-field-row"><label>Название:</label><input type="text" class="te-meeting-title" placeholder="Название встречи"></div>' +
          '<div class="te-field-row"><label>Дата:</label><input type="text" data-datepicker data-format="iso" placeholder="ГГГГ-ММ-ДД" class="te-meeting-date"></div>' +
          '<textarea class="te-slider-text te-meeting-notes" placeholder="Комментарий (опционально)"></textarea>' +
          '<div class="te-slider-actions">' +
            '<button class="te-btn te-btn-primary" data-slider="meeting-save">Создать</button>' +
            '<button class="te-btn" data-slider="close">Отмена</button>' +
          '</div>' +
        '</div>';
      document.body.appendChild(slider);
      // Init datepicker on new input
      if (window.DatePicker && typeof window.DatePicker.initElement === "function") {
        const dateInput = slider.querySelector(".te-meeting-date");
        if (dateInput) window.DatePicker.initElement(dateInput);
      }
      slider.querySelectorAll('[data-slider="close"]').forEach(function (btn) {
        btn.addEventListener("click", function () { slider.remove(); });
      });
      slider.querySelector('[data-slider="meeting-save"]').addEventListener("click", function () {
        const title = slider.querySelector(".te-meeting-title").value.trim();
        const date = slider.querySelector(".te-meeting-date").value.trim() || null;
        const notes = slider.querySelector(".te-meeting-notes").value.trim() || null;
        if (!title) { alert("Название обязательно"); return; }
        apiFetch(cfg.apiBase, "/meetings", { method: "POST", body: { title: title, date: date, notes: notes } })
          .then(function (r) {
            slider.remove();
            // Reload widget data (tasks + meetings) → re-render
            load();
            if (hooks.onMeetingCreated) hooks.onMeetingCreated(r.meeting);
          })
          .catch(function (e) { alert("Ошибка: " + e.message); });
      });
    }

    load();
    return {
      reload: load,
      getState: function () { return { tasks: tasks, sources: sources, meetings: meetings }; },
      openTaskById: openTaskById,
      openMeetingCreate: openMeetingCreate,  // v1.4 public API
    };
  }

  window.TaskEngine = { mount: mount };
})();
