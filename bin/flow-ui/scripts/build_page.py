#!/usr/bin/env python3
"""build_page.py — сборка страницы Экстранета из markdown (task 701 block 3).

Читает .md, размечает текст на блоки каталога и пишет {basename}.page.json
рядом с исходником. Формат — docs/PAGE_FORMAT.md.

Принцип: блоки выбираются из фиксированного каталога, вёрстка не изобретается.
Что не выводится из текста однозначно (zones / stages / kpi / criteria) —
сознательно НЕ угадывается: лучше отдать text, чем собрать схему из случайных
абзацев.

Использование:
    python3 scripts/build_page.py путь/к/файлу.md [--stdout]
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PAGE_SUFFIX = ".page.json"
FORMAT_VERSION = 1

# Маркеры врезок — те же, что распознаёт doc-patterns.js
CALLOUT_KINDS = [
    (re.compile(r"^\[!\s*(внимание|осторожно|warning|caution)\s*\]", re.I), "warn", "Внимание"),
    (re.compile(r"^\[!\s*(опасно|блокер|danger|important)\s*\]", re.I), "danger", "Важно"),
    (re.compile(r"^\[!\s*(важно|заметка|note|tip|подсказка)\s*\]", re.I), "", "Заметка"),
]
NEXT_RE = re.compile(r"(следующ|что дальше|дальнейшие шаги|next steps)", re.I)
META_HEAD_RE = (re.compile(r"параметр|поле|признак", re.I), re.compile(r"значение|описание", re.I))
BOLD_LEAD_RE = re.compile(r"^\*\*(.+?)\*\*\.?\s*(.*)$", re.S)
BOLD_ONLY_RE = re.compile(r"^\*\*(.+?):?\*\*:?$")


def _part_ahead(nodes, i):
    """Правда, если ближайший следующий заголовок глубже второго уровня.

    Так отличаем название части от обычного раздела: часть всегда открывает
    группу разделов. Заголовок того же или меньшего уровня раньше — значит
    часть пуста, и заголовок остаётся обычным разделом.
    """
    for n in nodes[i + 1:]:
        if n["kind"] != "heading":
            continue
        return n["level"] > 2
    return False


def strip_md(text):
    """Убирает инлайновую разметку — в слоты кладётся чистый текст."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text.strip()


def parse_nodes(md):
    """Markdown в плоский список узлов. Только то, что нужно каталогу."""
    nodes, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            nodes.append({"kind": "heading", "level": len(m.group(1)), "text": strip_md(m.group(2))})
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            nodes.append({"kind": "hr"})
            i += 1
            continue

        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            nodes.append({"kind": "quote", "text": " ".join(x.strip() for x in buf).strip()})
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            head = [strip_md(c) for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([strip_md(c) for c in lines[i].strip().strip("|").split("|")])
                i += 1
            nodes.append({"kind": "table", "head": head, "rows": rows})
            continue

        m = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if m:
            items, i = collect_list(lines, i, r"^\s*\d+[.)]\s+")
            nodes.append({"kind": "ol", "items": items})
            continue

        if re.match(r"^[-*+]\s+", stripped):
            items, i = collect_list(lines, i, r"^\s*[-*+]\s+")
            nodes.append({"kind": "ul", "items": items})
            continue

        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\||```|-{3,}$)", lines[i]
        ):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            nodes.append({"kind": "para", "raw": " ".join(buf), "text": strip_md(" ".join(buf))})
        else:
            i += 1
    return nodes


def collect_list(lines, i, marker_re):
    """Пункты списка вместе с их продолжениями.

    Пункт может переноситься на следующую строку с отступом — обычный markdown.
    Без склейки список рвётся на текстовые блоки, а фраза разрывается посередине
    (найдено сквозным прогоном на реальном саммари, task 701 block 5).
    """
    marker = re.compile(marker_re)
    items = []
    while i < len(lines):
        line = lines[i]
        if marker.match(line):
            items.append(marker.sub("", line).strip())
            i += 1
        elif (
            items
            and line.strip()
            and line[:1].isspace()
            and not re.match(r"^\s*(#{1,6}\s|>|\||```|-{3,}$)", line)
        ):
            items[-1] += " " + line.strip()
            i += 1
        else:
            break
    return items, i


def bold_lead_items(items):
    """Список, где КАЖДЫЙ пункт начинается с жирного → пары заголовок/тело.
    Одно исключение отменяет паттерн целиком — как в doc-patterns.js."""
    if len(items) < 3:
        return None
    out = []
    for it in items:
        m = BOLD_LEAD_RE.match(it.strip())
        if not m:
            return None
        out.append({"title": strip_md(m.group(1)).rstrip(".:"), "body": strip_md(m.group(2))})
    return out


def build_blocks(nodes):
    """Узлы в блоки каталога. Что не выводится однозначно — остаётся text."""
    blocks, stats, i, hero_done = [], {}, 0, False
    part = None  # название текущей части — надзаголовок для разделов внутри неё

    def add(b):
        blocks.append(b)
        stats[b["type"]] = stats.get(b["type"], 0) + 1

    while i < len(nodes):
        n = nodes[i]

        # Шапка: первый h1 + абзац «Тема:» + таблица «Параметр / Значение»
        if not hero_done and n["kind"] == "heading" and n["level"] == 1:
            hero = {"type": "hero", "title": n["text"]}
            i += 1
            if i < len(nodes) and nodes[i]["kind"] == "para":
                m = re.match(r"^\*\*(тема|о чём|предмет)\s*:?\*\*:?\s*(.*)$", nodes[i]["raw"].strip(), re.I | re.S)
                if m:
                    hero["lead"] = strip_md(m.group(2))
                    i += 1
            add(hero)
            hero_done = True

            # Таблица «Параметр / Значение» сразу за шапкой — отдельный блок
            # плашек. Раньше она уезжала в hero.chips плоской строкой, и
            # проекция «Страница» выглядела беднее «Текста», где то же самое
            # рисует doc-patterns.js как .doc-meta (задача 701 блок 5 раунд 2).
            if i < len(nodes) and nodes[i]["kind"] == "table":
                h = nodes[i]["head"]
                if len(h) == 2 and META_HEAD_RE[0].search(h[0]) and META_HEAD_RE[1].search(h[1]):
                    items = [{"label": r[0], "value": r[1]}
                             for r in nodes[i]["rows"] if len(r) == 2 and r[0] and r[1]]
                    if items:
                        add({"type": "meta", "items": items})
                        i += 1
            continue

        if n["kind"] == "heading":
            # Закрывающий блок: заголовок про следующие шаги + абзац
            if NEXT_RE.search(n["text"]) and i + 1 < len(nodes) and nodes[i + 1]["kind"] == "para":
                full = nodes[i + 1]["text"]
                dot = full.find(". ")
                when, body = (full[:dot].strip(), full[dot + 1:].strip()) if 8 <= dot <= 60 else (full, "")
                b = {"type": "next", "label": n["text"], "when": when}
                if body:
                    b["body"] = body
                add(b)
                i += 2
                continue
            # Два уровня разделов. Заголовок второго уровня, за которым идёт
            # третий, — это не раздел, а НАЗВАНИЕ ЧАСТИ: оно уезжает в eyebrow
            # каждого раздела внутри части. Так одиннадцать равновесных
            # заголовков читаются как три группы, и при этом не появляется ни
            # нового типа блока, ни новой разметки — только уровень заголовка,
            # который разбирался и раньше (см. level в parse и шапку выше).
            #
            # Правило срабатывает ТОЛЬКО когда в документе есть h3. Ни один
            # существующий исходник страниц h3 не использует, поэтому собранные
            # ранее страницы не меняются. Задача 718, блок 20140.
            if n["level"] == 2 and _part_ahead(nodes, i):
                part = n["text"]
                i += 1
                continue
            b = {"type": "section", "title": n["text"]}
            if n["level"] >= 3 and part:
                b["eyebrow"] = part
            add(b)
            i += 1
            continue

        if n["kind"] == "quote":
            hit = next((k for k in CALLOUT_KINDS if k[0].match(n["text"])), None)
            if hit:
                body = strip_md(hit[0].sub("", n["text"]).lstrip(" :—-"))
                b = {"type": "callout", "label": hit[2], "body": body}
                if hit[1]:
                    b["kind"] = hit[1]
                add(b)
            else:
                add({"type": "quote", "text": strip_md(n["text"])})
            i += 1
            continue

        if n["kind"] in ("ol", "ul"):
            pairs = bold_lead_items(n["items"])
            if pairs:
                add({"type": "steps", "items": pairs})
            else:
                add({"type": "text", "paragraphs": [strip_md(x) for x in n["items"]]})
            i += 1
            continue

        if n["kind"] == "table":
            add({"type": "table", "head": n["head"], "rows": n["rows"]})
            i += 1
            continue

        if n["kind"] == "hr":
            add({"type": "divider"})
            i += 1
            continue

        # Пары «жирный абзац-заголовок + список» подряд → карточки
        if n["kind"] == "para" and BOLD_ONLY_RE.match(n["raw"].strip()):
            group = []
            j = i
            while (
                j + 1 < len(nodes)
                and nodes[j]["kind"] == "para"
                and BOLD_ONLY_RE.match(nodes[j]["raw"].strip())
                and nodes[j + 1]["kind"] in ("ul", "ol")
            ):
                title = BOLD_ONLY_RE.match(nodes[j]["raw"].strip()).group(1).rstrip(":")
                # Пункты сохраняются списком: рендерер разложит их в ul, как
                # это делает doc-patterns.js в текстовой проекции. Склейка
                # через « · » давала простыню вместо буллетов.
                group.append({"title": strip_md(title),
                              "body": [strip_md(x) for x in nodes[j + 1]["items"]]})
                j += 2
            if len(group) >= 2:
                add({"type": "cards", "items": group})
                i = j
                continue

        if n["kind"] == "para":
            para = [n["text"]]
            i += 1
            while i < len(nodes) and nodes[i]["kind"] == "para" and not BOLD_ONLY_RE.match(nodes[i]["raw"].strip()):
                para.append(nodes[i]["text"])
                i += 1
            add({"type": "text", "paragraphs": para})
            continue

        i += 1

    return blocks, stats



# ─────────────────────────────────────────────────────────────────────────────
# Проекция «фрейм» — документ кабинета. Контракт: docs/KABINET_DOC_FORMAT.md
#
# Разбор markdown общий с проекцией блоков: parse_nodes() не знает ни про блоки,
# ни про фрейм. Именно поэтому проекция — ключ, а не второй скрипт: копия дала бы
# два разбора markdown, которые разъедутся на первой правке (задача 721, блок 104).
# ─────────────────────────────────────────────────────────────────────────────

KABINET_TYPES = {"cover", "homework", "feedback", "theses", "method"}
KABINET_FORMAT_VERSION = 2


class BuildRefused(Exception):
    """Отказ собрать. Наполовину собранный документ в кабинете клиента хуже,
    чем несобранный — поэтому отказ, а не пропуск (KABINET_DOC_FORMAT.md § 8)."""


def parse_front_matter(md):
    """YAML-шапка исходника → (поля, остаток текста). Шапки нет → пустые поля."""
    if not md.startswith("---"):
        return {}, md
    end = md.find("\n---", 3)
    if end == -1:
        return {}, md
    head, rest = md[3:end], md[end + 4:]
    meta = {}
    for line in head.split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, rest.lstrip("\n")


def esc(text):
    """Экранирование для вставки в шаблонную строку оболочки фрейма.

    Незакрытая шаблонная строка роняет страницу у клиента целиком — это не
    косметика, а единственное, что стоит между опечаткой в тексте и белым
    экраном в кабинете."""
    return (str(text or "")
            .replace("\\", "\\\\")
            .replace("`", "\\`")
            .replace("${", "$\\{"))


def html_esc(text):
    return (str(text or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# Адреса, которые документ кабинета имеет право сделать ссылкой. Контракт § 6.
# Список разрешённых, а не запрещённых: файл приходит из хранилища тенанта
# и доверенным источником разметки не является — ровно поэтому у проекции
# блоков ссылок нет вовсе (PAGE_FORMAT.md § 5). Всё, чего нет в списке,
# остаётся текстом, а не превращается в ссылку с чужой схемой.
HREF_OK = re.compile(r"^(#task/[A-Za-z0-9_-]+|#ep/\d+|https?://[^\s\"<>]+)$")

INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
# Оглядка на соседние звёздочки — дословно из strip_md. Без неё «**жирное**»
# разберётся как две пары курсива, и жирное исчезнет совсем.
INLINE_ITAL = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.S)
INLINE_CODE = re.compile(r"`(.+?)`", re.S)
INLINE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def node_src(n):
    """Сырой markdown узла. Разбор кладёт в text уже ОЧИЩЕННЫЙ текст —
    strip_md отработал на этапе parse_nodes, — а сырая строка остаётся в raw.
    Проекция блоков берёт text и права; проекции фрейма нужен raw, иначе
    преобразовывать в теги уже нечего (поймано синтетическим прогоном,
    задача 721, блок 303 раунд 2)."""
    return n.get("raw") or n.get("text", "")


def inline_md(text):
    """Инлайновая разметка абзаца в теги. Экранирование ПЕРВЫМ, теги вторым.

    Наоборот — и html_esc съест собственные угловые скобки тегов, превратив
    <strong> в &lt;strong&gt;. Читатель увидит текст тега вместо жирного,
    и ошибки при этом не будет.

    strip_md рядом остаётся и не меняется: на ней стоит проекция блоков,
    где разметка в слотах запрещена контрактом. Здесь другая задача —
    документ кабинета живёт в песочном фрейме и разметку нести может
    (задача 721, блок 303 раунд 2)."""
    out = html_esc(text)

    def link(m):
        label, href = m.group(1), m.group(2).strip()
        if not HREF_OK.match(href):
            return label          # чужая схема — остаётся текстом, не ссылкой
        return f'<a href="{href}">{label}</a>'

    out = INLINE_LINK.sub(link, out)
    out = INLINE_CODE.sub(r"<code>\1</code>", out)
    out = INLINE_BOLD.sub(r"<strong>\1</strong>", out)
    out = INLINE_ITAL.sub(r"<em>\1</em>", out)
    return out.strip()


# ── Маркеры секций в исходнике ────────────────────────────────────────────
# Секция объявляется абзацем-маркером [!имя] перед своим блоком. Приём взят
# у врезок проекции блоков (CALLOUT_KINDS выше) — там он проверен на живых
# материалах, и человеку не приходится учить второй синтаксис.
#
# ПОЧЕМУ ИМЕНА НЕ ПЕРЕСЕКАЮТСЯ С ВРЕЗОЧНЫМИ. Один и тот же исходник собирают
# обе проекции. Имя врезки, означающее здесь что-то другое, молча сменило бы
# вид врезки в десяти уже собранных материалах. Врезочные имена поэтому
# сохраняют ровно своё значение и здесь — они уходят в ветку "note".
SECTION_MARKS = {
    "плитки":      "tiles",
    "вердикты":    "verdicts",
    "находки":     "findings",
    "шаги":        "steps",
    "полосы":      "counters",
    "сравнение":   "compare",
    "что дальше":  "next",
    "оглавление":  "toc",
    "подвал":      "foot",
    "ещё не сделано": "pending",
    "еще не сделано": "pending",
}
# Тело может стоять В ТОМ ЖЕ абзаце, что и маркер: разбор склеивает строки,
# идущие подряд, и «[!важно]» с текстом на следующей строке приходит одним
# узлом. Приём врезок проекции блоков ровно такой же — там маркер тоже
# открывает абзац, а не занимает его целиком (поймано прогоном, не чтением).
MARK_RE = re.compile(r"^\[!\s*([^\]]+?)\s*\]\s*(.*)$", re.S)

# Значение ячейки вердикта → класс пилюли. Неизвестное значение остаётся
# обычной ячейкой: пилюля, которую никто не заводил, хуже её отсутствия.
VERDICT_PILLS = {
    "сделано": "yes", "готово": "yes", "да": "yes",
    "наполовину": "half", "частично": "half", "в работе": "half",
    "не сделано": "no", "нет": "no", "просрочено": "no",
}


def section_mark(node):
    """(имя секции, остаток абзаца) из маркера. Не маркер — (None, "").

    Неизвестное имя — отказ: молча пропустить значит потерять содержание."""
    if node.get("kind") != "para":
        return None, ""
    m = MARK_RE.match(node.get("raw", "").strip())
    if not m:
        return None, ""
    name = m.group(1).strip().lower()
    rest = m.group(2).strip()
    if name in SECTION_MARKS:
        return SECTION_MARKS[name], rest
    probe = "[!" + name + "]"
    for rx, _kind, _title in CALLOUT_KINDS:
        if rx.match(probe):
            return "note", rest
    raise BuildRefused(
        f"секция «{name}» не из каталога § 4. Молча пропустить значит потерять "
        "содержание (KABINET_DOC_FORMAT § 8)")


def _split_pair(text, default=""):
    """«значение — подпись» → (значение, подпись). Тире любое из трёх."""
    for dash in (" — ", " – ", " - "):
        if dash in text:
            a, b = text.split(dash, 1)
            return a.strip(), b.strip()
    return text.strip(), default


def _count_ratio(text):
    """«4 из 11» → (4.0, 11.0). Не разобралось — (None, None)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:из|/)\s*(\d+(?:[.,]\d+)?)", text)
    if not m:
        return None, None
    try:
        return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    except ValueError:
        return None, None


def section_id(key, ordinal):
    """Якорь раздела. Ключ панели, когда он есть, — иначе порядковый номер.

    Порядковый номер один не годится: ссылка на якорь уже ушла клиенту, а
    раздел переставили — и якорь показывает на чужой текст. Ключ переживает
    перестановку, потому что он свойство раздела, а не его места."""
    return key if key else f"r{ordinal}"


def build_frame(nodes, meta):
    """Узлы + шапка → разметка документа кабинета. Стилей не несёт: их даёт
    портал впрыском в оболочку фрейма (задача 721, блок 101)."""
    doc_type = meta.get("type")
    if not doc_type:
        raise BuildRefused("нет поля type — тип определяет форму, угадывать нельзя")
    if doc_type not in KABINET_TYPES:
        raise BuildRefused(
            f"тип «{doc_type}» неизвестен. Известные: " + ", ".join(sorted(KABINET_TYPES)))
    title = meta.get("title")
    if not title:
        raise BuildRefused("нет поля title — документ без заголовка неотличим от обрывка")

    out, stats = [], {}
    def bump(k):
        stats[k] = stats.get(k, 0) + 1

    # Предпроход: оглавлению нужны заголовки и якоря РАНЬШЕ, чем встретится
    # первый раздел. Второй проход дешевле, чем откладывать вывод.
    toc_items, ordinal = [], 0
    for n in nodes:
        if n.get("kind") == "heading" and n.get("level") == 2:
            ordinal += 1
            raw = strip_md(n.get("text", ""))
            m = re.search(r"\s*\{#([A-Za-z0-9_-]+)\}\s*$", raw)
            key = m.group(1) if m else None
            if m:
                raw = raw[: m.start()].rstrip()
            # Ключ едет третьим элементом, а не выводится из якоря. Якорь
            # панели РАВЕН ключу (section_id), и отличить его от «r7» можно
            # только угадыванием — а ключ бывает и коротким, и похожим
            # на что угодно из [A-Za-z0-9_-].
            toc_items.append((section_id(key, ordinal), raw, key))

    # data-doc помечает страницу, собранную сборщиком. По нему общий стиль
    # включает дисплейную типографику — старые материалы её не получают
    # и выглядят как выглядели (задача 721, блок 301).
    out.append(f'<div class="page" data-doc="{html_esc(doc_type)}">')
    out.append('<header class="head">')
    if meta.get("kicker"):
        out.append(f'<p class="eyebrow">{html_esc(meta["kicker"])}</p>')
    out.append(f"<h1>{html_esc(title)}</h1>")
    if meta.get("lead"):
        out.append(f'<p class="lead">{html_esc(meta["lead"])}</p>')
    out.append("</header>")
    bump("head")

    # Полоса прогресса. Пустая и скрытая: числа приходят от портала при
    # открытии, а не запекаются сборкой. Запечённая цифра протухает к следующей
    # встрече — ровно так на корне кабинета висит «9 / 11 задач домашки
    # сделано», когда задач двадцать шесть (задача 721, решение 05).
    #
    # Ставится только там, где есть панели: документу без задач считать нечего,
    # а пустая полоса читалась бы как «ничего не сделано».
    if any(key for _sid, _title, key in toc_items):
        out.append('<div class="prog" data-prog hidden>')
        out.append('<div class="hd"><span class="nm"></span><span class="qt"></span></div>')
        out.append('<div class="tr"><div class="fl"></div></div>')
        out.append('<p class="leg"></p>')
        out.append("</div>")
        bump("prog")

    open_section = False
    pending_mark = None
    ordinal = 0
    i = 0
    while i < len(nodes):
        n = nodes[i]
        kind = n.get("kind")

        mark, mark_rest = section_mark(n)
        if mark:
            # Оглавление содержания за собой не тянет — оно строится само.
            if mark == "toc":
                i += 1
                if toc_items:
                    out.append('<nav class="toc">')
                    out.append('<span class="label">В этом документе</span>')
                    out.append("<ol>")
                    for sid, stitle, skey in toc_items:
                        # Пункт-панель несёт ключ и пустое место под метку;
                        # заполняет их портал при открытии. Пункт без панели
                        # (введение, «что дальше») не получает ни того ни
                        # другого — метка у него означала бы задачу, которой
                        # нет (задача 721, блок 209).
                        if skey:
                            out.append(
                                f'<li data-key="{html_esc(skey)}">'
                                f'<a href="#{html_esc(sid)}">{html_esc(stitle)}</a>'
                                f'<span class="st"></span></li>')
                        else:
                            out.append(
                                f'<li><a href="#{html_esc(sid)}">{html_esc(stitle)}</a></li>')
                    out.append("</ol></nav>")
                    bump("toc")
                continue
            pending_mark = mark
            if not mark_rest:
                i += 1
                continue
            # Маркер с телом в том же абзаце: дальше по циклу идёт уже тело,
            # а не маркер. Указатель не двигаем — его сдвинет ветка секции.
            # text оставляем сырым: ниже он идёт через inline_md, а предварительный
            # strip_md срезал бы разметку до того, как её успеют превратить в теги.
            n = {"kind": "para", "raw": mark_rest, "text": mark_rest}
            kind = "para"

        # Заголовок глубже второго уровня выпадал МОЛЧА: ветка ниже ловит
        # только level == 2, а всё прочее доходило до конца цикла и терялось
        # без единого слова. Ровно тот исход, который § 8 запрещает — и поймать
        # его удалось только переносом старых страниц, где `###` стоит в каждом
        # блоке задачи, недели и контура (задача 721, блок 201).
        #
        # Отказ, а не отрисовка: третьего уровня нет в каталоге § 4, и завести
        # его молча значит получить возможность, которой нет в контракте.
        # Ни один существующий исходник `###` не использует — проверено.
        if kind == "heading" and n.get("level", 0) >= 3:
            raise BuildRefused(
                f"заголовок третьего уровня «{strip_md(n.get('text',''))[:60]}» — "
                "в каталоге § 4 такой секции нет, и молча пропустить значит "
                "потерять содержание (§ 8). Сделайте его разделом «## Заголовок», "
                "строкой таблицы или жирным началом пункта в «[!находки]»")

        if kind == "heading" and n.get("level") == 2:
            if open_section:
                out.append("</section>")
            ordinal += 1
            # Ключ панели пишется в заголовке: «## Заголовок {#ключ}». Раздел
            # с ключом — это панель: из неё скилл задач заводит задачу кабинета,
            # а ссылка внутри ведёт в эту задачу (KABINET_DOC_FORMAT § 4).
            raw_title = strip_md(n.get("text", ""))
            m = re.search(r"\s*\{#([A-Za-z0-9_-]+)\}\s*$", raw_title)
            key = m.group(1) if m else None
            if m:
                raw_title = raw_title[: m.start()].rstrip()
            sid = section_id(key, ordinal)
            attrs = f' id="{html_esc(sid)}"'
            if key:
                attrs += f' data-key="{html_esc(key)}"'
            out.append(f"<section{attrs}>")
            out.append(f"<h2>{html_esc(raw_title)}</h2>")
            if key:
                # Стрелку рисует стиль: правило a[href^="#task/"]::after покрывает и ссылки,
                # написанные в исходнике руками. Дублировать её в разметке значит получить
                # «Открыть задачу → →» — поймано прогоном блока 306 в живом кабинете.
                out.append(f'<p class="mono"><a href="#task/{html_esc(key)}">Открыть задачу</a></p>')
                bump("panel")
            open_section = True
            bump("section")
            pending_mark = None
            i += 1
            continue

        mk, pending_mark = pending_mark, None

        if mk == "tiles" and kind in ("ul", "ol"):
            out.append('<div class="tiles">')
            for it in n.get("items", []):
                alarm = it.strip().startswith("!")
                body = it.strip().lstrip("!").strip()
                value, label = _split_pair(strip_md(body))
                cls = "tile alarm" if alarm else "tile"
                out.append(f'<div class="{cls}"><b>{html_esc(value)}</b>'
                           f"<span>{html_esc(label)}</span></div>")
            out.append("</div>")
            bump("tiles")
            i += 1
            continue

        if mk == "counters" and kind in ("ul", "ol"):
            out.append('<div class="bars">')
            for it in n.get("items", []):
                label, amount = _split_pair(strip_md(it))
                done, total = _count_ratio(amount)
                pct = 0 if not total else max(0, min(100, round(done / total * 100)))
                cls = "bar done" if (total and done >= total) else "bar"
                out.append(f'<div class="{cls}"><div class="hd">'
                           f'<span class="nm">{html_esc(label)}</span>'
                           f'<span class="qt">{html_esc(amount)}</span></div>'
                           f'<div class="tr"><div class="fl" style="width:{pct}%"></div></div></div>')
            out.append("</div>")
            bump("bars")
            i += 1
            continue

        if mk == "findings" and kind in ("ul", "ol"):
            pairs = bold_lead_items(n.get("items", []))
            out.append('<div class="find">')
            for num, it in enumerate(n.get("items", []), start=1):
                if pairs:
                    head_txt, body_txt = pairs[num - 1]["title"], pairs[num - 1]["body"]
                else:
                    head_txt, body_txt = _split_pair(strip_md(it))
                out.append(f'<div><span class="num">{num:02d}</span><div>'
                           f"<h4>{html_esc(head_txt)}</h4>"
                           + (f"<p>{html_esc(body_txt)}</p>" if body_txt else "")
                           + "</div></div>")
            out.append("</div>")
            bump("find")
            i += 1
            continue

        if mk == "steps" and kind == "table":
            out.append('<div class="steps">')
            for row in n.get("rows", []):
                cells = [strip_md(c) for c in row]
                when = cells[0] if cells else ""
                head_txt = cells[1] if len(cells) > 1 else ""
                marks = cells[2] if len(cells) > 2 else ""
                out.append(f'<div><span class="tm">{html_esc(when)}</span><div>'
                           f"<h4>{html_esc(head_txt)}</h4>")
                items = [x.strip() for x in marks.split(";") if x.strip()]
                if items:
                    out.append("<ul>")
                    for it in items:
                        label, body = (it.split(":", 1) + [""])[:2] if ":" in it else ("", it)
                        li_cls = ' class="done"' if label.strip().lower().startswith("готово") else ""
                        out.append(f"<li{li_cls}><b>{html_esc(label.strip() or 'осталось')}</b>"
                                   f"<span>{html_esc(body.strip())}</span></li>")
                    out.append("</ul>")
                out.append("</div></div>")
            out.append("</div>")
            bump("steps")
            i += 1
            continue

        if mk == "verdicts" and kind == "table":
            out.append('<div class="tbl"><table>')
            if n.get("head"):
                out.append("<thead><tr>"
                           + "".join(f"<th>{inline_md((c))}</th>" for c in n["head"])
                           + "</tr></thead>")
            out.append("<tbody>")
            for row in n.get("rows", []):
                out.append("<tr>")
                for c in row:
                    val = strip_md(c)
                    pill = VERDICT_PILLS.get(val.strip().lower())
                    if pill:
                        out.append(f'<td><span class="v {pill}">{html_esc(val)}</span></td>')
                    else:
                        out.append(f"<td>{html_esc(val)}</td>")
                out.append("</tr>")
            out.append("</tbody></table></div>")
            bump("tbl")
            i += 1
            continue

        if mk == "compare" and kind == "table":
            caps = [strip_md(c) for c in (n.get("head") or ["Было", "Стало"])][:2]
            cols = [[], []]
            for row in n.get("rows", []):
                for j in (0, 1):
                    if len(row) > j and strip_md(row[j]):
                        cols[j].append(row[j])
            out.append('<div class="duo">')
            for j in (0, 1):
                cls = ' class="now"' if j == 1 else ""
                out.append(f"<div{cls}><div class=\"cap\">{html_esc(caps[j] if len(caps) > j else '')}</div>"
                           '<div class="in">')
                for p in cols[j]:
                    out.append(f"<p>{inline_md(p)}</p>")
                out.append("</div></div>")
            out.append("</div>")
            bump("duo")
            i += 1
            continue

        if mk == "next":
            out.append('<div class="next">')
            out.append('<span class="label">Что дальше</span>')
            if kind == "para":
                out.append(f"<h3>{inline_md(node_src(n))}</h3>")
                i += 1
                if i < len(nodes) and nodes[i].get("kind") == "para" and not section_mark(nodes[i])[0]:
                    out.append(f"<p>{inline_md(node_src(nodes[i]))}</p>")
                    i += 1
            if i < len(nodes) and nodes[i].get("kind") in ("ul", "ol"):
                out.append('<ul class="plain">')
                for it in nodes[i].get("items", []):
                    out.append(f"<li>{inline_md((it))}</li>")
                out.append("</ul>")
                i += 1
            out.append("</div>")
            bump("next")
            continue

        if mk == "foot" and kind == "para":
            out.append(f'<footer class="foot">{inline_md(node_src(n))}</footer>')
            bump("foot")
            i += 1
            continue

        if mk in ("note", "pending"):
            cls = "note pending" if mk == "pending" else "note"
            label = "Ещё не сделано" if mk == "pending" else "Важно"
            out.append(f'<div class="{cls}"><span class="label">{label}</span>')
            if kind == "para":
                out.append(f"<p>{inline_md(node_src(n))}</p>")
            elif kind in ("ul", "ol"):
                for it in n.get("items", []):
                    out.append(f"<p>{inline_md((it))}</p>")
            out.append("</div>")
            bump("note")
            i += 1
            continue

        # Немаркированные узлы — прежнее поведение, без изменений.
        if kind == "para":
            out.append(f"<p>{inline_md(node_src(n))}</p>")
            bump("text")
        elif kind in ("ul", "ol"):
            out.append('<ul class="plain">')
            for it in n.get("items", []):
                out.append(f"<li>{inline_md((it))}</li>")
            out.append("</ul>")
            bump("list")
        elif kind == "quote":
            # Цитата клиента его словами — своя секция каталога, не врезка.
            # До блока 303 она выдавалась классом .note: врезка и цитата
            # выглядели одинаково, хотя в каталоге § 4 это разные секции.
            body = (n.get("text", "") or "").strip()
            author = ""
            m = re.search(r"[—–-]\s*([^—–-]{1,80})$", body)
            if m and len(body) - m.start() < len(body) / 2:
                author = m.group(1).strip()
                body = body[: m.start()].strip()
            out.append(f'<blockquote class="quote"><p>{inline_md(body)}</p>'
                       + (f"<cite>{html_esc(strip_md(author))}</cite>" if author else "")
                       + "</blockquote>")
            bump("quote")
        elif kind == "table":
            out.append('<dl class="rows">')
            # В форме кабинета таблица без маркера — это пары «поле → значение»,
            # у неё нет шапки. Разбор markdown всегда считает первую строку
            # шапкой и кладёт её отдельно в head — поэтому head здесь
            # возвращается в строки, иначе первая пара каждой таблицы молча
            # теряется (поймано на прогоне).
            table_rows = list(n.get("rows", []))
            if n.get("head"):
                table_rows.insert(0, n["head"])
            for row in table_rows:
                cells = [inline_md((c)) for c in row]
                if len(cells) >= 2:
                    out.append(f"<div class=\"row\"><dt>{cells[0]}</dt><dd>{cells[1]}</dd></div>")
            out.append("</dl>")
            bump("rows")
        i += 1

    if open_section:
        out.append("</section>")
    out.append("</div>")
    return "\n".join(out), stats


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    to_stdout = "--stdout" in sys.argv
    if not args:
        print("Использование: build_page.py путь/к/файлу.md [--stdout]", file=sys.stderr)
        return 2

    src = Path(args[0])
    if not src.is_file() or src.suffix.lower() != ".md":
        print(f"Не markdown-файл: {src}", file=sys.stderr)
        return 2

    # PAGE_FORMAT.md § 3 — отпечаток от БАЙТОВ, без нормализации переводов строк
    raw_bytes = src.read_bytes()
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    md = raw_bytes.decode("utf-8")

    # Проекция по умолчанию — блоки: десять материалов собраны ею, и поведение
    # без ключа не меняется (задача 721, блок 104).
    projection = "blocks"
    for a in sys.argv[1:]:
        if a.startswith("--projection="):
            projection = a.split("=", 1)[1].strip()
    if projection not in ("blocks", "frame"):
        print(f"Неизвестная проекция: {projection}. Известные: blocks, frame", file=sys.stderr)
        return 2

    if projection == "frame":
        meta, body = parse_front_matter(md)
        try:
            html, stats = build_frame(parse_nodes(body), meta)
        except BuildRefused as e:
            print(f"Отказ собрать: {e}", file=sys.stderr)
            return 2
        header = (
            f"<!-- kabinet-doc v{KABINET_FORMAT_VERSION} · type={meta.get('type')} · "
            f"built_at={datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')} · "
            f"source_name={src.name} · source_hash={source_hash} -->\n"
        )
        text = header + html + "\n"
        if to_stdout:
            print(text, end="")
        else:
            out = src.with_name(src.stem + ".html")
            out.write_text(text, encoding="utf-8")
            print(f"Собрано: {out}")
        print(f"Тип: {meta.get('type')}  ·  отпечаток: {source_hash[:16]}…", file=sys.stderr)
        print("Секций: " + " · ".join(f"{k} {v}" for k, v in sorted(stats.items())), file=sys.stderr)
        return 0

    blocks, stats = build_blocks(parse_nodes(md))
    page = {
        "version": FORMAT_VERSION,
        "built_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source_name": src.name,
        "source_hash": source_hash,
        "blocks": blocks,
    }
    text = json.dumps(page, ensure_ascii=False, indent=2) + "\n"

    if to_stdout:
        print(text, end="")
    else:
        out = src.with_name(src.stem + PAGE_SUFFIX)
        out.write_text(text, encoding="utf-8")
        print(f"Собрано: {out}")

    print(f"Блоков: {len(blocks)}  ·  отпечаток: {source_hash[:16]}…", file=sys.stderr)
    print("Распознано: " + " · ".join(f"{k} {v}" for k, v in sorted(stats.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
