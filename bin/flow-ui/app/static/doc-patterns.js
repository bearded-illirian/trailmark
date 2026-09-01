/*
 * doc-patterns.js — распознавание паттернов обычного markdown (task 698 block 3)
 *
 * Поднимает качество отрисовки .md БЕЗ разметки в самом файле. Исходник
 * остаётся чистым текстом: он читается в Google Drive и правится руками,
 * а оформление появляется из узнавания обычных markdown-конструкций.
 *
 * Каждый паттерн строго условен: не совпало — молча ничего не делает.
 * Функция идемпотентна: повторный вызов на том же узле безопасен.
 *
 * Использование:
 *   window.DocPatterns.enhance(containerElement);
 */
(function (global) {
  "use strict";

  const DONE = "data-doc-enhanced";

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  /* ── Паттерн 1: шапка документа ─────────────────────────────
     Первый h1 + следующий абзац с «Тема:» + первая таблица вида
     «Параметр | Значение» → doc-hero с чипами метаданных. */
  function patternHero(root) {
    const h1 = root.querySelector("h1");
    if (!h1 || h1.closest(".doc-hero")) return;

    const hero = el("header", "doc-hero");
    const title = el("h1", "doc-hero__title", h1.textContent);
    hero.appendChild(title);

    const after = [];
    let node = h1.nextElementSibling;

    // Лид: первый абзац, начинающийся с жирного «Тема:» или подобного
    if (node && node.tagName === "P") {
      const strong = node.querySelector("strong");
      if (strong && /^(тема|о чём|предмет)\s*:?\s*$/i.test(strong.textContent.trim().replace(/:$/, "") + ":")) {
        const lead = el("p", "doc-hero__lead", node.textContent.replace(/^\s*\S+:\s*/, ""));
        hero.appendChild(lead);
        after.push(node);
        node = node.nextElementSibling;
      }
    }

    // Чипы: таблица из двух колонок с шапкой «Параметр / Значение»
    if (node && node.tagName === "TABLE") {
      const heads = Array.from(node.querySelectorAll("thead th")).map(t => t.textContent.trim().toLowerCase());
      const isMeta = heads.length === 2 && /параметр|поле|признак/.test(heads[0]) && /значение|описание/.test(heads[1]);
      if (isMeta) {
        const meta = el("div", "doc-meta");
        Array.from(node.querySelectorAll("tbody tr")).forEach(tr => {
          const cells = tr.querySelectorAll("td");
          if (cells.length !== 2) return;
          const k = cells[0].textContent.trim();
          const v = cells[1].textContent.trim();
          if (!k || !v) return;
          const item = el("div", "doc-meta__item");
          item.appendChild(el("span", "doc-meta__label", k));
          item.appendChild(el("span", "doc-meta__value", v));
          meta.appendChild(item);
        });
        if (meta.children.length) {
          hero.appendChild(meta);
          after.push(node);
        }
      }
    }

    // Заменяем только если что-то реально собрали сверх заголовка
    if (hero.children.length < 2) return;
    h1.replaceWith(hero);
    after.forEach(n => n.remove());
  }

  /* ── Паттерн 2: врезка ──────────────────────────────────────
     Цитата, начинающаяся с маркера [!ВАЖНО] / [!ЗАМЕТКА] /
     [!ВНИМАНИЕ] / [!NOTE] / [!WARNING] → doc-callout. */
  const CALLOUT_KINDS = [
    { re: /^\[!\s*(внимание|осторожно|warning|caution)\s*\]/i, kind: "warn", label: "Внимание" },
    { re: /^\[!\s*(опасно|блокер|danger|important)\s*\]/i, kind: "danger", label: "Важно" },
    { re: /^\[!\s*(важно|заметка|note|tip|подсказка)\s*\]/i, kind: "", label: "Заметка" },
  ];

  function patternCallout(root) {
    root.querySelectorAll("blockquote").forEach(bq => {
      if (bq.closest(".doc-callout")) return;
      const first = bq.querySelector("p");
      if (!first) return;
      const raw = first.textContent.trim();
      const hit = CALLOUT_KINDS.find(k => k.re.test(raw));
      if (!hit) return;

      const cls = "doc-callout" + (hit.kind ? ` doc-callout--${hit.kind}` : "");
      const box = el("div", cls);
      box.appendChild(el("span", "doc-callout__label", hit.label));
      const body = el("div", "doc-callout__body");
      // Первый абзац — без маркера, остальные как есть
      first.textContent = raw.replace(hit.re, "").replace(/^\s*[:—-]\s*/, "").trim();
      Array.from(bq.childNodes).forEach(n => body.appendChild(n));
      box.appendChild(body);
      bq.replaceWith(box);
    });
  }

  /* ── Паттерн 3: тезисы ──────────────────────────────────────
     Нумерованный список, где КАЖДЫЙ пункт начинается с <strong>
     и пунктов не меньше трёх → doc-steps. Строгое условие: один
     невыделенный пункт отменяет паттерн целиком. */
  function patternSteps(root, selector, extraClass) {
    root.querySelectorAll(selector || "ol").forEach(ol => {
      if (ol.closest(".doc-steps") || ol.querySelector("ol, ul")) return;
      const items = Array.from(ol.children).filter(c => c.tagName === "LI");
      if (items.length < 3) return;

      const parsed = items.map(li => {
        const strong = li.firstElementChild && li.firstElementChild.tagName === "STRONG"
          ? li.firstElementChild
          : (li.firstElementChild && li.firstElementChild.tagName === "P"
              && li.firstElementChild.firstElementChild
              && li.firstElementChild.firstElementChild.tagName === "STRONG"
                ? li.firstElementChild.firstElementChild : null);
        if (!strong) return null;
        const title = strong.textContent.trim();
        const clone = li.cloneNode(true);
        const s = clone.querySelector("strong");
        if (s) s.remove();
        const body = clone.textContent.replace(/^\s*[.:—-]\s*/, "").trim();
        return { title, body };
      });
      if (parsed.some(p => !p || !p.title)) return;

      const box = el("div", "doc-steps" + (extraClass ? " " + extraClass : ""));
      parsed.forEach(p => {
        const item = el("div", "doc-steps__item");
        item.appendChild(el("b", "doc-steps__title", p.title));
        if (p.body) item.appendChild(el("span", "doc-steps__body", p.body));
        box.appendChild(item);
      });
      ol.replaceWith(box);
    });
  }

  /* ── Паттерн 4: таблицы ─────────────────────────────────────
     Любая таблица оборачивается в прокручиваемый контейнер.
     Внутри обёртки таблица возвращает нормальное display: table. */
  function patternTable(root) {
    root.querySelectorAll("table").forEach(t => {
      if (t.closest(".doc-table__wrap")) return;
      const wrap = el("div", "doc-table__wrap");
      t.replaceWith(wrap);
      wrap.appendChild(t);
    });
  }

  /* ── Паттерн 5: ответственные ───────────────────────────────
     Абзац целиком из <strong> (заголовок-имя) + следующий за ним
     список → карточка. Нужно не меньше двух таких пар подряд,
     иначе это просто выделенный абзац. */
  function patternResponsibles(root) {
    const pairs = [];
    root.querySelectorAll("p").forEach(p => {
      if (p.closest(".doc-cards, .doc-hero")) return;
      const only = p.children.length === 1 && p.firstElementChild.tagName === "STRONG"
        && p.textContent.trim() === p.firstElementChild.textContent.trim();
      if (!only) return;
      const next = p.nextElementSibling;
      if (!next || (next.tagName !== "UL" && next.tagName !== "OL")) return;
      pairs.push({ head: p, list: next });
    });
    if (pairs.length < 2) return;

    // Группируем идущие подряд пары в одну сетку карточек
    let group = [];
    const flush = () => {
      if (group.length < 2) { group = []; return; }
      const box = el("div", "doc-cards");
      group.forEach(g => {
        const card = el("div", "doc-cards__item");
        card.appendChild(el("b", "doc-cards__title", g.head.textContent.replace(/:$/, "").trim()));
        const list = el("ul", "doc-cards__list");
        Array.from(g.list.querySelectorAll("li")).forEach(li => {
          list.appendChild(el("li", null, li.textContent.trim()));
        });
        card.appendChild(list);
        box.appendChild(card);
      });
      group[0].head.replaceWith(box);
      group.forEach(g => { g.list.remove(); if (g.head.parentNode) g.head.remove(); });
      group = [];
    };
    pairs.forEach((pair, i) => {
      const prev = pairs[i - 1];
      if (prev && prev.list.nextElementSibling === pair.head) group.push(pair);
      else { flush(); group = [pair]; }
    });
    flush();
  }

  /* ── Паттерн 6: закрывающий блок ────────────────────────────
     Заголовок h2 со словами «следующ» / «что дальше» / «дальнейшие
     шаги» + идущий за ним абзац → doc-next. Текст режется по первой
     точке: до неё крупная строка, после — пояснение. Режем только
     если первый сегмент 8-60 знаков, иначе сокращения вроде «авг.»
     дадут мусор. */
  const NEXT_RE = /(следующ|что дальше|дальнейшие шаги|next steps)/i;

  function patternNext(root) {
    root.querySelectorAll("h2").forEach(h => {
      if (h.closest(".doc-next")) return;
      if (!NEXT_RE.test(h.textContent)) return;
      const p = h.nextElementSibling;
      if (!p || p.tagName !== "P") return;

      const full = p.textContent.trim();
      if (!full) return;

      let when = full, body = "";
      const dot = full.indexOf(". ");
      if (dot >= 8 && dot <= 60) {
        when = full.slice(0, dot).trim();
        body = full.slice(dot + 1).trim();
      }

      const box = el("div", "doc-next");
      box.appendChild(el("span", "doc-next__label", h.textContent.trim()));
      box.appendChild(el("span", "doc-next__when", when));
      if (body) box.appendChild(el("div", "doc-next__body", body));
      h.replaceWith(box);
      p.remove();
    });
  }

  /* ── Паттерн 7: разделитель ─────────────────────────────────
     Горизонтальная черта сегодня не оформлена никак. Класс в
     стилях есть — соединяем. Правило без условий: hr в документе
     всегда смысловой, автор ставит его намеренно. */
  function patternDivider(root) {
    root.querySelectorAll("hr").forEach(hr => {
      if (hr.classList.contains("doc-divider")) return;
      hr.classList.add("doc-divider");
    });
  }

  /* ── Паттерн 8: цитата ──────────────────────────────────────
     Цитата БЕЗ маркера [!…] — то, что не забрал patternCallout.
     Последний абзац, начинающийся с тире, читается как подпись.

     ⚠️ Условие обратное к CALLOUT_KINDS намеренно: врезки должны
        остаться врезками, а сюда попадает только остальное. */
  function patternQuote(root) {
    root.querySelectorAll("blockquote").forEach(bq => {
      if (bq.closest(".doc-quote, .doc-callout")) return;
      const paras = Array.from(bq.querySelectorAll("p"));
      if (!paras.length) return;

      const raw = paras[0].textContent.trim();
      if (CALLOUT_KINDS.some(k => k.re.test(raw))) return;  // это врезка, не наша

      const box = el("div", "doc-quote");
      const last = paras[paras.length - 1];
      const isAuthor = paras.length > 1 && /^\s*[—–-]\s*\S/.test(last.textContent);

      const bodyParas = isAuthor ? paras.slice(0, -1) : paras;
      const text = bodyParas.map(p => p.textContent.trim()).filter(Boolean).join(" ");
      if (!text) return;

      box.appendChild(el("div", "doc-quote__text", text));
      if (isAuthor) {
        box.appendChild(el("div", "doc-quote__author",
          last.textContent.replace(/^\s*[—–-]\s*/, "").trim()));
      }
      bq.replaceWith(box);
    });
  }

  /* ── Паттерн 9: числа ───────────────────────────────────────
     Список, где КАЖДЫЙ пункт начинается с жирного числового
     значения → плитки с крупной цифрой.

     ⚠️ Условие узкое намеренно. «Жирный зачин» встречается почти
        в каждом списке, поэтому мало его — нужна именно ВЕЛИЧИНА:
        цифры, диапазон через тире, проценты, рубли, «девять из
        десяти». Тезис «**Нейросеть — калькулятор.**» под правило
        попасть не должен.

     ⚠️ От двух до четырёх пунктов. Плитки раскладываются сеткой
        minmax(160px, 1fr); десять чисел дадут мелкую кашу вместо
        акцента. Верхняя граница — часть правила, а не оформления. */
  const KPI_VALUE_RE = /^(?:[0-9][0-9\s.,]*(?:\s*[—–-]\s*[0-9][0-9\s.,]*)?\s*(?:%|₽|руб\.?|раз[а-я]*|час[а-я]*|мин[а-я]*|шт\.?)?|(?:[а-яё]+)\s+из\s+(?:[а-яё]+|[0-9]+)|[0-9]+\s*[-–—]\s*[0-9]+)$/i;

  function patternKpi(root) {
    root.querySelectorAll("ul, ol").forEach(list => {
      if (list.closest(".doc-kpi, .doc-steps, .doc-cards")) return;
      if (list.querySelector("ol, ul")) return;
      const items = Array.from(list.children).filter(c => c.tagName === "LI");
      if (items.length < 2 || items.length > 4) return;

      const parsed = items.map(li => {
        const strong = li.firstElementChild && li.firstElementChild.tagName === "STRONG"
          ? li.firstElementChild : null;
        if (!strong) return null;
        const value = strong.textContent.trim().replace(/[.:]$/, "");
        if (!KPI_VALUE_RE.test(value)) return null;
        const clone = li.cloneNode(true);
        const s = clone.querySelector("strong");
        if (s) s.remove();
        const label = clone.textContent.replace(/^\s*[.:—–-]\s*/, "").trim();
        if (!label) return null;
        return { value, label };
      });
      if (parsed.some(p => !p)) return;

      const box = el("div", "doc-kpi");
      parsed.forEach(p => {
        const item = el("div", "doc-kpi__item");
        item.appendChild(el("div", "doc-kpi__value", p.value));
        item.appendChild(el("div", "doc-kpi__label", p.label));
        box.appendChild(item);
      });
      list.replaceWith(box);
    });
  }

  function enhance(root) {
    if (!root || root.getAttribute(DONE) === "1") return root;
    try {
      patternHero(root);
      patternCallout(root);
      // ⚠️ Числа СТРОГО раньше тезисов: patternSteps забирает любой список
      //    с жирными зачинами, и числовой список подходит под его условие.
      //    Тот же случай, что «ответственные раньше определений» ниже.
      patternKpi(root);
      patternQuote(root);
      patternDivider(root);
      patternSteps(root, "ol");
      // Ответственные СТРОГО раньше определений: иначе списки под «Мы:»
      // будут поглощены как определения и пары развалятся
      patternResponsibles(root);
      patternSteps(root, "ul", "doc-steps--plain");
      patternNext(root);
      patternTable(root);
      root.setAttribute(DONE, "1");
    } catch (err) {
      // Оформление не должно ломать чтение документа
      if (global.console) console.warn("doc-patterns:", err.message);
    }
    return root;
  }

  global.DocPatterns = { enhance };
})(window);
