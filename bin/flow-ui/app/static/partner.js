// partner.js — Partner Portal SPA (task 624, block 8 folder navigation)
// Uses PARTNER_TOKEN from template. Endpoints: /api/extranet/{token}/{info,tree,file}
// (renamed from /api/partner in task 695 block 24 — the portal serves clients,
// students and contractors, not only partners; the old address still redirects)

const TOKEN = window.PARTNER_TOKEN;
const API_BASE = `/api/extranet/${TOKEN}`;

// ── Media renderer (block 677-2) ─────────────────────────────
const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "svg", "webp", "avif", "bmp", "ico"]);
const AUDIO_EXTS = new Set(["mp3", "wav", "m4a", "ogg", "oga", "flac", "aac", "opus"]);
const VIDEO_EXTS = new Set(["mp4", "webm", "mov", "m4v", "avi", "mkv"]);
const CODE_EXTS = new Set([
  "py", "js", "ts", "tsx", "jsx", "css", "scss", "sh", "bash", "zsh",
  "sql", "html", "xml", "yml", "yaml", "json", "toml", "ini", "conf",
  "rb", "go", "rs", "java", "c", "cpp", "h", "swift", "kt", "php",
]);

function getMediaKind(ext) {
  ext = (ext || "").toLowerCase();
  if (!ext) return "other";
  if (ext === "md" || ext === "markdown") return "md";
  if (ext === "pdf") return "pdf";
  if (IMAGE_EXTS.has(ext)) return "image";
  if (AUDIO_EXTS.has(ext)) return "audio";
  if (VIDEO_EXTS.has(ext)) return "video";
  if (CODE_EXTS.has(ext)) return "code";
  return "other";
}

function _escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function _fmtSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
// ── Lightbox (block 677-5) ───────────────────────────────
const _lightbox = {
  overlay: null,
  imgEl: null,
  counterEl: null,
  images: [],
  currentIdx: 0,
  touchStartX: null,
  keyHandler: null,
};

function _lbBuildOverlay() {
  if (_lightbox.overlay) return _lightbox.overlay;
  const ov = document.createElement("div");
  ov.className = "lightbox";
  ov.innerHTML = `
    <div class="lightbox-counter"><span data-idx>1</span> / <span data-total>1</span></div>
    <button class="lightbox-close" aria-label="Закрыть">×</button>
    <button class="lightbox-arrow lightbox-arrow-prev" aria-label="Предыдущая">‹</button>
    <img class="lightbox-image" alt="">
    <button class="lightbox-arrow lightbox-arrow-next" aria-label="Следующая">›</button>
  `;
  ov.querySelector(".lightbox-close").addEventListener("click", closeLightbox);
  ov.querySelector(".lightbox-arrow-prev").addEventListener("click", (e) => { e.stopPropagation(); navigateLightbox(-1); });
  ov.querySelector(".lightbox-arrow-next").addEventListener("click", (e) => { e.stopPropagation(); navigateLightbox(1); });
  ov.addEventListener("click", (e) => { if (e.target === ov) closeLightbox(); });
  ov.addEventListener("touchstart", (e) => { _lightbox.touchStartX = e.changedTouches[0].screenX; }, { passive: true });
  ov.addEventListener("touchend", (e) => {
    if (_lightbox.touchStartX === null) return;
    const dx = e.changedTouches[0].screenX - _lightbox.touchStartX;
    if (Math.abs(dx) > 50) navigateLightbox(dx > 0 ? -1 : 1);
    _lightbox.touchStartX = null;
  }, { passive: true });
  document.body.appendChild(ov);
  _lightbox.overlay = ov;
  _lightbox.imgEl = ov.querySelector(".lightbox-image");
  _lightbox.counterEl = ov.querySelector(".lightbox-counter");
  return ov;
}

function _lbPreload(idx) {
  if (idx < 0 || idx >= _lightbox.images.length) return;
  const img = new Image();
  img.src = `${API_BASE}/asset?path=${encodeURIComponent(_lightbox.images[idx].path)}`;
}

function _lbShow(idx) {
  if (idx < 0 || idx >= _lightbox.images.length) return;
  _lightbox.currentIdx = idx;
  const item = _lightbox.images[idx];
  _lightbox.imgEl.src = `${API_BASE}/asset?path=${encodeURIComponent(item.path)}`;
  _lightbox.imgEl.alt = item.name;
  _lightbox.counterEl.querySelector("[data-idx]").textContent = String(idx + 1);
  _lightbox.counterEl.querySelector("[data-total]").textContent = String(_lightbox.images.length);
  _lbPreload(idx + 1);
  _lbPreload(idx - 1);
}

function navigateLightbox(delta) {
  const n = _lightbox.images.length;
  if (n <= 1) return;
  const next = (_lightbox.currentIdx + delta + n) % n;
  _lbShow(next);
}

async function openLightbox(path) {
  const folder = path.includes("/") ? path.substring(0, path.lastIndexOf("/")) : "";
  try {
    const list = await api(`/images-in-folder?path=${encodeURIComponent(folder)}`);
    if (!Array.isArray(list) || list.length === 0) return;
    _lightbox.images = list;
    const idx = list.findIndex(item => item.path === path);
    _lightbox.currentIdx = idx >= 0 ? idx : 0;
    _lbBuildOverlay();
    _lightbox.overlay.classList.add("lightbox-open");
    document.body.style.overflow = "hidden";
    _lbShow(_lightbox.currentIdx);
    _lightbox.keyHandler = (e) => {
      if (e.key === "Escape") closeLightbox();
      else if (e.key === "ArrowLeft") navigateLightbox(-1);
      else if (e.key === "ArrowRight") navigateLightbox(1);
    };
    document.addEventListener("keydown", _lightbox.keyHandler);
  } catch (err) {
    console.warn("Lightbox open failed:", err);
  }
}

function closeLightbox() {
  if (!_lightbox.overlay) return;
  _lightbox.overlay.classList.remove("lightbox-open");
  document.body.style.overflow = "";
  if (_lightbox.keyHandler) {
    document.removeEventListener("keydown", _lightbox.keyHandler);
    _lightbox.keyHandler = null;
  }
}

function renderPdf(url) {
  return `<iframe class="media-pdf" src="${url}" type="application/pdf"></iframe>`;
}
function renderImage(url, name, path) {
  const pathAttr = path ? ` data-lb-path="${_escapeHtml(path)}" onclick="openLightbox(this.dataset.lbPath)" style="cursor:zoom-in"` : "";
  return `<img class="media-image" src="${url}" alt="${_escapeHtml(name || "")}"${pathAttr}>`;
}
function renderAudio(url) {
  return `<audio class="media-audio" controls src="${url}"></audio>`;
}
function renderVideo(url) {
  return `<video class="media-video" controls src="${url}"></video>`;
}
function renderDownload(url, name, size) {
  const sizeStr = _fmtSize(size);
  return `<div class="media-download">
    <div class="media-download-icon">📄</div>
    <div class="media-download-name"><strong>${_escapeHtml(name || "file")}</strong>${sizeStr ? ` <span class="muted">— ${sizeStr}</span>` : ""}</div>
    <a class="media-download-btn" href="${url}" download="${_escapeHtml(name || "")}">⬇ Скачать</a>
  </div>`;
}

// Navigation state — current directory path (empty = root)

async function api(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    if (res.status === 404) throw new Error("Не найдено");
    if (res.status === 403) throw new Error("Доступ запрещён");
    throw new Error(`Ошибка ${res.status}`);
  }
  return res.json();
}

async function loadInfo() {
  try {
    const info = await api("/info");
    document.getElementById("partner-name").textContent = info.name;
  } catch (err) {
    document.getElementById("partner-name").textContent = "⚠️ Неверная ссылка";
    document.getElementById("tree").innerHTML =
      '<div class="muted">Проверь ссылку — токен недействителен или устарел.</div>';
    throw err;
  }
}

function renderBreadcrumb() {
  const bc = document.getElementById("breadcrumb");
  if (!bc) return;
  bc.innerHTML = "";

  // Только «Корень». Сегменты пути исчезли вместе с самим состоянием
  // «нахожусь внутри папки»: дерево раскрывается, а не проваливается, и
  // показывать было нечего, кроме технического «fd › 142». Ссылка остаётся —
  // она ведёт на обложку (задача 706, блок 232).
  const rootLink = document.createElement("a");
  rootLink.href = "#";
  rootLink.textContent = "🏠 Корень";
  rootLink.addEventListener("click", (e) => {
    e.preventDefault();
    navigateTo("");
  });
  bc.appendChild(rootLink);
}

/** Возврат на стартовый экран кабинета.
 *
 *  Зовётся только с пустым путём: после блока 232 клик по папке раскрывает её
 *  на месте, а не уводит внутрь, и «перейти в папку» как действие исчезло.
 *  Точки входа — «🏠 Корень» в крошках и логотип в шапке.
 *
 *  Обложка показывается ПЕРЕД деревом. Раньше было наоборот: дерево само
 *  открывало первый документ корня, и обложка появлялась, только если открывать
 *  было нечего. Пока в корне лежали одни папки, это работало; как только корень
 *  стал плоским, автооткрытие начало срабатывать всегда, и обложка перестала
 *  открываться совсем. Обложка — заявленный стартовый экран, первый документ в
 *  списке — случайность раскладки.
 */
async function navigateTo() {
  // Файл закрыт — прячем все кнопки шапки.
  applyHeaderButtons(null);
  const coverShown = await showCover();
  // Очистка ДО дерева, а не после: дерево может само открыть первый документ
  // (портал без обложки), и очистка следом стёрла бы его.
  if (!coverShown) clearContent();
  await loadTree({ autoOpen: !coverShown });
}

/** Подсказка зависит от того, что человек реально видит.
 *
 *  На узком экране левой панели нет вовсе (style.css прячет .left-panel), и
 *  «слева» отправляло в пустоту: там нечего выбирать. Порог 768px — тот же,
 *  что у медиазапроса; держать их в согласии обязательно, иначе текст и
 *  вёрстка разойдутся. Задача 718, блок 20130.
 */
function emptyHintText() {
  const narrow = window.matchMedia("(max-width: 768px)").matches;
  return narrow ? "Выберите документ в списке снизу." : "Выбери файл слева.";
}

function clearContent() {
  const content = document.getElementById("content");
  if (content) {
    content.innerHTML = `<div class="muted center">${emptyHintText()}</div>`;
  }
}

// ── Кнопки шапки по виду материала (блок 71050) ──────────────
// Виды, у которых есть что копировать текстом.
const COPYABLE_KINDS = ["text", "doc", "md", "code", "other"];
// Виды, которые имеет смысл печатать. Аудио и видео печатать нечего.
// Страницы (page_html) нет ни в одном из двух списков намеренно: её содержимое
// живёт в песочнице, и ни копирование текста, ни печать до него не дотянутся.
// Показывать кнопку, которая ничего не делает, хуже, чем не показывать.
const PRINTABLE_KINDS = ["text", "doc", "md", "code", "other", "pdf", "image"];

/** Какие кнопки показать для открытого материала.
 *
 *  Одна функция на оба места — открытие файла и уход с него. Раньше показ и
 *  сброс жили порознь двумя парами строк, и правка одного места без другого
 *  оставляла кнопку висеть от предыдущего материала. У счёта-PDF при этом
 *  предлагалось «Скопировать текст», а копировать там нечего — с этого блок и
 *  начался.
 *
 *  @param info null — файл закрыт, спрятать всё. Иначе {kind, path, downloadUrl, name}
 */
function applyHeaderButtons(info) {
  const copyBtn = document.getElementById("copy-btn");
  const printBtn = document.getElementById("print-btn");
  const downloadBtn = document.getElementById("download-btn");

  if (!info) {
    [copyBtn, printBtn, downloadBtn].forEach(b => { if (b) b.style.display = "none"; });
    return;
  }

  if (copyBtn) {
    copyBtn.style.display = COPYABLE_KINDS.includes(info.kind) ? "" : "none";
    copyBtn.dataset.path = info.path;
  }
  if (printBtn) {
    printBtn.style.display = PRINTABLE_KINDS.includes(info.kind) ? "" : "none";
  }
  if (downloadBtn) {
    // Скачать можно всё, у чего есть байты. У материала «наружу» файла на нашей
    // стороне нет вовсе — там своя ссылка в теле страницы.
    const can = Boolean(info.downloadUrl) && info.kind !== "external";
    downloadBtn.style.display = can ? "" : "none";
    if (can) {
      downloadBtn.href = info.downloadUrl;
      // Имя для сохранения считает сервер (блок 71070): к человеческому
      // названию дописано расширение из mime. Сами дописать не можем — у
      // витрины нет ни имени файла, ни типа. Полагаться на то, что браузер
      // допишет расширение сам, нельзя: у счёта название кончается датой
      // «19.08.2026», и он принял «.2026» за расширение.
      downloadBtn.setAttribute("download", info.downloadName || info.name || "");
    }
  }
}

/** Показать ожидание в контейнере (блок 71060).
 *
 *  Одна разметка на оба места, где мы действительно ждём ответа — открытие
 *  материала и сборка проекции. Раньше в обоих местах стоял свой div, и третье
 *  место появилось бы копипастой.
 *
 *  Встроенным видам (pdf, картинка, аудио, видео) спиннер НЕ ставим: там
 *  разметка подставляется мгновенно, а грузит уже сам браузер внутри рамки —
 *  наш спиннер исчез бы раньше содержимого и соврал бы. Индикатор, который
 *  врёт, приучает на себя не смотреть.
 */
function showLoading(container, text) {
  if (!container) return;
  container.innerHTML =
    `<div class="load-wrap"><span class="load-spin"></span>` +
    `<span>${_escapeHtml(text || "Загрузка…")}</span></div>`;
}

// ── Собранные страницы (task 701 block 2) ────────────────────
// Кэш записей дерева нужен, чтобы openFile мог проверить наличие парной
// страницы без лишнего запроса /tree на каждое открытие документа.
let treeEntries = [];

/** Есть ли у документа собранная страница.
 *
 *  Признак приходит из дерева, а НЕ выводится из имени файла. В ветке
 *  Экстранета имён файлов нет вообще — там путь вида ep/{id}, — поэтому
 *  правило по расширению работало бы только в двух ветках из трёх
 *  (задача 701, decision-02). Служебный файл страницы в дерево не попадает:
 *  его убирает бэкенд, а не этот фильтр.
 */
function hasPageFor(docPath) {
  return Boolean(epEntryFor(docPath)?.has_page);
}

/** Запись дерева по пути. */
function epEntryFor(docPath) {
  return treeEntries.find(e => !e.is_dir && String(e.path) === String(docPath));
}

/** Вид материала Экстранета — тот, что прислал сервер (задача 695 block 71010).
 *
 *  Не getMediaKind: у материала Экстранета нет расширения. Путь — ep/{id},
 *  имя вида «Счёт № 38 от 19.08.2026», а тип известен только каталогу тенанта.
 *  Ровно та же причина, по которой has_page едет с сервера.
 */
function epKindFor(docPath) {
  return epEntryFor(docPath)?.kind || "";
}

// Виды, которые браузер рисует сам, получив адрес. Зеркало KINDS_INLINE_ASSET
// в app/extranet_resolver.py.
const EP_INLINE_KINDS = ["pdf", "image", "audio", "video"];

/** Страница целиком в изолированном фрейме.
 *
 * Песочница `allow-scripts` без `allow-same-origin` даёт фрейму уникальный
 * непрозрачный источник: скрипты внутри работают, доступа к родительскому
 * документу и к магик-токену в его адресе нет.
 *
 * Наблюдатель высоты дописывается порталом, а не требуется от страницы. Иначе
 * каждая новая страница обязана была бы помнить про этот протокол, а забытый
 * скрипт давал бы полосу прокрутки внутри фрейма — читателю пришлось бы
 * крутить два уровня сразу.
 */
function buildPageFrame(html) {
  // Механика песочницы живёт в static/sandbox-frame.js — её делит с китом
  // задач, где рисуется описание (задача 706, блок 2332). Здесь остаётся
  // только знание портала: из какого узла фрейм однажды исчезнет.
  return window.buildSandboxFrame(
    html, document.getElementById("content"), undefined, openFromFrame,
    // true — остаёмся на документе: слайдер откроется поверх него
    (id) => openTaskFromFrame(id, true),
    panelStatuses);
}

/** Карта «ключ панели → статус задачи» для полосы прогресса документа.
 *
 *  Своим запросом, а не из бокового списка: `loadTasksSidebar` задачи
 *  выбрасывает, оставляя только встречи со счётчиком, и зовётся лишь из
 *  `switchTab("tasks")`. На документе вкладку задач могли не открывать ни разу
 *  — тем более после блока 208, который перестал её переключать.
 *
 *  Обещание кэшируется, а не результат: два фрейма на экране спросят
 *  одновременно, и без этого ушло бы два запроса. Живёт до перезагрузки —
 *  цифра обновляется тогда же, когда человек заново открывает документ.
 */
let panelStatusesPromise = null;
function panelStatuses() {
  if (!panelStatusesPromise) {
    panelStatusesPromise = fetch(`/api/tasks/${TOKEN}/tasks`)
      .then(r => r.json())
      .then(data => {
        const map = {};
        (data.tasks || []).forEach(t => {
          if (t.panel_key) map[t.panel_key] = t.status;
        });
        return map;
      })
      // Не получилось — забываем обещание: следующее открытие документа
      // попробует снова, а не унаследует пустую карту навсегда.
      .catch(() => { panelStatusesPromise = null; return null; });
  }
  return panelStatusesPromise;
}

/** SHA-256 от байтов UTF-8, hex нижним регистром — см. PAGE_FORMAT.md § 3.
 *  Возвращает null если crypto.subtle недоступен (портал открыт по HTTP):
 *  тогда страница показывается без пометки, а не ломается. */
async function sha256Hex(text) {
  try {
    if (!window.crypto || !window.crypto.subtle) return null;
    const bytes = new TextEncoder().encode(text);
    const buf = await window.crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(buf))
      .map(b => b.toString(16).padStart(2, "0"))
      .join("");
  } catch (err) {
    return null;
  }
}

/** Обложка портала — что читатель видит до того, как что-то выбрал.
 *
 * Ручка отвечает 404, когда обложки нет, и это обычный случай, а не ошибка:
 * портал ведёт себя как раньше и показывает подсказку. Рисуется тем же
 * изолированным фреймом, что и остальные страницы (задача 706, блок 200).
 */
async function showCover() {
  const content = document.getElementById("content");
  if (!content) return false;
  try {
    const data = await api("/cover");
    if (!data || !data.content) return false;
    content.innerHTML = "";
    content.appendChild(buildPageFrame(data.content));
    return true;
  } catch (err) {
    return false;
  }
}

// ── Дерево кабинета ──────────────────────────────────────────────────────
//
// Раньше клик по папке уводил ВНУТРЬ: currentPath переписывался, список
// перерисовывался содержимым папки, соседи исчезали, сверху появлялось
// техническое «fd › 142». Человек терял из виду кабинет целиком ради одного
// документа. Теперь папка раскрывается под собой, а всё остальное остаётся
// на экране — оглавление, а не файловый менеджер (задача 706, блок 232).

/** Записи по уровням: путь папки → её содержимое. Корень под пустым ключом. */
let treeLevels = {};
/** Пути раскрытых папок. Живёт до перезагрузки страницы. */
const expandedPaths = new Set();

// Что открыто прямо сейчас. Раньше это жило только классом .active на строке
// дерева, но на узком экране дерева нет вовсе — шторке пришлось бы читать
// разметку скрытого элемента. Отдельное состояние честнее и переживает
// перерисовку списка (задача 718, блок 20130).
let currentDocPath = null;

/** Записи уровня. Загруженный уровень берётся из памяти: состав материалов
 *  в течение сессии не меняется, гонять сеть на каждое раскрытие незачем. */
async function ensureLevel(path) {
  if (treeLevels[path]) return treeLevels[path];
  const query = path ? `/tree?path=${encodeURIComponent(path)}` : "/tree";
  const raw = (await api(query)) || [];
  // Папки вперёд файлов — и только это. Порядок внутри группы приходит с
  // бэкенда: папки ORDER BY sort_order, материалы ORDER BY is_extra, sort_order.
  // Это порядок, который человек задал через go-extranet-folder, и алфавит его
  // затирал. Сортировка стабильна (ES2019), поэтому группировка не переставляет
  // соседей внутри группы.
  //
  // Применяется К УРОВНЮ, а не ко всему дереву: после склейки уровней общая
  // сортировка утащила бы вложенный документ наверх, к папкам корня.
  const entries = raw.slice().sort((a, b) => (a.is_dir === b.is_dir ? 0 : a.is_dir ? -1 : 1));
  treeLevels[path] = entries;
  // treeEntries читает epEntryFor, а через неё hasPageFor — признак «у документа
  // есть свёрстанная страница», по которому рисуется переключатель проекций.
  // Поэтому здесь ВСЕ загруженные уровни: при раскрытом дереве видно больше,
  // чем один уровень, и документ из папки иначе открылся бы без переключателя.
  treeEntries = Object.values(treeLevels).flat();
  return entries;
}

/** Плоский список того, что сейчас видно: обход вглубь только у раскрытых. */
function flattenTree(path = "", depth = 0, out = []) {
  for (const entry of treeLevels[path] || []) {
    out.push({ entry, depth });
    if (entry.is_dir && expandedPaths.has(entry.path)) {
      flattenTree(entry.path, depth + 1, out);
    }
  }
  return out;
}

function renderTree() {
  const tree = document.getElementById("tree");
  if (!tree) return;
  const rows = flattenTree();
  if (rows.length === 0) {
    tree.innerHTML = '<div class="muted">Пусто.</div>';
    return;
  }
  tree.innerHTML = "";
  for (const { entry, depth } of rows) {
    const open = entry.is_dir && expandedPaths.has(entry.path);
    const item = document.createElement("div");
    item.className = "tree-item" + (entry.is_dir ? " is-dir" : " is-file") + (open ? " is-open" : "");
    item.dataset.path = entry.path;
    item.dataset.isDir = String(entry.is_dir);
    item.dataset.depth = String(depth);
    item.style.paddingLeft = (10 + depth * 16) + "px";
    const icon = entry.is_dir ? (open ? "📂" : "📁") : "📄";
    item.innerHTML = `<span class="tree-icon">${icon}</span> <span class="tree-name">${entry.name}</span>`;
    if (entry.is_dir) {
      item.addEventListener("click", () => toggleFolder(entry.path));
    } else {
      item.addEventListener("click", () => openFile(entry.path, item));
    }
    tree.appendChild(item);
  }
  renderMobilePicker(rows);
}

/** Открыть документ по просьбе страницы или описания задачи.
 *
 *  Просить может только фрейм, и только про ЭТОТ портал: путь сверяется с тем,
 *  что портал сам показал в дереве. Белый список нужен не от чужого портала —
 *  токен свой, чужой недостижим, — а от содержимого: разметку описания задачи
 *  правит клиент, и без проверки можно было бы попросить открыть что угодно
 *  (задача 706, блок 226).
 */
async function openFromFrame(path) {
  // Уровень с документом мог быть не загружен: папку ещё не открывали.
  // Догружаем папки корня — глубже не идём, вложенных папок в папках нет.
  let parent = findLevelOf(path);
  if (parent === null) {
    for (const entry of treeLevels[""] || []) {
      if (entry.is_dir) await ensureLevel(entry.path);
    }
    parent = findLevelOf(path);
  }
  if (parent === null) return;   // нет в дереве — не наше дело

  if (parent) {
    expandedPaths.add(parent);
    renderTree();
  }
  const item = document.querySelector(`.tree-item[data-path="${CSS.escape(path)}"]`);
  openFile(path, item);
}

/** Открыть задачу по просьбе страницы кабинета или по адресу.
 *
 *  У функции два вызывающих, и им нужно разное.
 *
 *  ИЗ ДОКУМЕНТА (`keepBackground = true`). Слайдер открывается поверх текста,
 *  вкладка не переключается. Прежде здесь стоял `switchTab("tasks")` с доводом
 *  «человек не должен догадываться, что задачи живут на соседней вкладке»
 *  (задача 706, блок 2371). Довод верен для короткого документа и оборачивается
 *  против себя на длинном: домашка в пятнадцать пунктов, человека выбрасывает
 *  из текста, место чтения теряется. Закрыл слайдер — остался там же, где читал.
 *
 *  ИЗ АДРЕСА (`keepBackground = false`, умолчание). Ссылка `#task/NNN` приходит
 *  из письма или чата, документа на экране нет вовсе — вкладка задач там
 *  единственный осмысленный фон. Поведение прежнее.
 *
 *  Слайдер добавляется в `document.body` (кит задач), поэтому рисуется поверх
 *  чего угодно. Переключение вкладки было нужно только чтобы кит успел
 *  смонтироваться — теперь монтируем его явно и молча.
 */
function openTaskFromFrame(taskId, keepBackground) {
  if (keepBackground) {
    // Панель задач останется скрытой. Кит переберётся при первом настоящем
    // переходе на вкладку: switchTab зовёт монтирование каждый раз.
    taskOpenKeepsBackground = true;
    mountTaskEngine();
  } else {
    taskOpenKeepsBackground = false;
    switchTab("tasks");
  }
  const open = () => {
    if (taskEngineWidget && typeof taskEngineWidget.openTaskById === "function") {
      taskEngineWidget.openTaskById(taskId);
    }
  };
  // Кит монтируется при первом показе вкладки — на холодном старте его ещё нет.
  // Ждём появления, а не гадаем задержкой: сам кит доберёт задачи, если список
  // ещё не пришёл.
  if (taskEngineWidget) { open(); return; }
  let tries = 0;
  const wait = setInterval(() => {
    if (taskEngineWidget || ++tries > 20) { clearInterval(wait); open(); }
  }, 100);
}

/** Путь папки, в которой лежит документ. Пустая строка — корень, null — нет. */
function findLevelOf(path) {
  for (const [levelPath, entries] of Object.entries(treeLevels)) {
    if (entries.some(e => !e.is_dir && String(e.path) === String(path))) return levelPath;
  }
  return null;
}

async function toggleFolder(path) {
  if (expandedPaths.has(path)) {
    expandedPaths.delete(path);
  } else {
    await ensureLevel(path);
    expandedPaths.add(path);
  }
  renderTree();
}

/** На узком экране левой панели нет вовсе (style.css прячет её целиком), и эта
 *  шторка — единственная навигация.
 *
 *  Записи берутся из тех же `rows`, что рисуют дерево, — источник правды один,
 *  расхождения между экранами быть не может.
 *
 *  Раньше здесь был нативный <select>. Он убран (задача 718, блок 20130) по двум
 *  причинам, обе проверены на живом iPhone. Первая: список плоский по природе,
 *  а дерево двухуровневое. Вторая, и главная: iOS закрывает свой picker при
 *  каждом выборе, поэтому путь до документа складывался из четырёх касаний —
 *  открыть, выбрать папку, дождаться закрытия, открыть снова. Здесь папка это
 *  заголовок группы, а не строка выбора: содержимое уже раскрыто, и до любого
 *  документа два касания.
 */
function renderMobilePicker(rows) {
  const list = document.getElementById("mobile-nav-list");
  const pill = document.getElementById("mobile-nav-pill");
  if (!list || !pill) return;

  list.innerHTML = "";
  for (const { entry } of rows) {
    if (entry.is_dir) {
      const head = document.createElement("div");
      head.className = "mobile-nav-group";
      head.textContent = entry.name;
      list.appendChild(head);
      continue;
    }
    const item = document.createElement("button");
    item.type = "button";
    item.className = "mobile-nav-item" + (entry.path === currentDocPath ? " is-active" : "");
    item.dataset.path = entry.path;
    item.textContent = entry.name;
    item.addEventListener("click", () => {
      closeMobileSheet();
      openFile(entry.path);
    });
    list.appendChild(item);
  }

  // На пилюле — то, что открыто. Пустая подпись объясняет, что делать.
  const active = rows.find(r => !r.entry.is_dir && r.entry.path === currentDocPath);
  const label = document.getElementById("mobile-nav-current");
  if (label) label.textContent = active ? active.entry.name : "Выберите документ";
}

/** Переставить выделение и подпись пилюли, не пересобирая список.
 *  Имя документа берём из уже отрисованной кнопки — второго источника не надо. */
function syncMobileNavSelection() {
  const list = document.getElementById("mobile-nav-list");
  const label = document.getElementById("mobile-nav-current");
  if (!list) return;
  let activeName = null;
  list.querySelectorAll(".mobile-nav-item").forEach(el => {
    const hit = el.dataset.path === currentDocPath;
    el.classList.toggle("is-active", hit);
    if (hit) activeName = el.textContent;
  });
  if (label) label.textContent = activeName || "Выберите документ";
}

function openMobileSheet() {
  const sheet = document.getElementById("mobile-nav-sheet");
  const back = document.getElementById("mobile-nav-backdrop");
  const pill = document.getElementById("mobile-nav-pill");
  if (!sheet || !back || !pill) return;
  sheet.hidden = false;
  back.hidden = false;
  pill.setAttribute("aria-expanded", "true");
  // Страница замирает, пока шторка открыта — иначе тач-жест по списку уходит
  // на body и вместо записей едет вся страница. Ровно так же поступает
  // лайтбокс этого же файла, см. openLightbox. Снимается в closeMobileSheet,
  // куда сходятся все четыре выхода. Задача 718, блок 20140.
  document.body.style.overflow = "hidden";
  const act = sheet.querySelector(".mobile-nav-item.is-active");
  if (act && act.scrollIntoView) act.scrollIntoView({ block: "nearest" });
  markSheetOverflow(sheet);
}

/** Пометить шторку классом, когда список в неё не влез. Класс включает
 *  градиент у нижней кромки: без него ровный обрез читается как конец списка,
 *  и клиент решает, что документов больше нет. */
function markSheetOverflow(sheet) {
  if (!sheet) return;
  const more = sheet.scrollHeight - sheet.clientHeight > 4;
  sheet.classList.toggle("has-more", more);
}

function closeMobileSheet() {
  const sheet = document.getElementById("mobile-nav-sheet");
  const back = document.getElementById("mobile-nav-backdrop");
  const pill = document.getElementById("mobile-nav-pill");
  if (!sheet || !back || !pill) return;
  sheet.hidden = true;
  back.hidden = true;
  pill.setAttribute("aria-expanded", "false");
  // Возврат скролла странице. Если это не сработает, клиент получит страницу,
  // которую нельзя листать, и ни одной ошибки в консоли — поэтому снятие живёт
  // здесь, в единственной точке выхода, а не в обработчике одной кнопки.
  document.body.style.overflow = "";
}

/** Обработчики ставятся один раз: renderMobilePicker вызывается на каждую
 *  перерисовку дерева, и навешивать их там значило бы копить дубли. */
function initMobileSheet() {
  const pill = document.getElementById("mobile-nav-pill");
  const back = document.getElementById("mobile-nav-backdrop");
  if (!pill || !back) return;
  pill.addEventListener("click", () => {
    const open = pill.getAttribute("aria-expanded") === "true";
    if (open) closeMobileSheet(); else openMobileSheet();
  });
  back.addEventListener("click", closeMobileSheet);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeMobileSheet();
  });
}

async function loadTree({ autoOpen = true } = {}) {
  const tree = document.getElementById("tree");
  renderBreadcrumb();
  try {
    treeLevels = {};
    expandedPaths.clear();
    const entries = await ensureLevel("");
    renderTree();

    const files = entries.filter(e => !e.is_dir);
    const dirs = entries.filter(e => e.is_dir);

    // Раскрытие папок НЕ зависит от autoOpen — это была ошибка блока 20140.
    // На узком экране шторка это единственная навигация, а строится она из
    // flattenTree(), то есть показывает содержимое только РАСКРЫТЫХ папок.
    // Обложка приходит с autoOpen=false, и пока раскрытие жило внутри ветки
    // автооткрытия, портал с обложкой отдавал шторку с двумя пустыми группами:
    // заголовки «Встречи» и «Документы» без единой записи под ними. Найдено
    // 26.08 замером сразу после выкладки обложки (задача 718, блок 20150).
    //
    // От autoOpen зависит только одно — открывать ли документ самим. Обложка
    // задаёт стартовый экран явно, и подменять его первым попавшимся документом
    // нельзя.
    const narrow = window.matchMedia("(max-width: 768px)").matches;
    const toExpand = narrow
      ? dirs                                                    // все папки — для шторки
      : (autoOpen && files.length === 0 ? dirs.slice(0, 1) : []); // десктоп как было
    let firstNested = null;
    for (const dir of toExpand) {
      const inner = await ensureLevel(dir.path);
      expandedPaths.add(dir.path);
      if (!firstNested) firstNested = (inner || []).find(e => !e.is_dir) || null;
    }
    if (toExpand.length > 0) renderTree();

    // Автооткрытие только когда файлы действительно есть: иначе портал
    // попытается «открыть» папку как документ.
    if (autoOpen) {
      if (files.length > 0) openFile(files[0].path);
      else if (firstNested) openFile(firstNested.path);
    }
  } catch (err) {
    tree.innerHTML = `<div class="muted">Ошибка загрузки: ${err.message}</div>`;
  }
}


/** Рисует одну из двух проекций документа с переключателем между ними.
 *  pagePath — собранная страница, mdPath — исходник (может быть null, если
 *  страница открыта напрямую). active: "page" | "text". */
/** Рисует документ в выбранной проекции.
 *
 *  Путь один — docPath. Проекция выбирается параметром запроса, потому что
 *  это два представления одного документа, а не два файла.
 */
// Загруженные документы: docPath → {page, pageErr, mdText, stale}.
// Держится только в памяти вкладки. В хранилище браузера не уходит намеренно:
// отпечаток source_hash защищает от устаревания лишь при живом сравнении,
// а переживший перезагрузку кэш дал бы шанс показать клиенту вчерашнюю версию.
const projectionCache = new Map();

// Служебный режим: адрес с ?raw=1. Нужен нам, чтобы сверить обе проекции
// одного документа. Клиент видит один документ и не выбирает, в каком виде
// его читать — переключатель убран из клиентского вида решением раунда 3
// блока 5: две проекции это наша внутренняя кухня, не его забота.
const RAW_MODE = new URLSearchParams(location.search).has("raw");

/** Обе проекции документа: из памяти либо из сети при первом обращении. */
async function loadProjections(docPath) {
  const cached = projectionCache.get(docPath);
  if (cached) return cached;

  const url = `/file?path=${encodeURIComponent(docPath)}`;

  let page = null, pageErr = null;
  try {
    const raw = await api(`${url}&projection=page`);
    page = JSON.parse(raw.content);
  } catch (err) {
    pageErr = err.message;
  }

  let mdText = null;
  try {
    mdText = (await api(url)).content;
  } catch (err) {
    mdText = null;
  }

  // Отпечаток считается один раз на загрузку, а не на каждое переключение
  // (PAGE_FORMAT.md § 3).
  let stale = false;
  if (mdText !== null && page && page.source_hash) {
    const actual = await sha256Hex(mdText);
    stale = Boolean(actual && actual !== String(page.source_hash).toLowerCase());
  }

  const entry = { page, pageErr, mdText, stale };
  projectionCache.set(docPath, entry);
  return entry;
}

/** Текст документа в буфер обмена. Действие, а не режим: читателю не нужно
 *  выбирать, в каком виде смотреть документ, ему нужно унести текст к себе. */
async function copyDocumentText(docPath) {
  const btn = document.getElementById("copy-btn");
  if (!btn) return;

  // У документа со страницей текст уже в памяти. У обычного — нет: кэш
  // заполняет только renderProjection, поэтому здесь дочитываем сами.
  let text = (projectionCache.get(docPath) || {}).mdText;
  if (!text) {
    try {
      text = (await api(`/file?path=${encodeURIComponent(docPath)}`)).content;
    } catch (err) {
      text = null;
    }
  }
  // Картинка приезжает data-строкой, видео и архивы — ссылкой. Копировать
  // такое бессмысленно, честнее сказать что не вышло.
  if (!text || text.startsWith("data:") || text.startsWith("external:")) {
    const prev = btn.textContent;
    btn.textContent = "Нечего копировать";
    setTimeout(() => { btn.textContent = prev; }, 2000);
    return;
  }

  let ok = false;
  try {
    // Требует защищённого соединения; по http метода просто нет.
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      ok = true;
    }
  } catch (err) {
    ok = false;
  }
  if (!ok) {
    // Тихий откат, а не исключение в консоль — как в sha256Hex.
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      ok = document.execCommand("copy");
      document.body.removeChild(ta);
    } catch (err) {
      ok = false;
    }
  }

  const was = btn.textContent;
  btn.textContent = ok ? "Скопировано" : "Не получилось";
  setTimeout(() => { btn.textContent = was; }, 2000);
}

document.addEventListener("click", e => {
  const btn = e.target.closest && e.target.closest("#copy-btn");
  if (btn && btn.dataset.path) copyDocumentText(btn.dataset.path);
});

async function renderProjection(docPath, active) {
  const content = document.getElementById("content");

  // Экран гасим только когда данных ещё нет. При переключении между уже
  // загруженными проекциями «Загрузка…» была бы враньём и морганием.
  const warm = projectionCache.has(docPath);
  if (!warm) showLoading(content);

  const { page, pageErr, mdText, stale } = await loadProjections(docPath);

  // Страница собрана раньше правок исходника — показываем текст, он всегда
  // актуален. Раньше здесь была пометка «смотрите во вкладке Текст», но это
  // просьба к читателю обойти НАШУ недоработку: пересобрать страницу обязаны
  // мы. В служебном режиме страница показывается как есть, с пометкой.
  if (stale && !RAW_MODE && mdText !== null) active = "text";

  content.innerHTML = "";

  // Переключатель — только служебный. У клиента выбора нет: он читает документ,
  // а не выбирает его представление.
  if (RAW_MODE && mdText !== null && page) {
    content.appendChild(renderSwitch(docPath, active));
  }

  if (active === "text" && mdText !== null) {
    const box = document.createElement("div");
    box.className = "md-content";
    box.innerHTML = marked.parse(mdText, { breaks: true });
    if (window.DocPatterns) window.DocPatterns.enhance(box);
    content.appendChild(box);
    box.querySelectorAll("pre code").forEach(b => { if (window.hljs) hljs.highlightElement(b); });
    return;
  }

  if (!page) {
    const err = document.createElement("div");
    err.className = "muted center";
    err.textContent = `Файл страницы не открылся: ${pageErr || "неизвестная ошибка"}`;
    content.appendChild(err);
    return;
  }

  // Пометка об устаревании: отпечаток посчитан при загрузке, здесь только
  // показываем результат.
  if (stale && RAW_MODE) {
    const warn = document.createElement("div");
    warn.className = "doc-callout doc-callout--warn doc-stale";
    const lbl = document.createElement("span");
    lbl.className = "doc-callout__label";
    lbl.textContent = "Собрана раньше правок";
    const body = document.createElement("div");
    body.className = "doc-callout__body";
    body.textContent = "Исходный текст изменили после сборки страницы. "
      + "Клиенту вместо неё показывается текст — пересобрать.";
    warn.appendChild(lbl);
    warn.appendChild(body);
    content.appendChild(warn);
  }

  content.appendChild(window.DocBlocks.render(page));
}

/** Две кнопки над содержимым. Активная подсвечена, вторая переключает. */
function renderSwitch(docPath, active) {
  const box = document.createElement("div");
  box.className = "doc-switch";
  [["page", "Страница"], ["text", "Текст"]].forEach(([key, label]) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "doc-switch__btn" + (key === active ? " is-active" : "");
    btn.textContent = label;
    btn.addEventListener("click", () => {
      if (key !== active) renderProjection(docPath, key);
    });
    box.appendChild(btn);
  });
  return box;
}

async function openFile(path, itemEl) {
  const content = document.getElementById("content");
  showLoading(content, "Открываем материал…");

  // Набор кнопок зависит от того, что открыто (блок 71050).
  {
    const entry = epEntryFor(path);
    const isEp = path.startsWith("ep/");
    const kind = isEp ? (entry?.kind || "") : getMediaKind(path.split(".").pop().toLowerCase());
    const fileName = isEp ? (entry?.name || "") : path.split("/").pop();
    applyHeaderButtons({
      kind,
      path,
      name: fileName,
      downloadName: isEp ? (entry?.download_name || "") : "",
      downloadUrl: isEp
        ? `${API_BASE}/ep-asset?path=${encodeURIComponent(path)}`
        : `${API_BASE}/asset?path=${encodeURIComponent(path)}`,
    });
  }

  // Highlight selection
  document.querySelectorAll(".tree-item.active").forEach(el => el.classList.remove("active"));
  if (itemEl) itemEl.classList.add("active");

  // То же выделение в шторке узкого экрана. Точечно, а не перерисовкой дерева:
  // openFile вызывается и из автооткрытия, и из самой шторки, а полная
  // перерисовка на каждый переход сбрасывала бы прокрутку списка.
  currentDocPath = path;
  syncMobileNavSelection();

  try {
    const ext = path.split(".").pop().toLowerCase();
    const kind = getMediaKind(ext);
    const name = path.split("/").pop();

    // Документ с собранной страницей — открываем страницу, даём переключатель
    // на исходный текст. Проверка идёт ПЕРВОЙ и одинаково для всех веток
    // дерева: признак пришёл с сервера, расширение здесь ни при чём
    // (задача 701 block 7).
    if (hasPageFor(path)) {
      await renderProjection(path, "page");
      return;
    }

    // Экстранет-материал (task 695 block 71). Вид решает бэкенд: у витрины нет
    // расширения файла, только имя и mime из каталога тенанта, поэтому
    // getMediaKind по расширению здесь не работает вовсе.
    if (path.startsWith("ep/")) {
      const epKind = epKindFor(path);
      const epName = epEntryFor(path)?.name || "";

      // Показываем материал теми же просмотрщиками, что и файл с диска
      // (задача 677). Раньше эта ветка вела свой разбор на три вида не от
      // хорошей жизни: отдавать браузеру было нечего — файла на диске витрины
      // нет, а PDF строкой не передашь. Блок 71000 завёл ep-asset, и разбор
      // стал не нужен.
      // Страница целиком — своя вёрстка, а не 17 блоков каталога. Рисуется в
      // изолированном фрейме: файл приезжает из хранилища тенанта и доверенным
      // источником разметки не является, а в адресе этой страницы живёт
      // магик-токен. Песочница без allow-same-origin отрезает фрейму доступ
      // к родителю, и прочитать токен он не может.
      if (epKind === "page_html") {
        try {
          const data = await api(`/file?path=${encodeURIComponent(path)}`);
          content.innerHTML = "";
          content.appendChild(buildPageFrame(data.content || ""));
        } catch (err) {
          content.innerHTML = `<div class="muted center">Не удалось открыть страницу: ${_escapeHtml(err.message || "")}</div>`;
        }
        return;
      }

      if (EP_INLINE_KINDS.includes(epKind)) {
        const assetUrl = `${API_BASE}/ep-asset?path=${encodeURIComponent(path)}`;
        let html;
        if (epKind === "pdf") html = renderPdf(assetUrl);
        // Путь лайтбоксу не передаём: он строит адрес через /asset, а тот ходит
        // по папке партнёра на диске, где материала Экстранета нет. Отдельная
        // работа, здесь не она.
        else if (epKind === "image") html = renderImage(assetUrl, epName, null);
        else if (epKind === "audio") html = renderAudio(assetUrl);
        else html = renderVideo(assetUrl);
        content.innerHTML = html;
        return;
      }

      try {
        const data = await api(`/file?path=${encodeURIComponent(path)}`);
        const body = data.content || "";

        // Что браузер не рисует сам — открывается на стороне облака. Сюда
        // попадает docx: белый список типов его не пропускает, да и показать
        // его браузеру нечем.
        if (body.startsWith("external:")) {
          const url = body.slice("external:".length);
          // Где лежит материал — говорит сервер (блок 71020). Зашитая строка
          // про Яндекс.Диск врала всем, чей материал лежит в другом облаке.
          // Названия не пришло — обходимся без имени, а не угадываем.
          const storage = data.storage_label || "";
          const whereText = storage
            ? `Материал откроется в «${_escapeHtml(storage)}» — там же можно скачать.`
            : "Материал откроется в облаке — там же можно скачать.";
          content.innerHTML =
            `<div class="ep-external">` +
            `<p><b>${_escapeHtml(data.name || "Материал")}</b></p>` +
            `<p><a href="${_escapeHtml(url)}" target="_blank" rel="noopener">Открыть в новой вкладке</a></p>` +
            `<p class="muted">${whereText}</p>` +
            `</div>`;
          return;
        }

        // Документ Word: с бэкенда приходит готовая разметка, уже очищенная
        // белым списком тегов. Через marked её гнать нельзя — это не разметка
        // markdown, а HTML, и разбор её только испортит. Рисуем в .md-content,
        // чтобы оформление совпало с расшифровками, а не заводить второе.
        if (epKind === "doc") {
          content.innerHTML = `<div class="md-content">${body}</div>`;
          if (window.DocPatterns) {
            window.DocPatterns.enhance(content.querySelector(".md-content"));
          }
          return;
        }

        // Остальное — текст, как было
        const html = marked.parse(body, { breaks: true });
        content.innerHTML = `<div class="md-content">${html}</div>`;
        if (window.DocPatterns) {
          window.DocPatterns.enhance(content.querySelector(".md-content"));
        }
        content.querySelectorAll("pre code").forEach(block => {
          if (window.hljs) hljs.highlightElement(block);
        });
      } catch (err) {
        content.innerHTML = `<div class="muted center">Не удалось открыть материал: ${_escapeHtml(err.message || "")}</div>`;
      }
      return;
    }

    // Media: build /asset URL, render inline (no /file text fetch needed)
    if (kind === "pdf" || kind === "image" || kind === "audio" || kind === "video") {
      const assetUrl = `${API_BASE}/asset?path=${encodeURIComponent(path)}`;
      let html;
      if (kind === "pdf") html = renderPdf(assetUrl);
      else if (kind === "image") html = renderImage(assetUrl, name, path);
      else if (kind === "audio") html = renderAudio(assetUrl);
      else html = renderVideo(assetUrl);
      content.innerHTML = html;
      return;
    }

    // Text-based: fetch /file endpoint
    if (kind === "md" || kind === "code" || kind === "other") {
      try {
        const data = await api(`/file?path=${encodeURIComponent(path)}`);
        if (kind === "md") {
          const html = marked.parse(data.content, { breaks: true });
          content.innerHTML = `<div class="md-content">${html}</div>`;
          // Распознавание паттернов: оформление без разметки в исходнике
          if (window.DocPatterns) {
            window.DocPatterns.enhance(content.querySelector(".md-content"));
          }
          content.querySelectorAll("pre code").forEach(block => {
            if (window.hljs) hljs.highlightElement(block);
          });
        } else if (kind === "code") {
          const pre = document.createElement("pre");
          const code = document.createElement("code");
          code.className = `language-${ext}`;
          code.textContent = data.content;
          pre.appendChild(code);
          content.innerHTML = "";
          content.appendChild(pre);
          if (window.hljs) hljs.highlightElement(code);
        } else {
          const pre = document.createElement("pre");
          pre.textContent = data.content;
          content.innerHTML = "";
          content.appendChild(pre);
        }
      } catch (fileErr) {
        // /file returns 415 for binary — fallback to download
        if (fileErr.message && /415/.test(fileErr.message)) {
          const assetUrl = `${API_BASE}/asset?path=${encodeURIComponent(path)}`;
          content.innerHTML = renderDownload(assetUrl, name, null);
        } else {
          throw fileErr;
        }
      }
    }
  } catch (err) {
    content.innerHTML = `<div class="muted center">Ошибка: ${err.message}</div>`;
  }
}

// ── Tabs (Files / Tasks) ─────────────────────────────────────
let taskEngineState = { activeMeetingId: null, meetings: [], allTasksCount: 0 };
let taskEngineWidget = null;
// Открытие задачи начато из документа — вкладку переключать не надо.
// Кит не решает про вкладки сам: он СПРАШИВАЕТ витрину через onNeedTasksTab,
// и до этой правки витрина всегда отвечала «да». Флаг — её ответ «нет,
// я показываю задачу поверх документа». Съедается одним вопросом: у кита
// на одно открытие приходится ровно один вызов, включая ветку повтора
// после догрузки списка (задача 721, блок 208).
let taskOpenKeepsBackground = false;

function switchTab(tab) {
  const tabsWrap = document.querySelector(".tabs");
  if (!tabsWrap) return;
  const btn = tabsWrap.querySelector(`[data-tab="${tab}"]`);
  if (!btn) return;
  tabsWrap.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === btn));
  const tree = document.getElementById("tree");
  const breadcrumb = document.getElementById("breadcrumb");
  const content = document.getElementById("content");
  const tasksPanel = document.getElementById("tasks-panel");
  const tasksSidebar = document.getElementById("tasks-sidebar");
  if (tab === "files") {
    if (tree) tree.style.display = "";
    if (breadcrumb) breadcrumb.style.display = "";
    if (content) content.style.display = "";
    if (tasksPanel) tasksPanel.style.display = "none";
    if (tasksSidebar) tasksSidebar.style.display = "none";
  } else if (tab === "tasks") {
    if (tree) tree.style.display = "none";
    if (breadcrumb) breadcrumb.style.display = "none";
    if (content) content.style.display = "none";
    if (tasksPanel) tasksPanel.style.display = "";
    if (tasksSidebar) tasksSidebar.style.display = "";
    loadTasksSidebar();
    mountTaskEngine();
  }
  // v1.4.1: persist active tab в URL hash
  if (window.location.hash !== `#${tab}`) {
    history.replaceState(null, "", `#${tab}`);
  }
}

function setupTabs() {
  const tabsWrap = document.querySelector(".tabs");
  if (!tabsWrap) return;
  tabsWrap.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-tab]");
    if (!btn) return;
    switchTab(btn.dataset.tab);
  });
  // v1.4.1: init from URL hash on page load
  const initialTab = window.location.hash === "#tasks" ? "tasks" : "files";
  if (initialTab !== "files") switchTab(initialTab);
}

/** Открыть то, что названо в адресе: #ep/NNN — документ, #task/NNN — задачу.
 *
 *  Внутри кабинета такие ссылки работали всегда — их перехватывает страница в
 *  песочнице и просит родителя открыть. Снаружи не работали: при загрузке
 *  разбирался только «#tasks», и ссылка на документ молча показывала обложку.
 *  Пока кабинет открывали одной ссылкой на корень, это никого не задевало;
 *  как только ссылку на конкретный документ понадобилось отправить в письме
 *  или в чат — стало видно (задача 715, блок 400).
 *
 *  Вызывается ПОСЛЕ обложки и дерева: openFromFrame ищет документ в дереве и
 *  сам догружает папки, но пустое дерево ему искать негде.
 */
async function openFromHash() {
  const h = window.location.hash || "";
  if (h.startsWith("#ep/")) {
    await openFromFrame(h.slice(1));
    return true;
  }
  if (h.startsWith("#task/")) {
    const id = parseInt(h.slice(6), 10);
    // false явно, а не по умолчанию: через месяц не должно выглядеть
    // так, будто аргумент просто забыли
    if (id > 0) { openTaskFromFrame(id, false); return true; }
  }
  return false;
}

async function loadTasksSidebar() {
  const sidebar = document.getElementById("tasks-sidebar");
  if (!sidebar) return;
  try {
    const data = await fetch(`/api/tasks/${TOKEN}/tasks`).then(r => r.json());
    taskEngineState.meetings = data.meetings || [];
    taskEngineState.allTasksCount = (data.tasks || []).length;
    // Count tasks per meeting + none
    const countByMeeting = {};
    let noneCount = 0;
    (data.tasks || []).forEach(t => {
      if (t.meeting_id != null) countByMeeting[t.meeting_id] = (countByMeeting[t.meeting_id] || 0) + 1;
      else noneCount++;
    });
    let html = '<div class="tasks-sidebar-inner">';
    // Top: universal filters (Все + Без встречи)
    html += `<button class="ts-item${taskEngineState.activeMeetingId === null ? ' active' : ''}" data-meeting="all">🎯 Все <span class="ts-count">${taskEngineState.allTasksCount}</span></button>`;
    const activeNone = taskEngineState.activeMeetingId === '__none' ? ' active' : '';
    html += `<button class="ts-item${activeNone}" data-meeting="__none">📎 Без встречи <span class="ts-count">${noneCount}</span></button>`;
    if (taskEngineState.meetings.length > 0) {
      html += '<div class="ts-section-label">ИЗ ВСТРЕЧ</div>';
      taskEngineState.meetings.forEach(m => {
        const cnt = countByMeeting[m.id] || 0;
        const active = taskEngineState.activeMeetingId === m.id ? ' active' : '';
        html += `<button class="ts-item${active}" data-meeting="${m.id}"><div class="ts-title">${escHtml(m.title)}</div><div class="ts-meta">${m.date || ''} <span class="ts-count">${cnt}</span></div></button>`;
      });
    }
    html += '</div>';
    // v1.4: sticky-bottom «+ Встреча» button
    html += '<div class="tasks-sidebar-footer"><button class="ts-add-meeting" data-action="add-meeting">➕ Новая встреча</button></div>';
    sidebar.innerHTML = html;
    sidebar.querySelectorAll('[data-meeting]').forEach(btn => {
      btn.addEventListener('click', () => {
        const mid = btn.dataset.meeting;
        taskEngineState.activeMeetingId = mid === 'all' ? null : (mid === '__none' ? '__none' : parseInt(mid, 10));
        loadTasksSidebar();
        remountTaskEngine();
      });
    });
    // v1.4: sticky-bottom + Встреча button
    const addBtn = sidebar.querySelector('[data-action="add-meeting"]');
    if (addBtn) {
      addBtn.addEventListener('click', () => {
        if (taskEngineWidget && typeof taskEngineWidget.openMeetingCreate === 'function') {
          taskEngineWidget.openMeetingCreate();
        }
      });
    }
  } catch (err) {
    sidebar.innerHTML = `<div class="muted">Ошибка: ${err.message}</div>`;
  }
}

function escHtml(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function mountTaskEngine() { remountTaskEngine(); }

function remountTaskEngine() {
  const container = document.getElementById("tasks-panel");
  if (!container || !window.TaskEngine) return;
  const cfg = {
    apiBase: `/api/tasks/${TOKEN}`,
    mode: "embedded",
    sections: { groupBy: "meeting" },
    showFilters: true,
    showAddButton: true,
    // Список исполнителей больше не задаётся здесь: кит берёт участников из
    // ответа /tasks, а витрина складывает их из справочника портала. Раньше тут
    // стояли имена первого клиента, и Артём видел «Антона» (задача 706, блок 234).
    // Описание задачи может позвать документ кабинета: клик уводит на вкладку
    // «Файлы» и открывает его (задача 706, блок 226).
    onNeedTasksTab: () => {
      // Кит спрашивает, показать ли вкладку задач. Если открытие пришло
      // из документа — отвечаем «нет» и гасим флаг: он на одно открытие.
      if (taskOpenKeepsBackground) { taskOpenKeepsBackground = false; return; }
      switchTab("tasks");
    },
    onOpenDocument: (path) => {
      document.querySelectorAll(".te-slider").forEach(s => s.remove());
      switchTab("files");
      openFromFrame(path);
    },
    hooks: {
      onMeetingCreated: () => { loadTasksSidebar(); },  // v1.4: refresh sidebar
    },
  };
  if (taskEngineState.activeMeetingId !== null) {
    cfg.filter = { meetingId: taskEngineState.activeMeetingId };
  }
  taskEngineWidget = window.TaskEngine.mount(container, cfg);
}

function setupLogoHome() {
  const logo = document.querySelector(".topbar .logo");
  if (!logo) return;
  logo.style.cursor = "pointer";
  logo.title = "На главную страницу кабинета";
  logo.addEventListener("click", () => navigateTo(""));
}

(async function init() {
  try {
    setupTabs();
    setupLogoHome();
    initMobileSheet();
    await loadInfo();
    // Обложка идёт ПЕРЕД деревом, и это важно. Раньше было наоборот: дерево
    // само открывало первый файл корня, а обложка показывалась, только если
    // открывать было нечего. Пока в корне лежали одни папки, это работало —
    // 22.08 корень стал плоским (задача 706, блок 231), автооткрытие начало
    // срабатывать всегда, и обложка перестала открываться совсем.
    // Обложка — заявленный стартовый экран портала; первый документ в списке —
    // случайность раскладки. При споре выигрывает обложка.
    // Адрес с якорем на документ важнее обложки: человек пришёл по ссылке на
    // конкретную страницу, и показать ему вместо неё стартовый экран — значит
    // не выполнить единственную просьбу, с которой он пришёл.
    const wantsDeepLink = /^#(ep|task)\//.test(window.location.hash || "");
    const coverShown = wantsDeepLink ? false : await showCover();
    await loadTree({ autoOpen: !coverShown && !wantsDeepLink });
    if (wantsDeepLink) await openFromHash();
  } catch (err) {
    console.error(err);
  }
})();
