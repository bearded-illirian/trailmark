/*
 * doc-blocks.js — рендерер собранных страниц (task 698 block 2)
 *
 * Принимает список блоков и строит DOM. Словарь типов совпадает с классами
 * .doc-* в style.css. Значения кладутся ТОЛЬКО через textContent — файл
 * страницы приходит из хранилища тенанта и не является доверенным источником
 * разметки.
 *
 * Формат:
 *   { "version": 1, "blocks": [ { "type": "hero", ... }, ... ] }
 *
 * Использование:
 *   const node = window.DocBlocks.render(pageObject);
 *   container.replaceChildren(node);
 */
(function (global) {
  "use strict";

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null && text !== "") n.textContent = String(text);
    return n;
  }

  function arr(v) {
    return Array.isArray(v) ? v : [];
  }

  const RENDERERS = {
    hero(b) {
      const w = el("header", "doc-hero");
      if (b.kicker) w.appendChild(el("div", "doc-hero__kicker", b.kicker));
      w.appendChild(el("h1", "doc-hero__title", b.title || ""));
      if (b.lead) w.appendChild(el("p", "doc-hero__lead", b.lead));
      const chips = arr(b.chips);
      if (chips.length) {
        const c = el("div", "doc-hero__chips");
        chips.forEach(t => c.appendChild(el("span", "doc-hero__chip", t)));
        w.appendChild(c);
      }
      return w;
    },

    section(b) {
      const w = el("div", "doc-section");
      if (b.eyebrow) w.appendChild(el("div", "doc-section__eyebrow", b.eyebrow));
      w.appendChild(el("h2", "doc-section__title", b.title || ""));
      return w;
    },

    meta(b) {
      // Плашки «поле → значение» под шапкой. Ту же разметку строит
      // doc-patterns.js из таблицы «Параметр / Значение» в текстовой
      // проекции — обе проекции обязаны выглядеть одинаково (задача 701
      // блок 5 раунд 2, находка визуальной проверки).
      const w = el("div", "doc-meta");
      arr(b.items).forEach(it => {
        const item = el("div", "doc-meta__item");
        item.appendChild(el("span", "doc-meta__label", it.label || ""));
        item.appendChild(el("span", "doc-meta__value", it.value || ""));
        w.appendChild(item);
      });
      return w;
    },

    text(b) {
      const w = el("div", "doc-text");
      const paras = arr(b.paragraphs).length ? arr(b.paragraphs) : [b.text].filter(Boolean);
      paras.forEach(t => w.appendChild(el("p", null, t)));
      return w;
    },

    cards(b) {
      const w = el("div", "doc-cards");
      arr(b.items).forEach(it => {
        const c = el("div", "doc-cards__item");
        c.appendChild(el("b", "doc-cards__title", it.title || ""));
        // Тело — строка либо список пунктов. Проверка МАССИВА идёт первой:
        // el() зовёт String(value), и массив тихо превратился бы в «a,b,c».
        if (Array.isArray(it.body)) {
          const list = el("ul", "doc-cards__list");
          it.body.forEach(line => list.appendChild(el("li", null, line)));
          if (list.children.length) c.appendChild(list);
        } else if (it.body) {
          c.appendChild(el("span", "doc-cards__body", it.body));
        }
        w.appendChild(c);
      });
      return w;
    },

    kpi(b) {
      const w = el("div", "doc-kpi");
      arr(b.items).forEach(it => {
        const c = el("div", "doc-kpi__item");
        c.appendChild(el("div", "doc-kpi__value", it.value || ""));
        if (it.label) c.appendChild(el("div", "doc-kpi__label", it.label));
        w.appendChild(c);
      });
      return w;
    },

    criteria(b) {
      const w = el("div", "doc-criteria");
      arr(b.items).forEach(it => {
        const c = el("div", "doc-criteria__item");
        c.appendChild(el("b", "doc-criteria__name", it.name || ""));
        if (it.why) c.appendChild(el("span", "doc-criteria__why", it.why));
        w.appendChild(c);
      });
      return w;
    },

    zones(b) {
      const w = el("div", "doc-zones");
      arr(b.zones).forEach((z, i) => {
        const zone = el("div", "doc-zone");
        const head = el("div", "doc-zone__head");
        head.appendChild(el("span", "doc-zone__tag", z.tag || `Зона ${i + 1}`));
        head.appendChild(el("span", "doc-zone__name", z.name || ""));
        if (z.where) head.appendChild(el("span", "doc-zone__where", z.where));
        zone.appendChild(head);

        const body = el("div", "doc-zone__body");
        arr(z.steps).forEach((st, j) => {
          const s = el("div", "doc-zone__step");
          s.appendChild(el("em", "doc-zone__step-n", st.label || `Шаг ${j + 1}`));
          s.appendChild(el("strong", "doc-zone__step-title", st.title || ""));
          if (st.body) s.appendChild(el("small", "doc-zone__step-body", st.body));
          body.appendChild(s);
        });
        zone.appendChild(body);

        const notes = arr(z.notes);
        if (notes.length) {
          const f = el("div", "doc-zone__foot");
          notes.forEach(t => f.appendChild(el("span", null, t)));
          zone.appendChild(f);
        }
        w.appendChild(zone);

        if (z.link) {
          const l = el("div", "doc-zones__link");
          l.appendChild(el("div", "doc-zones__bar"));
          l.appendChild(el("p", "doc-zones__link-text", z.link));
          w.appendChild(l);
        }
      });
      return w;
    },

    stages(b) {
      const w = el("div", "doc-stages");
      arr(b.items).forEach((st, i) => {
        const c = el("div", "doc-stage");
        const h = el("div", "doc-stage__head");
        h.appendChild(el("span", "doc-stage__n", st.tag || `Этап ${i + 1}`));
        h.appendChild(el("span", "doc-stage__when", st.when || ""));
        c.appendChild(h);
        const body = el("div", "doc-stage__body");
        arr(st.rows).forEach(r => {
          const g = el("div");
          g.appendChild(el("div", "doc-stage__label", r.label || ""));
          g.appendChild(el("div", "doc-stage__value", r.value || ""));
          body.appendChild(g);
        });
        c.appendChild(body);
        w.appendChild(c);
      });
      return w;
    },

    steps(b) {
      const w = el("div", "doc-steps");
      arr(b.items).forEach(it => {
        const li = el("div", "doc-steps__item");
        li.appendChild(el("b", "doc-steps__title", it.title || ""));
        if (it.body) li.appendChild(el("span", "doc-steps__body", it.body));
        w.appendChild(li);
      });
      return w;
    },

    callout(b) {
      const kind = b.kind === "warn" || b.kind === "danger" ? ` doc-callout--${b.kind}` : "";
      const w = el("div", "doc-callout" + kind);
      if (b.label) w.appendChild(el("span", "doc-callout__label", b.label));
      w.appendChild(el("div", "doc-callout__body", b.body || ""));
      return w;
    },

    quote(b) {
      const w = el("blockquote", "doc-quote");
      w.appendChild(el("div", "doc-quote__text", b.text || ""));
      if (b.author) w.appendChild(el("div", "doc-quote__author", b.author));
      return w;
    },

    image(b) {
      const w = el("figure", "doc-image");
      const img = document.createElement("img");
      img.src = b.src || "";
      img.alt = b.alt || "";
      img.loading = "lazy";
      w.appendChild(img);
      if (b.caption) w.appendChild(el("figcaption", "doc-image__caption", b.caption));
      return w;
    },

    files(b) {
      const w = el("div", "doc-files");
      arr(b.items).forEach(it => {
        const row = el("div", "doc-files__item");
        row.appendChild(el("span", "doc-files__name", it.name || ""));
        if (it.meta) row.appendChild(el("span", "doc-files__meta", it.meta));
        w.appendChild(row);
      });
      return w;
    },

    table(b) {
      const w = el("div", "doc-table");
      if (b.title) w.appendChild(el("div", "doc-table__title", b.title));
      const wrap = el("div", "doc-table__wrap");
      const t = document.createElement("table");
      const head = arr(b.head);
      if (head.length) {
        const thead = document.createElement("thead");
        const tr = document.createElement("tr");
        head.forEach(h => tr.appendChild(el("th", null, h)));
        thead.appendChild(tr);
        t.appendChild(thead);
      }
      const tbody = document.createElement("tbody");
      arr(b.rows).forEach(r => {
        const tr = document.createElement("tr");
        arr(r).forEach(c => tr.appendChild(el("td", null, c)));
        tbody.appendChild(tr);
      });
      t.appendChild(tbody);
      wrap.appendChild(t);
      w.appendChild(wrap);
      if (b.caption) w.appendChild(el("div", "doc-table__caption", b.caption));
      return w;
    },

    next(b) {
      const w = el("div", "doc-next");
      if (b.label) w.appendChild(el("span", "doc-next__label", b.label));
      w.appendChild(el("span", "doc-next__when", b.when || ""));
      if (b.body) w.appendChild(el("div", "doc-next__body", b.body));
      return w;
    },

    divider() {
      return el("hr", "doc-divider");
    },
  };

  function renderBlock(b) {
    if (!b || typeof b !== "object") return null;
    const fn = RENDERERS[b.type];
    if (!fn) {
      const warn = el("div", "doc-callout doc-callout--warn");
      warn.appendChild(el("span", "doc-callout__label", "Неизвестный блок"));
      warn.appendChild(el("div", "doc-callout__body", `Тип «${b.type}» не поддерживается этой версией портала.`));
      return warn;
    }
    try {
      return fn(b);
    } catch (err) {
      const warn = el("div", "doc-callout doc-callout--danger");
      warn.appendChild(el("span", "doc-callout__label", "Ошибка блока"));
      warn.appendChild(el("div", "doc-callout__body", `Блок «${b.type}» не отрисован: ${err.message}`));
      return warn;
    }
  }

  function render(page) {
    const root = el("article", "doc-page");
    const blocks = page && Array.isArray(page.blocks) ? page.blocks : [];
    if (!blocks.length) {
      root.appendChild(el("p", "muted", "Страница пуста — в файле нет блоков."));
      return root;
    }
    blocks.forEach(b => {
      const node = renderBlock(b);
      if (node) root.appendChild(node);
    });
    return root;
  }

  global.DocBlocks = { render, renderBlock, types: Object.keys(RENDERERS) };
})(window);
