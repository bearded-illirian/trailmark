"""
extranet_resolver.py — resolver для порталов режима «Экстранет» (Radar OS).

Задача radar-os--695, этап 2 (блоки 30-32).

Третий источник данных витрины, наряду с двумя существующими:

  - файловый портал   — материалы лежат папкой в portals_root на нашем диске
  - personal_flow     — материалы резолвятся из personal_flow.sqlite тенанта
  - **экстранет**     — материалы описаны в portal_materials, а файлы живут
                        в облаке клиента (Яндекс.Диск / Google Drive / S3),
                        подключённом к режиму

Consumer: partners_api.py /tree + /file. Развилка та же, что для personal_flow —
см. partner_tree(), где ветка выбирается до обращения к диску.

## Почему признак именно такой

Первым кандидатом был tenant_code / owner_employee_id, по аналогии с
personal_flow. Проверка на живых данных это опровергла: оба поля пусты у
**всех 12** порталов, включая экстранетовский. Единственное, что реально
разделяет — наличие строк в portal_materials (2 у портала Ильи, 0 у остальных).

Это не обходной путь, а определение по существу: экстранет-портал — тот, чьи
материалы описаны в junction-таблице, а не лежат папкой на диске.

## Известное ограничение

Экстранет-портал с **пустым пакетом** имеет ноль строк в portal_materials и
неотличим от файлового. Витрина в этом случае пойдёт искать папку, не найдёт и
ответит «Partner folder not found on disk». Обрабатывается в partner_tree
(блок 31): когда нет ни строк, ни папки — отдаём пустое дерево, а не 404.

Радикальное решение — явная колонка source в partners, заполняемая при создании.
Отложено: миграция схемы ради случая, которого пока не существует.
"""

from __future__ import annotations

import base64
import html as _html
import io
import logging
import os
import sqlite3
import urllib.error
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

_log = logging.getLogger(__name__)

# Чем превращаем docx в разметку (блок 71030, decision-15).
#
# Выбор делается ОДИН РАЗ здесь, при загрузке модуля, по факту «библиотека
# импортируется или нет» — а не на каждом документе по его содержимому. Развилка
# по содержимому отклонена решением: проверка «что внутри» стоит столько же,
# сколько разбор, а два пути на один результат разъезжаются, и один и тот же
# договор начинает выглядеть по-разному в зависимости от начинки.
#
# Запасной разбор существует не ради скорости, а на случай переезда или забытой
# установки: пост-receive хук pip не зовёт, и строка в requirements.txt сама
# ничего не поставит. Тогда клиент видит текст договора, а не пятисотку.
try:
    import mammoth as _mammoth
except ImportError:  # pragma: no cover — зависит от окружения, не от кода
    _mammoth = None
    # Уровень warning обязателен: сервис запущен как uvicorn --log-level warning,
    # всё что ниже уровнем в журнал systemd не попадёт вовсе, и эта запись
    # пропала бы молча — а вместе с ней и знание, что работает запасной путь.
    logging.getLogger(__name__).warning(
        "DOCX_FALLBACK_ACTIVE: mammoth не установлен, документы разбираются "
        "запасным способом. Картинки внутри документа и гиперссылки будут "
        "потеряны. Лечится: /srv/vschk-flow-ui/venv/bin/pip install mammoth "
        "+ рестарт vschk-flow-ui.service"
    )

# Feature flag — откат без выкатки кода
EXTRANET_RESOLVER_ENABLED = os.getenv("EXTRANET_RESOLVER_ENABLED", "1") == "1"

# База витрины: та же, где живут partners и portal_materials
PARTNERS_DB_PATH = os.getenv(
    "PARTNERS_DB_PATH",
    "/srv/vschk-flow-ui/data/partners.db",
)


def _open_partners_db() -> Optional[sqlite3.Connection]:
    """Открыть базу витрины на чтение. None, если файла нет.

    mode=ro — резолвер только читает. Пишет в эту же базу сама витрина
    через свои модули, конфликта нет.
    """
    db_path = Path(PARTNERS_DB_PATH)
    if not db_path.is_file():
        return None

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def is_extranet_portal(partner: dict) -> bool:
    """Портал получает материалы из каталога Экстранета, а не с диска?

    Признак — наличие хотя бы одной строки в portal_materials **или** заведённой
    папки в portal_folders. Запросы идут по индексам (partner_id первым полем),
    поэтому их не жалко звать на каждом запросе дерева и файла.

    Папки добавлены к признаку блоком 72000, и это не формальность: портал, где
    структура заведена, а материалы ещё не положены, — рабочий случай, с него
    начинается выдача. Без папок в признаке такой портал считался бы файловым и
    получил бы «папка не найдена на диске» вместо своих пустых папок.
    """
    if not EXTRANET_RESOLVER_ENABLED:
        return False

    partner_id = partner.get("id")
    if partner_id is None:
        return False

    conn = _open_partners_db()
    if conn is None:
        return False

    try:
        row = conn.execute(
            "SELECT 1 FROM portal_materials WHERE partner_id = ? LIMIT 1",
            (partner_id,),
        ).fetchone()
        if row is not None:
            return True
        try:
            row = conn.execute(
                "SELECT 1 FROM portal_folders WHERE partner_id = ? LIMIT 1",
                (partner_id,),
            ).fetchone()
        except sqlite3.Error:
            # Таблицы папок ещё нет (витрина выкачена раньше миграции) —
            # признак остаётся прежним, поведение вчерашним.
            return False
        return row is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def resolve_portal_folders(partner: dict) -> list[dict]:
    """Папки портала — те, что завёл человек (блок 72000).

    Пустой список означает «папок нет», и портал показывается плоским. Пустая
    ПАПКА при этом — обычное дело: «Тренажёр» заводится заранее как место, куда
    будет складываться.
    """
    partner_id = partner.get("id")
    conn = _open_partners_db()
    if conn is None:
        return []

    try:
        cursor = conn.execute(
            "SELECT folder_id, title, sort_order FROM portal_folders "
            "WHERE partner_id = ? ORDER BY sort_order, folder_id",
            (partner_id,),
        )
        return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error:
        # Таблицы ещё нет (витрина выкачена раньше миграции) — портал покажется
        # плоским, как показывался вчера. Это безопасная деградация, а не отказ.
        return []
    finally:
        conn.close()


def resolve_portal_materials(partner: dict) -> Optional[list[dict]]:
    """Материалы портала в порядке, заданном оператором при сборке пакета.

    Args:
        partner: строка partners.db с ключом id

    Returns:
        list[dict] с ключами material_id, name, size, mime, sort_order, chapter,
        is_extra, has_page, folder_id — для экстранет-портала;
        None — если портал не экстранетовский, резолвер выключен или база
        витрины недоступна. None и [] означают разное: первое «не наш случай,
        иди дальше по веткам», второе «наш, но пусто».

    has_page — у материала есть собранная страница, вторая проекция того же
    документа (задача 701, decision-02). Витрина по этому признаку решает,
    что открывать по умолчанию; за самим содержимым идёт в облако.

    folder_id — папка портала, в которой лежит материал; пусто — материал лежит
    в корне, и это законное место, а не поломка (блок 72000, decision-16).

    chapter — наследие модели, в которой папка выводилась из этого поля. Читается
    ради старых порталов, но структуру больше не задаёт: она приезжает списком
    папок отдельно.
    """
    if not is_extranet_portal(partner):
        return None

    partner_id = partner.get("id")
    conn = _open_partners_db()
    if conn is None:
        return None

    try:
        cursor = conn.execute(
            """
            SELECT material_id, name, size, mime, sort_order, chapter, has_page, is_extra, is_cover, folder_id
            FROM portal_materials
            WHERE partner_id = ?
            -- Допы всегда после материалов пакета: сортировка парой, а не по
            -- sort_order одному. Материал пакета с большим порядком должен идти
            -- раньше любого допа (task 695 block 80).
            ORDER BY is_extra, sort_order, name
            """,
            (partner_id,),
        )
        return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error:
        return None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Содержимое материала (блок 32)
# ─────────────────────────────────────────────────────────────────────────

# Сколько байт готовы поднять в память и отдать строкой. Тезисы — 23 КБ,
# транскрипт — 113 КБ; порог с запасом, но заведомо ниже видео.
MAX_INLINE_BYTES = 5 * 1024 * 1024

# Таймаут на скачивание самого файла. Ссылку резолвит _call_radar_resolve
# со своим таймаутом — этот только про облако.
_FETCH_TIMEOUT = 30.0

# Что показываем текстом. Остальное остаётся на прежнем пути скачивания:
# бинарь в строковое поле PartnerFileContentOut не кладём.
_TEXT_MIME_PREFIXES = ("text/",)
_TEXT_MIME_EXACT = {
    "application/json",
    "application/xml",
    "application/x-yaml",
    "application/yaml",
}
_TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".csv", ".json", ".xml", ".yml", ".yaml", ".log"}


class MaterialContentError(RuntimeError):
    """Материал есть, но содержимое получить не удалось.

    Отдельный тип нужен чтобы consumer отличил «нет такого материала» (404)
    от «материал наш, но облако не ответило» (502) — для клиента это разные
    сообщения, и второе не должно выглядеть как отсутствующий документ.
    """


def is_text_material(name: str, mime: str) -> bool:
    """Отдавать этот материал текстом или оставить на скачивание?

    Mime приходит из каталога тенанта и для markdown часто оказывается
    text/plain, но бывает и пустым — тогда решает расширение имени.
    """
    mime = (mime or "").split(";")[0].strip().lower()
    if mime:
        if mime.startswith(_TEXT_MIME_PREFIXES) or mime in _TEXT_MIME_EXACT:
            return True
        # Явно не текст — расширению уже не верим, mime конкретнее
        return False

    lowered = (name or "").lower()
    return any(lowered.endswith(ext) for ext in _TEXT_EXTENSIONS)


# Что портал умеет показывать сам, а что отдаёт наружу ссылкой.
#
# Блок 71 и decision-02.R2 различали три вида: текст, картинку и «всё
# остальное» ссылкой. Причина была не в форматах, а в том, что отдать байты
# было нечем: материал лежит в облаке, файла на диске витрины нет, а PDF
# строкой не передашь. С блоком 71000 появился ep-asset, и ограничение снято —
# теперь портал показывает то же, что и обычный флоу (задача 677).
KIND_TEXT = "text"
KIND_IMAGE = "image"
KIND_PDF = "pdf"
KIND_AUDIO = "audio"
KIND_VIDEO = "video"
# Документ Word. Браузер его не рисует ни в каком виде — это zip с XML внутри.
# Показываем текстом, превратив у себя (блок 71040): чужие просмотрщики
# запрещены решением, подписанный договор не должен уезжать на их серверы.
KIND_DOC = "doc"
KIND_EXTERNAL = "external"

# Страница целиком: свёрстанный HTML, который портал рисует в изолированном
# фрейме. Нужен там, где 17 блоков каталога не хватает — разбор, кабинет
# менторинга, коммерческое предложение со своей графикой.
#
# Почему фрейм, а не общий DOM: файл приезжает из хранилища тенанта и
# доверенным источником разметки не является (PAGE_FORMAT.md § 5). В адресе
# страницы портала живёт магик-токен, и разметка в общем документе смогла бы
# его прочитать. Песочница без same-origin отрезает этот путь.
KIND_PAGE_HTML = "page_html"

# Виды, которые браузер рисует сам, получив адрес. Фронт по ним зовёт
# renderPdf / renderImage / renderAudio / renderVideo задачи 677.
KINDS_INLINE_ASSET = frozenset({KIND_IMAGE, KIND_PDF, KIND_AUDIO, KIND_VIDEO})

_IMAGE_MIME_PREFIX = "image/"
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
_PDF_MIME = "application/pdf"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_AUDIO_MIME_PREFIX = "audio/"
_VIDEO_MIME_PREFIX = "video/"
_PAGE_MIME = "text/html"
_PAGE_EXTENSIONS = {".html", ".htm"}


def material_kind(name: str, mime: str) -> str:
    """Как показывать материал: текстом, картинкой или ссылкой наружу.

    Решает бэкенд, а не фронтенд. У витрины нет расширения файла — только имя
    вроде «Счёт № 38 от 19.08.2026» и mime из каталога тенанта, поэтому
    классификация по расширению на стороне браузера для экстранета не работает
    вовсе. Вид едет в дереве рядом с has_page — тот добавлен задачей 701 по
    ровно той же причине.

    Порядок проверок значим. Первой идёт страница: её mime text/html подходит
    под префикс text/, и проверка текста забрала бы её себе — клиент увидел бы
    исходник разметки вместо оформления. Сразу за ней текст: разметка
    расшифровок приходит с mime text/* либо вовсе без него, и утечь в
    «остальное» ей нельзя — на ней стоит портал, принятый клиентом.
    """
    normalized = (mime or "").split(";")[0].strip().lower()
    lowered_name = (name or "").lower()

    # Страница проверяется ДО текста: text/html подходит под префикс text/, и
    # без этой проверки свёрстанная страница уехала бы в KIND_TEXT — клиент
    # увидел бы исходник разметки вместо оформления.
    if normalized == _PAGE_MIME or (
        not normalized and any(lowered_name.endswith(e) for e in _PAGE_EXTENSIONS)
    ):
        return KIND_PAGE_HTML

    if is_text_material(name, mime):
        return KIND_TEXT

    if normalized.startswith(_IMAGE_MIME_PREFIX):
        return KIND_IMAGE

    if normalized == _PDF_MIME:
        return KIND_PDF
    if normalized == _DOCX_MIME:
        return KIND_DOC
    if normalized.startswith(_AUDIO_MIME_PREFIX):
        return KIND_AUDIO
    if normalized.startswith(_VIDEO_MIME_PREFIX):
        return KIND_VIDEO

    if not normalized:
        lowered = (name or "").lower()
        if any(lowered.endswith(ext) for ext in _IMAGE_EXTENSIONS):
            return KIND_IMAGE
        if lowered.endswith(".pdf"):
            return KIND_PDF
        if lowered.endswith(".docx"):
            return KIND_DOC

    # Остальное — наружу ссылкой. Сюда попадают старые .doc, таблицы и
    # презентации: mammoth умеет только Word нового формата, а браузер не рисует
    # ни то ни другое. Это ограничение инструментов, а не наше решение.
    return KIND_EXTERNAL


# ─────────────────────────────────────────────────────────────────────────
# docx → разметка (блок 71030)
# ─────────────────────────────────────────────────────────────────────────

# Сколько может весить распакованное содержимое документа (блок 71040).
# Потолок MAX_INLINE_BYTES накрывает файл, но не то, во что он разворачивается:
# 17 КБ архива при злом умысле дают гигабайты XML. Размер читается из оглавления
# архива ДО распаковки — проверка после неё сама стала бы способом положить
# сервис.
MAX_DOCX_UNPACKED_BYTES = 40 * 1024 * 1024

# Что разрешено остаться в разметке документа, попадающей на страницу клиента.
# Всё остальное выбрасывается вместе с содержимым тега.
_HTML_ALLOWED_TAGS = frozenset({
    "p", "br", "strong", "em", "u", "s", "sup", "sub",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote",
    "table", "thead", "tbody", "tr", "td", "th",
    "a", "img",
})
# Теги, у которых нет закрывающего.
_HTML_VOID_TAGS = frozenset({"br", "img"})
# Теги, которые выбрасываются ВМЕСТЕ С СОДЕРЖИМЫМ. Просто снять тег мало:
# текст скрипта тогда протекает в документ как видимая строка, и клиент читает
# «alert(1)» посреди договора. Безопасно, но выглядит как сломанный документ.
_HTML_DROP_CONTENT_TAGS = frozenset({
    "script", "style", "iframe", "object", "embed", "noscript",
    "svg", "math", "template", "head", "title",
})


class _SafeHtml(HTMLParser):
    """Разметка документа, очищенная белым списком тегов.

    Содержимое документа приходит из облака тенанта и загружено человеком, то
    есть недоверенное. Документ, в который вписан скрипт, был бы дырой куда
    хуже, чем невозможность показать docx (decision-15).

    Атрибуты выбрасываются ВСЕ, кроме двух. Так проще и надёжнее, чем
    перечислять опасные: одним движением исчезают onclick, onerror, style и
    href="javascript:". Оставлены ровно те два, ради которых выбран mammoth:
    ссылка внутри документа (только http и https) и картинка, встроенная им
    же (только data:image).

    Регулярками такое не чистят: регулярка на HTML пропускает то, чего не
    предусмотрел автор, и узнаёшь об этом от чужого человека.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._open: list[str] = []
        self._muted = 0

    def _attrs(self, tag: str, attrs) -> str:
        out = []
        for name, value in attrs:
            value = value or ""
            low = value.strip().lower()
            if tag == "a" and name == "href" and (low.startswith("http://") or low.startswith("https://")):
                out.append(f' href="{_html.escape(value, quote=True)}" target="_blank" rel="noopener"')
            elif tag == "img" and name == "src" and low.startswith("data:image/"):
                out.append(f' src="{_html.escape(value, quote=True)}"')
        return "".join(out)

    def handle_starttag(self, tag, attrs):
        if tag in _HTML_DROP_CONTENT_TAGS:
            self._muted += 1
            return
        if self._muted or tag not in _HTML_ALLOWED_TAGS:
            return
        self._out.append(f"<{tag}{self._attrs(tag, attrs)}>")
        if tag not in _HTML_VOID_TAGS:
            self._open.append(tag)

    def handle_endtag(self, tag):
        if tag in _HTML_DROP_CONTENT_TAGS:
            self._muted = max(0, self._muted - 1)
            return
        if self._muted or tag not in _HTML_ALLOWED_TAGS or tag in _HTML_VOID_TAGS:
            return
        if tag in self._open:
            # Закрываем всё, что осталось открытым внутри — иначе чужая
            # незакрытая разметка утащит за собой вёрстку страницы.
            while self._open:
                closing = self._open.pop()
                self._out.append(f"</{closing}>")
                if closing == tag:
                    break

    def handle_data(self, data):
        if self._muted:
            return
        self._out.append(_html.escape(data))

    def result(self) -> str:
        while self._open:
            self._out.append(f"</{self._open.pop()}>")
        return "".join(self._out)


def sanitize_document_html(raw_html: str) -> str:
    """Очистить разметку документа перед показом клиенту."""
    parser = _SafeHtml()
    parser.feed(raw_html)
    parser.close()
    return parser.result()


def _docx_guard_size(raw: bytes) -> None:
    """Отказать документу, который разворачивается во что-то несуразное."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            total = sum(info.file_size for info in z.infolist())
    except zipfile.BadZipFile as e:
        raise MaterialContentError(f"это не документ Word: {e}") from e
    if total > MAX_DOCX_UNPACKED_BYTES:
        raise MaterialContentError(
            f"документ разворачивается в {total} байт — больше порога "
            f"{MAX_DOCX_UNPACKED_BYTES}"
        )


# Пространство имён WordprocessingML — им размечено содержимое документа.
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_converter_name() -> str:
    """Каким способом сейчас разбираются документы: «mammoth» или «встроенный».

    Отличить один от другого по результату нельзя: на договоре из 10 394 знаков
    оба дали посимвольно одинаковый текст. Поэтому способ приходится спрашивать
    прямо — иначе запасной путь работал бы незамеченным.
    """
    return "mammoth" if _mammoth is not None else "встроенный"


def _docx_runs(node) -> str:
    """Текст прогонов абзаца, с жирным начертанием там, где оно есть."""
    out = []
    for r in node.iter(_W + "r"):
        text = "".join(t.text or "" for t in r.iter(_W + "t"))
        if not text:
            continue
        rpr = r.find(_W + "rPr")
        bold = rpr is not None and rpr.find(_W + "b") is not None
        esc = _html.escape(text)
        out.append(f"<strong>{esc}</strong>" if bold else esc)
    return "".join(out)


def _docx_paragraph(node) -> str:
    inner = _docx_runs(node)
    if not inner.strip():
        return ""
    ppr = node.find(_W + "pPr")
    style = ""
    if ppr is not None:
        st = ppr.find(_W + "pStyle")
        if st is not None:
            style = (st.get(_W + "val") or "").lower()
    if style.startswith("heading"):
        level = "".join(c for c in style if c.isdigit()) or "2"
        return f"<h{level}>{inner}</h{level}>"
    if "listparagraph" in style:
        return f"<li>{inner}</li>"
    return f"<p>{inner}</p>"


def _docx_table(node) -> str:
    """Таблица документа. В договоре ею размечены реквизиты сторон — потерять
    её значит потерять то, ради чего документ и открывают."""
    rows = []
    for tr in node.findall(_W + "tr"):
        cells = [
            "<td>" + "".join(_docx_paragraph(p) for p in tc.findall(_W + "p")) + "</td>"
            for tc in tr.findall(_W + "tc")
        ]
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def _docx_to_html_builtin(raw: bytes) -> str:
    """Запасной разбор — только стандартной библиотекой.

    Работает, когда mammoth не установлен. Умеет заголовки, жирное начертание,
    списки и таблицы; картинки внутри документа и гиперссылки теряет — об этом
    сказано в записи журнала при старте, чтобы потеря не была молчаливой.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise MaterialContentError(f"это не документ Word: {e}") from e

    # Внешние сущности XML: xml.etree в Python 3.12 их не подставляет — то есть
    # документ, ссылающийся на файл сервера, ничего не утащит. Это свойство
    # ВЕРСИИ, а не вечная гарантия: при обновлении Python проверить заново.
    body = ET.fromstring(xml).find(_W + "body")
    if body is None:
        raise MaterialContentError("в документе нет содержимого")

    parts = []
    for node in body:
        if node.tag == _W + "p":
            parts.append(_docx_paragraph(node))
        elif node.tag == _W + "tbl":
            parts.append(_docx_table(node))
    return "".join(parts)


def docx_to_html(raw: bytes) -> str:
    """Документ Word в разметку. Способ выбран один раз при загрузке модуля.

    Возвращает разметку, уже очищенную белым списком тегов: содержимое приходит
    из чужого документа и попадает на страницу клиента, поэтому доверять ему
    нельзя ни на одном из двух путей конвертации (блок 71040, decision-15).
    """
    _docx_guard_size(raw)

    if _mammoth is not None:
        try:
            converted = _mammoth.convert_to_html(io.BytesIO(raw)).value
        except Exception as e:  # библиотека кидает своё, обычного типа нет
            raise MaterialContentError(f"не удалось разобрать документ: {e}") from e
    else:
        converted = _docx_to_html_builtin(raw)

    # Чистка стоит ЗДЕСЬ, на выходе, а не в ветках выше: оба способа проходят
    # через неё одинаково. Поставить её в одну ветку из двух — тот самый дефект
    # «правка нужна в двух местах», из-за которого в этой задаче заведены
    # materials.php (блок 80) и _bytes_from_resolved (блок 5010).
    return sanitize_document_html(converted)


# Кусок, которым материал переливается из облака в браузер. 64 КБ — столько же
# читает за раз FileResponse у соседнего /asset.
_STREAM_CHUNK = 64 * 1024


def open_material_stream(stream_url: str):
    """Открыть поток по ссылке облака: (генератор кусков, размер или None).

    Зачем витрине качать самой, когда у неё есть готовая ссылка (decision-14):
    подписанный адрес Яндекса приходит с пометкой «вложение» и обезличенным
    типом, и браузер по нему файл СКАЧИВАЕТ вместо показа. Поправить адрес
    нельзя — параметры входят в подпись, правка даёт 403. Значит, забираем сами
    и отдаём со своим заголовком.

    Потоком, а не целиком в память: потолок MAX_INLINE_BYTES защищает от
    строкового содержимого, которое и так приходит целиком. Здесь его нет —
    лекция на 300 МБ занимает столько же места, сколько счёт на 126 КБ.

    Отказ облака превращается в честную ошибку только при открытии потока.
    Обрыв в середине уже ничем не прикрыть: заголовки ответа ушли, и остаётся
    оборванная передача. Это цена потока, названная в decision-14.
    """
    try:
        req = urllib.request.Request(stream_url, method="GET")
        resp = urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT)
    except urllib.error.HTTPError as e:
        raise MaterialContentError(f"облако ответило HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise MaterialContentError(f"облако недоступно: {e.reason}") from e
    except OSError as e:
        raise MaterialContentError(f"не удалось начать скачивание: {e}") from e

    raw_length = resp.headers.get("Content-Length") or ""
    size = int(raw_length) if raw_length.isdigit() else None

    def chunks():
        with resp:
            while True:
                chunk = resp.read(_STREAM_CHUNK)
                if not chunk:
                    break
                yield chunk

    return chunks(), size


def _bytes_from_resolved(resolved: dict) -> bytes:
    """Байты материала из ответа Radar OS, в какой бы форме тот ни пришёл.

    Режим stream отвечает одной из двух форм (§7.2 манифеста интеграций v1.0.5):
    ссылочной — когда у хранилища есть короткоживущая подписанная ссылка
    (Яндекс.Диск), и байтовой — когда такой ссылки не существует физически
    (Google Drive отдаёт содержимое по токену). Смотреть надо на то, что пришло,
    а не предполагать: раньше здесь безусловно требовался stream_url, и материал
    из Google открывался ошибкой.

    Оба потребителя ниже зовут эту функцию вместо собственных одинаковых кусков —
    иначе следующая форма ответа снова потребует правки в двух местах.
    """
    content_b64 = str(resolved.get("content_base64") or "")
    if content_b64:
        try:
            raw = base64.b64decode(content_b64, validate=True)
        except (ValueError, TypeError) as e:
            raise MaterialContentError(f"облако прислало битое содержимое: {e}") from e
        if len(raw) > MAX_INLINE_BYTES:
            raise MaterialContentError(
                f"материал больше порога {MAX_INLINE_BYTES} байт"
            )
        return raw

    stream_url = str(resolved.get("stream_url") or "")
    if not stream_url:
        raise MaterialContentError(
            "Radar OS не вернул ни ссылку на файл, ни его содержимое"
        )

    try:
        req = urllib.request.Request(stream_url, method="GET")
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            # +1 байт чтобы отличить «ровно порог» от «обрезали по порогу»
            raw = resp.read(MAX_INLINE_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise MaterialContentError(f"облако ответило HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise MaterialContentError(f"облако недоступно: {e.reason}") from e
    except OSError as e:
        raise MaterialContentError(f"обрыв при скачивании: {e}") from e

    if len(raw) > MAX_INLINE_BYTES:
        raise MaterialContentError(f"материал больше порога {MAX_INLINE_BYTES} байт")

    return raw


def resolve_material_form(
    tenant_code: str,
    material_id: int,
    *,
    size_hint: int | None = None,
    projection: str = "source",
) -> tuple[str, str | bytes, str]:
    """Форма, в которой Radar OS отдал материал, БЕЗ разворачивания в байты.

    Возвращает одно из двух:
      ("url",   подписанный_адрес, mime)  — облако умеет короткоживущую ссылку
      ("bytes", содержимое,        mime)  — не умеет, отдало содержимое

    Зачем отдельно от resolve_material_bytes: тот всегда доводит до байтов, и
    ссылка внутри него — промежуточный шаг. Для показа в браузере это потеря:
    по ссылке файл заберёт сам браузер, любого размера и не через нас (D13).

    Функция встаёт РЯДОМ с существующими, а не вместо. На resolve_material_content
    и resolve_material_bytes держится показ текста и картинок — портал Ильи стоит
    на них, ломать нельзя.
    """
    # Импорт ЛОКАЛЬНЫЙ — как в трёх соседних функциях: на уровне модуля его нет,
    # иначе граф импортов замкнётся (partners_api тянет extranet_resolver).
    from . import portals_api

    # os.getenv напрямую — тоже как у соседей. Помощника _hmac_secret() в этом
    # модуле не существует: я взял оба имени по памяти вместо чтения, и эндпоинт
    # падал пятисоткой дважды подряд.
    secret = os.getenv("PORTAL_HMAC_SECRET")
    if not secret:
        raise MaterialContentError(
            "PORTAL_HMAC_SECRET не задан — проверить systemd EnvironmentFile "
            "/srv/vschk/env.d/extranet_portals.env"
        )

    try:
        resolved = portals_api._call_radar_resolve(
            tenant_code, int(material_id), secret, mode="stream", projection=projection
        )
    except portals_api._RadarResolveError as e:
        raise MaterialContentError(f"Radar OS не отдал материал: {e}") from e

    mime = str(resolved.get("mime") or "application/octet-stream")

    stream_url = str(resolved.get("stream_url") or "")
    if stream_url:
        # Ссылочная форма: размер не наша забота вовсе — файл забирает браузер.
        # Потолок MAX_INLINE_BYTES здесь НЕ применяется, и это главный выигрыш
        # решения: видео и крупные документы становятся возможны.
        return ("url", stream_url, mime)

    content_b64 = str(resolved.get("content_base64") or "")
    if content_b64:
        try:
            raw = base64.b64decode(content_b64, validate=True)
        except (ValueError, TypeError) as e:
            raise MaterialContentError(f"облако прислало битое содержимое: {e}") from e
        # Порог применяется ТОЛЬКО к байтовой форме: здесь содержимое реально
        # проходит через наш процесс.
        if len(raw) > MAX_INLINE_BYTES:
            raise MaterialContentError(
                f"материал больше порога {MAX_INLINE_BYTES} байт"
            )
        return ("bytes", raw, mime)

    raise MaterialContentError(
        "Radar OS не вернул ни ссылку на файл, ни его содержимое"
    )


def resolve_material_bytes(
    tenant_code: str,
    material_id: int,
    size_hint: int = 0,
    projection: str = "source",
) -> bytes:
    """Сырые байты материала из облака — для картинок.

    Отличается от resolve_material_content только тем, что не декодирует в
    текст: картинку надо отдать как есть, чтобы дальше упаковать в data-строку.

    Raises:
        MaterialContentError — на любом сбое цепочки.
    """
    from . import portals_api

    secret = os.getenv("PORTAL_HMAC_SECRET")
    if not secret:
        raise MaterialContentError(
            "PORTAL_HMAC_SECRET не задан — проверить systemd EnvironmentFile "
            "/srv/vschk/env.d/extranet_portals.env"
        )

    # size_hint приходит из каталога и описывает ИСХОДНИК. Для страницы он
    # не годится: большой markdown заблокировал бы маленькую страницу рядом.
    # От переразмеренного ответа всё равно защищает проверка длины ниже.
    if projection == "source" and size_hint and size_hint > MAX_INLINE_BYTES:
        raise MaterialContentError(
            f"материал {size_hint} байт — больше порога {MAX_INLINE_BYTES}"
        )

    try:
        resolved = portals_api._call_radar_resolve(
            tenant_code, int(material_id), secret, mode="stream", projection=projection
        )
    except portals_api._RadarResolveError as e:
        raise MaterialContentError(f"Radar OS не отдал ссылку: {e}") from e

    return _bytes_from_resolved(resolved)


def resolve_material_public_url(
    tenant_code: str, material_id: int
) -> tuple[str, str]:
    """Публичная ссылка на материал и название облака, где он лежит.

    Режим publish, а не stream: stream живёт десять минут и годится только для
    немедленного скачивания на нашей стороне. Публичная ссылка ведёт на страницу
    облака, которая сама показывает видео — ровно это и нужно (decision-02.R2).

    Название приходит оттуда же, одним ответом (блок 71020). Своего списка
    вендоров витрина не заводит: соответствие «код облака → название» живёт в
    шине Radar OS, и второе место правды разъехалось бы на первом же новом
    вендоре. Пустое название — не беда: подпись просто обойдётся без имени.
    """
    from . import portals_api

    secret = os.getenv("PORTAL_HMAC_SECRET")
    if not secret:
        raise MaterialContentError("PORTAL_HMAC_SECRET не задан")

    try:
        resolved = portals_api._call_radar_resolve(
            tenant_code, int(material_id), secret, mode="publish"
        )
    except portals_api._RadarResolveError as e:
        raise MaterialContentError(f"Radar OS не отдал ссылку: {e}") from e

    url = str(resolved.get("publish_url") or "")
    if not url:
        raise MaterialContentError("Radar OS вернул пустую публичную ссылку")
    return url, str(resolved.get("storage_label") or "")


def resolve_material_content(
    tenant_code: str,
    material_id: int,
    size_hint: int = 0,
    projection: str = "source",
) -> str:
    """Текст материала из облака, подключённого к режиму «Экстранет».

    Две ссылки в цепочке:

      1. material_resolve_url.php в режиме stream — отдаёт подписанную прямую
         ссылку на файл, живёт ~10 минут, не кэшируется;
      2. по этой ссылке забираем сами байты.

    Почему stream, а не publish: publish возвращает публичную ссылку yadi.sk,
    которая отдаёт HTML-страницу Я.Диска, а не файл — за содержимым пришлось бы
    ходить ещё и в публичный API Яндекса. Stream отдаёт файл сразу, не требует
    публикации материала и поэтому переживёт переход режима в приватный
    (задача 666, W21), когда публичных ссылок не станет вовсе.

    projection выбирает представление материала: `source` — сам документ,
    `page` — собранная страница рядом с ним (задача 701, decision-02).

    Raises:
        MaterialContentError — на любом сбое цепочки, с причиной в тексте.
    """
    # Ленивый импорт: portals_api тянет за собой конфиг и роутеры, а этот модуль
    # грузится из partners_api. Импорт внутри функции держит граф модулей ацикличным.
    from . import portals_api

    secret = os.getenv("PORTAL_HMAC_SECRET")
    if not secret:
        raise MaterialContentError(
            "PORTAL_HMAC_SECRET не задан — проверить systemd EnvironmentFile "
            "/srv/vschk/env.d/extranet_portals.env"
        )

    # size_hint приходит из каталога и описывает ИСХОДНИК. Для страницы он
    # не годится: большой markdown заблокировал бы маленькую страницу рядом.
    # От переразмеренного ответа всё равно защищает проверка длины ниже.
    if projection == "source" and size_hint and size_hint > MAX_INLINE_BYTES:
        raise MaterialContentError(
            f"материал {size_hint} байт — больше порога {MAX_INLINE_BYTES}"
        )

    try:
        resolved = portals_api._call_radar_resolve(
            tenant_code, int(material_id), secret, mode="stream", projection=projection
        )
    except portals_api._RadarResolveError as e:
        raise MaterialContentError(f"Radar OS не отдал ссылку: {e}") from e

    raw = _bytes_from_resolved(resolved)

    # Каталог хранит наши же markdown в UTF-8. errors='replace' — чтобы один
    # битый байт не превращал документ в ошибку на глазах у клиента.
    return raw.decode("utf-8", errors="replace")
