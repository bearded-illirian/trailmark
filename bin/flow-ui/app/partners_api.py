"""
partners_api.py — FastAPI endpoints for partner portal (task 624).

Security-critical:
- Token validation via app.partners.get_partner_by_token
- Path isolation: partner sees ONLY files in their own folder
- Path traversal protection: `../` normalized + validated against partner root
- No listing endpoint of all partners (admin-only via CLI)

Endpoints:
  GET  /api/partner/{token}/info         → basic partner info (name, folder)
  GET  /api/partner/{token}/tree         → list of files/folders under partner folder
  GET  /api/partner/{token}/file?path=X  → content of a specific file
"""

from __future__ import annotations

import mimetypes
import base64
import logging
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from . import extranet_resolver
from . import partners
from .html_to_markdown import html_to_markdown, MarkdownConvertError
from . import personal_flow_resolver
from .config import Config

log = logging.getLogger(__name__)


# MIME types allowed for /asset endpoint — image/audio/video/pdf + generic download.
# Blocks executable / html to avoid XSS via user-uploaded content.
_ALLOWED_MIME_PREFIXES = ("image/", "audio/", "video/")
_ALLOWED_MIME_EXACT = {
    "application/pdf",
    "application/octet-stream",
    # Документ Word — только чтобы его можно было СКАЧАТЬ (блок 71050).
    # Список закрывает html и исполняемое ради защиты от подставленного скрипта;
    # docx в этот класс не входит: браузер его не исполняет и не рисует, отдача
    # байтов ничего не открывает. Показ идёт другим путём — конвертацией в
    # текст (блок 71040), и к этому списку отношения не имеет.
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Простой текст — чтобы «Скачать исходник» работал у расшифровок и заметок
    # (блок 73059). До этой строки текстовый материал Экстранета показывался в
    # портале, но кнопка скачивания под ним отдавала 415: у Ильи так лежали два
    # материала, и дырка была не будущей, а живой.
    #
    # Перечислены ДВА ТОЧНЫХ типа, а не префикс "text/", и это не педантизм:
    # под префикс попал бы text/html, ради защиты от которого список и заведён.
    # Простой текст в опасный класс не входит — браузер его не исполняет.
    "text/plain",
    "text/markdown",
}

# NB: в main.py есть второй перечень (_ASSET_ALLOWED_EXACT) с пометкой «mirror».
# Зеркалом он быть перестал ещё в блоке 71050, когда docx добавили только сюда,
# и это осознанно: /asset отдаёт файлы с диска витрины, ep-asset — материалы
# Экстранета из облака тенанта. Разные поверхности — разные допущения.
# Расхождение здесь названо прямо, чтобы следующий читатель не принял его за
# забывчивость и не «починил» синхронизацией.

# Image extensions for /images-in-folder gallery endpoint (block 677-4).
# Mirror of IMAGE_EXTS in partner.js + app.js.
_IMAGE_EXTS = frozenset({"png", "jpg", "jpeg", "gif", "svg", "webp", "avif", "bmp", "ico"})


def _is_allowed_mime(mime: str) -> bool:
    """Whitelist gate for /asset endpoint. Returns True for media + pdf + generic bin."""
    if not mime:
        return True  # unknown → falls back to octet-stream, allowed
    if mime in _ALLOWED_MIME_EXACT:
        return True
    return any(mime.startswith(p) for p in _ALLOWED_MIME_PREFIXES)


# Prefix renamed /api/partner → /api/extranet in task 695 block 20: the portal
# serves clients, students and contractors, not only partners. Module and file
# names deliberately keep the old wording — renaming internals would multiply the
# diff without changing anything the reader sees.
router = APIRouter(prefix="/api/extranet", tags=["extranet"])


class PartnerInfoOut(BaseModel):
    code: str
    name: str
    folder_path: str


# Task 701: имя файла второй проекции — {basename}.page.json рядом с {basename}.md.
# Правило действует только в файловых ветках; у Экстранета связь задаёт page_ref.
PAGE_SUFFIX = ".page.json"


class PartnerFileEntryOut(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    # Task 701 block 7: у документа есть вторая проекция — собранная страница.
    # Признак приходит из дерева, а не выводится фронтендом из имени файла:
    # в ветке Экстранета имён файлов нет вообще, там путь вида ep/{id}.
    has_page: bool = False
    # Task 695 block 71010: вид материала Экстранета — та же причина, что и у
    # has_page. Расширения у записи нет, есть имя вроде «Счёт № 38» и mime из
    # каталога тенанта, поэтому getMediaKind по расширению на фронте для этой
    # ветки не работает вовсе. Пусто у обычных файлов на диске — там вид
    # по-прежнему считает браузер по расширению.
    kind: Optional[str] = None
    # Task 695 block 71070: имя, под которым файл сохранится на диск.
    # Отдельно от name, потому что name — человеческое название материала
    # («Счёт № 38 от 19.08.2026»), а сохранять надо с расширением. Считает
    # бэкенд по той же причине, что и kind: расширения у витрины нет, оно
    # выводится из mime каталога тенанта. Пусто у файлов с диска — там имя
    # файла и есть имя файла.
    download_name: Optional[str] = None


class PartnerFileContentOut(BaseModel):
    path: str
    name: str
    content: str
    size: int
    # Название облака, где лежит материал Экстранета — для подписи под ссылкой
    # (блок 71020). Пусто у файлов с диска: они лежат у нас, и подписывать
    # нечем. Список названий живёт в Radar OS, витрина имён вендоров не знает.
    storage_label: Optional[str] = None


def _resolve_partner_root(cfg: Config) -> Path:
    """Get the root directory for all partner content (legacy path).

    Preferred: use _resolve_partner_folder(cfg, partner) which handles portals/{type}/{code}.
    Kept for backward compat with any caller that only needs the root.
    """
    root = cfg.paths.partner_content_root
    if not root:
        raise HTTPException(
            status_code=500,
            detail="partner_content_root not configured",
        )
    return Path(root).expanduser().resolve()


def _resolve_partner_folder(cfg: Config, partner: dict) -> Path:
    """Resolve absolute filesystem folder for a partner.

    Preferred order (task 651 block 500 portals refactor):
      1. portals_root / partner['portal_type'] / partner['folder_path']
         — new layout: portals/{partners,school,client}/{code}/
      2. partner_content_root / partner['folder_path']
         — legacy fallback for local dev before portals migration

    On VDS after migration: partner_content is a symlink → portals/partners,
    so legacy fallback still works for partner-type portals, but school
    (Anton) requires portals_root to be configured.
    """
    portal_type = partner.get("portal_type") or "partner"
    folder_path = partner.get("folder_path") or partner.get("code") or ""

    if cfg.paths.portals_root:
        base = Path(cfg.paths.portals_root).expanduser().resolve()
        return (base / portal_type / folder_path).resolve()

    # Legacy fallback (before portals_root задан)
    if cfg.paths.partner_content_root:
        base = Path(cfg.paths.partner_content_root).expanduser().resolve()
        return (base / folder_path).resolve()

    raise HTTPException(
        status_code=500,
        detail="Neither portals_root nor partner_content_root configured",
    )


def _validate_and_resolve_path(
    partner_folder: Path, requested_path: str
) -> Path:
    """
    Safely resolve requested_path against partner_folder.

    Prevents path traversal via `../` — resolved path MUST be inside
    partner_folder. Raises HTTPException(403) if not.
    """
    # Strip leading slash / dots
    requested = requested_path.lstrip("/").lstrip(".")
    if not requested:
        return partner_folder

    # Resolve absolute path
    candidate = (partner_folder / requested).resolve()

    # Ensure candidate is inside partner_folder (no traversal escape)
    try:
        candidate.relative_to(partner_folder)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Access denied: path outside partner folder",
        )

    return candidate


def _get_partner_or_404(cfg: Config, token: str) -> dict:
    """Load partner by token, 404 if not found or inactive."""
    if not cfg.paths.partners_db:
        raise HTTPException(500, "partners_db not configured")
    partner = partners.get_partner_by_token(
        Path(cfg.paths.partners_db).expanduser(), token
    )
    if not partner:
        raise HTTPException(404, "Invalid or expired token")
    return partner



# Расширения для типов, которые портал отдаёт сам. Явно, а не только через
# mimetypes: тот отвечает по-разному в разных версиях Python — 3.9 про
# text/markdown не знает вовсе, 3.12 знает. Скачанная расшифровка не должна
# терять расширение из-за версии интерпретатора на очередном сервере.
# Тип, с которым свёрстанная страница уходит клиенту при скачивании. В белом
# списке он уже есть — заводился под расшифровки (блок 73059), и странице
# годится ровно тот же: это текст, браузер его не исполняет.
_MARKDOWN_MIME = "text/markdown"

_MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/markdown": ".md",
    "text/plain": ".txt",
}


def _attachment_header(filename: str) -> str:
    """Заголовок вложения с именем, которое переживёт кириллицу.

    Две формы разом, как велит RFC 6266: голый filename= для старых читателей и
    filename*= с процентным кодированием для всех остальных. Без второй формы
    «22.08 — разбор.md» доезжает до диска мусором — имена материалов у нас
    русские все до единого, так что это не редкий случай, а обычный.

    В ASCII-запасной вариант кириллица не переводится транслитом: перевод
    выдумывает имя, которого человек не писал. Не-ASCII заменяется на «_»,
    и запасным именем пользуется только тот, кто не понял filename*.
    """
    ascii_name = "".join(c if 32 < ord(c) < 127 and c not in '"\\' else "_" for c in filename)
    quoted = quote(filename, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quoted}'


def _download_name(name: str, mime: str) -> str:
    """Имя для сохранения на диск: человеческое название плюс расширение.

    Расширение выводится из mime, потому что у материала Экстранета имени файла
    нет вовсе — есть название вроде «Счёт № 38 от 19.08.2026».

    Проверка «есть ли уже расширение» идёт по КОНЦУ имени, а не по наличию
    точки, и это не придирка: в названии счёта стоит дата, имя кончается на
    «.2026», и браузер принял её за расширение — файл сохранился без «.pdf» и не
    открывался двойным щелчком (блок 71070). Точка в названии ничего не значит,
    значит только совпадение с расширением.
    """
    clean = (mime or "").split(";")[0].strip().lower()
    if not clean:
        return name
    ext = _MIME_EXTENSIONS.get(clean) or mimetypes.guess_extension(clean) or ""
    if not ext or name.lower().endswith(ext.lower()):
        return name
    return name + ext


def _material_entry(m: dict) -> "PartnerFileEntryOut":
    """Материал как лист дерева. Путь — непрозрачный id, не имя файла."""
    name = m["name"] or f"Материал #{m['material_id']}"
    mime = str(m.get("mime") or "")
    kind = extranet_resolver.material_kind(name, mime)
    # Страница скачивается текстом, а не разметкой (блок 2411), поэтому имя ей
    # считается по типу ОТДАЧИ, а не по типу хранения. Иначе клиент получил бы
    # markdown в файле «22.08 — разбор.html» — содержимое одно, расширение
    # другое, и открывается такое браузером как сломанная страница.
    name_mime = _MARKDOWN_MIME if kind == extranet_resolver.KIND_PAGE_HTML else mime
    return PartnerFileEntryOut(
        name=name,
        path=f"ep/{m['material_id']}",
        is_dir=False,
        size=m.get("size"),
        has_page=bool(m.get("has_page")),
        kind=kind,
        download_name=_download_name(name, name_mime),
    )


def _extranet_tree(
    materials: list[dict], folders: list[dict], path: str
) -> list["PartnerFileEntryOut"]:
    """Дерево экстранет-портала: заведённые папки и то, что в них лежит.

    До блока 72000 папок как вещи не было — они выводились из строкового поля
    `chapter` у материалов, по трём правилам, которых оператор не видел: раздел
    проставлен не всем → папок нет вовсе; раздел один → папок нет; убрали из
    раздела последний материал → папка исчезла. Пустая папка при такой модели
    невозможна, а она — требование: место, куда будет складываться, клиент
    должен видеть заранее (decision-16).

    Теперь показываем ровно то, что завели: папки приезжают отдельным списком,
    материал знает свою папку номером. Материал без папки лежит в корне рядом с
    папками — это нормальное состояние, а не поломка.

    Папка адресуется своим номером, а не порядковым индексом: индекс съезжал при
    добавлении папки, и открытый у клиента портал показывал не то, что минуту
    назад. Тот же приём, что и у материалов — `ep/{id}` вместо имени файла: имя
    свободное, и «Встречи 12/08» со слэшем развалили бы путь на два уровня.
    """
    # Обложка в дереве не показывается: она рисуется на старте, когда читатель
    # ещё ничего не выбрал (задача 706, блок 200). Оставить её строкой в списке
    # значило бы показать один и тот же документ дважды.
    materials = [m for m in materials if not m.get("is_cover")]

    by_folder: dict[int, list[dict]] = {}
    roots: list[dict] = []
    for m in materials:
        fid = m.get("folder_id")
        if isinstance(fid, int) and fid > 0:
            by_folder.setdefault(fid, []).append(m)
        else:
            roots.append(m)

    known = {int(f["folder_id"]) for f in folders if f.get("folder_id") is not None}

    if not path:
        entries = [
            PartnerFileEntryOut(
                name=str(f.get("title") or ""),
                path=f"fd/{int(f['folder_id'])}",
                is_dir=True,
                size=None,
            )
            for f in folders
            if f.get("folder_id") is not None
        ]
        # Материал, чья папка не доехала, показываем в корне, а не прячем.
        # Спрятанный материал выглядит как «его нет» — а он есть, и клиент за
        # ним пришёл. Лучше показать не на месте, чем не показать вовсе.
        entries.extend(
            _material_entry(m)
            for m in materials
            if not (isinstance(m.get("folder_id"), int) and m["folder_id"] in known)
        )
        return entries

    if not path.startswith("fd/"):
        return []
    raw_id = path[3:].strip()
    if not raw_id.isdigit():
        return []
    folder_id = int(raw_id)
    if folder_id not in known:
        return []
    return [_material_entry(m) for m in by_folder.get(folder_id, [])]


def register_routes(app, cfg: Config) -> None:
    """Register partner routes on the given FastAPI app."""

    @router.get("/{token}/info", response_model=PartnerInfoOut)
    def partner_info(token: str) -> PartnerInfoOut:
        partner = _get_partner_or_404(cfg, token)
        return PartnerInfoOut(
            code=partner["code"],
            name=partner["name"],
            folder_path=partner["folder_path"],
        )

    @router.get("/{token}/tree", response_model=list[PartnerFileEntryOut])
    def partner_tree(
        token: str, path: str = Query("", description="Subpath under partner folder")
    ) -> list[PartnerFileEntryOut]:
        partner = _get_partner_or_404(cfg, token)

        # Task 660 block 9050: personal_flow shares — resolve через cross-DB
        # personal_flow.sqlite share_files JOIN files (root listing only, MVP scope)
        if personal_flow_resolver.is_personal_flow_share(partner):
            files = personal_flow_resolver.resolve_share_files(partner) or []
            return [
                PartnerFileEntryOut(
                    name=f["name"],
                    path=f"pf/{f['provider']}/{f['file_id']}",  # opaque path для /file lookup
                    is_dir=False,
                    size=f.get("size_bytes"),
                )
                for f in files
            ]

        # Task 695 block 31: экстранет-портал — материалы описаны в portal_materials,
        # файлы живут в облаке тенанта. Ветка стоит после personal_flow (у того свой
        # признак) и до дисковой — иначе дисковая успеет бросить 404 про папку,
        # которой у облачного портала никогда и не было.
        materials = extranet_resolver.resolve_portal_materials(partner)
        if materials is not None:
            folders = extranet_resolver.resolve_portal_folders(partner)
            return _extranet_tree(materials, folders, path)

        partner_folder = _resolve_partner_folder(cfg, partner)

        if not partner_folder.exists():
            # Экстранет-портал с пустым пакетом неотличим от файлового: строк в
            # portal_materials нет, папки на диске тоже. Клиенту честнее пустой
            # портал, чем сообщение про наш диск — именно этот текст сбил
            # диагностику в блоке 8. Отличить два случая здесь нечем, и пустое
            # дерево безопаснее 404 на клиентской странице.
            return []

        target = _validate_and_resolve_path(partner_folder, path)
        if not target.exists():
            raise HTTPException(404, f"Path not found: {path}")
        if not target.is_dir():
            raise HTTPException(400, f"Path is not a directory: {path}")

        children = [c for c in sorted(target.iterdir()) if not c.name.startswith(".")]

        # Task 701 block 7: собранная страница — вторая проекция документа,
        # а не самостоятельный файл. В дереве её не показываем, вместо этого
        # помечаем исходник признаком. Решение о признаке принимает бэкенд:
        # в ветке Экстранета имён файлов нет вовсе, и фронтенд обязан работать
        # одинаково во всех трёх ветках (decision-02).
        page_owners = {
            c.name[: -len(PAGE_SUFFIX)] + ".md"
            for c in children
            if c.is_file() and c.name.endswith(PAGE_SUFFIX)
        }

        entries = []
        for child in children:
            if child.is_file() and child.name.endswith(PAGE_SUFFIX):
                continue
            entries.append(
                PartnerFileEntryOut(
                    name=child.name,
                    path=str(child.relative_to(partner_folder)),
                    is_dir=child.is_dir(),
                    size=child.stat().st_size if child.is_file() else None,
                    has_page=child.name in page_owners,
                )
            )
        return entries

    def _task_counts(partner: dict) -> Optional[tuple[int, int]]:
        """Сколько задач портала закрыто и сколько всего.

        Считает витрина, а не страница. Страница живёт в песочнице без
        allow-same-origin — до задач ей не дотянуться, и это защита магического
        токена, а не недоделка (`app/static/sandbox-frame.js`).

        Возвращает None при любой заминке: портал мог никогда не заводить задач,
        базы может не быть, таблицы может не быть. Тогда обложка отдаётся с тем
        числом, которое в ней написано, — то есть ровно как до этой правки.
        Обложка это первый экран клиента, и ошибка здесь дороже неточной цифры.
        """
        portal_type = partner.get("portal_type") or "partner"
        folder = partner.get("folder_path") or partner.get("code") or ""
        root = Path(cfg.paths.portals_root or cfg.paths.partner_content_root or "").expanduser()
        db = root / portal_type / folder / ".kit-data" / "tasks.sqlite"
        if not db.exists():
            return None
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        except sqlite3.OperationalError:
            return None
        try:
            name = partner.get("name") or ""
            total, done = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(status='done'),0) FROM tasks "
                "WHERE assigned_to = ?", (name,)
            ).fetchone()
            # Имя портала и имя в задачах совпадают не везде: у портала может
            # быть «Антон Гефт (@AVGeft)», а в задачах «Антон Гефт». Пустой
            # результат при непустой таблице означает не «нечего показывать»,
            # а несовпадение имён — тогда считаем всё, что есть в портале.
            # База и так своя у каждого портала, чужого сюда не попадёт.
            if total == 0:
                total, done = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(status='done'),0) FROM tasks"
                ).fetchone()
            return (int(done), int(total)) if total else None
        except sqlite3.Error:
            return None
        finally:
            conn.close()

    def _fill_counts(html: str, counts: Optional[tuple[int, int]]) -> str:
        """Подставить числа в элементы с data-count="done" и "total".

        Метки нет — возвращаем разметку нетронутой. Так обложка, собранная до
        этой правки, продолжает работать со своим вписанным числом.
        """
        if not counts:
            return html
        done, total = counts
        for mark, value in (("done", done), ("total", total)):
            html = re.sub(
                r'(<([a-z]+)[^>]*\bdata-count="%s"[^>]*>)(.*?)(</\2>)' % mark,
                lambda m, v=value: f"{m.group(1)}{v}{m.group(4)}",
                html,
                flags=re.DOTALL,
            )
        return html

    @router.get("/{token}/cover", response_model=PartnerFileContentOut)
    def partner_cover(token: str):
        """Обложка портала — что читатель видит до того, как что-то выбрал.

        Отдельная ручка, а не поле в дереве: дерево возвращает список, класть
        в него запись «не документ» пришлось бы соглашением, которое фронт
        обязан помнить. Отсутствие обложки — обычный случай, а не ошибка:
        404 значит «показывай как раньше» (задача 706, блок 200).
        """
        partner = partners.get_partner_by_token(cfg.paths.partners_db, token)
        if not partner:
            raise HTTPException(status_code=404, detail="Invalid or expired token")

        materials = extranet_resolver.resolve_portal_materials(partner) or []
        cover = next((m for m in materials if m.get("is_cover")), None)
        if cover is None:
            raise HTTPException(status_code=404, detail="No cover")

        tenant_code = partner.get("tenant_code") or ""
        material_id = int(cover["material_id"])
        try:
            content = extranet_resolver.resolve_material_content(
                tenant_code, material_id, size_hint=int(cover.get("size") or 0)
            )
        except extranet_resolver.MaterialContentError as e:
            raise HTTPException(status_code=502, detail=str(e))

        # Счётчик задач на обложке: считаем здесь, а не в странице.
        # Отказ подсчёта не должен трогать выдачу — обложка важнее цифры.
        try:
            content = _fill_counts(content, _task_counts(partner))
        except Exception:  # noqa: BLE001 — обложка важнее счётчика
            log.warning("cover counts failed for portal %s", partner.get("code"))

        return PartnerFileContentOut(
            path=f"ep/{material_id}",
            name=str(cover.get("name") or ""),
            size=len(content.encode("utf-8")),
            content=content,
        )

    @router.get("/{token}/file", response_model=PartnerFileContentOut)
    def partner_file(
        token: str,
        path: str = Query(..., description="Relative path to file"),
        projection: str = Query(
            "source",
            description="source — сам документ, page — собранная страница (задача 701)",
        ),
    ) -> PartnerFileContentOut:
        partner = _get_partner_or_404(cfg, token)

        # Task 660 block 9050: personal_flow shares — path format "pf/{provider}/{file_id}"
        # MVP scope: content proxy deferred (libsodium encrypted OAuth в bus_credentials —
        # Python не имеет vault decrypt key). Return metadata + native Drive URL.
        # Client opens `web_view_link` для actual view.
        if personal_flow_resolver.is_personal_flow_share(partner) and path.startswith("pf/"):
            parts = path.split("/", 2)
            if len(parts) != 3:
                raise HTTPException(400, "Invalid personal_flow file path")
            _, provider, file_id = parts
            f = personal_flow_resolver.get_share_file(partner, provider, file_id)
            if not f:
                raise HTTPException(404, "File not found in share (revoked/expired/mismatch)")
            # MVP: content field содержит note + native URL для client redirect
            content = (
                f"[Personal Flow file — open in native app]\n\n"
                f"Name: {f['name']}\n"
                f"Type: {f['mime_type']}\n"
                f"URL: {f['web_view_link']}\n"
            )
            return PartnerFileContentOut(
                path=path,
                name=f["name"],
                content=content,
                size=f.get("size_bytes") or 0,
            )

        # Task 695 block 32: экстранет-портал — путь вида "ep/{material_id}".
        # Файл лежит не у нас, а в облаке тенанта; за содержимым идём в Radar OS.
        if path.startswith("ep/"):
            materials = extranet_resolver.resolve_portal_materials(partner)
            if materials is None:
                raise HTTPException(404, f"File not found: {path}")

            raw_id = path[3:].strip()
            if not raw_id.isdigit():
                raise HTTPException(400, "Invalid extranet material path")
            material_id = int(raw_id)

            # material_id приходит из браузера — сверяем с материалами именно
            # этого портала, иначе подстановка чужого id открыла бы чужой каталог.
            material = next(
                (m for m in materials if int(m["material_id"]) == material_id), None
            )
            if material is None:
                raise HTTPException(404, "Material not in portal")

            name = material.get("name") or f"Материал #{material_id}"
            size = int(material.get("size") or 0)
            mime = str(material.get("mime") or "")

            tenant_code = str(partner.get("tenant_code") or "")
            if not tenant_code:
                raise HTTPException(
                    500,
                    "У портала не указан тенант — материал не с кем сопоставить",
                )

            # Собранная страница — вторая проекция того же материала, не
            # отдельный файл в дереве (задача 701, decision-02). Отдаётся
            # всегда как текст: это JSON, который разбирает рендерер.
            if projection == "page":
                if not material.get("has_page"):
                    raise HTTPException(404, "У материала нет собранной страницы")
                try:
                    page = extranet_resolver.resolve_material_content(
                        tenant_code, material_id, projection="page"
                    )
                except extranet_resolver.MaterialContentError as e:
                    raise HTTPException(502, f"Не удалось получить страницу: {e}")
                return PartnerFileContentOut(
                    path=path,
                    name=name,
                    size=len(page.encode("utf-8")),
                    content=page,
                )

            # Вид решает бэкенд, а не браузер: у витрины нет расширения файла,
            # только имя и mime из каталога тенанта (блок 71, decision-02.R2).
            kind = extranet_resolver.material_kind(name, mime)

            try:
                # Страница едет тем же путём, что и текст: портал получает
                # разметку строкой и рисует её в изолированном фрейме. Без
                # этой ветки новый вид проваливался в «открыть в облаке» —
                # клиент видел строку external:https://… вместо страницы.
                if kind in (extranet_resolver.KIND_TEXT, extranet_resolver.KIND_PAGE_HTML):
                    content = extranet_resolver.resolve_material_content(
                        tenant_code, material_id, size_hint=size
                    )
                    return PartnerFileContentOut(
                        path=path,
                        name=name,
                        # size в витрине — копия с момента загрузки и могла
                        # устареть; длина реально полученного честнее.
                        size=len(content.encode("utf-8")),
                        content=content,
                    )

                if kind == extranet_resolver.KIND_DOC:
                    raw = extranet_resolver.resolve_material_bytes(
                        tenant_code, material_id, size_hint=size
                    )
                    # Разметка приходит уже очищенной белым списком тегов —
                    # чистка стоит на выходе docx_to_html, одной точкой на оба
                    # способа конвертации (блок 71040, decision-15).
                    document = extranet_resolver.docx_to_html(raw)
                    return PartnerFileContentOut(
                        path=path,
                        name=name,
                        # Длина разметки, а не исходного файла: size в каталоге
                        # относится к docx, а клиенту едет текст.
                        size=len(document.encode("utf-8")),
                        content=document,
                    )

                # Совместимость, а не рабочий путь (блок 71010). С этого блока
                # картинку показывает ep-asset, и свежий partner.js сюда за ней
                # не приходит. Ветка оставлена намеренно: partner.html грузит
                # /static/partner.js без версии в адресе, поэтому у уже
                # открытого портала в браузере лежит прежний файл, и он позовёт
                # /file. Убрать — когда появится сброс кэша по версии.
                if kind == extranet_resolver.KIND_IMAGE:
                    raw = extranet_resolver.resolve_material_bytes(
                        tenant_code, material_id, size_hint=size
                    )
                    # Поле content строковое — картинка едет data-строкой.
                    # Base64 раздувает на треть, поэтому порог в резолвере не
                    # поднимаем: 5 МБ картинки дают ~6,7 МБ ответа.
                    mime_clean = (mime or "image/png").split(";")[0].strip()
                    encoded = base64.b64encode(raw).decode("ascii")
                    return PartnerFileContentOut(
                        path=path,
                        name=name,
                        size=len(raw),
                        content=f"data:{mime_clean};base64,{encoded}",
                    )

                # Что браузер не рисует сам — открывается на стороне облака.
                # Своего плеера у дерева нет: страница облака умеет и перемотку,
                # и полный экран.
                url, storage_label = extranet_resolver.resolve_material_public_url(
                    tenant_code, material_id
                )
                return PartnerFileContentOut(
                    path=path,
                    name=name,
                    size=size,
                    content=f"external:{url}",
                    storage_label=storage_label or None,
                )
            except extranet_resolver.MaterialContentError as e:
                raise HTTPException(502, f"Не удалось получить материал: {e}")

        partner_folder = _resolve_partner_folder(cfg, partner)

        if not partner_folder.exists():
            raise HTTPException(404, "Partner folder not found on disk")

        # Проекция страницы в файловых ветках: служебный файл убран из дерева
        # (см. partner_tree), поэтому по имени его больше не запросить — путь
        # выводится из исходника тем же правилом, что и признак has_page.
        if projection == "page":
            if not path.lower().endswith(".md"):
                raise HTTPException(404, "У документа нет собранной страницы")
            path = path[: -len(".md")] + PAGE_SUFFIX

        target = _validate_and_resolve_path(partner_folder, path)
        if not target.exists() or not target.is_file():
            raise HTTPException(404, f"File not found: {path}")

        # Size guard — max 500 KB for markdown
        max_size = cfg.filesystem.max_file_size_kb * 1024
        size = target.stat().st_size
        if size > max_size:
            raise HTTPException(413, f"File too large: {size} > {max_size} bytes")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "Binary files not supported")

        rel_path = str(target.relative_to(partner_folder))
        return PartnerFileContentOut(
            path=rel_path,
            name=target.name,
            content=content,
            size=size,
        )

    @router.api_route("/{token}/asset", methods=["GET", "HEAD"])
    def partner_asset(
        token: str,
        path: str = Query(..., description="Relative path to binary asset (pdf/image/audio/video)"),
    ):
        """Serve binary assets (PDF/PNG/MP3/MP4/etc) with correct Content-Type.

        Mirror of shares_api.py:200-228 pattern. NB: no `filename=` passed to
        FileResponse — otherwise browsers download instead of inline preview.
        """
        partner = _get_partner_or_404(cfg, token)
        partner_folder = _resolve_partner_folder(cfg, partner)

        if not partner_folder.exists():
            raise HTTPException(404, "Partner folder not found on disk")

        target = _validate_and_resolve_path(partner_folder, path)
        if not target.exists() or not target.is_file():
            raise HTTPException(404, f"Asset not found: {path}")

        media_type, _ = mimetypes.guess_type(str(target))
        if not media_type:
            media_type = "application/octet-stream"

        if not _is_allowed_mime(media_type):
            raise HTTPException(415, f"MIME type not allowed: {media_type}")

        return FileResponse(path=str(target), media_type=media_type)

    @router.api_route("/{token}/ep-asset", methods=["GET", "HEAD"])
    def partner_ep_asset(
        request: Request,
        token: str,
        path: str = Query(..., description="Путь материала Экстранета вида ep/{material_id}"),
    ):
        """Материал Экстранета браузеру — как /asset отдаёт файл с диска.

        Отличие в том, откуда берётся содержимое: у материала Экстранета файла
        на диске витрины нет, он лежит в облаке тенанта. Radar OS отдаёт его
        одной из двух форм и честно помечает какой (D11), а здесь по этой форме
        и решаем (D13):

          ссылка → 302 на подписанный адрес: файл забирает сам браузер, любого
                   размера, и трафик через витрину не идёт вовсе;
          байты  → отдаём содержимым с типом из каталога.

        ВЕНДОР ЗДЕСЬ НЕ УПОМИНАЕТСЯ НИ РАЗУ, и это проверяемый признак того, что
        решение не выродилось в расщепление по облаку: облако, которое завтра
        научится отдавать ссылку, заработает без единой правки.

        NB: filename= не передаём — как и в /asset, иначе браузер начнёт
        скачивать вместо показа, и весь смысл встроенного просмотра пропадёт.
        """
        partner = _get_partner_or_404(cfg, token)

        if not path.startswith("ep/"):
            raise HTTPException(400, "Этот адрес только для материалов Экстранета")
        raw_id = path[3:].strip()
        if not raw_id.isdigit():
            raise HTTPException(400, "Invalid extranet material path")
        material_id = int(raw_id)

        # Проверка принадлежности — ПЕРВОЙ и обязательно здесь, а не в соседнем
        # эндпоинте: номер приходит из браузера, и без сверки подстановка чужого
        # открыла бы чужой документ.
        materials = extranet_resolver.resolve_portal_materials(partner)
        if materials is None:
            raise HTTPException(404, f"File not found: {path}")
        material = next(
            (m for m in materials if int(m["material_id"]) == material_id), None
        )
        if material is None:
            raise HTTPException(404, "Material not in portal")

        tenant_code = str(partner.get("tenant_code") or "")
        if not tenant_code:
            raise HTTPException(
                500, "У портала не указан тенант — материал не с кем сопоставить"
            )

        catalog_mime = str(material.get("mime") or "") or "application/octet-stream"
        catalog_name = str(material.get("name") or "")

        # Свёрстанная страница уходит клиенту ТЕКСТОМ, а не разметкой.
        #
        # Ветка стоит ВЫШЕ заслона намеренно. Страница лежит с mime text/html,
        # а он в белый список не пущен и не будет: отдача разметки с нашего
        # домена — это исполняемый файл в руках клиента. До этой ветки кнопка
        # «Скачать» у шести документов кабинета всегда отвечала 415 — то есть
        # была, но не работала (задача 706, блок 2411).
        #
        # Заслон при этом не ослаблен ни на йоту: наружу идёт производный
        # markdown с типом text/markdown, а исходный html не покидает витрину
        # ни при каком раскладе. Показ страницы этой ветки не касается — он
        # берёт разметку через /file и работает как работал.
        if extranet_resolver.material_kind(catalog_name, catalog_mime) == \
                extranet_resolver.KIND_PAGE_HTML:
            if request.method == "HEAD":
                # Длину не обещаем: она у markdown своя, а считать её значит
                # сходить в облако и сконвертировать — ровно та работа, ради
                # отказа от которой HEAD и отвечает без облака.
                return Response(
                    status_code=200,
                    media_type=_MARKDOWN_MIME,
                    headers={"Cache-Control": "no-store"},
                )
            try:
                raw = extranet_resolver.resolve_material_bytes(
                    tenant_code, material_id, size_hint=int(material.get("size") or 0)
                )
                text = html_to_markdown(
                    raw.decode("utf-8", errors="replace"),
                    max_bytes=extranet_resolver.MAX_INLINE_BYTES,
                )
            except (extranet_resolver.MaterialContentError, MarkdownConvertError) as e:
                raise HTTPException(502, f"Не удалось собрать текст страницы: {e}")

            return Response(
                content=text.encode("utf-8"),
                media_type=_MARKDOWN_MIME,
                headers={
                    "Cache-Control": "no-store",
                    # Вложение здесь уместно, в отличие от остальных видов:
                    # показывать markdown в браузере нечем, а кнопка и была
                    # кнопкой скачивания.
                    "Content-Disposition": _attachment_header(
                        _download_name(catalog_name, _MARKDOWN_MIME)
                    ),
                },
            )

        # Тип проверяем до отдачи — и отдаём ровно с этим типом. При
        # перенаправлении заслон проверял тип из каталога, а заголовок ставило
        # облако: проверяли одно, браузер получал другое (decision-14).
        if not _is_allowed_mime(catalog_mime.split(";")[0].strip()):
            raise HTTPException(415, f"MIME type not allowed: {catalog_mime}")

        # HEAD отвечаем, ни разу не сходив в облако. Тело для него всё равно не
        # отправляется, а поток мы бы скачали целиком впустую: у StreamingResponse
        # нет отсечки по методу, какая есть у FileResponse. Размер берём из
        # каталога — он и есть то, что спрашивают этим запросом.
        if request.method == "HEAD":
            head_headers = {"Cache-Control": "no-store"}
            catalog_size = int(material.get("size") or 0)
            if catalog_size > 0:
                head_headers["Content-Length"] = str(catalog_size)
            return Response(
                status_code=200, media_type=catalog_mime, headers=head_headers
            )

        try:
            form, payload, mime = extranet_resolver.resolve_material_form(
                tenant_code, material_id, size_hint=int(material.get("size") or 0)
            )
        except extranet_resolver.MaterialContentError as e:
            raise HTTPException(502, f"Не удалось получить материал: {e}")

        out_mime = mime or catalog_mime
        # Содержимое живёт в облаке и там же меняется — не кэшируем.
        headers = {"Cache-Control": "no-store"}

        if form == "url":
            # Не перенаправляем: браузер получил бы «вложение» и скачал файл
            # вместо показа (decision-14, проверено на живом адресе).
            stream, size = extranet_resolver.open_material_stream(str(payload))
            if size is not None:
                headers["Content-Length"] = str(size)
            return StreamingResponse(stream, media_type=out_mime, headers=headers)

        return Response(content=payload, media_type=out_mime, headers=headers)

    @router.get("/{token}/images-in-folder", response_model=list[PartnerFileEntryOut])
    def partner_images_in_folder(
        token: str,
        path: str = Query("", description="Subpath under partner folder (empty = root)"),
    ) -> list[PartnerFileEntryOut]:
        """Return all image files in a specific folder (for lightbox gallery, block 677-5)."""
        partner = _get_partner_or_404(cfg, token)
        partner_folder = _resolve_partner_folder(cfg, partner)

        if not partner_folder.exists():
            raise HTTPException(404, "Partner folder not found on disk")

        target = _validate_and_resolve_path(partner_folder, path)
        if not target.exists() or not target.is_dir():
            raise HTTPException(404, f"Folder not found: {path}")

        images = []
        for child in sorted(target.iterdir()):
            if not child.is_file() or child.name.startswith("."):
                continue
            ext = child.suffix.lower().lstrip(".")
            if ext not in _IMAGE_EXTS:
                continue
            rel_path = str(child.relative_to(partner_folder))
            images.append(PartnerFileEntryOut(
                name=child.name,
                path=rel_path,
                is_dir=False,
                size=child.stat().st_size,
            ))
        return images

    app.include_router(router)
