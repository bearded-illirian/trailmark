#!/usr/bin/env python3
"""Старая страница кабинета → исходник markdown нашего формата.

ЗАЧЕМ. Пятнадцать материалов кабинета Артёма собраны руками до контракта:
каждый несёт собственный блок <style> на ~290 строк и свою вёрстку. Перенести
их на конструкцию значит получить из каждого исходник по KABINET_DOC_FORMAT,
который потом соберёт build_page.py. Руками это пятнадцать разборов вёрстки.

ПОЧЕМУ НЕ PANDOC. Он переводит теги, а не смысл. Таблицы старых страниц свёрстаны
списками определений `dl > div.row > dt + dd` — pandoc отдаёт «термин, жёсткий
перенос, значение», и сборщик читает это абзацем: вся структура таблиц пропадает.
Замер блока 201: у «Инфраструктуры проекта» из 33 пунктов доезжает 5.

ЧТО ДЕЛАЕТ ЭТОТ. Отображает СЛОВАРЬ КЛАССОВ старых страниц на секции формата.
Словарь общий: семнадцать классов из двадцати восьми уже знает общий стиль
кабинета — страницы писались одной рукой, и это делает отображение возможным.

ЧЕГО НЕ ДЕЛАЕТ. Не угадывает. Всё, чему нет соответствия в § 4 контракта,
идёт в отчёт потерь построчно, а не растворяется в тексте. Схемы `<svg>`
не переносятся вовсе — им нужен движок схем (задача 721, блок 307).

Выхлоп ВСЕГДА требует человека: ключи панелей `{#ключ}` из старой страницы
не выводятся — их там не было, — и решение, что считать панелью, принимает
не скрипт.

Задача 721, блок 201.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    raise SystemExit("Нужен bs4: pip install beautifulsoup4 lxml")

# Врезки старых страниц → имена врезок формата (§ 5).
NOTE_KINDS = {"pending": "ещё не сделано", "alarm": "внимание", "good": "заметка"}

# Классы, которые ничего не значат для исходника: их роль чисто оформительская,
# и общий стиль даёт то же самое сам.
COSMETIC = {"dim", "small", "plain", "label", "page", "head", "human"}


def esc(t):
    """Экранируем то, что markdown прочтёт как разметку."""
    return re.sub(r"([\\`*_\[\]|])", r"\\\1", t)


def inline(el):
    """Содержимое узла с сохранением жирного, кода и ссылок."""
    out = []
    for n in el.children:
        if isinstance(n, NavigableString):
            out.append(esc(str(n)))
        elif isinstance(n, Tag):
            # Пустой строчный тег markdown-разметки не даёт: `<i></i>` превращался
            # в голые `**` посреди строки. В старых страницах такие теги стоят
            # оформлением — заливкой полосы, засечкой — и текста не несут.
            if n.name in ("b", "strong", "i", "em", "code", "kbd") \
                    and not n.get_text(strip=True):
                continue
            if n.name in ("b", "strong"):
                out.append(f"**{inline(n).strip()}**")
            elif n.name in ("i", "em"):
                out.append(f"*{inline(n).strip()}*")
            elif n.name in ("code", "kbd") or "mono" in (n.get("class") or []):
                out.append(f"`{n.get_text(' ', strip=True)}`")
            elif n.name == "a":
                href = n.get("href", "")
                txt = inline(n).strip()
                # Ссылку на задачу сборщик рисует сам из ключа панели —
                # переносить её значит получить её дважды (блок 306).
                out.append(txt if href.startswith("#task/") else f"[{txt}]({href})")
            elif n.name == "br":
                out.append(" ")
            else:
                out.append(inline(n))
    return re.sub(r"[ \t]+", " ", "".join(out))


def cell(el):
    """Ячейка таблицы: трубы внутри сломали бы строку."""
    return inline(el).strip().replace("\n", " ").replace("|", "\\|")


class Разбор:
    def __init__(self):
        self.строки = []
        self.потери = []

    def add(self, s=""):
        self.строки.append(s)

    def потеря(self, что, где, сколько=1):
        self.потери.append({"что": что, "где": где, "сколько": сколько})

    # ── секции формата ────────────────────────────────────────────────────

    def rows(self, dl, где):
        """dl > div.row > dt + dd → таблица из двух колонок (§ 5, `rows`).

        Шапки у неё нет: первая строка — тоже пара. Отсюда пустая строка
        выравнивания сразу после первой пары."""
        # Две формы разметки, и вторую нельзя делать запасной по признаку
        # «пар не нашлось». Раньше здесь стояло `... or [dl]`, и у списка
        # без обёрток находилась РОВНО ОДНА пара — первая: список уже не пуст,
        # запасная ветка не включается, остальные пары пропадают молча.
        # У «Плана на месяц» так терялось по паре с каждой недели.
        обёртки = dl.find_all(["div", "li"], recursive=False)
        if обёртки:
            пары = [(cell(row.find("dt")), cell(row.find("dd")))
                    for row in обёртки if row.find("dt") and row.find("dd")]
        else:
            # dt/dd лежат прямо в dl — берём их попарно, все
            пары = [(cell(a), cell(b))
                    for a, b in zip(dl.find_all("dt"), dl.find_all("dd"))]
        if not пары:
            self.потеря("список определений без пар", где)
            return
        self.add()
        self.add(f"| {пары[0][0]} | {пары[0][1]} |")
        self.add("|---|---|")
        for a, b in пары[1:]:
            self.add(f"| {a} | {b} |")
        self.add()

    def tiles(self, box, где):
        """.tiles > .tile → `[!плитки]` и список `значение — подпись`."""
        пункты = []
        for t in box.select(".tile"):
            узлы = [x for x in t.children if isinstance(x, Tag)]
            if len(узлы) >= 2:
                знач = inline(узлы[0]).strip()
                подп = " ".join(inline(x).strip() for x in узлы[1:]).strip()
            else:
                знач, подп = inline(t).strip(), ""
            тревога = "!" if "alarm" in (t.get("class") or []) else ""
            пункты.append(f"- {тревога}{знач} — {подп}".rstrip(" —"))
        if not пункты:
            self.потеря("плитки без содержимого", где)
            return
        self.add()
        self.add("[!плитки]")
        self.add()
        self.строки.extend(пункты)
        self.add()

    def findings(self, box, где):
        """.causes > .cause → `[!находки]`: нумерованный список, каждый пункт
        с жирного заголовка. Номера рисует сборщик — из разметки они убираются."""
        пункты = []
        for c in box.select(".cause"):
            h = c.find(["h3", "h4"])
            заг = inline(h).strip() if h else ""
            тело = " ".join(
                inline(p).strip() for p in c.find_all("p") if p.get_text(strip=True))
            пункты.append(f"1. **{заг}** {тело}".strip())
        if not пункты:
            self.потеря("находки без содержимого", где)
            return
        self.add()
        self.add("[!находки]")
        self.add()
        self.строки.extend(пункты)
        self.add()

    def note(self, box, где):
        классы = box.get("class") or []
        имя = next((NOTE_KINDS[k] for k in классы if k in NOTE_KINDS), "важно")
        # Подпись врезки `.label` — её собственный заголовок. Слитая с текстом,
        # она читается началом предложения: «Где проходит граница Бот объясняет
        # и подсказывает». Отделяем жирным.
        подпись = box.select_one(".label")
        if подпись:
            подпись.extract()
        текст = " ".join(
            inline(p).strip() for p in box.find_all(["p", "div"], recursive=False)
            if p.get_text(strip=True)) or inline(box).strip()
        if подпись:
            текст = f"**{подпись.get_text(' ', strip=True)}.** {текст}".strip()
        self.add()
        self.add(f"[!{имя}] {текст}")
        self.add()

    # ── обход ─────────────────────────────────────────────────────────────

    def узел(self, el, где):
        if isinstance(el, NavigableString):
            return
        if not isinstance(el, Tag):
            return
        классы = set(el.get("class") or [])
        имя = el.name

        if имя in ("style", "script", "link", "meta", "title"):
            return
        if имя == "svg":
            self.потеря("схема svg — переносится движком схем, блок 307", где)
            return
        if имя == "h2":
            self.add()
            self.add(f"## {el.get_text(' ', strip=True)}")
            self.add()
            return
        if имя in ("h3", "h4"):
            # Третьего уровня в каталоге § 4 нет, и сборщик на нём отказывает.
            # Переносим текст жирным, чтобы он не пропал, и записываем
            # в потери: чем это должно стать — разделом, строкой таблицы или
            # пунктом находок — решает человек, а не догадка скрипта.
            т = el.get_text(" ", strip=True)
            self.потеря(f"подзаголовок «{т[:44]}» — выбрать форму: раздел, "
                        f"строка таблицы или пункт находок", где)
            self.add()
            self.add(f"**{т}**")
            self.add()
            return
        if имя in ("p", "figcaption"):
            # Ссылка «Открыть задачу» — её сборщик рисует сам по ключу панели,
            # и переносить её значит получить её дважды. Но выбрасывать ВЕСЬ
            # абзац можно только когда ссылка и есть весь абзац: «Порядок шагов
            # — в задаче Поднять сервер» это проза, и она пропала целиком
            # (поймано замером блока 201, а не чтением).
            ссылка = el.find("a", href=re.compile(r"^#task/"))
            if ссылка and el.get_text(strip=True) == ссылка.get_text(strip=True):
                return
            т = inline(el).strip()
            if т:
                self.add(т)
                self.add()
            return
        if имя in ("ul", "ol"):
            маркер = (lambda i: f"{i}.") if имя == "ol" else (lambda i: "-")
            self.add()
            for i, li in enumerate(el.find_all("li", recursive=False), 1):
                self.add(f"{маркер(i)} {inline(li).strip()}")
            self.add()
            return
        if имя == "dl":
            self.rows(el, где)
            return
        if имя == "blockquote" or "said" in классы:
            self.add()
            self.add("> " + inline(el).strip())
            self.add()
            return
        if "tiles" in классы:
            self.tiles(el, где)
            return
        if "causes" in классы:
            self.findings(el, где)
            return
        if "note" in классы:
            self.note(el, где)
            return
        if "foot" in классы:
            self.add()
            self.add("[!подвал] " + inline(el).strip())
            self.add()
            return

        # Узел без блочных детей — его текст больше никто не заберёт. Спуск
        # внутрь такого узла доходит до строк, а строки обход пропускает:
        # подпись `.loop-when` «круглосуточно, отвечает сразу» пропала именно
        # так, и заметил её только пофразовый замер.
        БЛОЧНЫЕ = {"p", "div", "section", "article", "ul", "ol", "dl", "table",
                   "h1", "h2", "h3", "h4", "blockquote", "figure", "figcaption",
                   "header", "footer", "aside", "nav", "svg"}
        if not any(isinstance(c, Tag) and c.name in БЛОЧНЫЕ for c in el.children):
            # Несколько соседних строчных детей — это не фраза, а набор полей:
            # у ленты недель `.track > .seg` лежат `Неделя 1`, `22 → 29 авг`,
            # `Фундамент` тремя `span` подряд, и склейка встык давала
            # «Неделя 122 → 29 авгФундамент». Разделяем точкой — так же, как
            # разделены поля в плитках контракта.
            поля = [inline(c).strip() for c in el.children
                    if isinstance(c, Tag) and inline(c).strip()]
            голый = "".join(str(c) for c in el.children
                            if isinstance(c, NavigableString)).strip()
            т = " · ".join(поля) if len(поля) > 1 and not голый else inline(el).strip()
            if т:
                self.add(т)
                self.add()
            return

        # Прочее — спускаемся внутрь. Неизвестная обёртка не должна съедать
        # содержание: молча потерять хуже, чем перенести без формы.
        неизвестная = классы - COSMETIC - {"row", "rows", "tile", "loop", "loops",
                                           "loop-h", "cause", "mono", "eyebrow", "lead"}
        if неизвестная and имя in ("div", "section", "article"):
            self.потеря(f"обёртка .{'.'.join(sorted(неизвестная))} — формы нет, "
                        f"содержимое перенесено без неё", где)
        for ch in el.children:
            self.узел(ch, где)


def convert(html):
    s = BeautifulSoup(html, "lxml")
    for t in s(["script"]):
        t.decompose()
    р = Разбор()

    head = s.select_one(".head") or s
    h1 = head.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else (
        s.title.get_text(strip=True) if s.title else "")
    kicker = head.select_one(".eyebrow")
    lead = head.select_one(".lead")

    # Тип ставится заглушкой `theses` и переписывается человеком: из старой
    # вёрстки он не выводится, а угаданный неверно тип меняет форму документа.
    # Пять известных: cover, homework, feedback, theses, method.
    шапка = ["---", "type: theses", f"title: {title}"]
    if kicker:
        шапка.append(f"kicker: {kicker.get_text(' ', strip=True)}")
    if lead:
        шапка.append(f"lead: {lead.get_text(' ', strip=True)}")
    шапка += ["---", ""]

    page = s.select_one(".page") or s.body or s
    for el in page.children:
        if isinstance(el, Tag) and "head" in (el.get("class") or []):
            continue
        где = ""
        if isinstance(el, Tag):
            h = el.find("h2")
            где = h.get_text(" ", strip=True) if h else el.name
        р.узел(el, где)

    тело = re.sub(r"\n{3,}", "\n\n", "\n".join(р.строки)).strip()
    return "\n".join(шапка) + тело + "\n", р.потери


def main():
    ap = argparse.ArgumentParser(
        description="Старая страница кабинета → исходник markdown формата")
    ap.add_argument("source", help="Файл .html старой страницы")
    ap.add_argument("-o", "--out", default=None, help="Куда писать. По умолчанию рядом")
    ap.add_argument("--losses", action="store_true", help="Отчёт потерь в JSON на stderr")
    a = ap.parse_args()

    src = Path(a.source)
    if not src.is_file():
        raise SystemExit(f"Нет файла: {src}")

    md, потери = convert(src.read_text(encoding="utf-8"))
    out = Path(a.out) if a.out else src.with_suffix(".md")
    out.write_text(md, encoding="utf-8")
    print(f"Собрано: {out}")
    print(f"Потерь: {len(потери)}", file=sys.stderr)
    if a.losses:
        print(json.dumps(потери, ensure_ascii=False, indent=1), file=sys.stderr)
    # Ключи панелей скрипт не выводит: в старой странице их не было, и решать,
    # что считать панелью, человеку, а не догадке.
    print("Ключи панелей {#ключ} проставляются руками — § 4 контракта", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
