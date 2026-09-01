/* Общий стиль страниц кабинета.
 *
 * ЗАЧЕМ. До этого файла каждая страница кабинета несла собственный блок <style>.
 * Три страницы из четырёх были побайтно одинаковы — 7886 байт, 48 селекторов,
 * одна md5. На двухстах кабинетах по пятнадцать материалов это три тысячи копий
 * одного стиля: правка одного правила означала пересборку и перезаливку трёх
 * тысяч файлов. Задача 721, блок 101, решение 19 задачи 706.
 *
 * ПОЧЕМУ СТРОКОЙ, А НЕ ФАЙЛОМ .css. Стиль впрыскивается в srcdoc песочного фрейма
 * строкой. Замер показал, что <link> на файл портала тоже работает — но он держится
 * на том, что у витрины нет политики безопасности, а её однажды поставят. Строка
 * не зависит ни от политики, ни от сети. Ссылка остаётся возможной оптимизацией,
 * когда стиль вырастет.
 *
 * ПОРЯДОК. Впрыск встаёт ДО разметки страницы. Тогда собственный <style> старых
 * материалов идёт позже и перекрывает общий — пятнадцать существующих страниц
 * продолжают выглядеть как выглядели, пока их не перенесут блоком 202.
 *
 * Источник переноса: pages/homework-2.html задачи 706, блок <style> дословно.
 */
(function (global) {
  "use strict";
  global.KABINET_PAGE_CSS = `
  /* ── Визуальная система кабинета, v2 ────────────────────────────────────
     Фон и текст берутся у темы портала saffron-graphite, чтобы страница
     сидела в кабинете как своя. Всё остальное — своя шкала: у портала нет
     ни поверхностей, ни теней, ни радиусов, ни подложек под состояния,
     и без них страница выглядит голым текстом. */
  :root {
    --font-display: Bitter, "PT Serif", Georgia, "Times New Roman", serif;
    --font-text: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

    --bg:        #0f1117;
    --card:      #151d29;
    --card-2:    #1b2531;
    --sunken:    #0b1017;
    --text:      #e8eaf0;
    --muted:     #8b93a8;
    --dim:       #6a7387;
    --line:      #252b3a;
    --line-soft: #1c2331;

    --brand:      #F4A300;
    --brand-soft: #2a1f0c;
    --alarm:      #e06a62;
    --alarm-soft: #2c1614;
    --calm:       #5fc08f;
    --calm-soft:  #10281e;
    /* Нейтральное состояние — «ещё не сделано», без окраски в хорошо или плохо.
       Пары не было вовсе, и врезка pending собиралась из фона и линии: ей
       нечем было отличаться от страницы (задача 721, блок 302). */
    --neutral:      #9aa6bf;
    --neutral-soft: #1a2130;

    --radius: 10px;
    --shadow: 0 1px 2px rgba(0,0,0,.35), 0 10px 26px -16px rgba(0,0,0,.8);
  }
  /* Страница следует теме КАБИНЕТА: портал стампует data-theme при открытии.
     Тёмная — умолчание, поэтому вспышки при загрузке нет. */
  :root[data-theme="light"] {
    --bg:        #fafaf9;
    --card:      #ffffff;
    --card-2:    #f4f5f7;
    --sunken:    #f1f2f4;
    --text:      #14161c;
    --muted:     #5c6472;
    --dim:       #838b98;
    --line:      #e3e5ea;
    --line-soft: #eceef2;

    --brand:      #a9700a;
    --brand-soft: #fdf3e0;
    --alarm:      #c33a32;
    --alarm-soft: #fbeceb;
    --calm:       #1f7a52;
    --calm-soft:  #e8f5ee;
    --neutral:      #55606f;
    --neutral-soft: #eef0f4;

    --shadow: 0 1px 2px rgba(16,20,28,.06), 0 10px 26px -16px rgba(16,20,28,.28);
  }

  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-text);
    font-size: 17px;
    line-height: 1.62;
    -webkit-font-smoothing: antialiased;
  }
  /* Моно — только цифры, даты, надзаголовки и метки. Фирменная гарнитура
     остаётся Inter; контраст пропорционального и моноширинного и делает
     страницу собранной, а не пёстрой. */
  .mono { font-family: var(--font-mono); }

  .page { max-width: 780px; margin: 0 auto; padding: clamp(32px,5vw,60px) clamp(16px,4vw,26px) 96px; display: flex; flex-direction: column; gap: clamp(30px,4vw,42px); }

  .eyebrow {
    font-family: var(--font-mono);
    font-size: 11.5px; font-weight: 500; letter-spacing: .16em;
    text-transform: uppercase; color: var(--brand); margin: 0;
  }

  header.head { display: flex; flex-direction: column; gap: 13px; }
  h1 { margin: 0; font-size: clamp(31px,5.4vw,44px); font-weight: 800; letter-spacing: -.025em; line-height: 1.08; text-wrap: balance; }

  /* Дисплейный шрифт — только для страниц, собранных сборщиком: он ставит
     data-doc на корень. Пятнадцать существующих материалов семейство для h1
     не объявляют вовсе и наследуют его от body — а прямое правило наследование
     перебивает, и заголовки у клиента молча сменились бы на сериф. Поймано
     замером, а не рассуждением (задача 721, блок 301). */
  [data-doc] h1 { font-family: var(--font-display); font-weight: 700; letter-spacing: -.015em; line-height: 1.1; }
  .lead { margin: 0; color: var(--muted); font-size: clamp(16px,2.2vw,18px); max-width: 62ch; }

  /* ── Плитки цифр ── */
  .tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .tile {
    background: var(--card); border: 1px solid var(--line);
    border-radius: var(--radius); box-shadow: var(--shadow);
    padding: 16px 17px; display: flex; flex-direction: column; gap: 6px;
  }
  .tile b {
    font-family: var(--font-mono);
    font-size: 26px; font-weight: 600; letter-spacing: -.02em;
    font-variant-numeric: tabular-nums; line-height: 1.05;
  }
  .tile span { font-size: 13.5px; color: var(--muted); line-height: 1.42; }
  .tile.alarm { background: var(--alarm-soft); border-color: color-mix(in srgb, var(--alarm) 34%, transparent); }
  .tile.alarm b { color: var(--alarm); }
  .tile.small b { font-size: 19px; }

  /* ── Секции ── */
  section { display: flex; flex-direction: column; gap: 15px; }
  section > h2 {
    margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -.015em;
    padding-top: 24px; border-top: 1px solid var(--line);
  }
  section p { margin: 0; max-width: 68ch; }
  section p.dim { color: var(--muted); }

  /* ── Карточка со строками «поле → значение» ── */
  .rows {
    background: var(--card); border: 1px solid var(--line);
    border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden;
  }
  .row {
    display: grid; grid-template-columns: minmax(120px, 180px) 1fr;
    gap: 4px 20px; padding: 14px 18px; border-bottom: 1px solid var(--line-soft);
  }
  .row:last-child { border-bottom: 0; }
  .row dt { font-weight: 600; font-size: 15.5px; }
  .row dd { margin: 0; color: var(--muted); }
  .row dd.pending { color: var(--dim); font-style: italic; }

  /* ── Список с шафрановой засечкой ── */
  ul.plain { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 11px; }
  ul.plain li { padding-left: 22px; position: relative; max-width: 68ch; }
  ul.plain li::before {
    content: ""; position: absolute; left: 0; top: .58em;
    width: 9px; height: 2px; border-radius: 2px; background: var(--brand);
  }

  /* ── Ссылка ── */
  /* Кликабельное должно выглядеть кликабельным: до этого стиля ссылок в наборе
     не было вовсе, и человек просто не заметил бы, что по тексту можно нажать.
     Открываются ссылки новой вкладкой — это делает сам портал (задача 706,
     блок 225), в разметке ничего указывать не нужно. */
  a { color: var(--brand); text-decoration: none;
      border-bottom: 1px solid color-mix(in srgb, var(--brand) 40%, transparent);
      transition: border-color .12s ease, color .12s ease; }
  a:hover { border-bottom-color: var(--brand); }
  a:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; border-radius: 2px; }
  /* Ссылка внутрь кабинета: остаётся в той же вкладке, поэтому и выглядит
     иначе — стрелка вместо подчёркивания (задача 706, блок 226). */
  a[href^="#ep/"], a[href^="#task/"] { border-bottom: 0; font-weight: 600; }
  a[href^="#ep/"]::after, a[href^="#task/"]::after { content: " →"; }

  /* ── Врезка ── */
  .note {
    background: var(--brand-soft);
    border: 1px solid color-mix(in srgb, var(--brand) 26%, transparent);
    border-radius: var(--radius); padding: 17px 20px;
    display: flex; flex-direction: column; gap: 8px;
  }
  .note p { margin: 0; max-width: 66ch; }
  .note .label {
    font-family: var(--font-mono);
    font-size: 11px; font-weight: 500; letter-spacing: .14em;
    text-transform: uppercase; color: var(--brand);
  }
  /* Было: подложка --sunken темнее фона и линия --line. В тёмной теме это
     читалось дырой, в светлой — вообще ничем. Нейтральная пара даёт врезке
     собственный тон в обеих темах, как он есть у brand / alarm / calm. */
  .note.pending {
    background: var(--neutral-soft);
    border-color: color-mix(in srgb, var(--neutral) 32%, transparent);
  }
  .note.pending .label { color: var(--neutral); }
  .note.pending p:last-child { color: var(--muted); font-style: italic; }

  footer.foot {
    border-top: 1px solid var(--line); padding-top: 22px;
    color: var(--dim); font-size: 14.5px;
  }

  /* Описание задачи рисуется в левой колонке слайдера — примерно вдвое ýже
     документа. Сетки, рассчитанные на широкую страницу, там сжимаются в кашу.
     Порог 780 попадает в этот случай и не задевает планшет (задача 706, блок 2371). */
  @media (max-width: 780px) {
    .tiles { grid-template-columns: repeat(2, 1fr); }
    .page { padding: 0; }
  }
  @media (max-width: 640px) { .tiles { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 420px) {
    .tiles { grid-template-columns: 1fr; }
    .row { grid-template-columns: 1fr; gap: 2px; }
  }


  .z h2 { margin: 30px 0 12px; font-size: 21px; font-weight: 700; letter-spacing: -.015em; }
  [data-doc] section > h2, [data-doc] .z h2 { font-family: var(--font-display); letter-spacing: -.01em; }
  .z h3 { margin: 22px 0 9px; font-size: 16.5px; font-weight: 650; color: var(--brand); }
  .z p { margin: 0 0 13px; font-size: 15.5px; line-height: 1.62; }
  .z ul { margin: 0 0 14px; padding-left: 22px; }
  .z li { margin: 0 0 7px; font-size: 15.5px; line-height: 1.58; }
  .z code { font-family: var(--font-mono); font-size: 13.5px;
            background: var(--sunken); border: 1px solid var(--line-soft);
            border-radius: 6px; padding: 1px 6px; }
  .z strong { font-weight: 650; color: var(--text); }
  .z hr { border: 0; border-top: 1px solid var(--line); margin: 26px 0; }

  /* ══ Приёмы разбора ═══════════════════════════════════════════════════════
     Двадцать разобранных страниц дали восемь повторяющихся форм. Они жили
     копиями в каждой странице; здесь они становятся общими.

     ПРАВИЛО ЦВЕТА. Ни одного литерального цвета — только токены. Заготовки
     были написаны литералами (#4ade80, #fbbf24, rgba(...)), и светлая тема
     их не переопределяла: пилюли бледнели, чипы сливались с фоном. Три
     дефекта из четырёх — один и тот же промах (задача 721, блок 302).

     ПРАВИЛО ШИРИНЫ. Ширина зависит от типа содержимого, а не от места
     в документе. Текст ограничен: строка длиннее ~62 знаков теряется глазом
     на обратном ходе. Данные — таблицы, сетки, полосы — идут во всю ширину:
     таблица, которую перенесли, перестаёт быть таблицей. */

  /* ── Пилюля вердикта ── */
  /* Три состояния на трёх существующих парах токенов; новых цветов не нужно.
     Рамка обязательна: в светлой теме подложки бледные, и без рамки пилюля
     перестаёт читаться как пилюля. */
  .v {
    display: inline-block; font-family: var(--font-mono);
    font-size: 11px; font-weight: 500; letter-spacing: .07em;
    text-transform: uppercase; white-space: nowrap;
    padding: 3px 9px 2px; border-radius: 4px;
    background: var(--card-2); border: 1px solid var(--line); color: var(--muted);
  }
  .v.yes  { background: var(--calm-soft);  border-color: color-mix(in srgb, var(--calm) 42%, transparent);  color: var(--calm); }
  /* Шафран на шафрановой подложке — единственная из трёх пар, которая
     не дотягивает до контраста мелкого текста: он тёплый и средний по
     светлоте, а не тёмный. Замер светлой темы дал 3.81 при пороге 4.5.
     Подмешиваем цвет текста: в светлой теме он тёмный и цвет темнеет,
     в тёмной светлый и цвет светлеет — обе стороны выигрывают. */
  .v.half { background: var(--brand-soft); border-color: color-mix(in srgb, var(--brand) 42%, transparent);
            color: color-mix(in srgb, var(--brand) 82%, var(--text)); }
  .v.no   { background: var(--alarm-soft); border-color: color-mix(in srgb, var(--alarm) 42%, transparent); color: var(--alarm); }

  /* ── Таблица с настоящей шапкой ── */
  /* Вторая форма таблицы, не замена .rows: там пары «поле → значение», здесь
     сетка со столбцами. Прокрутка живёт на обёртке — описание задачи рисуется
     в колонке вдвое ýже документа, и min-width без обёртки унёс бы текст
     за край (задача 706, блок 2371). */
  .tbl {
    overflow-x: auto; background: var(--card); border: 1px solid var(--line);
    border-radius: var(--radius); box-shadow: var(--shadow);
  }
  .tbl table { border-collapse: collapse; width: 100%; min-width: 520px; font-size: 15px; }
  .tbl th {
    font-family: var(--font-mono); font-size: 11px; font-weight: 500;
    letter-spacing: .07em; text-transform: uppercase; color: var(--muted);
    text-align: left; white-space: nowrap;
    padding: 12px 16px; border-bottom: 1px solid var(--line);
  }
  .tbl td { padding: 12px 16px; border-bottom: 1px solid var(--line-soft); vertical-align: top; }
  .tbl tr:last-child td { border-bottom: 0; }
  .tbl td:first-child { font-weight: 600; }
  .tbl td.num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

  /* ── Карточки находок ── */
  .find {
    display: grid; gap: 1px; background: var(--line);
    border: 1px solid var(--line); border-radius: var(--radius);
    overflow: hidden; box-shadow: var(--shadow);
  }
  .find > div {
    background: var(--card); padding: 17px 20px;
    display: grid; grid-template-columns: 30px 1fr; gap: 14px; align-items: start;
  }
  .find .num {
    font-family: var(--font-mono); font-size: 12.5px; color: var(--brand);
    font-variant-numeric: tabular-nums; padding-top: 3px;
  }
  .find h4 { margin: 0 0 4px; font-size: 16px; font-weight: 600; line-height: 1.35; }
  .find p { margin: 0; font-size: 14.5px; color: var(--muted); line-height: 1.5; max-width: 62ch; }

  /* ── Слоты «шаг → время → готово» ── */
  .steps {
    display: grid; gap: 1px; background: var(--line);
    border: 1px solid var(--line); border-radius: var(--radius);
    overflow: hidden; box-shadow: var(--shadow);
  }
  .steps > div {
    background: var(--card); padding: 17px 20px;
    display: grid; grid-template-columns: 86px 1fr; gap: 16px; align-items: start;
  }
  .steps .tm {
    font-family: var(--font-mono); font-size: 13px; color: var(--brand);
    font-variant-numeric: tabular-nums; padding-top: 2px;
  }
  .steps h4 { margin: 0 0 4px; font-size: 16px; font-weight: 600; }
  .steps h4 + p { margin: 0; font-size: 14.5px; color: var(--muted); max-width: 62ch; }
  .steps ul {
    list-style: none; margin: 11px 0 0; padding: 11px 0 0;
    display: grid; gap: 8px; border-top: 1px solid var(--line-soft);
  }
  .steps li { display: grid; grid-template-columns: 100px 1fr; gap: 12px; font-size: 14.5px; }
  .steps li b {
    font-family: var(--font-mono); font-size: 11px; font-weight: 500;
    letter-spacing: .07em; text-transform: uppercase; color: var(--muted); padding-top: 3px;
  }
  .steps li.done b { color: var(--calm); }

  /* ── Полосы прогресса ── */
  .bars { display: grid; gap: 11px; }
  .bar {
    background: var(--card); border: 1px solid var(--line);
    border-radius: var(--radius); box-shadow: var(--shadow); padding: 15px 18px;
  }
  .bar .hd { display: flex; justify-content: space-between; align-items: baseline; gap: 14px; margin-bottom: 10px; }
  .bar .nm { font-size: 15px; font-weight: 500; }
  .bar .qt {
    font-family: var(--font-mono); font-size: 12.5px; color: var(--muted);
    font-variant-numeric: tabular-nums; white-space: nowrap;
  }
  .bar .tr { height: 7px; background: var(--card-2); border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
  /* Ноль — тоже состояние. При width:0 остаётся засечка в четыре пикселя:
     пустая дорожка читается как «данных нет», а не как «ещё не начали». */
  .bar .fl { height: 100%; min-width: 4px; background: var(--brand); border-radius: 3px; }
  .bar.done .fl { background: var(--calm); }

  /* ── Полоса прогресса документа ──────────────────────────────────────────
     Живёт под шапкой и заполняется порталом при открытии: цифры приходят
     из задач кабинета, а не из сборки. Форма взята у .bar выше — та же
     дорожка, та же заливка, тот же приём «ноль тоже состояние».

     Правило [hidden] стоит ЯВНО и обязано идти последним. Любой display
     у .prog перебивает атрибут hidden, и полоса показалась бы всем — включая
     страницы, которым портал не ответит вовсе. Пустая полоса хуже её
     отсутствия: она говорит «ничего не сделано», а не «данных нет». */
  .prog {
    display: grid; gap: 10px;
    background: var(--card); border: 1px solid var(--line);
    border-radius: var(--radius); box-shadow: var(--shadow); padding: 15px 18px;
  }
  .prog .hd { display: flex; justify-content: space-between; align-items: baseline; gap: 14px; }
  .prog .nm { font-size: 15px; font-weight: 500; }
  .prog .qt {
    font-family: var(--font-mono); font-size: 12.5px; color: var(--muted);
    font-variant-numeric: tabular-nums; white-space: nowrap;
  }
  .prog .tr { height: 7px; background: var(--card-2); border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
  .prog .fl { height: 100%; min-width: 4px; width: 0; background: var(--calm); border-radius: 3px; }
  .prog .leg {
    margin: 0; font-family: var(--font-mono); font-size: 11.5px;
    color: var(--dim); letter-spacing: .02em;
  }
  .prog[hidden] { display: none; }

  /* ── Цитата клиента ── */
  .quote {
    border-left: 3px solid var(--brand); background: var(--card);
    border-radius: 0 var(--radius) var(--radius) 0; padding: 16px 20px;
    display: flex; flex-direction: column; gap: 9px;
  }
  .quote p { margin: 0; font-size: 16.5px; line-height: 1.5; font-style: italic; max-width: 60ch; }
  .quote cite { font-family: var(--font-mono); font-size: 12.5px; color: var(--muted); font-style: normal; }

  /* ── Сравнение двумя колонками ── */
  /* Колонка «стало» выделяется рамкой, а не другим фоном: два разных фона
     рядом читаются как две разные страницы, а не как две стороны одного. */
  .duo { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .duo > div {
    background: var(--card); border: 1px solid var(--line);
    border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden;
  }
  .duo .cap {
    font-family: var(--font-mono); font-size: 11.5px; font-weight: 500;
    letter-spacing: .07em; text-transform: uppercase; color: var(--muted);
    padding: 11px 18px; border-bottom: 1px solid var(--line);
  }
  .duo .in { padding: 17px 18px 20px; display: flex; flex-direction: column; gap: 8px; }
  .duo .in p { margin: 0; font-size: 14.5px; color: var(--muted); line-height: 1.55; max-width: 62ch; }
  .duo .in strong { color: var(--text); font-weight: 650; }
  .duo > div.now { border-color: color-mix(in srgb, var(--brand) 34%, transparent); }
  .duo > div.now .cap { color: var(--brand); }

  /* ── Закрывающий блок «что дальше» ── */
  /* Отличается от .note не украшением, а положением: он последний и отвечает
     на вопрос «и что теперь». Понятие уже знает сборщик — build_page.py, NEXT_RE. */
  .next {
    background: var(--brand-soft);
    border: 1px solid color-mix(in srgb, var(--brand) 30%, transparent);
    border-radius: var(--radius); padding: 20px 22px; margin-top: 6px;
    display: flex; flex-direction: column; gap: 11px;
  }
  .next .label {
    font-family: var(--font-mono); font-size: 11px; font-weight: 500;
    letter-spacing: .14em; text-transform: uppercase; color: var(--brand);
  }
  .next h3 { margin: 0; font-size: 19px; font-weight: 700; letter-spacing: -.01em; }
  [data-doc] .next h3 { font-family: var(--font-display); }
  .next p { margin: 0; max-width: 66ch; }

  /* ── Оглавление с якорями ── */
  .toc {
    background: var(--card); border: 1px solid var(--line);
    border-radius: var(--radius); box-shadow: var(--shadow);
    padding: 16px 20px 18px; display: flex; flex-direction: column; gap: 11px;
  }
  .toc .label {
    font-family: var(--font-mono); font-size: 11px; font-weight: 500;
    letter-spacing: .14em; text-transform: uppercase; color: var(--muted);
  }
  .toc ol { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 7px; counter-reset: toc; }
  /* Третья колонка — место метки статуса. Пункты без панели третьего элемента
     не несут вовсе и спокойно занимают первые две: auto у пустой колонки
     схлопывается в ноль, и строка выглядит как раньше. */
  .toc li { counter-increment: toc; display: grid; grid-template-columns: 26px 1fr auto; gap: 10px; align-items: baseline; }
  .toc li::before {
    content: counter(toc, decimal-leading-zero);
    font-family: var(--font-mono); font-size: 12px; color: var(--dim);
    font-variant-numeric: tabular-nums;
  }
  .toc a { border-bottom: 0; color: var(--text); font-size: 15.5px; font-weight: 500; }
  .toc a:hover { color: var(--brand); }
  /* Метка статуса пункта. Форма — пилюли вердиктов выше, включая починку
     контраста светлой темы из блока 302. Пустая метка не занимает места:
     до ответа портала её содержимое пусто, и рамки быть не должно. */
  .toc .st {
    font-family: var(--font-mono); font-size: 10.5px; font-weight: 500;
    letter-spacing: .06em; white-space: nowrap;
  }
  .toc .st:not(:empty) {
    padding: 2px 8px; border-radius: 999px; border: 1px solid transparent;
  }
  .toc .st.done { background: var(--calm-soft);    border-color: color-mix(in srgb, var(--calm) 42%, transparent);    color: var(--calm); }
  .toc .st.doing { background: var(--brand-soft);  border-color: color-mix(in srgb, var(--brand) 42%, transparent);
                   color: color-mix(in srgb, var(--brand) 82%, var(--text)); }
  .toc .st.todo { background: var(--neutral-soft); border-color: color-mix(in srgb, var(--neutral) 34%, transparent); color: var(--neutral); }
  /* Якорь не должен уезжать под верхний край фрейма: прокручивает портал,
     и без отступа заголовок раздела встаёт впритык к границе. */
  [data-doc] section[id] { scroll-margin-top: 18px; }
  html { scroll-behavior: smooth; }
  @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }

  /* ── Пороги для новых сеток ──────────────────────────────────────────────
     Те же три, что и у прежних форм: 780 — колонка слайдера, 640 — планшет,
     420 — телефон. Полная мобильная типографика по каждому блоку — блок 308. */
  @media (max-width: 780px) {
    .duo { grid-template-columns: 1fr; }
    .find > div { grid-template-columns: 24px 1fr; gap: 11px; }
    .steps > div { grid-template-columns: 1fr; gap: 8px; }
    .steps .tm { padding-top: 0; }
  }
  @media (max-width: 420px) {
    .steps li { grid-template-columns: 1fr; gap: 2px; }
    .steps li b { padding-top: 0; }
    /* На телефоне метка не помещается третьей колонкой и переносится строкой
       ниже. Без указания колонки она встаёт под номер и читается как мусор —
       ставим её под заголовок, к которому она относится. Полная мобильная
       типографика — блок 308. */
    .toc li { grid-template-columns: 22px 1fr; gap: 8px 8px; }
    .toc li .st { grid-column: 2; justify-self: start; }
    .bar .hd { flex-direction: column; align-items: flex-start; gap: 3px; margin-bottom: 8px; }
  }
`;
})(window);
