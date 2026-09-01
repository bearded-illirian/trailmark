"""Свёрстанная страница → markdown-текст.

ЗАЧЕМ. У страницы кабинета единственная кнопка — «Скачать», и она отдавала 415:
`text/html` намеренно не пущен в белый список `partners_api._is_allowed_mime`,
потому что отдача разметки с нашего домена — это исполняемый файл в руках
клиента. Кнопка была, работы не делала. Отдаём вместо неё производный текст:
наружу уходит markdown, исходная разметка не уходит никуда, заслон не трогаем.

ПОЧЕМУ СВОЙ, А НЕ ГОТОВЫЙ. Универсальный конвертер ничего не знает про нашу
вёрстку. Плитка `<span class="n">12</span>правил подключены` у него слипается в
`**12**правил` — соседние элементы разделены отступом, а не пробелом, и в
тексте отступ исчезает. Проверено на семи страницах кабинета до того, как
писать этот файл. Своих правил тут два десятка, и они про нашу же разметку.

ЧЕГО ЭТОТ МОДУЛЬ НЕ УМЕЕТ И НЕ ДОЛЖЕН. Схему, собранную из блоков с подписями,
в текст не перевести — из неё выходит столбик обрывков «Агент», «нельзя
встать». Такие места помечает автор страницы атрибутом `data-md`, а не
угадывает конвертер. Без пометки блок переводится как обычный — молча и, скорее
всего, плохо.

ЗАВИСИМОСТЕЙ НЕТ. `html.parser` из стандартной библиотеки — тот же, на котором
стоит `_SafeHtml` в extranet_resolver.py. Ставить на витрину нечего.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

__all__ = ["html_to_markdown", "MarkdownConvertError"]


class MarkdownConvertError(Exception):
    """Разметку не удалось превратить в текст."""


# Содержимое этих тегов в текст не идёт вовсе. Список — копия соседнего
# _HTML_DROP_CONTENT_TAGS из extranet_resolver.py, и совпадение не случайно:
# там он защищает показ, здесь — выгрузку, причина одна.
#
# Одиночных тегов (meta, link, br) в списке нет, и это НЕ упущение. Счётчик
# растёт на открывающем и падает на закрывающем; у одиночного закрывающего не
# бывает, поэтому попади он сюда — счётчик застрял бы навсегда, и документ
# вышел бы пустым. Поймано ровно так на прототипе: 21 <link> в шапке страницы
# дали ноль строк на выходе.
_DROP = frozenset({
    "script", "style", "iframe", "object", "embed", "noscript",
    "svg", "math", "template", "head", "title",
})

# Теги, на которых текущая строка заканчивается.
_BLOCK = frozenset({
    "p", "div", "section", "article", "header", "footer", "figure", "figcaption",
    "h1", "h2", "h3", "h4", "h5", "h6", "li", "dt", "dd", "tr", "blockquote",
    "ul", "ol", "dl", "table", "thead", "tbody",
})

_PREFIX = {
    "h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ",
    "h5": "##### ", "h6": "###### ",
    "li": "- ", "blockquote": "> ",
}

# Список определений идёт ОДНОЙ строкой на пару: «**Язык:** Python 3».
#
# Раньше dt и dd были обычными блоками, и каждая пара разваливалась на два
# абзаца — термин, пустая строка, значение с отступом. Формально markdown
# верный, читается рванина: в «Инфраструктуре» так шло десять пар подряд.
#
# Отступ у одинокого dd всё же нужен — если термина не было, значение не
# должно слипаться с предыдущим абзацем.
_ORPHAN_DD_PREFIX = "  "


class _Converter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._lines: list[str] = []
        self._buf: list[str] = []
        self._prefix: str | None = None
        self._drop = 0
        # Глубина пропуска по data-md="skip": считаем ВЛОЖЕННЫЕ теги, иначе
        # закрытие первого же внутреннего <span> сняло бы пропуск со всего блока.
        self._skip = 0
        self._skip_depth = 0
        self._row: list[str] = []
        self._table_head_done = True
        self._link: str | None = None
        # См. _sep: отличает открывающий инлайн-маркер от закрывающего.
        self._just_opened = False
        self._ordered: list[bool] = []

    # ── строки ──────────────────────────────────────────────────────────
    def _flush(self) -> None:
        text = "".join(self._buf)
        self._buf = []
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            self._prefix = None
            return
        self._lines.append((self._prefix or "") + text)
        self._prefix = None

    def _sep(self) -> None:
        """Пробел на стыке соседних элементов.

        `<b>12</b><span>правил</span>` — в вёрстке между ними отступ, в тексте
        не остаётся ничего, и выходит «**12**правил». Пробел ставится, только
        если его там ещё нет: иначе плодятся двойные.

        Отличать закрывающий маркер от открывающего по последнему символу
        нельзя — `**` выглядит одинаково с обеих сторон. Первая версия
        сравнивала именно символ, запрещала пробел после любой звёздочки и тем
        самым не чинила ровно тот случай, ради которого написана. Поэтому
        признак хранится флагом: после ОТКРЫВАЮЩЕГО маркера пробел не нужен,
        после закрывающего нужен.
        """
        if self._just_opened:
            return
        if self._buf and not self._buf[-1].endswith((" ", "\n", "(", "[")):
            self._buf.append(" ")

    # ── теги ────────────────────────────────────────────────────────────
    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _DROP:
            # Схема нарисована, а не написана, и в текст не переводится. Но у
            # доступной схемы уже есть подпись для тех, кто её не видит —
            # aria-label. Она написана автором страницы, точна и не выдумана
            # конвертером: берём её вместо молчаливого выброса, иначе читатель
            # скачанного файла не узнает, что здесь вообще что-то было.
            if tag == "svg" and not self._drop:
                label = dict(attrs).get("aria-label", "").strip()
                if label:
                    self._flush()
                    self._lines.append("> " + label)
            self._drop += 1
            return
        if self._drop:
            return

        a = dict(attrs)
        if self._skip:
            self._skip_depth += 1
            return

        marker = a.get("data-md")
        if marker is not None:
            self._flush()
            if marker.strip().lower() != "skip":
                # Замена: автор страницы сам сказал, чем блок выглядит в тексте.
                self._lines.append("> " + marker.strip())
            self._skip = 1
            self._skip_depth = 1
            return

        if tag in ("ul", "ol"):
            self._flush()
            self._ordered.append(tag == "ol")
            return
        if tag == "table":
            self._flush()
            self._table_head_done = False
            return
        if tag == "tr":
            self._row = []
            return
        if tag in ("td", "th"):
            self._buf = []
            return
        if tag == "hr":
            self._flush()
            self._lines.append("---")
            return
        if tag == "br":
            self._buf.append(" ")
            return

        if tag == "dd":
            # Строку НЕ завершаем: значение дописывается к термину, который уже
            # лежит в буфере. Если термина не было — буфер пуст, и значение
            # получит собственный отступ.
            if not "".join(self._buf).strip():
                self._prefix = _ORPHAN_DD_PREFIX
            self._sep()
            return

        if tag in _BLOCK:
            self._flush()
            prefix = _PREFIX.get(tag)
            if tag == "li" and self._ordered and self._ordered[-1]:
                prefix = "1. "
            self._prefix = prefix

        self._sep()
        if tag in ("b", "strong", "dt"):
            self._buf.append("**"); self._just_opened = True
        elif tag in ("i", "em", "cite"):
            self._buf.append("*"); self._just_opened = True
        elif tag == "code" or (tag == "span" and "mono" in (a.get("class") or "")):
            self._buf.append("`"); self._just_opened = True
        elif tag == "a":
            href = (a.get("href") or "").strip()
            # Внутренние якоря портала (#ep/12, #task/3) вне портала не ведут
            # никуда — оставляем текст без адреса, а не ссылку в никуда.
            self._link = href if href.lower().startswith(("http://", "https://")) else None
            if self._link:
                self._buf.append("["); self._just_opened = True

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP:
            self._drop = max(0, self._drop - 1)
            return
        if self._drop:
            return
        if self._skip:
            self._skip_depth -= 1
            if self._skip_depth <= 0:
                self._skip = 0
            return

        self._just_opened = False
        if tag in ("b", "strong"):
            self._buf.append("**")
        elif tag == "dt":
            # Термин списка определений — жирный заголовок со своим двоеточием.
            self._buf.append(":**")
        elif tag in ("i", "em", "cite"):
            self._buf.append("*")
        elif tag == "code":
            self._buf.append("`")
        elif tag == "span":
            # Закрывать кавычку вслепую нельзя: `mono` — лишь часть span'ов.
            # Признак — незакрытая кавычка в текущей строке.
            if self._buf and "".join(self._buf).count("`") % 2:
                self._buf.append("`")
        elif tag == "a":
            if self._link:
                self._buf.append(f"]({self._link})")
                self._link = None

        if tag == "dt":
            # Пара не закончена — ждём значение. Строку завершит dd, а если его
            # нет вовсе, её закроет следующий блок или конец документа.
            return
        if tag in ("td", "th"):
            self._row.append(re.sub(r"\s+", " ", "".join(self._buf)).strip())
            self._buf = []
            return
        if tag == "tr":
            if self._row:
                self._lines.append("| " + " | ".join(self._row) + " |")
                if not self._table_head_done:
                    self._lines.append("|" + "---|" * len(self._row))
                    self._table_head_done = True
                self._row = []
            return
        if tag in ("ul", "ol"):
            if self._ordered:
                self._ordered.pop()
        if tag == "table":
            self._table_head_done = True

        if tag in _BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._drop or self._skip:
            return
        if data.strip():
            self._just_opened = False
        self._buf.append(data)

    def result(self) -> str:
        self._flush()

        # Номер причины или пункта нарисован кружком рядом с заголовком, и в
        # тексте от него остаётся одинокая цифра строкой — «1», потом
        # «### Между этапами нет границы». Приклеиваем к заголовку: нумерация
        # сохраняется, сирота исчезает.
        #
        # Правило намеренно узкое — строка ЦЕЛИКОМ из числа и сразу за ней
        # заголовок. Число, живущее в тексте самостоятельно, так не выглядит:
        # рядом с ним всегда есть слова.
        merged: list[str] = []
        skip_next = False
        for i, line in enumerate(self._lines):
            if skip_next:
                skip_next = False
                continue
            bare = line.strip().rstrip(".")
            nxt = self._lines[i + 1] if i + 1 < len(self._lines) else ""
            if bare.isdigit() and nxt.startswith("#"):
                hashes, _, title = nxt.partition(" ")
                merged.append(f"{hashes} {bare}. {title}")
                skip_next = True
                continue
            merged.append(line)

        out: list[str] = []
        for line in merged:
            if line or (out and out[-1]):
                out.append(line)
        return "\n\n".join(x for x in out if x).strip() + "\n"


def html_to_markdown(raw_html: str, *, max_bytes: int | None = None) -> str:
    """Разметку страницы — в markdown-текст.

    max_bytes — потолок для ИСХОДНОЙ разметки. Проверяется до разбора: смысла
    парсить то, что мы всё равно не отдадим, нет, а память тратится сразу.
    """
    if not raw_html:
        raise MarkdownConvertError("пустая разметка")
    if max_bytes is not None and len(raw_html.encode("utf-8")) > max_bytes:
        raise MarkdownConvertError(
            f"страница больше порога {max_bytes} байт"
        )
    parser = _Converter()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception as e:  # noqa: BLE001 — что угодно из разбора чужой разметки
        raise MarkdownConvertError(f"разметка не разобралась: {e}") from e
    text = parser.result()
    if not text.strip():
        # Пустой ответ страшнее ошибки: клиент сохранит файл и не поймёт, что
        # тот пуст. Пусть лучше кнопка честно скажет, что не смогла.
        raise MarkdownConvertError("после разбора не осталось текста")
    return text
