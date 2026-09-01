// personal_flow.js — Personal Flow SPA controller
//
// Task: radar-os--660-personal-flow-mode block 6003 (W6.3)
//
// Responsibilities:
// - On page load: fetch cross-domain session context from radar-os verify endpoint
//   (https://team.radar.vschk.online/radar/api/session/verify.php?mode=personal_flow)
// - Hash-based SPA routing: #/settings / #/tab/X / #/file/Y / #/analytics
//   (default = inbox — no hash)
// - Empty placeholder views per tab — real content fills в downstream blocks:
//   * Wave 4 sync atoms → Файлы tab gets files tree
//   * Block 6004 → Настройки gets Google Picker + connections list
//   * Block 6006 → backend endpoints для tabs/files/file-content read
//   * Wave 7 → Аналитика gets dashboard widgets
//
// Auth model: SSO cookie radar_session (.vschk.online scope, shared с
// team.radar.vschk.online). Не залогинен → 401 from verify → redirect на
// auth.vschk.online. Non-team session (superadmin without tenant) → tenant_code=null →
// error card «Залогиньтесь через Team Portal».

const VERIFY_URL = 'https://team.radar.vschk.online/radar/api/session/verify.php?mode=personal_flow';
const AUTH_LOGIN_URL = 'https://auth.vschk.online/';

// Session state — populated after verify fetch
window._pfState = null;

// ── DOM helpers ─────────────────────────────────────────────────────────────
function $(sel) { return document.querySelector(sel); }
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null) continue; // 60067.2: skip null/undefined attrs — иначе setAttribute('disabled', 'null') = disabled=true (HTML any value → truthy)
    if (k === 'class') node.className = v;
    else if (k === 'style') node.setAttribute('style', v);
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, String(v));
  }
  for (const child of children) {
    if (child == null) continue;
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

// ── Cross-domain API fetch (settings endpoints via radar-os backend) ────────
// Task 660 block 60042: helper для settings endpoints через SSO cookie.
// Cross-subdomain: cookie radar_session на .vschk.online scope shared с team.radar.
const PF_API_BASE = 'https://team.radar.vschk.online/radar/api/personal-flow';
async function apiFetchPF(path, opts = {}) {
  const url = `${PF_API_BASE}/${path}`;
  const init = { credentials: 'include', ...opts };
  if (opts.body && typeof opts.body === 'object') {
    init.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    init.body = JSON.stringify(opts.body);
  }
  const resp = await fetch(url, init);
  const data = await resp.json().catch(() => ({ ok: false, error: 'INVALID_JSON' }));
  if (!resp.ok || !data.ok) {
    throw new Error(data.error || `HTTP_${resp.status}`);
  }
  return data;
}

// ── Session verify ──────────────────────────────────────────────────────────
async function verifySession() {
  try {
    const resp = await fetch(VERIFY_URL, { credentials: 'include' });
    if (resp.status === 401) {
      // Not authenticated → redirect to auth
      const returnUrl = encodeURIComponent(window.location.href);
      window.location.href = `${AUTH_LOGIN_URL}?return=${returnUrl}`;
      return null;
    }
    const data = await resp.json();
    if (!data.ok) {
      renderError('Ошибка проверки сессии', `Backend вернул error: ${data.error || 'unknown'}`);
      return null;
    }
    return data;
  } catch (e) {
    renderError('Сеть недоступна', `Не удалось получить session context: ${String(e.message || e)}`);
    return null;
  }
}

// ── Renderers ───────────────────────────────────────────────────────────────
function renderError(title, description) {
  $('#pf-context').textContent = 'Ошибка';
  const content = $('#content');
  content.replaceChildren(
    el('div', { class: 'muted center', style: 'padding: 40px' },
      el('h2', {}, title),
      el('p', {}, description),
    )
  );
}

function renderNoTenantContext() {
  $('#pf-context').textContent = 'Нет контекста';
  const content = $('#content');
  content.replaceChildren(
    el('div', { class: 'muted center', style: 'padding: 40px' },
      el('h2', {}, 'Залогиньтесь через Team Portal'),
      el('p', {}, 'Personal Flow — личное пространство сотрудника. Откройте Team Portal под конкретным тенантом и кликните пункт «Флоу» в левом меню.'),
      el('p', {},
        el('a', { href: 'https://team.radar.vschk.online/', target: '_blank' },
          'Открыть Team Portal ↗'
        )
      ),
    )
  );
}

function renderContextHeader(state) {
  $('#pf-context').textContent = `${state.employee_name || state.tenant_code} · ${state.mode_role || 'нет доступа'}`;
}

// ── Inbox recursive tree (block 60047, refactor of 60052 flat MVP) ─────────
const TREE_ROW_STYLE = 'padding: 5px 8px; cursor: pointer; border-radius: 3px; margin: 1px 0; font-size: 13px; display: flex; align-items: center; gap: 6px; user-select: none;';
const TREE_ROW_ACTIVE = 'background: rgba(244,163,0,0.15); color: #f4a300;';
const TREE_ARROW_STYLE = 'display: inline-block; width: 12px; text-align: center; font-size: 10px; opacity: 0.6; transition: transform 0.1s;';
const TREE_ARROW_EXPANDED = 'display: inline-block; width: 12px; text-align: center; font-size: 10px; opacity: 0.6; transform: rotate(90deg);';
const TREE_LOADING_STYLE = 'padding: 6px 10px; opacity: 0.5; font-size: 11px; font-style: italic;';

// Cache для expand state (survives через collapse/expand toggles + refreshSettingsSection)
// Key format: `tab_${id}` OR `folder_${id}`. Value: {data: fetched_response, promise: in-flight Promise or null}
const TREE_CACHE = new Map();

function nodeKey(type, id) {
  return `${type}_${id}`;
}

async function fetchNodeChildren(type, id, provider) {
  // 60061: provider param (default google_drive backwards compat). Cache namespace by provider
  // чтобы Google/Yandex/S3 не conflict при похожих IDs.
  provider = provider || 'google_drive';
  const key = `${provider}_${nodeKey(type, id)}`;
  const cached = TREE_CACHE.get(key);
  if (cached && cached.data) return cached.data;
  if (cached && cached.promise) return await cached.promise;

  let path;
  if (type === 'tab') {
    // tabs_tree resolves provider через tab.provider column — no need to pass
    path = `tabs_tree.php?tab_id=${encodeURIComponent(id)}`;
  } else if (type === 'folder') {
    path = `folder_tree.php?folder_id=${encodeURIComponent(id)}&provider=${encodeURIComponent(provider)}`;
  } else {
    throw new Error(`Unknown node type: ${type}`);
  }

  const promise = apiFetchPF(path).then(data => {
    TREE_CACHE.set(key, { data, promise: null });
    return data;
  }).catch(err => {
    TREE_CACHE.delete(key); // Don't cache errors — allow retry
    throw err;
  });
  TREE_CACHE.set(key, { data: null, promise });
  return await promise;
}

// Render tree node recursively.
// node = {type: 'tab'|'folder'|'file', id, name, mimeType?, size?, depth, folder_id_for_children?}
// folder_id_for_children — для type='tab' это tab.id (эффективно tabs_tree call);
//                          для type='folder' это folder.id (folder_tree call).
function renderTreeNode(node, activeVendors) {
  const wrapper = el('div', {});
  const isFolder = node.type === 'tab' || node.type === 'folder';
  const currentHash = window.location.hash;
  const isActiveFile = node.type === 'file' && currentHash === `#/file/${node.id}`;

  const arrow = isFolder
    ? el('span', { style: TREE_ARROW_STYLE, class: 'tree-arrow' }, '▸')
    : el('span', { style: 'display: inline-block; width: 12px' }, '');

  const iconChar = node.type === 'file'
    ? mimeIcon(node.mimeType || '')
    : '📁';
  const icon = el('span', { style: 'font-size: 12px' }, iconChar);

  const label = el('span', { style: 'flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap' }, node.name || '(без имени)');

  // 60069: grey-out top-level tabs если vendor toggle-off в Settings.
  // activeVendors — Set<vendor_handle> где binding.is_active=1. Recursive children
  // не имеют activeVendors context — safe, только top-level tabs проверяются.
  const isSyncOff = node.type === 'tab' && node.provider && activeVendors && !activeVendors.has(node.provider);
  const rowClass = 'tree-row' + (isSyncOff ? ' tab-sync-off' : '');
  const rowTitle = isSyncOff ? 'Sync выключен — включи в Настройки → Подключённые провайдеры' : null;

  const rowStyle = TREE_ROW_STYLE + `padding-left: ${8 + node.depth * 16}px;` + (isActiveFile ? TREE_ROW_ACTIVE : '');
  const row = el('div', {
    style: rowStyle,
    class: rowClass,
    title: rowTitle,
    'data-node-key': isFolder ? nodeKey(node.type, node.id) : `file_${node.id}`,
  }, arrow, icon, label);

  const childrenContainer = el('div', { style: 'display: none' });

  if (node.type === 'file') {
    // 60066: mode-aware click per D19. Under Analytics tab → rescope; under Files tab → renderFile viewer.
    row.onclick = () => {
      const provider = encodeURIComponent(node.provider || 'google_drive');
      const fileId = encodeURIComponent(node.id);
      window.location.hash = getActiveTab() === 'analytics'
        ? `#/analytics/file/${provider}/${fileId}`
        : `#/file/${provider}/${fileId}`;
    };
    if (node.size != null && node.size > 0) {
      row.appendChild(el('span', { style: 'font-size: 10px; opacity: 0.4; margin-left: 4px' }, formatFileSize(node.size)));
    }
    wrapper.appendChild(row);
    return wrapper;
  }

  // Folder / tab — expandable
  let expanded = false;
  const toggleExpand = async (ev) => {
    if (ev) ev.stopPropagation();
    if (expanded) {
      childrenContainer.style.display = 'none';
      arrow.textContent = '▸';
      arrow.setAttribute('style', TREE_ARROW_STYLE);
      expanded = false;
      return;
    }
    expanded = true;
    arrow.textContent = '▾';
    arrow.setAttribute('style', TREE_ARROW_STYLE);
    childrenContainer.style.display = 'block';

    // 60061: provider inheritance — pass node.provider down + into fetchNodeChildren cache key
    const nodeProvider = node.provider || 'google_drive';
    const key = `${nodeProvider}_${nodeKey(node.type, node.id)}`;
    const cached = TREE_CACHE.get(key);
    if (!cached || !cached.data) {
      childrenContainer.replaceChildren(
        el('div', { style: TREE_LOADING_STYLE + `padding-left: ${8 + (node.depth + 1) * 16}px` }, 'Загрузка…')
      );
      try {
        await fetchNodeChildren(node.type, node.id, nodeProvider);
      } catch (e) {
        childrenContainer.replaceChildren(
          el('div', { style: TREE_LOADING_STYLE + `padding-left: ${8 + (node.depth + 1) * 16}px; color: #f4a300` }, `Ошибка: ${String(e.message || e)}`)
        );
        return;
      }
    }
    // Render children from cache — inherit provider для children
    const data = TREE_CACHE.get(key).data;
    const folderNodes = (data.folders || []).map(f => renderTreeNode({
      type: 'folder', id: f.id, name: f.name, depth: node.depth + 1, provider: nodeProvider,
    }));
    const fileNodes = (data.files || []).map(f => renderTreeNode({
      type: 'file', id: f.id, name: f.name, mimeType: f.mimeType, size: f.size, depth: node.depth + 1, provider: nodeProvider,
    }));
    const truncatedNotice = data.truncated ? [
      el('div', { style: TREE_LOADING_STYLE + `padding-left: ${8 + (node.depth + 1) * 16}px; color: #f4a300` }, '⚠️ Показаны первые 100')
    ] : [];
    const emptyNotice = folderNodes.length === 0 && fileNodes.length === 0 ? [
      el('div', { style: TREE_LOADING_STYLE + `padding-left: ${8 + (node.depth + 1) * 16}px` }, 'Пусто')
    ] : [];
    childrenContainer.replaceChildren(...folderNodes, ...fileNodes, ...truncatedNotice, ...emptyNotice);
  };

  row.onclick = (ev) => {
    // 60066: under Analytics tab, folder click also rescopes analytics (in addition to expand).
    if (getActiveTab() === 'analytics' && node.type === 'folder') {
      window.location.hash = `#/analytics/folder/${encodeURIComponent(node.id)}`;
    }
    return toggleExpand(ev);
  };
  wrapper.appendChild(row);
  wrapper.appendChild(childrenContainer);
  return wrapper;
}

// 60066: derive active tab from hash. Reused by tree click handlers per D19.
function getActiveTab() {
  const p0 = (window.location.hash.slice(1).split('/').filter(Boolean)[0] || '');
  if (p0 === 'analytics') return 'analytics';
  if (p0 === 'settings') return 'settings';
  return 'inbox';
}

async function populateLeftTree() {
  const tree = $('#tree');
  if (!tree) return;
  tree.replaceChildren(el('div', { class: 'muted', style: 'padding: 10px; font-size: 12px' }, 'Загрузка вкладок…'));
  try {
    // 60069: parallel fetch mode_integrations чтобы знать active bindings per vendor для grey-out.
    // fetchModeIntegrations — helper из 60067, cross-origin с credentials.
    const [tabsResp, intResp] = await Promise.all([
      apiFetchPF('settings/tabs_list.php'),
      fetchModeIntegrations('personal_flow').catch(() => ({ active: [] })), // Silent fail — если endpoint fails, все tabs показать normal (не grey-out)
    ]);
    const tabs = tabsResp.tabs || [];
    const activeVendors = new Set(
      (intResp.active || [])
        .filter(b => b.is_active === 1 || b.is_active === true)
        .map(b => b.vendor_handle)
    );
    if (tabs.length === 0) {
      tree.replaceChildren(
        el('div', { class: 'muted', style: 'padding: 12px; font-size: 12px' },
          el('p', {}, 'Нет подключённых папок.'),
          el('p', { style: 'margin-top: 6px' },
            el('a', { href: '#/settings', style: 'color: #f4a300' }, 'Добавить →'),
          ),
        )
      );
      return;
    }
    const nodes = tabs.map(t => renderTreeNode({
      // 60061: pass tab.provider так children будут fetched через correct provider endpoint.
      // Also prefix name с provider indicator (🅶 Google, 🅨 Yandex) для визуальной differentiation.
      type: 'tab', id: t.id, provider: t.provider || 'google_drive', depth: 0,
      name: (t.provider === 'yandex_disk' ? '🅨 ' : '🅶 ') + t.display_name,
    }, activeVendors));
    // 60066: «Все папки» pseudo-node first row per D19 — click clears selection = global scope.
    const globalNode = el('div', {
      style: TREE_ROW_STYLE + 'padding-left: 8px; font-weight: 500;',
      class: 'tree-row',
    },
      el('span', { style: 'display: inline-block; width: 12px' }, ''),
      el('span', { style: 'font-size: 12px' }, '📊'),
      el('span', { style: 'flex: 1' }, 'Все папки'),
    );
    globalNode.onclick = () => {
      window.location.hash = getActiveTab() === 'analytics' ? '#/analytics' : '';
    };
    const separator = el('div', { style: 'height: 1px; background: rgba(255,255,255,0.08); margin: 6px 8px' });
    tree.replaceChildren(globalNode, separator, ...nodes);
  } catch (e) {
    tree.replaceChildren(
      el('div', { class: 'muted', style: 'padding: 10px; font-size: 12px; color: #f4a300' },
        `Ошибка загрузки: ${String(e.message || e)}`
      )
    );
  }
}

// ── FSM Settings (block 8004 task 686) ──────────────────────────────────────
let _modeFilesSettingsCache = null;
// 8009 task 686: track какой tree currently rendered в left panel — avoid re-fetch при tab switch
let _lastPopulatedTree = null;

// ── FSM Режимы tab (block 8011 task 686) ────────────────────────────────────
let _modesTreeCache = null;
const _itemsTreeCache = {};
const _filesCache = {};
const _expandedNodes = { modes: {}, items: {} };  // track which nodes are expanded

async function fetchModesTree(force = false) {
  if (!force && _modesTreeCache) return _modesTreeCache;
  const resp = await fetch(`${MODE_FILES_API_BASE}/modes_tree.php`, { credentials: 'include' });
  const data = await resp.json().catch(() => ({ ok: false, error: 'INVALID_JSON' }));
  if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP_${resp.status}`);
  _modesTreeCache = data;
  return data;
}

async function fetchItemsTree(modeCode, force = false) {
  if (!force && _itemsTreeCache[modeCode]) return _itemsTreeCache[modeCode];
  const resp = await fetch(`${MODE_FILES_API_BASE}/items_tree.php?mode=${encodeURIComponent(modeCode)}`, { credentials: 'include' });
  const data = await resp.json().catch(() => ({ ok: false, error: 'INVALID_JSON' }));
  if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP_${resp.status}`);
  _itemsTreeCache[modeCode] = data;
  return data;
}

async function fetchFilesForItem(modeCode, itemId, force = false) {
  const key = `${modeCode}:${itemId}`;
  if (!force && _filesCache[key]) return _filesCache[key];
  const resp = await fetch(`${MODE_FILES_API_BASE}/files_list.php?mode=${encodeURIComponent(modeCode)}&item=${encodeURIComponent(itemId)}`, { credentials: 'include' });
  const data = await resp.json().catch(() => ({ ok: false, error: 'INVALID_JSON' }));
  if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP_${resp.status}`);
  _filesCache[key] = data;
  return data;
}

// 8015 task 686: deep-link resolver — file_id → {mode_code, item_id}. Cache keyed by "provider|id"
const _fileLocateCache = new Map();
async function fetchFileLocation(fileId, provider) {
  const key = `${provider}|${fileId}`;
  if (_fileLocateCache.has(key)) return _fileLocateCache.get(key);
  const resp = await fetch(`${MODE_FILES_API_BASE}/file_locate.php?file_id=${encodeURIComponent(fileId)}&provider=${encodeURIComponent(provider)}`, { credentials: 'include' });
  const data = await resp.json().catch(() => ({ ok: false, error: 'INVALID_JSON' }));
  if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP_${resp.status}`);
  _fileLocateCache.set(key, data);
  return data;
}

async function populateModesTree() {
  const tree = $('#tree');
  if (!tree) return;
  tree.replaceChildren(el('div', { class: 'muted', style: 'padding: 10px; font-size: 12px' }, 'Загрузка режимов…'));

  let data;
  try { data = await fetchModesTree(); }
  catch (e) {
    tree.replaceChildren(el('div', { class: 'muted', style: 'padding: 10px; font-size: 12px; color: #f4a300' },
      `Ошибка: ${String(e.message || e)}`));
    return;
  }
  const modes = data.modes || [];
  if (modes.length === 0) {
    tree.replaceChildren(el('div', { class: 'muted', style: 'padding: 12px; font-size: 13px; opacity: 0.6' },
      el('p', {}, 'Нет FSM-режимов с файлами.'),
      el('p', { style: 'margin-top: 8px; font-size: 11px' }, 'Файлы появляются когда режим их создаёт (транскрипты встреч, чаты Нейронки).'),
    ));
    return;
  }

  const rowsContainer = el('div', {});
  for (const m of modes) {
    const modeExpanded = !!_expandedNodes.modes[m.code];
    const chevron = el('span', { style: 'display: inline-block; width: 12px; cursor: pointer' }, modeExpanded ? '▾' : '▸');
    const modeRow = el('div', {
      style: TREE_ROW_STYLE + 'padding-left: 8px; font-weight: 500;',
      class: 'tree-row',
    },
      chevron,
      el('span', { style: 'font-size: 12px' }, '📁'),
      el('span', { style: 'flex: 1' }, m.title),
      el('span', { style: 'font-size: 10px; opacity: 0.5' }, `${m.file_count} ${pluralize(m.file_count, ['файл','файла','файлов'])}`),
    );
    modeRow.onclick = async () => {
      _expandedNodes.modes[m.code] = !_expandedNodes.modes[m.code];
      // Clear expanded items when collapsing mode
      if (!_expandedNodes.modes[m.code]) _expandedNodes.items[m.code] = {};
      await populateModesTree();
    };
    rowsContainer.appendChild(modeRow);

    if (modeExpanded) {
      // Items sub-tree
      let itemsData;
      try { itemsData = await fetchItemsTree(m.code); }
      catch (e) {
        rowsContainer.appendChild(el('div', { style: 'padding: 6px 32px; color: #f4a300; font-size: 12px' }, `Ошибка: ${String(e.message || e)}`));
        continue;
      }
      const items = itemsData.items || [];
      for (const it of items) {
        const itemKey = it.item_id;
        const itemExpanded = !!(_expandedNodes.items[m.code] || {})[itemKey];
        const itemChevron = el('span', { style: 'display: inline-block; width: 12px; cursor: pointer' }, itemExpanded ? '▾' : '▸');
        // 8013 task 686: display_title (block 8012 backend) — human name if available, else item_id
        const displayTitle = it.display_title || it.item_id;
        const subtitle = it.subtitle || '';
        const labelBlock = el('span', { style: 'flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: flex; flex-direction: column' },
          el('span', { style: 'font-size: 12px; overflow: hidden; text-overflow: ellipsis' }, displayTitle),
          subtitle ? el('span', { style: 'font-size: 10px; opacity: 0.55; overflow: hidden; text-overflow: ellipsis' }, subtitle) : null,
        );
        const itemRow = el('div', {
          style: TREE_ROW_STYLE + 'padding-left: 32px;',
          class: 'tree-row',
        },
          itemChevron,
          el('span', { style: 'font-size: 11px' }, '📂'),
          labelBlock,
          el('span', { style: 'font-size: 10px; opacity: 0.5' }, `${it.file_count}`),
        );
        itemRow.onclick = async () => {
          _expandedNodes.items[m.code] = _expandedNodes.items[m.code] || {};
          _expandedNodes.items[m.code][itemKey] = !_expandedNodes.items[m.code][itemKey];
          await populateModesTree();
        };
        rowsContainer.appendChild(itemRow);

        if (itemExpanded) {
          let filesData;
          try { filesData = await fetchFilesForItem(m.code, it.item_id); }
          catch (e) {
            rowsContainer.appendChild(el('div', { style: 'padding: 6px 56px; color: #f4a300; font-size: 11px' }, `Ошибка: ${String(e.message || e)}`));
            continue;
          }
          const files = filesData.files || [];
          for (const f of files) {
            const fileRow = el('div', {
              style: TREE_ROW_STYLE + 'padding-left: 56px; cursor: pointer;',
              class: 'tree-row',
              // 8014 task 686: data-node-key для updateTreeHighlight (шафран highlight active file)
              'data-node-key': `file_${f.file_id || f.file_name}`,
              title: `${f.file_type} · ${(f.size_bytes / 1024).toFixed(1)} kB · ${f.provider}`,
            },
              el('span', { style: 'display: inline-block; width: 12px' }, ''),
              el('span', { style: 'font-size: 11px' }, '📄'),
              el('span', { style: 'flex: 1; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap' }, f.file_name),
            );
            fileRow.onclick = () => {
              // 8013 task 686: inline viewer через #/modes/file/{provider}/{id} → handleRoute → renderFile
              if (f.file_id && f.provider) {
                window.location.hash = `#/modes/file/${encodeURIComponent(f.provider)}/${encodeURIComponent(f.file_id)}`;
              } else if (f.file_url && (f.file_url.startsWith('http://') || f.file_url.startsWith('https://'))) {
                window.open(f.file_url, '_blank');
              } else {
                alert(`Файл не имеет прямой ссылки (${f.provider}). Открой через vendor UI.`);
              }
            };
            rowsContainer.appendChild(fileRow);
          }
        }
      }
    }
  }
  tree.replaceChildren(rowsContainer);
}

function renderModesInbox() {
  const content = $('#content');
  content.replaceChildren(
    el('div', { style: SECTION_STYLE },
      el('h1', { style: 'margin-bottom: 4px' }, 'Файлы режимов'),
      el('p', { style: 'opacity: 0.6; margin-bottom: 24px' }, 'Автоматически созданные файлы из ваших режимов — транскрипты встреч, чаты Нейронки, документы и т.п.'),
      el('div', { class: 'muted center', style: 'padding: 40px' },
        el('p', {}, 'Выбери режим в меню слева, чтобы посмотреть файлы.'),
        el('p', { style: 'font-size: 12px; opacity: 0.5; margin-top: 12px' }, 'Клик по имени файла откроет его в Google Drive / Yandex Диске.'),
      ),
    )
  );
}

const MODE_FILES_API_BASE = 'https://team.radar.vschk.online/radar/api/team/mode_files';

async function fetchModeFilesSettings(force = false) {
  if (!force && _modeFilesSettingsCache) return _modeFilesSettingsCache;
  const resp = await fetch(`${MODE_FILES_API_BASE}/settings.php`, { credentials: 'include' });
  const data = await resp.json().catch(() => ({ ok: false, error: 'INVALID_JSON' }));
  if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP_${resp.status}`);
  _modeFilesSettingsCache = data;
  return data;
}

async function populateSettingsTree() {
  const tree = $('#tree');
  if (!tree) return;
  tree.replaceChildren(el('div', { class: 'muted', style: 'padding: 10px; font-size: 12px' }, 'Загрузка настроек…'));

  const currentHash = window.location.hash;
  const activeModeCode = currentHash.startsWith('#/settings/storage/')
    ? decodeURIComponent(currentHash.replace('#/settings/storage/', ''))
    : null;
  const isStorageRoot = currentHash === '#/settings/storage';

  let data = null;
  try {
    data = await fetchModeFilesSettings();
  } catch (e) {
    tree.replaceChildren(el('div', { class: 'muted', style: 'padding: 10px; font-size: 12px; color: #f4a300' },
      `Ошибка: ${String(e.message || e)}`));
    return;
  }
  const modes = data.modes || [];
  const withFiles = modes.filter(m => m.has_files === 1);
  const withoutFiles = modes.filter(m => m.has_files !== 1);

  const items = [];

  // Static nav items (placeholders — full screens deferred)
  const staticNav = [
    { key: 'profile', icon: '👤', label: 'Профиль' },
    { key: 'oauth', icon: '🔐', label: 'OAuth и токены' },
    { key: 'notifications', icon: '🔔', label: 'Уведомления' },
  ];
  staticNav.forEach(nav => {
    items.push(el('div', {
      style: TREE_ROW_STYLE + 'padding-left: 8px; opacity: 0.55; cursor: default;',
      class: 'tree-row',
      title: 'Раздел в разработке',
    },
      el('span', { style: 'display: inline-block; width: 12px' }, ''),
      el('span', { style: 'font-size: 12px' }, nav.icon),
      el('span', { style: 'flex: 1' }, nav.label),
    ));
  });

  // Divider
  items.push(el('div', { style: 'height: 1px; background: rgba(255,255,255,0.08); margin: 6px 8px' }));

  // 📁 Режимы root — clickable
  const modesRoot = el('div', {
    style: TREE_ROW_STYLE + 'padding-left: 8px; font-weight: 500;' + (isStorageRoot ? ' background: rgba(244,163,0,0.15);' : ''),
    class: 'tree-row',
  },
    el('span', { style: 'display: inline-block; width: 12px' }, '▾'),
    el('span', { style: 'font-size: 12px' }, '📁'),
    el('span', { style: 'flex: 1' }, 'Режимы'),
    el('span', { style: 'font-size: 10px; opacity: 0.5' }, `${withFiles.length}/${modes.length}`),
  );
  modesRoot.onclick = () => { window.location.hash = '#/settings/storage'; };
  items.push(modesRoot);

  // Group "С файлами"
  if (withFiles.length > 0) {
    items.push(el('div', {
      style: 'padding: 6px 8px 4px 24px; font-size: 10px; opacity: 0.5; text-transform: uppercase; letter-spacing: 0.5px;',
    }, '─── С файлами ───'));
    withFiles.forEach(m => {
      const row = el('div', {
        style: TREE_ROW_STYLE + 'padding-left: 32px;' + (activeModeCode === m.code ? ' background: rgba(244,163,0,0.15);' : ''),
        class: 'tree-row',
      },
        el('span', { style: 'font-size: 12px' }, '📁'),
        el('span', { style: 'flex: 1' }, m.title),
        el('span', { style: 'font-size: 10px; opacity: 0.6' }, m.file_count > 0 ? String(m.file_count) : ''),
      );
      row.onclick = () => { window.location.hash = `#/settings/storage/${encodeURIComponent(m.code)}`; };
      items.push(row);
    });
  }

  // Group "Без файлов"
  if (withoutFiles.length > 0) {
    items.push(el('div', {
      style: 'padding: 8px 8px 4px 24px; font-size: 10px; opacity: 0.5; text-transform: uppercase; letter-spacing: 0.5px;',
    }, '─── Без файлов ───'));
    withoutFiles.forEach(m => {
      const row = el('div', {
        style: TREE_ROW_STYLE + 'padding-left: 32px; opacity: 0.55;' + (activeModeCode === m.code ? ' background: rgba(244,163,0,0.15); opacity: 1;' : ''),
        class: 'tree-row',
        title: 'Режим не использует файловое хранилище',
      },
        el('span', { style: 'font-size: 12px' }, '⚪'),
        el('span', { style: 'flex: 1' }, m.title),
      );
      row.onclick = () => { window.location.hash = `#/settings/storage/${encodeURIComponent(m.code)}`; };
      items.push(row);
    });
  }

  tree.replaceChildren(...items);
}

// 8008 task 686: VENDOR_LABELS map (MODE_FILE_TYPES const removed per user feedback — хардкод drift-prone)
const VENDOR_LABELS = {
  google_drive: 'Google Drive',
  yandex_disk: 'Yandex Диск',
};

// 8008 task 686: Russian 3-form plural helper
function pluralize(n, forms) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}

// 8008 task 686: compute effective vendor — уses primary если set + connected, иначе fallback на первый connected
function computeEffectiveVendor(vendors, primary) {
  const connected = (vendors || []).filter(v => v.is_connected === 1);
  if (primary) {
    const found = connected.find(v => v.handle === primary);
    if (found) return { handle: primary, label: VENDOR_LABELS[primary] || primary, isAuto: false };
  }
  if (connected.length > 0) {
    const first = connected[0];
    return { handle: first.handle, label: VENDOR_LABELS[first.handle] || first.handle, isAuto: true };
  }
  return { handle: null, label: 'нет подключений', isAuto: true };
}

// 8008 task 686: inline confirm modal — replace native confirm() с styled overlay + card
function showFsmConfirmModal({ title, currentLabel, newLabel, fileCount }) {
  return new Promise((resolve) => {
    const overlay = el('div', {
      style: 'position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:10000; display:flex; align-items:center; justify-content:center;',
    });
    const filesText = fileCount > 0
      ? `Существующие ${fileCount} ${pluralize(fileCount, ['файл', 'файла', 'файлов'])} останутся в ${currentLabel}. Новые файлы пойдут в ${newLabel}.`
      : `Хранилище для новых файлов будет ${newLabel}.`;
    const card = el('div', {
      style: 'background:#1a1f2e; border-radius:12px; padding:28px 32px; max-width:480px; box-shadow:0 20px 60px rgba(0,0,0,0.5); color:#e8edf5; font-size:14px; line-height:1.5;',
    },
      el('h2', { style: 'margin:0 0 16px; font-size:18px; font-weight:600' }, title || 'Подтвердите действие'),
      el('div', { style: 'padding:12px 14px; background:rgba(255,255,255,0.04); border-radius:8px; margin-bottom:12px; display:flex; flex-direction:column; gap:6px' },
        el('div', {}, el('span', { style: 'opacity:0.6' }, 'Сейчас: '), el('strong', {}, currentLabel)),
        el('div', {}, el('span', { style: 'opacity:0.6' }, 'Планируется: '), el('strong', {}, newLabel)),
      ),
      el('p', { style: 'margin:0 0 20px; opacity:0.85' }, filesText),
      el('div', { style: 'display:flex; gap:10px; justify-content:flex-end' },
        el('button', {
          style: 'padding:10px 18px; background:transparent; color:#e8edf5; border:1px solid rgba(255,255,255,0.2); border-radius:6px; cursor:pointer; font-size:13px',
          onclick: () => close(false),
        }, 'Отмена'),
        el('button', {
          style: 'padding:10px 18px; background:rgba(244,163,0,0.15); color:#f4a300; border:1px solid #f4a300; border-radius:6px; cursor:pointer; font-size:13px; font-weight:500',
          onclick: () => close(true),
        }, 'Сменить'),
      ),
    );
    overlay.appendChild(card);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(false); });
    const onKey = (e) => { if (e.key === 'Escape') close(false); };
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
    function close(result) {
      document.removeEventListener('keydown', onKey);
      overlay.remove();
      resolve(result);
    }
  });
}

async function renderStorageOverview() {
  const content = $('#content');
  content.replaceChildren(el('div', { class: 'muted center', style: 'padding: 40px' }, 'Загрузка…'));
  let data;
  try { data = await fetchModeFilesSettings(); }
  catch (e) {
    content.replaceChildren(el('div', { style: SECTION_STYLE },
      el('h1', {}, 'Файловое хранилище'),
      el('p', { style: 'color: #f4a300' }, `Ошибка: ${String(e.message || e)}`),
    ));
    return;
  }
  const vendors = data.vendors || [];
  const modes = data.modes || [];
  const activeFsm = modes.filter(m => m.has_files === 1);

  const vendorRows = vendors.map(v =>
    el('div', { style: 'padding: 8px 12px; display: flex; align-items: center; gap: 8px' },
      el('span', {}, v.is_connected ? '🟢' : '⚠️'),
      el('span', { style: 'flex: 1' }, VENDOR_LABELS[v.handle] || v.handle),
      el('span', { style: 'font-size: 12px; opacity: 0.6' }, v.is_connected ? 'подключено' : 'не подключено'),
    )
  );

  const modeRows = activeFsm.length > 0 ? activeFsm.map(m => {
    const eff = computeEffectiveVendor(vendors, m.primary_vendor);
    const suffix = eff.isAuto ? ' (автовыбор)' : '';
    const filesLabel = `${m.file_count} ${pluralize(m.file_count, ['файл', 'файла', 'файлов'])}`;
    return el('div', { style: 'padding: 10px 12px; display: flex; align-items: center; gap: 8px; cursor: pointer', class: 'tree-row',
      onclick: () => { window.location.hash = `#/settings/storage/${encodeURIComponent(m.code)}`; }
    },
      el('span', {}, '📁'),
      el('span', { style: 'flex: 1' }, m.title),
      el('span', { style: 'opacity: 0.6; font-size: 12px' }, `→ ${eff.label}${suffix} · ${filesLabel}`),
    );
  }) : [el('div', { class: 'muted', style: 'padding: 12px; font-size: 13px; opacity: 0.6' }, 'Нет активных FSM режимов.')];

  content.replaceChildren(
    el('div', { style: SECTION_STYLE },
      el('h1', { style: 'margin-bottom: 4px' }, 'Файловое хранилище — обзор'),
      el('p', { style: 'opacity: 0.6; margin-bottom: 24px' }, 'Подключённые хранилища и активные режимы, использующие файлы.'),
      el('h2', { style: H_SECTION }, 'Подключённые хранилища'),
      el('div', { style: 'background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 24px' }, ...vendorRows),
      el('h2', { style: H_SECTION }, `Режимы с файлами (${activeFsm.length} из ${modes.length})`),
      el('div', { style: 'background: rgba(255,255,255,0.03); border-radius: 8px' }, ...modeRows),
      el('p', { style: 'opacity: 0.5; font-size: 12px; margin-top: 20px; text-align: center' }, 'Выбери режим в меню слева или клик на карточку выше для настройки vendor.'),
    )
  );
}

async function saveModePrimary(modeCode, newVendor, currentVendorLabel, fileCount) {
  const newLabel = VENDOR_LABELS[newVendor] || newVendor;
  const ok = await showFsmConfirmModal({
    title: `Сменить хранилище на ${newLabel}?`,
    currentLabel: currentVendorLabel,
    newLabel,
    fileCount,
  });
  if (!ok) return;
  try {
    const resp = await fetch(`${MODE_FILES_API_BASE}/set_primary.php`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode_code: modeCode, vendor_handle: newVendor }),
    });
    const data = await resp.json().catch(() => ({ ok: false, error: 'INVALID_JSON' }));
    if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP_${resp.status}`);
    _modeFilesSettingsCache = null;
    await populateSettingsTree();
    await renderStorageMode(modeCode);
  } catch (e) {
    alert(`Не удалось сохранить: ${String(e.message || e)}`);
  }
}

async function renderStorageMode(modeCode) {
  const content = $('#content');
  content.replaceChildren(el('div', { class: 'muted center', style: 'padding: 40px' }, 'Загрузка…'));
  let data;
  try { data = await fetchModeFilesSettings(); }
  catch (e) {
    content.replaceChildren(el('div', { style: SECTION_STYLE }, el('p', { style: 'color: #f4a300' }, `Ошибка: ${String(e.message || e)}`)));
    return;
  }
  const mode = (data.modes || []).find(m => m.code === modeCode);
  if (!mode) {
    content.replaceChildren(el('div', { style: SECTION_STYLE },
      el('h1', {}, 'Режим не найден'),
      el('p', {}, `Не удалось найти режим «${modeCode}» на этом тенанте.`),
    ));
    return;
  }

  if (mode.has_files !== 1) {
    content.replaceChildren(el('div', { style: SECTION_STYLE },
      el('h1', { style: 'margin-bottom: 4px' }, `${mode.title}`),
      el('p', { style: 'opacity: 0.6; font-family: monospace; margin-bottom: 24px' }, mode.code),
      el('div', { style: CARD_STYLE + 'flex-direction: column; align-items: flex-start' },
        el('div', { style: 'font-size: 16px; margin-bottom: 8px' }, '⚪ Этот режим не использует файловое хранилище'),
        el('p', { style: 'opacity: 0.7; line-height: 1.5' },
          'Данные этого режима хранятся в БД. Файлы (attachments, экспорты, генерации) режим не создаёт.',
        ),
        el('p', { style: 'opacity: 0.5; font-size: 13px; margin-top: 12px' },
          'Если нужна поддержка файлов — режим можно расширить архитектурно. Напиши команде.',
        ),
      ),
    ));
    return;
  }

  // has_files=1 → detail with vendor radio
  const connectedSupportedVendors = (data.vendors || []).filter(v => v.is_connected === 1);
  const currentPrimary = mode.primary_vendor;
  // 8008: compute effective vendor — real vendor even когда primary=null (Level 4 fallback)
  const effective = computeEffectiveVendor(data.vendors, currentPrimary);
  let selectedVendor = effective.handle;

  const radioList = connectedSupportedVendors.length > 0
    ? connectedSupportedVendors.map(v => {
        const inputId = `vendor-${v.handle}`;
        const isEffective = v.handle === effective.handle;
        return el('label', {
          style: 'display: flex; align-items: center; gap: 10px; padding: 10px 12px; cursor: pointer; border-radius: 6px; background: rgba(255,255,255,0.02); margin-bottom: 6px',
        },
          el('input', {
            type: 'radio', name: 'primary-vendor', value: v.handle, id: inputId,
            checked: isEffective ? 'checked' : null,
            onchange: (e) => {
              selectedVendor = e.target.value;
              const btn = $('#save-primary-btn');
              if (btn) btn.disabled = (selectedVendor === effective.handle);
            },
          }),
          el('span', { style: 'flex: 1' }, VENDOR_LABELS[v.handle] || v.handle),
          isEffective && effective.isAuto
            ? el('span', { style: 'font-size: 11px; opacity: 0.5' }, '(текущий по автовыбору)')
            : (isEffective ? el('span', { style: 'font-size: 11px; opacity: 0.5' }, '(текущий)') : null),
        );
      })
    : [el('div', { style: 'padding: 12px; opacity: 0.6; font-size: 13px' }, 'Нет подключённых поддерживаемых vendor. Подключи OAuth в OAuth и токены.')];

  const folderPath = `Режимы/${mode.code}/items/`;
  const folderVendorText = effective.handle
    ? `Хранится в ${effective.label}${effective.isAuto ? ' (автовыбор)' : ''} аккаунте`
    : 'Хранилище не определено — подключи OAuth vendor';

  content.replaceChildren(el('div', { style: SECTION_STYLE },
    el('h1', { style: 'margin-bottom: 4px' }, mode.title),
    el('p', { style: 'opacity: 0.6; font-family: monospace; margin-bottom: 20px' }, mode.code),

    el('div', { style: CARD_STYLE + 'background: rgba(76, 175, 80, 0.08); border-left: 3px solid #4caf50; padding: 8px 12px; margin-bottom: 20px' },
      el('span', {}, '✅ Файловое хранилище активно'),
    ),

    el('h2', { style: H_SECTION }, 'Vendor по умолчанию'),
    ...radioList,
    el('div', { style: 'margin-top: 12px; margin-bottom: 24px' },
      el('button', {
        id: 'save-primary-btn',
        style: BTN_ACTIVE,
        disabled: 'disabled',
        onclick: () => saveModePrimary(mode.code, selectedVendor, effective.label, mode.file_count),
      }, 'Сохранить'),
    ),

    el('h2', { style: H_SECTION }, 'Корневая папка'),
    el('div', { style: CARD_STYLE + 'flex-direction: column; align-items: flex-start; gap: 8px' },
      el('span', { style: 'font-family: monospace; font-size: 13px' }, folderPath),
      el('span', { style: 'opacity: 0.5; font-size: 12px' }, folderVendorText),
    ),

    el('h2', { style: H_SECTION }, 'Статистика'),
    el('div', { style: CARD_STYLE },
      el('span', {}, `Всего файлов: ${mode.file_count} · ${(mode.total_size / 1024).toFixed(1)} kB`),
    ),
  ));
}

function renderInbox() {
  // 60047: right panel = welcome. All navigation в left tree через populateLeftTree.
  const content = $('#content');
  content.replaceChildren(
    el('div', { style: 'padding: 60px 40px; max-width: 700px; margin: 0 auto; text-align: center' },
      el('h1', { style: 'margin-bottom: 16px' }, 'Файлы'),
      el('p', { style: 'opacity: 0.7; margin-bottom: 20px; font-size: 15px' },
        'Открой Настройки → добавь папку. Или разверни папку в левом меню и выбери файл.'
      ),
      el('p', { style: 'margin-top: 24px' },
        el('a', { href: '#/settings', style: 'color: #f4a300; font-weight: 500' }, 'Открыть Настройки →')
      ),
    )
  );
}

// ── Analytics (block 60066) ──────────────────────────────────────────────────
// Per Decision 19: hybrid tree=context/tab=lens. Scope из hash routing:
//   #/analytics → global (все папки)
//   #/analytics/folder/{id} → per-folder scope
//   #/analytics/file/{provider}/{id} → per-file scope

async function renderAnalytics(selection) {
  const content = $('#content');
  content.replaceChildren(
    el('div', { class: 'muted center', style: 'padding: 40px' }, 'Загрузка аналитики…')
  );

  const scope = selection?.type || 'global';
  let query = 'analytics/summary.php?scope=' + scope;
  if (scope === 'folder') query += `&id=${encodeURIComponent(selection.id)}`;
  if (scope === 'file')   query += `&id=${encodeURIComponent(selection.id)}&provider=${encodeURIComponent(selection.provider)}`;

  let data;
  try {
    data = await apiFetchPF(query);
  } catch (e) {
    content.replaceChildren(
      el('div', { class: 'muted center', style: 'padding: 40px' },
        el('h2', {}, 'Ошибка загрузки аналитики'),
        el('p', {}, String(e.message || e)),
      )
    );
    return;
  }

  const title = analyticsTitle(scope, selection, data.totals);
  const sections = [
    el('h1', { style: 'margin: 24px 32px 4px; font-size: 22px' }, title),
    el('div', { style: 'margin: 0 32px 24px; font-size: 12px; opacity: 0.5' }, analyticsSubtitle(scope, data.totals)),
    renderCounterCards(scope, data.totals),
  ];

  if (scope !== 'file') {
    sections.push(el('h3', { style: 'margin: 32px 32px 12px; font-size: 13px; text-transform: uppercase; opacity: 0.6' }, 'Типы файлов'));
    sections.push(data.by_mime.length > 0
      ? renderMimeBars(data.by_mime)
      : el('div', { style: 'margin: 0 32px; opacity: 0.5; font-size: 13px' }, 'Нет файлов для анализа типов.'));
  }

  sections.push(el('h3', { style: 'margin: 32px 32px 12px; font-size: 13px; text-transform: uppercase; opacity: 0.6' },
    scope === 'file' ? 'История событий' : 'Активность за год'));
  sections.push(data.heatmap.length > 0
    ? el('div', { style: 'margin: 0 32px' }, renderHeatmap(data.heatmap))
    : el('div', { style: 'margin: 0 32px; opacity: 0.5; font-size: 13px' }, 'Нет активности за 365 дней (Wave 4 sync ещё не собирал события).'));

  const heatmapTotal = data.heatmap.reduce((sum, c) => sum + c.count, 0);
  if (heatmapTotal > 0) {
    sections.push(el('div', { style: 'margin: 8px 32px 40px; font-size: 12px; opacity: 0.5' },
      `Всего ${heatmapTotal} действий за 365 дней`));
  }

  content.replaceChildren(el('div', { style: 'max-width: 1000px; margin: 0 auto' }, ...sections));
}

function analyticsTitle(scope, selection, totals) {
  if (scope === 'global') return 'Аналитика — Все папки';
  if (scope === 'folder') return 'Аналитика — 📁 папка (' + (totals.files_count || 0) + ' файлов)';
  if (scope === 'file')   return 'Аналитика — ' + mimeIcon('') + ' ' + (totals.name || '(файл)');
  return 'Аналитика';
}

function analyticsSubtitle(scope, totals) {
  if (scope === 'file') {
    const size = formatFileSize(totals.size_bytes || 0);
    const modified = (totals.modified_time || '').slice(0, 10);
    return `${size}${modified ? ' · изменён ' + modified : ''}`;
  }
  return '';
}

function renderCounterCards(scope, totals) {
  const CARD = 'flex: 1; padding: 20px; background: rgba(255,255,255,0.05); border-radius: 8px; text-align: center;';
  const VALUE = 'font-size: 28px; font-weight: 600; color: #f4a300; margin-bottom: 4px;';
  const LABEL = 'font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.6;';
  const mk = (value, label) => el('div', { style: CARD },
    el('div', { style: VALUE }, String(value)),
    el('div', { style: LABEL }, label));

  let cards;
  if (scope === 'global') {
    cards = [
      mk(totals.tabs_count, 'Папок'),
      mk(totals.files_count, 'Файлов'),
      mk(totals.folders_count, 'Подпапок'),
      mk(totals.providers_count, 'Провайдеров'),
    ];
  } else if (scope === 'folder') {
    cards = [
      mk(totals.level, 'Уровень'),
      mk(totals.files_count, 'Файлов'),
      mk(totals.folders_count, 'Подпапок'),
    ];
  } else {
    cards = [
      mk(totals.opens || 0, 'Открытий'),
      mk(formatFileSize(totals.size_bytes || 0) || '—', 'Размер'),
      mk((totals.modified_time || '—').slice(0, 10), 'Изменён'),
    ];
  }
  return el('div', { style: 'display: flex; gap: 12px; margin: 0 32px' }, ...cards);
}

function renderMimeBars(bars) {
  const wrap = el('div', { style: 'margin: 0 32px; display: flex; flex-direction: column; gap: 6px' });
  const max = Math.max(...bars.map(b => b.count), 1);
  for (const b of bars) {
    const pct = Math.round((b.count / max) * 100);
    wrap.appendChild(el('div', { style: 'display: flex; align-items: center; gap: 12px; font-size: 12px' },
      el('div', { style: 'width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap' },
        mimeIcon(b.mime) + ' ' + b.mime),
      el('div', { style: 'flex: 1; height: 16px; background: rgba(255,255,255,0.05); border-radius: 3px; position: relative' },
        el('div', { style: `width: ${pct}%; height: 100%; background: #f4a300; border-radius: 3px` })),
      el('div', { style: 'width: 40px; text-align: right; opacity: 0.7' }, String(b.count)),
    ));
  }
  return wrap;
}

// Copied from vschk-flow-ui/app/static/app.js:766-788 (block 60066).
// CSS classes .heatmap + .heatmap-cell.tier-N reused из global style.css:763-784.
// Deferred: extract в shared/heatmap.js когда 3+ consumers (сейчас Flow UI /stats + Personal Flow).
function renderHeatmap(cells) {
  const map = new Map(cells.map(c => [c.date, c.count]));
  const grid = el('div', { class: 'heatmap' });
  const today = new Date();
  const dayCount = 371; // 52 weeks + current
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
    grid.append(el('div', {
      class: `heatmap-cell tier-${tier}`,
      title: `${iso} — ${c} events`,
    }));
  }
  return grid;
}

// ── Settings section (block 60042) ──────────────────────────────────────────
const SECTION_STYLE = 'padding: 24px 32px; max-width: 900px; margin: 0 auto;';
const CARD_STYLE = 'padding: 16px 20px; margin-bottom: 12px; background: rgba(255,255,255,0.05); border-radius: 8px; display: flex; justify-content: space-between; align-items: center;';
const BADGE_ACTIVE = 'padding: 4px 10px; background: rgba(76,175,80,0.2); color: #4CAF50; border-radius: 4px; font-size: 11px;';
const BADGE_PROVIDER = 'padding: 3px 8px; background: rgba(58,167,226,0.2); color: #3AA7E2; border-radius: 3px; font-size: 10px; margin-left: 8px;';
const BTN_DANGER = 'padding: 6px 14px; background: transparent; color: #f4a300; border: 1px solid #f4a300; border-radius: 4px; cursor: pointer; font-size: 12px;';
const BTN_DISABLED = 'padding: 10px 20px; background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.4); border: 1px dashed rgba(255,255,255,0.15); border-radius: 6px; cursor: not-allowed; font-size: 13px;';
const BTN_ACTIVE = 'padding: 10px 20px; background: rgba(244,163,0,0.15); color: #f4a300; border: 1px solid #f4a300; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500;';
const BTN_SECONDARY = 'padding: 10px 20px; background: transparent; color: rgba(255,255,255,0.7); border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; cursor: pointer; font-size: 13px;';
const MODAL_OVERLAY = 'position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 9998; display: flex; align-items: center; justify-content: center; padding: 20px;';
const MODAL_CARD = 'background: #1a1a1a; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 28px 32px; max-width: 460px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.5); z-index: 9999;';
const MODAL_LABEL = 'display: block; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.6; margin-bottom: 6px; margin-top: 16px;';
const MODAL_INPUT = 'width: 100%; padding: 10px 12px; background: #0f0f0f; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; color: #e8e8e8; font-size: 14px; outline: none; box-sizing: border-box;';
const MODAL_SELECT = 'width: 100%; padding: 10px 12px; background: #0f0f0f; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; color: #e8e8e8; font-size: 14px; outline: none; box-sizing: border-box; cursor: pointer;';
const H_SECTION = 'font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.6; margin: 32px 0 12px;';

// Google Picker — public identifier, restricted by HTTP Referer в Cloud Console.
// PENDING_CLOUD_CONSOLE — заменить на реальный API key после Виктор setup Cloud Console
// (Picker API enabled + API key restricted к referrer flow.vschk.online/*).
// APP_ID — Cloud Console project number (task 657 project «radar-vschk»).
const GOOGLE_PICKER_API_KEY = 'AIzaSyDE7HuqnhfSGojcM0j0pItcwtUhVjXVhX0';
const GOOGLE_APP_ID = '411617266417';
const EMPTY_STYLE = 'padding: 24px; text-align: center; opacity: 0.6; background: rgba(255,255,255,0.03); border-radius: 8px;';

// 60067: separate API base для mode_integrations (лежат в /radar/api/team/mode_integrations/*,
// не в personal-flow/*). Cross-origin с team.radar.vschk.online — CORS enabled в endpoint (block 60067 backend).
const MODE_INTEGRATIONS_API_BASE = 'https://team.radar.vschk.online/radar/api/team/mode_integrations';

async function fetchModeIntegrations(modeCode) {
  const resp = await fetch(`${MODE_INTEGRATIONS_API_BASE}/list.php?mode_code=${encodeURIComponent(modeCode)}`, {
    credentials: 'include',
  });
  const data = await resp.json().catch(() => ({ ok: false, error: 'INVALID_JSON' }));
  if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP_${resp.status}`);
  return data;
}

async function renderSettings() {
  const content = $('#content');
  content.replaceChildren(
    el('div', { class: 'muted center', style: 'padding: 40px' }, 'Загрузка настроек…')
  );
  let available = [];
  let active = [];
  let tabs = [];
  try {
    const [intResp, tabsResp] = await Promise.all([
      fetchModeIntegrations('personal_flow'),
      apiFetchPF('settings/tabs_list.php'),
    ]);
    available = intResp.available || [];
    active = intResp.active || [];
    tabs = tabsResp.tabs || [];
  } catch (e) {
    content.replaceChildren(
      el('div', { class: 'muted center', style: 'padding: 40px' },
        el('h2', {}, 'Ошибка загрузки настроек'),
        el('p', {}, `Backend вернул: ${String(e.message || e)}`),
        el('p', { class: 'muted', style: 'font-size: 12px' }, 'Проверь что залогинен в Team Portal (SSO).'),
      )
    );
    return;
  }

  // Section 1 — Providers (60067: via mode_vendor_availability whitelist)
  // Show только whitelisted vendors для personal_flow (google_drive + yandex_disk).
  // Toggle-on = vendor participates в Personal Flow sync (Wave 4 consumer).
  const providersItems = available.length > 0
    ? renderVendorCards(available, active)
    : [el('div', { style: EMPTY_STYLE },
        el('p', {}, 'Нет доступных провайдеров для этого режима.'),
        el('p', { style: 'margin-top: 8px', class: 'muted', 'font-size': '12px' },
          'Whitelist настраивается в mode_vendor_availability (SQL only, см. MODE_VENDOR_AVAILABILITY_MANIFEST).'
        ),
      )];

  // Backward-compat shape для существующих modals (showCreateFolderModal / showProviderSelectModal)
  // — они принимают старый connections shape. Convert available → old shape.
  const connections = available
    .filter(v => v.is_installed == 1 || v.is_installed === true)
    .map(v => ({ service_handle: v.handle, service_name: v.name_ru || v.handle }));

  // Section 2 — Tabs (synced folders)
  const tabsItems = tabs.length > 0
    ? tabs.map(t => el('div', { style: CARD_STYLE },
        el('div', {},
          el('div', { style: 'font-weight: 500' },
            '📁 ' + t.display_name,
            el('span', { style: BADGE_PROVIDER }, t.provider || 'google_drive'),
          ),
          el('div', { style: 'font-size: 11px; opacity: 0.6; margin-top: 4px; font-family: monospace' },
            t.gdrive_folder_id || ''
          ),
        ),
        el('button', {
          style: BTN_DANGER,
          onclick: async () => {
            if (!confirm(`Отключить папку «${t.display_name}»?\n\nФайлы в Drive не удалятся — только Соня перестанет их sync'ить в Personal Flow.`)) return;
            try {
              await apiFetchPF('settings/tabs_delete.php', { method: 'POST', body: { tab_id: t.id } });
              await refreshSettingsSection();
            } catch (e) {
              alert(`Не удалось отключить: ${String(e.message || e)}`);
            }
          }
        }, 'Отключить'),
      ))
    : [el('div', { style: EMPTY_STYLE },
        el('p', {}, 'Пока не добавлено ни одной папки. Нажми кнопку ниже 👇'),
      )];

  content.replaceChildren(
    el('div', { style: SECTION_STYLE },
      el('h1', { style: 'margin-bottom: 4px' }, 'Настройки Personal Flow'),
      el('p', { style: 'opacity: 0.6; margin-bottom: 24px' }, 'Управление подключёнными провайдерами и синхронизируемыми папками.'),

      el('h2', { style: H_SECTION }, 'Подключённые провайдеры'),
      ...providersItems,

      el('h2', { style: H_SECTION }, 'Синхронизируемые папки'),
      ...tabsItems,

      el('div', { style: 'margin-top: 20px; text-align: center; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap' },
        el('button', {
          style: BTN_ACTIVE,
          onclick: () => showCreateFolderModal(connections),
        }, '+ Создать папку'),
        el('button', {
          style: BTN_SECONDARY,
          onclick: () => showProviderSelectModal(connections),
        }, 'Выбрать существующую папку'),
      ),
    )
  );
}

async function refreshSettingsSection() {
  // Re-render Settings — вызывается после успешного tabs_delete
  // без full page reload, чтобы UI обновился immediately.
  await renderSettings();
  await populateLeftTree(); // Refresh left tree (block 60052)
}

// 60067: renderVendorCards — port essentials из radar/team/src/lib/mode-integrations-panel.js.
// Full component (drag-n-drop reorder + sync log + config editor) deferred YAGNI —
// Personal Flow сейчас нужны только 2 vendors с простым toggle.
function renderVendorCards(available, active) {
  // 60068: port service-card + settings-toggle--saffron structure из Team Portal
  // (radar/team/lib/mode-integrations-panel.js:141-163 template).
  // CSS живёт в style.css block 60068 append (vendor-card.css + settings-toggle.css).
  const activeByHandle = Object.fromEntries((active || []).map(b => [b.vendor_handle, b]));
  return available.map(v => {
    const binding = activeByHandle[v.handle];
    const isActive = !!binding && (binding.is_active === 1 || binding.is_active === true);
    const isInstalled = v.is_installed == 1 || v.is_installed === true;
    const name = v.name_ru || v.handle;
    const desc = v.description_ru || '';
    const typeLabel = v.integration_type || 'Хранилище';

    let statusCls, statusText;
    if (!isInstalled) {
      statusCls = 'service-card__status service-card__status--needs-key';
      statusText = 'Подключи в Team Portal';
    } else if (isActive) {
      statusCls = 'service-card__status service-card__status--connected';
      statusText = '✓ Sync активен';
    } else {
      statusCls = 'service-card__status service-card__status--idle';
      statusText = 'Sync выключен';
    }

    // Toggle input — CSS `.settings-toggle input:checked + .settings-toggle__track` handles visual state
    const toggleInputAttrs = { type: 'checkbox' };
    if (isActive) toggleInputAttrs.checked = 'checked';
    if (!isInstalled) toggleInputAttrs.disabled = 'disabled';
    const toggleInput = el('input', toggleInputAttrs);

    toggleInput.addEventListener('change', async (ev) => {
      if (!isInstalled) {
        ev.target.checked = !ev.target.checked;
        alert(`Чтобы активировать ${name} — сначала подключи vendor в Team Portal → Интеграции`);
        return;
      }
      const newActive = ev.target.checked ? 1 : 0;
      try {
        const resp = await fetch(`${MODE_INTEGRATIONS_API_BASE}/toggle.php`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode_code: 'personal_flow', vendor_handle: v.handle, is_active: newActive }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP_${resp.status}`);
        await refreshSettingsSection();
      } catch (e) {
        ev.target.checked = !ev.target.checked;
        alert(`Не удалось переключить: ${String(e.message || e)}`);
      }
    });

    const cardCls = isInstalled ? 'service-card' : 'service-card service-card--not-installed';

    return el('div', { class: cardCls, 'data-vendor-handle': v.handle, 'data-installed': isInstalled ? '1' : '0' },
      el('div', { class: 'service-card__body' },
        el('div', { class: 'service-card__name' }, name),
        desc ? el('div', { class: 'service-card__desc' }, desc) : null,
      ),
      el('div', { class: 'service-card__footer' },
        el('span', { class: 'service-card__type' }, typeLabel),
        el('span', { class: 'service-card__toggle' },
          el('label', { class: 'settings-toggle settings-toggle--saffron' },
            toggleInput,
            el('span', { class: 'settings-toggle__track' }),
          ),
          el('span', { class: statusCls }, statusText),
        ),
      ),
    );
  });
}

// ── Create folder modal (block 60044) ───────────────────────────────────────
function showCreateFolderModal(connectedProviders) {
  // connectedProviders — array of {handle, name} для current employee.
  // Dropdown показывает: active connected providers (selectable) + Yandex/S3 disabled 'Скоро'.
  const activeHandles = new Set((connectedProviders || []).map(c => c.service_handle));
  const providerOptions = [
    // 60061: Yandex enabled когда подключён в bus_tenant_connections
    { value: 'google_drive', label: 'Google Drive', enabled: activeHandles.has('google_drive') },
    { value: 'yandex_disk', label: 'Яндекс Диск', enabled: activeHandles.has('yandex_disk') },
    { value: 's3', label: 'Amazon S3 (скоро)', enabled: false },
  ];
  const firstEnabled = providerOptions.find(p => p.enabled);
  if (!firstEnabled) {
    alert('Не подключено ни одного провайдера. Подключи Google Drive через Team Portal → Интеграции.');
    return;
  }

  const overlay = el('div', { style: MODAL_OVERLAY, id: 'pf-modal-create-folder' });
  const nameInput = el('input', {
    type: 'text',
    style: MODAL_INPUT,
    placeholder: 'Например: Клиенты 2026',
    id: 'pf-new-folder-name',
  });
  const providerSelect = el('select', { style: MODAL_SELECT, id: 'pf-new-folder-provider' });
  providerOptions.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.value;
    opt.textContent = p.label;
    if (!p.enabled) opt.disabled = true;
    if (p.value === firstEnabled.value) opt.selected = true;
    providerSelect.appendChild(opt);
  });

  const errorSlot = el('div', { style: 'font-size: 12px; color: #f4a300; margin-top: 12px; min-height: 16px' });
  const card = el('div', { style: MODAL_CARD });

  // Last-create context (only latest — no history per Виктор feedback 60044.3)
  let lastCreated = null; // {name, tab_id}

  const close = () => {
    overlay.remove();
    document.removeEventListener('keydown', onKey);
  };

  const renderFormPhase = () => {
    // Reset error slot content on re-render
    errorSlot.textContent = '';
    const submitBtn = el('button', { style: BTN_ACTIVE }, 'Создать');
    const cancelBtn = el('button', { style: BTN_SECONDARY, onclick: close }, 'Отмена');

    const submit = async () => {
      const name = nameInput.value.trim();
      const provider = providerSelect.value;
      if (name === '') {
        errorSlot.textContent = 'Введи название папки';
        nameInput.focus();
        return;
      }
      errorSlot.textContent = '';
      submitBtn.disabled = true;
      submitBtn.textContent = 'Создаём…';
      try {
        const resp = await apiFetchPF('create_folder.php', {
          method: 'POST',
          body: { provider, name },
        });
        lastCreated = { name, tab_id: resp.tab_id };
        await refreshSettingsSection(); // Update left tree + settings underneath
        renderSuccessPhase();            // Swap card contents to success state
      } catch (e) {
        errorSlot.textContent = `Не удалось создать: ${String(e.message || e)}`;
        submitBtn.disabled = false;
        submitBtn.textContent = 'Создать';
      }
    };
    submitBtn.onclick = submit;
    submit._current = submit; // expose for Enter handler

    card.replaceChildren(
      el('h2', { style: 'margin: 0 0 4px; font-size: 18px' }, 'Новая папка'),
      el('p', { style: 'margin: 0 0 8px; opacity: 0.6; font-size: 13px' },
        'Папка создастся в корне выбранного провайдера и сразу появится в списке синхронизируемых.'
      ),
      el('label', { style: MODAL_LABEL }, 'Провайдер'),
      providerSelect,
      el('label', { style: MODAL_LABEL }, 'Название папки'),
      nameInput,
      errorSlot,
      el('div', { style: 'display: flex; gap: 10px; justify-content: flex-end; margin-top: 24px' },
        cancelBtn, submitBtn,
      ),
    );

    // Focus & save reference for Enter handler
    currentSubmit = submit;
    setTimeout(() => nameInput.focus(), 50);
  };

  const renderSuccessPhase = () => {
    const createMoreBtn = el('button', { style: BTN_ACTIVE }, '+ Создать ещё');
    const goToFolderBtn = el('button', { style: BTN_SECONDARY }, 'Перейти в папку →');

    createMoreBtn.onclick = () => {
      // Reset name input, keep provider selection (batch UX)
      nameInput.value = '';
      renderFormPhase();
    };
    goToFolderBtn.onclick = () => {
      const tabId = lastCreated && lastCreated.tab_id;
      close();
      if (tabId) window.location.hash = `#/tab/${tabId}`;
    };

    card.replaceChildren(
      el('div', { style: 'text-align: center; padding: 12px 0 8px' },
        el('div', { style: 'font-size: 36px; color: #4CAF50; margin-bottom: 12px' }, '✓'),
        el('h2', { style: 'margin: 0 0 6px; font-size: 18px' }, 'Папка создана'),
        el('p', { style: 'margin: 0 0 4px; opacity: 0.8; font-size: 14px; font-weight: 500' },
          lastCreated ? lastCreated.name : ''
        ),
        el('p', { style: 'margin: 0; opacity: 0.6; font-size: 13px' }, 'Что дальше?'),
      ),
      el('div', { style: 'display: flex; gap: 10px; justify-content: center; margin-top: 24px; flex-wrap: wrap' },
        goToFolderBtn, createMoreBtn,
      ),
    );
    setTimeout(() => createMoreBtn.focus(), 50);
  };

  // Enter handler needs to know which submit function is current (form phase only)
  let currentSubmit = null;
  const onKey = (ev) => {
    if (ev.key === 'Escape') { close(); return; }
    if (ev.key === 'Enter' && document.activeElement === nameInput && currentSubmit) { currentSubmit(); }
  };
  document.addEventListener('keydown', onKey);

  // Click outside card → close
  overlay.onclick = (ev) => { if (ev.target === overlay) close(); };

  overlay.appendChild(card);
  document.body.appendChild(overlay);
  renderFormPhase();
}

// ── Google Picker integration (block 60043) ─────────────────────────────────
// Loads gapi.load('picker') on-demand, fetches per-user OAuth access_token
// через oauth_token.php, builds PickerBuilder с DocsView(FOLDERS), callback
// posts выбранную folder в tabs_add.php → refresh Settings.
//
// Prereqs (Cloud Console — user manual step):
// 1) Picker API enabled в task 657 GCP project
// 2) API key restricted к HTTP Referer flow.vschk.online/*
// 3) OAuth 2.0 Client authorized JS origin https://flow.vschk.online added
// 4) Values pasted into GOOGLE_PICKER_API_KEY + GOOGLE_APP_ID consts above
let _pickerApiLoaded = false;

async function showPicker() {
  if (GOOGLE_PICKER_API_KEY === 'PENDING_CLOUD_CONSOLE') {
    alert('Google Picker пока не настроен.\n\nВиктор должен зайти в Cloud Console (task 657 project), enable Picker API, создать API key restricted к referrer flow.vschk.online, добавить authorized JS origin, и paste API key в personal_flow.js const GOOGLE_PICKER_API_KEY.\n\nПодробности — в user-note-60043.1.md.');
    return;
  }

  if (typeof gapi === 'undefined') {
    alert('Google JS SDK не загрузился. Reload страницы или проверь network (apis.google.com blocked?).');
    return;
  }

  let tokenResp;
  try {
    tokenResp = await apiFetchPF('settings/oauth_token.php?provider=google_drive');
  } catch (e) {
    alert(`Не удалось получить OAuth token: ${String(e.message || e)}\n\nПроверь что Google Drive подключён в Team Portal → Интеграции.`);
    return;
  }
  const accessToken = tokenResp.access_token;

  const buildAndShow = () => {
    const view = new google.picker.DocsView(google.picker.ViewId.FOLDERS)
      .setSelectFolderEnabled(true)
      .setMimeTypes('application/vnd.google-apps.folder');
    const picker = new google.picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(accessToken)
      .setDeveloperKey(GOOGLE_PICKER_API_KEY)
      .setAppId(GOOGLE_APP_ID)
      .setCallback(onPickerCallback)
      .build();
    picker.setVisible(true);
  };

  if (_pickerApiLoaded) {
    buildAndShow();
  } else {
    gapi.load('picker', () => {
      _pickerApiLoaded = true;
      buildAndShow();
    });
  }
}

async function onPickerCallback(data) {
  if (!data || data.action !== google.picker.Action.PICKED) return;
  const docs = data.docs || [];
  if (docs.length === 0) return;
  const doc = docs[0];
  if (doc.mimeType !== 'application/vnd.google-apps.folder') {
    alert('Выбери папку, а не файл.');
    return;
  }

  try {
    await apiFetchPF('settings/tabs_add.php', {
      method: 'POST',
      body: {
        gdrive_folder_id: doc.id,
        display_name: doc.name || 'Без имени',
        provider: 'google_drive',
      },
    });
    await refreshSettingsSection();
  } catch (e) {
    alert(`Не удалось добавить папку: ${String(e.message || e)}`);
  }
}

function renderTab(tabId) {
  // 60047: right panel = welcome. Дерево — в левой панели.
  const content = $('#content');
  content.replaceChildren(
    el('div', { style: 'padding: 60px 40px; max-width: 700px; margin: 0 auto; text-align: center' },
      el('h1', { style: 'margin-bottom: 16px; font-size: 22px' }, 'Выбери файл в дереве слева ←'),
      el('p', { style: 'opacity: 0.7; font-size: 15px' },
        'Раскрой папку стрелкой ▸ чтобы увидеть её содержимое, затем клик по файлу — откроется viewer.'
      ),
    )
  );
}

function mimeIcon(mime) {
  if (!mime) return '📄';
  if (mime.startsWith('image/')) return '🖼️';
  if (mime.startsWith('video/')) return '🎬';
  if (mime.startsWith('audio/')) return '🎵';
  if (mime === 'application/pdf') return '📕';
  if (mime.includes('spreadsheet') || mime.includes('excel')) return '📊';
  if (mime.includes('document') || mime.includes('word')) return '📝';
  if (mime.includes('presentation') || mime.includes('powerpoint')) return '📽️';
  return '📄';
}

function formatFileSize(bytes) {
  if (bytes == null || bytes === 0) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

// ── Viewer router (block 60053) ─────────────────────────────────────────────
const PROXY_FILE_URL = 'https://team.radar.vschk.online/radar/api/personal-flow/proxy-file.php';
const MARKDOWN_SIZE_LIMIT = 500 * 1024; // 500KB

// Office mime types (uploaded .docx/.xlsx/.pptx + legacy .doc/.xls/.ppt).
// Google-native mime (google-apps.document/spreadsheet/presentation) — handled
// separately с их own docs.google.com preview URLs.
// Task 60049: Drive preview iframe для Office = drive.google.com/file/d/{id}/preview
const OFFICE_MIMES = new Set([
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
  'application/msword',                                                        // .doc
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',        // .xlsx
  'application/vnd.ms-excel',                                                  // .xls
  'application/vnd.openxmlformats-officedocument.presentationml.presentation', // .pptx
  'application/vnd.ms-powerpoint',                                             // .ppt
]);

// Explicit blacklist — mime types где Drive preview заведомо useless.
// Executables, disk images, archives (кроме zip который Google list'ает) →
// сразу empty state с кнопкой Open in Drive.
const NO_PREVIEW_MIMES = new Set([
  'application/x-msdownload',    // .exe
  'application/x-executable',
  'application/x-mach-binary',   // .dmg macOS
  'application/x-apple-diskimage',
  'application/x-msi',            // .msi
  'application/x-iso9660-image', // .iso
]);

async function renderFile(fileId, provider) {
  // 60063: provider param — default 'google_drive' backwards compat.
  provider = provider || 'google_drive';
  const content = $('#content');
  content.replaceChildren(
    el('div', { class: 'muted center', style: 'padding: 40px' }, 'Загрузка файла…')
  );
  let meta;
  try {
    const resp = await apiFetchPF(`file_meta.php?file_id=${encodeURIComponent(fileId)}&provider=${encodeURIComponent(provider)}`);
    meta = resp.file;
  } catch (e) {
    content.replaceChildren(
      el('div', { class: 'muted center', style: 'padding: 40px' },
        el('h2', {}, 'Файл не найден'),
        el('p', {}, String(e.message || e)),
        el('p', { style: 'margin-top: 16px' },
          el('a', { href: '#/', style: 'color: #f4a300' }, '← Назад к файлам')
        ),
      )
    );
    return;
  }

  const mime = meta.mimeType || '';
  // 60063: provider-aware fallback link — Google → webViewLink; Yandex → disk.yandex.ru/client/disk если нет public_url.
  const fallbackLink = meta.webViewLink || (provider === 'yandex_disk' ? 'https://disk.yandex.ru/client/disk' : '');
  const linkLabel = provider === 'yandex_disk' ? 'Открыть в Яндекс Диск ↗' : 'Открыть в Drive ↗';

  const header = el('div', { style: 'padding: 16px 32px; border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between' },
    el('div', {},
      el('div', { style: 'font-weight: 500; font-size: 15px' }, mimeIcon(mime) + ' ' + (meta.name || fileId)),
      el('div', { style: 'font-size: 11px; opacity: 0.5; margin-top: 4px; font-family: monospace' }, mime),
    ),
    fallbackLink ? el('a', { href: fallbackLink, target: '_blank', style: 'color: #f4a300; font-size: 12px' }, linkLabel) : el('span', {}),
  );

  // 60063: proxy URL с provider param для media/text fetches
  const proxyUrl = `${PROXY_FILE_URL}?file_id=${encodeURIComponent(fileId)}&provider=${encodeURIComponent(provider)}`;

  let viewer;
  if (mime === 'application/vnd.google-apps.document') {
    viewer = viewerIframe(`https://docs.google.com/document/d/${fileId}/preview`, fallbackLink);
  } else if (mime === 'application/vnd.google-apps.spreadsheet') {
    viewer = viewerIframe(`https://docs.google.com/spreadsheets/d/${fileId}/preview`, fallbackLink);
  } else if (mime === 'application/vnd.google-apps.presentation') {
    viewer = viewerIframe(`https://docs.google.com/presentation/d/${fileId}/preview`, fallbackLink);
  } else if (mime === 'application/pdf') {
    // Google Drive preview iframe работает только для Google-hosted PDF. Yandex PDF → proxy stream.
    viewer = provider === 'google_drive'
      ? viewerIframe(`https://drive.google.com/file/d/${fileId}/preview`, fallbackLink)
      : el('iframe', { src: proxyUrl, style: 'flex: 1; width: 100%; border: none; min-height: 80vh' });
  } else if (OFFICE_MIMES.has(mime)) {
    // 60049: Office via Google Drive preview. Yandex Office → generic viewer (пока)
    viewer = provider === 'google_drive'
      ? viewerIframe(`https://drive.google.com/file/d/${fileId}/preview`, fallbackLink)
      : viewerUnknown(meta, fileId, provider);
  } else if (mime.startsWith('image/')) {
    viewer = el('div', { style: 'flex: 1; padding: 20px; text-align: center; overflow: auto' },
      el('img', { src: proxyUrl, style: 'max-width: 100%; max-height: 90vh' })
    );
  } else if (mime.startsWith('video/')) {
    // 60063.4: Yandex video → card с кнопкой «Открыть в новой вкладке» на proxy URL
    // (browser navigates → 302 → Yandex CDN → native fullscreen player, top-level browsing
    // context не имеет CORS restriction для media). Все хитрые inline варианты (video,
    // iframe) упираются в browser policies. Google Drive → native <video> element как раньше.
    if (provider === 'yandex_disk') {
      viewer = viewerMediaCard(meta, fileId, 'видео');
    } else {
      viewer = el('div', { style: 'flex: 1; padding: 20px; text-align: center; display: flex; align-items: center; justify-content: center' },
        el('video', { src: proxyUrl, controls: 'controls', preload: 'metadata', style: 'width: 100%; max-width: 1200px; max-height: 80vh; background: #000' })
      );
    }
  } else if (mime.startsWith('audio/')) {
    // 60063.4: same card approach для Yandex audio
    if (provider === 'yandex_disk') {
      viewer = viewerMediaCard(meta, fileId, 'аудио');
    } else {
      viewer = el('div', { style: 'flex: 1; padding: 40px; text-align: center' },
        el('audio', { src: proxyUrl, controls: 'controls', preload: 'metadata', style: 'width: 100%; max-width: 700px' })
      );
    }
  } else if (mime.startsWith('text/') || mime === 'application/json') {
    viewer = await viewerText(fileId, meta, mime, provider);
  } else {
    viewer = viewerUnknown(meta, fileId, provider);
  }

  content.replaceChildren(
    el('div', { style: 'display: flex; flex-direction: column; height: 100%' }, header, viewer)
  );
}

// 60063.5: card viewer для Yandex media — button async publishes file через backend
// file_share_url.php → gets public URL типа disk.360.yandex.ru/i/HASH → window.open.
// Yandex UI открывает файл в preview mode (video/audio/pdf inline player).
// Trade-off: файл становится published (shareable) — user может unpublish вручную.
function viewerMediaCard(meta, fileId, kindLabel) {
  const mime = meta.mimeType || '';
  const sizeText = meta.size ? ` · ${formatFileSize(meta.size)}` : '';
  const btn = el('button', {
    style: 'display: inline-block; padding: 14px 28px; background: rgba(244,163,0,0.15); color: #f4a300; border: 1px solid #f4a300; border-radius: 6px; cursor: pointer; font-size: 15px; font-weight: 500',
  }, `Открыть ${kindLabel} в Яндекс Диске ↗`);

  btn.onclick = async () => {
    const originalText = btn.textContent;
    btn.textContent = 'Публикуем файл...';
    btn.disabled = true;
    try {
      const resp = await apiFetchPF(`file_share_url.php?file_id=${encodeURIComponent(fileId)}&provider=yandex_disk`);
      const publicUrl = resp.public_url;
      if (!publicUrl) throw new Error('Пустой public_url в ответе');
      window.open(publicUrl, '_blank', 'noopener');
      btn.textContent = originalText;
      btn.disabled = false;
    } catch (e) {
      btn.textContent = originalText;
      btn.disabled = false;
      alert(`Не удалось открыть файл: ${String(e.message || e)}`);
    }
  };

  return el('div', { style: 'flex: 1; padding: 60px 40px; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center' },
    el('div', { style: 'font-size: 80px; margin-bottom: 20px' }, mimeIcon(mime)),
    el('h2', { style: 'margin: 0 0 8px; font-size: 20px' }, meta.name || 'Файл'),
    el('p', { style: 'margin: 0 0 8px; opacity: 0.5; font-size: 12px; font-family: monospace' }, (mime || 'unknown mime') + sizeText),
    el('p', { style: 'margin: 0 0 32px; opacity: 0.7; font-size: 14px; max-width: 500px' },
      `Inline проигрыватель ${kindLabel} для Яндекс Диска не поддерживается. Нажми кнопку — файл откроется в preview Яндекс Диска в новой вкладке (полноэкранный плеер со стримингом и перемоткой).`
    ),
    btn,
    el('p', { style: 'margin-top: 16px; opacity: 0.4; font-size: 11px; max-width: 400px' },
      'При открытии файл будет опубликован в Яндекс Диске (публичная ссылка). Можно отменить публикацию вручную в UI Яндекс Диска.'
    ),
  );
}

function viewerIframe(src, fallbackLink) {
  return el('iframe', {
    src,
    style: 'flex: 1; width: 100%; border: none; min-height: 80vh',
    allow: 'autoplay',
  });
}

async function viewerText(fileId, meta, mime, provider) {
  // 60063: provider param — default google_drive backwards compat
  provider = provider || 'google_drive';
  const wrap = el('div', { style: 'flex: 1; padding: 30px 40px; overflow: auto; max-width: 900px; margin: 0 auto; width: 100%' });
  if (meta.size && meta.size > MARKDOWN_SIZE_LIMIT) {
    wrap.appendChild(el('div', { style: 'padding: 12px; background: rgba(244,163,0,0.1); border-radius: 6px; margin-bottom: 20px; font-size: 12px' },
      '⚠️ Файл больше 500KB — рендер как plain text (без markdown).'
    ));
  }
  try {
    const resp = await fetch(`${PROXY_FILE_URL}?file_id=${encodeURIComponent(fileId)}&provider=${encodeURIComponent(provider)}`, { credentials: 'include' });
    if (!resp.ok) throw new Error(`HTTP_${resp.status}`);
    const raw = await resp.text();
    if (mime === 'text/markdown' && (!meta.size || meta.size <= MARKDOWN_SIZE_LIMIT)) {
      const div = el('div', { class: 'markdown-body' });
      // breaks:true — как в витрине портала (partner.js, все три вызова).
      // Без него одиночный перенос строки склеивается в абзац, и один и тот же
      // файл выглядит на двух страницах по-разному. Block 4.
      div.innerHTML = window.marked ? window.marked.parse(raw, { breaks: true }) : `<pre>${escapeHtml(raw)}</pre>`;
      if (window.hljs) {
        div.querySelectorAll('pre code').forEach(b => window.hljs.highlightElement(b));
      }
      // Распознавание паттернов — ПОСЛЕ подсветки, как в портале (partner.js:708).
      //
      // Оформление документа появляется здесь: обложка с мета-плитками, врезки,
      // тезисы с нумерацией, карточки, закрывающий блок. Каждый паттерн строго
      // условен — не совпало, молча ничего не делает, файл остаётся читаемым.
      //
      // ⚠️ Проверка на window.DocPatterns обязательна: скрипт подключён обычным
      //    тегом без defer, но если он однажды не загрузится, документ должен
      //    показаться без оформления, а не пропасть вместе с ошибкой.
      if (window.DocPatterns) {
        window.DocPatterns.enhance(div);
      }
      wrap.appendChild(div);
    } else {
      wrap.appendChild(el('pre', { style: 'white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, monospace; font-size: 13px' }, raw));
    }
  } catch (e) {
    wrap.appendChild(el('div', { style: 'color: #f4a300' }, `Ошибка загрузки контента: ${String(e.message || e)}`));
  }
  return wrap;
}

// 60049: Universal fallback — если mime не в explicit NO_PREVIEW blacklist
// (executables/archives/etc), пытаемся Drive preview iframe.
// Google inline покажет их «cannot preview» если реально не может.
// Если file_id отсутствует ИЛИ mime в blacklist → показываем empty state.
function viewerUnknown(meta, fileId, provider) {
  // 60063: provider param — Yandex fallback URL (disk.yandex.ru/client/disk) когда нет webViewLink
  provider = provider || 'google_drive';
  const mime = meta.mimeType || '';
  const isBlacklisted = NO_PREVIEW_MIMES.has(mime);
  // Drive preview iframe работает только для Google Drive files. Yandex → empty state.
  if (fileId && !isBlacklisted && provider === 'google_drive') {
    return viewerIframe(`https://drive.google.com/file/d/${fileId}/preview`, meta.webViewLink);
  }
  // Fallback link — Google webViewLink OR Yandex disk root
  const fallbackLink = meta.webViewLink || (provider === 'yandex_disk' ? 'https://disk.yandex.ru/client/disk' : '');
  const linkLabel = provider === 'yandex_disk' ? 'Открыть в Яндекс Диск ↗' : 'Открыть в Google Drive ↗';
  return el('div', { style: 'flex: 1; padding: 60px; text-align: center' },
    el('h2', { style: 'margin-bottom: 12px' }, mimeIcon(mime) + ' ' + (meta.name || 'Файл')),
    el('p', { style: 'opacity: 0.7; margin-bottom: 20px' }, 'Inline preview не поддерживается для этого типа.'),
    el('p', { style: 'font-size: 12px; opacity: 0.5; margin-bottom: 24px; font-family: monospace' }, mime || 'unknown mime'),
    fallbackLink ? el('a', {
      href: fallbackLink,
      target: '_blank',
      style: 'display: inline-block; padding: 10px 20px; background: rgba(244,163,0,0.15); color: #f4a300; border: 1px solid #f4a300; border-radius: 6px; text-decoration: none',
    }, linkLabel) : el('span', {}),
  );
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
}

// Update tree file highlight — вызывается из handleRoute (60047)
function updateTreeHighlight() {
  const hash = window.location.hash;
  // 8014 task 686: match оба паттерна — #/file/{...} (Files tab) и #/modes/file/{...} (Modes tab)
  const match = hash.match(/^#\/(?:modes\/)?file\/(.+)$/);
  // 60063: hash может быть #/file/{provider}/{id} (extract id after known provider prefix)
  // OR legacy #/file/{id} (whole tail = id). Data attribute на row = `file_${id}` in either case.
  let activeKey = null;
  if (match) {
    const tail = match[1];
    const KNOWN_PROVIDERS = ['google_drive', 'yandex_disk'];
    const providerPrefix = KNOWN_PROVIDERS.find(p => tail.startsWith(encodeURIComponent(p) + '/'));
    const idRaw = providerPrefix ? tail.slice(encodeURIComponent(providerPrefix).length + 1) : tail;
    activeKey = `file_${decodeURIComponent(idRaw)}`;
  }
  document.querySelectorAll('#tree .tree-row').forEach(row => {
    const key = row.getAttribute('data-node-key');
    if (key === activeKey) {
      // Add active bg (preserve padding-left)
      const current = row.getAttribute('style') || '';
      if (!current.includes('rgba(244,163,0,0.15)')) {
        row.setAttribute('style', current + 'background: rgba(244,163,0,0.15); color: #f4a300;');
      }
    } else {
      const current = row.getAttribute('style') || '';
      row.setAttribute('style', current.replace(/background:\s*rgba\(244,163,0,0\.15\);\s*color:\s*#f4a300;\s*/g, ''));
    }
  });
}

// ── Hash routing ────────────────────────────────────────────────────────────
function handleRoute() {
  const hash = window.location.hash.slice(1); // strip leading #
  const parts = hash.split('/').filter(Boolean);

  // 60065: derive active tab from route. file/tab/fallback → inbox (they're drill-in of Файлы).
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  let activeTab = 'inbox';
  if (parts[0] === 'settings') activeTab = 'settings';
  else if (parts[0] === 'analytics') activeTab = 'analytics';
  else if (parts[0] === 'modes') activeTab = 'modes';
  document.querySelector(`.tab[data-tab="${activeTab}"]`)?.classList.add('active');

  // 8004 task 686: Settings tab теперь имеет свою tree (settings tree) — tree всегда visible.
  // Legacy settings без /storage — full render как раньше, tree hidden.
  const isStorageSubroute = parts[0] === 'settings' && parts[1] === 'storage';
  document.querySelector('.left-panel')?.classList.toggle('no-tree', activeTab === 'settings' && !isStorageSubroute);

  if (parts.length === 0 || parts[0] === '' || parts[0] === 'inbox' || parts[0] === 'tab' || parts[0] === 'file') {
    // 8009 task 686: restore file tree на switch если currently settings
    if (_lastPopulatedTree !== 'files') {
      populateLeftTree();
      _lastPopulatedTree = 'files';
    }
  }

  if (parts[0] === 'modes') {
    // 8011 task 686: Режимы tab route
    // 8013 task 686: #/modes/file/{provider}/{id} — inline viewer в правой панели, tree сохраняется
    if (parts[1] === 'file' && parts[2] && parts[3]) {
      const KNOWN_PROVIDERS = new Set(['google_drive', 'yandex_disk']);
      const maybeProvider = decodeURIComponent(parts[2]);
      const fileProvider = KNOWN_PROVIDERS.has(maybeProvider) ? maybeProvider : 'google_drive';
      const fileId = decodeURIComponent(parts.slice(3).join('/'));
      // 8015 task 686: deep-link auto-expand tree — resolve file → mode/item → expand nodes → populate → renderFile
      renderFile(fileId, fileProvider);
      (async () => {
        try {
          const loc = await fetchFileLocation(fileId, fileProvider);
          _expandedNodes.modes[loc.mode_code] = true;
          _expandedNodes.items[loc.mode_code] = _expandedNodes.items[loc.mode_code] || {};
          _expandedNodes.items[loc.mode_code][loc.item_id] = true;
          await populateModesTree();
          _lastPopulatedTree = 'modes';
          updateTreeHighlight();
        } catch (e) {
          // Fallback: file not found или endpoint fail → tree collapsed, viewer работает
          if (_lastPopulatedTree !== 'modes') {
            await populateModesTree();
            _lastPopulatedTree = 'modes';
          }
          updateTreeHighlight();
        }
      })();
      return;
    }
    if (_lastPopulatedTree !== 'modes') {
      populateModesTree();
      _lastPopulatedTree = 'modes';
    }
    renderModesInbox();
    updateTreeHighlight();  // 8014 task 686: clear highlight на #/modes root
    return;
  }

  if (parts.length === 0 || parts[0] === '' || parts[0] === 'inbox') {
    renderInbox();
  } else if (parts[0] === 'settings' && parts[1] === 'storage') {
    // 8004 task 686: FSM Settings routes
    if (_lastPopulatedTree !== 'settings') {
      populateSettingsTree();
      _lastPopulatedTree = 'settings';
    } else {
      populateSettingsTree();  // still re-render чтобы highlight сменился при клике на mode leaf
    }
    if (parts[2]) {
      renderStorageMode(decodeURIComponent(parts[2]));
    } else {
      renderStorageOverview();
    }
  } else if (parts[0] === 'settings') {
    renderSettings();
  } else if (parts[0] === 'analytics') {
    // 60066: analytics subroutes для scope selection per D19.
    // #/analytics → global; #/analytics/folder/{id}; #/analytics/file/{provider}/{id}
    let selection = null;
    if (parts[1] === 'folder' && parts[2]) {
      selection = { type: 'folder', id: decodeURIComponent(parts[2]) };
    } else if (parts[1] === 'file' && parts[2] && parts[3]) {
      selection = { type: 'file', provider: decodeURIComponent(parts[2]), id: decodeURIComponent(parts.slice(3).join('/')) };
    }
    renderAnalytics(selection);
  } else if (parts[0] === 'tab' && parts[1]) {
    renderTab(parts[1]);
  } else if (parts[0] === 'file' && parts[1]) {
    // 60063: hash pattern #/file/{provider}/{id} (backwards compat: #/file/{id} → provider=google_drive default).
    // fileId содержит encoded path (Yandex) с `/` — reassemble slice(2).join('/') после decoding parts.
    const KNOWN_PROVIDERS = new Set(['google_drive', 'yandex_disk']);
    const maybeProvider = decodeURIComponent(parts[1]);
    let fileProvider, fileId;
    if (KNOWN_PROVIDERS.has(maybeProvider) && parts[2]) {
      fileProvider = maybeProvider;
      fileId = decodeURIComponent(parts.slice(2).join('/'));
    } else {
      // Legacy: #/file/{id} — default google_drive
      fileProvider = 'google_drive';
      fileId = decodeURIComponent(parts.slice(1).join('/'));
    }
    renderFile(fileId, fileProvider);
  } else {
    renderInbox();
  }
  updateTreeHighlight();
}

function wireTabClicks() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      // 8004 task 686: settings tab default → #/settings/storage (activate FSM overview)
      // 8011 task 686: modes tab default → #/modes (activate Режимы tree)
      if (target === 'settings') {
        window.location.hash = '#/settings/storage';
      } else if (target === 'modes') {
        window.location.hash = '#/modes';
      } else {
        window.location.hash = target === 'inbox' ? '' : `#/${target}`;
      }
    });
  });
  window.addEventListener('hashchange', handleRoute);
}

// ── Provider select modal + Yandex picker (block 60061) ─────────────────────
function showProviderSelectModal(connectedProviders) {
  const activeHandles = new Set((connectedProviders || []).map(c => c.service_handle));
  const hasGoogle = activeHandles.has('google_drive');
  const hasYandex = activeHandles.has('yandex_disk');
  if (!hasGoogle && !hasYandex) {
    alert('Не подключено ни одного провайдера. Подключи в Team Portal → Интеграции.');
    return;
  }

  // 60062: 2-step select — кнопки provider'ов default BTN_SECONDARY,
  // click → selected (BTN_ACTIVE), submit button справа от Отмена активируется.
  const overlay = el('div', { style: MODAL_OVERLAY, id: 'pf-modal-provider-select' });
  const close = () => { overlay.remove(); document.removeEventListener('keydown', onKey); };

  let selectedProvider = null;

  // Style constants для disabled/selected states — inline (не в top-level consts чтобы не расширять globals)
  const BTN_PROVIDER_DEFAULT = BTN_SECONDARY;
  const BTN_PROVIDER_SELECTED = BTN_ACTIVE;
  const BTN_PROVIDER_DISABLED = 'padding: 10px 20px; background: rgba(255,255,255,0.02); color: rgba(255,255,255,0.3); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; cursor: not-allowed; font-size: 13px;';

  // Build provider buttons — conditional disabled attribute (fix bug 60061)
  const buildProviderBtn = (label, provider, isAvailable) => {
    const attrs = {
      style: isAvailable ? BTN_PROVIDER_DEFAULT : BTN_PROVIDER_DISABLED,
      'data-provider': provider,
    };
    if (!isAvailable) attrs.disabled = 'disabled';
    else attrs.onclick = () => {
      selectedProvider = provider;
      // Re-style all provider buttons
      btnGoogle.setAttribute('style', selectedProvider === 'google_drive' ? BTN_PROVIDER_SELECTED : (hasGoogle ? BTN_PROVIDER_DEFAULT : BTN_PROVIDER_DISABLED));
      btnYandex.setAttribute('style', selectedProvider === 'yandex_disk' ? BTN_PROVIDER_SELECTED : (hasYandex ? BTN_PROVIDER_DEFAULT : BTN_PROVIDER_DISABLED));
      // Activate submit
      submitBtn.removeAttribute('disabled');
      submitBtn.setAttribute('style', BTN_ACTIVE);
    };
    return el('button', attrs, label);
  };

  const btnGoogle = buildProviderBtn('🅶  Google Drive' + (hasGoogle ? '' : '  (не подключён)'), 'google_drive', hasGoogle);
  const btnYandex = buildProviderBtn('🅨  Яндекс Диск' + (hasYandex ? '' : '  (не подключён)'), 'yandex_disk', hasYandex);

  const cancelBtn = el('button', { style: BTN_SECONDARY, onclick: close }, 'Отмена');
  const submitBtn = el('button', {
    style: BTN_PROVIDER_DISABLED,
    disabled: 'disabled',
    onclick: () => {
      if (!selectedProvider) return;
      close();
      if (selectedProvider === 'google_drive') showPicker();
      else if (selectedProvider === 'yandex_disk') showYandexPicker();
    },
  }, 'Выбрать папку →');

  const card = el('div', { style: MODAL_CARD },
    el('h2', { style: 'margin: 0 0 4px; font-size: 18px' }, 'Откуда выбрать папку?'),
    el('p', { style: 'margin: 0 0 20px; opacity: 0.6; font-size: 13px' },
      'Выбери провайдера — затем нажми «Выбрать папку».'
    ),
    el('div', { style: 'display: flex; flex-direction: column; gap: 10px' }, btnGoogle, btnYandex),
    el('div', { style: 'display: flex; gap: 10px; justify-content: flex-end; margin-top: 24px' }, cancelBtn, submitBtn),
  );
  overlay.onclick = (ev) => { if (ev.target === overlay) close(); };
  const onKey = (ev) => { if (ev.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
}

// Yandex picker modal — recursive tree browser (Yandex не имеет ready-made SDK,
// строим своё UI через folder_tree.php?provider=yandex_disk).
function showYandexPicker() {
  const overlay = el('div', { style: MODAL_OVERLAY, id: 'pf-modal-yandex-picker' });
  const close = () => overlay.remove();

  // Selected folder state (updated when user clicks a folder row в tree)
  let selectedPath = null;
  let selectedName = null;

  const statusText = el('div', { style: 'font-size: 12px; opacity: 0.6; min-height: 16px; margin-top: 8px' }, 'Раскрой папки и выбери одну для подключения.');
  const submitBtn = el('button', { style: BTN_ACTIVE, disabled: 'disabled' }, 'Подключить');
  const cancelBtn = el('button', { style: BTN_SECONDARY, onclick: close }, 'Отмена');

  const treeContainer = el('div', { style: 'max-height: 60vh; overflow-y: auto; margin-top: 12px; padding: 8px; background: #0f0f0f; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08)' });

  // Custom tree node factory — click on folder row = select it (highlight) + set state.
  // Click on arrow = expand/collapse via folder_tree.php?provider=yandex_disk.
  const YP_CACHE = new Map(); // separate cache для Yandex picker (не conflict с main TREE_CACHE)

  const renderYNode = (path, name, depth) => {
    const wrapper = el('div', {});
    const arrow = el('span', { style: TREE_ARROW_STYLE }, '▸');
    const icon = el('span', {}, '📁');
    const label = el('span', { style: 'flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap' }, name);
    const row = el('div', {
      style: TREE_ROW_STYLE + `padding-left: ${8 + depth * 16}px;`,
    }, arrow, icon, label);
    const children = el('div', { style: 'display: none' });

    let expanded = false;
    const toggle = async (ev) => {
      if (ev) ev.stopPropagation();
      if (expanded) {
        children.style.display = 'none';
        arrow.textContent = '▸';
        expanded = false;
        return;
      }
      expanded = true;
      arrow.textContent = '▾';
      children.style.display = 'block';
      const cached = YP_CACHE.get(path);
      if (!cached) {
        children.replaceChildren(el('div', { style: TREE_LOADING_STYLE + `padding-left: ${8 + (depth + 1) * 16}px` }, 'Загрузка…'));
        try {
          const data = await apiFetchPF(`folder_tree.php?folder_id=${encodeURIComponent(path)}&provider=yandex_disk`);
          YP_CACHE.set(path, data);
        } catch (e) {
          children.replaceChildren(el('div', { style: TREE_LOADING_STYLE + `padding-left: ${8 + (depth + 1) * 16}px; color: #f4a300` }, `Ошибка: ${String(e.message || e)}`));
          return;
        }
      }
      const data = YP_CACHE.get(path);
      const folderNodes = (data.folders || []).map(f => renderYNode(f.id, f.name, depth + 1));
      if (folderNodes.length === 0) {
        children.replaceChildren(el('div', { style: TREE_LOADING_STYLE + `padding-left: ${8 + (depth + 1) * 16}px` }, 'Пусто'));
      } else {
        children.replaceChildren(...folderNodes);
      }
    };

    // Click на row = select folder (не toggle). Click strictly на arrow = expand/collapse.
    // Simpler UX: arrow toggle, rest of row = select.
    arrow.onclick = (ev) => { ev.stopPropagation(); toggle(); };
    row.onclick = () => {
      // Clear previous selection
      treeContainer.querySelectorAll('[data-yp-selected="1"]').forEach(r => {
        r.setAttribute('data-yp-selected', '0');
        r.style.background = 'transparent';
        r.style.color = '';
      });
      row.setAttribute('data-yp-selected', '1');
      row.style.background = 'rgba(244,163,0,0.15)';
      row.style.color = '#f4a300';
      selectedPath = path;
      selectedName = name;
      submitBtn.removeAttribute('disabled');
      statusText.textContent = `Выбрано: ${name} (${path})`;
    };
    wrapper.appendChild(row);
    wrapper.appendChild(children);
    return wrapper;
  };

  // Initial: fetch root '/' и рендерим top-level folders
  treeContainer.replaceChildren(el('div', { style: TREE_LOADING_STYLE }, 'Загрузка корня Yandex Диска…'));
  apiFetchPF('folder_tree.php?folder_id=' + encodeURIComponent('/') + '&provider=yandex_disk')
    .then(data => {
      YP_CACHE.set('/', data);
      const rootNodes = (data.folders || []).map(f => renderYNode(f.id, f.name, 0));
      if (rootNodes.length === 0) {
        treeContainer.replaceChildren(el('div', { style: TREE_LOADING_STYLE }, 'Нет папок в корне Yandex Диска.'));
      } else {
        treeContainer.replaceChildren(...rootNodes);
      }
    })
    .catch(e => {
      treeContainer.replaceChildren(el('div', { style: TREE_LOADING_STYLE + '; color: #f4a300' }, `Ошибка: ${String(e.message || e)}`));
    });

  const submit = async () => {
    if (!selectedPath) return;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Подключаем…';
    try {
      await apiFetchPF('settings/tabs_add.php', {
        method: 'POST',
        body: { gdrive_folder_id: selectedPath, display_name: selectedName, provider: 'yandex_disk' },
      });
      close();
      await refreshSettingsSection();
    } catch (e) {
      statusText.textContent = `Не удалось подключить: ${String(e.message || e)}`;
      statusText.style.color = '#f4a300';
      submitBtn.disabled = false;
      submitBtn.textContent = 'Подключить';
    }
  };
  submitBtn.onclick = submit;

  const card = el('div', { style: MODAL_CARD + 'max-width: 620px;' },
    el('h2', { style: 'margin: 0 0 4px; font-size: 18px' }, '🅨 Выбрать папку из Яндекс Диска'),
    el('p', { style: 'margin: 0 0 8px; opacity: 0.6; font-size: 13px' },
      'Раскрой ▸ чтобы увидеть содержимое папки. Клик по названию — выбор.'
    ),
    treeContainer,
    statusText,
    el('div', { style: 'display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px' },
      cancelBtn, submitBtn,
    ),
  );
  overlay.onclick = (ev) => { if (ev.target === overlay) close(); };
  const onKey = (ev) => { if (ev.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); } };
  document.addEventListener('keydown', onKey);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
}

// ── Boot ────────────────────────────────────────────────────────────────────
(async function boot() {
  const state = await verifySession();
  if (!state) return; // redirect or error already rendered

  window._pfState = state;

  if (!state.tenant_code || !state.employee_id) {
    renderNoTenantContext();
    return;
  }

  renderContextHeader(state);
  wireTabClicks();
  handleRoute();

  // Populate left tree with tabs (block 60052)
  populateLeftTree();
})();
