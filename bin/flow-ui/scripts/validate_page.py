#!/usr/bin/env python3
"""validate_page.py — проверка собранной страницы (task 701 block 4).

Сверяет .page.json с контрактом docs/PAGE_FORMAT.md.

Каталог типов берётся из РЕЕСТРА RENDERERS в app/static/doc-blocks.js —
по § 7 при расхождении спецификации и кода верен код. Обязательные слоты
берутся из таблицы § 4 спецификации. Расхождение между этими двумя
источниками — отдельная ошибка: ровно так на блоке 3 нашёлся тип next,
который сборщик выдавал, а рендерер не умел рисовать.

Использование:
    python3 scripts/validate_page.py файл.page.json [ещё.page.json ...]
    python3 scripts/validate_page.py --expect-fail docs/demo.page.json

Коды возврата: 0 — проверка дала ожидаемый результат, 1 — нет.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDERERS_JS = ROOT / "app" / "static" / "doc-blocks.js"
PATTERNS_JS = ROOT / "app" / "static" / "doc-patterns.js"
SPEC_MD = ROOT / "docs" / "PAGE_FORMAT.md"

# Конструкции, которые doc-patterns.js строит в текстовой проекции, и типы
# каталога, которые обязаны давать тот же результат в собранной странице.
# Соответствие задано вручную: у доработчика нет реестра типов, только имена
# классов, поэтому сверка — эвристика, а не контракт (задача 701 блок 5 р.2,
# находка визуальной проверки: .doc-meta существовал только в одном движке).
PATTERN_TO_TYPE = {
    "doc-hero": "hero",
    "doc-meta": "meta",
    "doc-cards": "cards",
    "doc-steps": "steps",
    "doc-callout": "callout",
    "doc-next": "next",
    "doc-table": "table",
    # Дописаны 26.08 (задача 718 блок 20095). Рендереры этих двух были на месте
    # с самого начала — doc-blocks.js:193 для quote, :93 для kpi, 13 правил в
    # style.css, — а в словаре их не хватало. Из-за этого валидатор отдавал код 1
    # на ЛЮБОЙ странице: сверка реестра с движком шла до проверки самого файла,
    # и «class не сопоставлен» вылезал, даже когда страница была без замечаний.
    # Первым на это налетело резюме встречи с цитатой.
    "doc-quote": "quote",
    "doc-kpi": "kpi",
}

MIN_TYPES = 10  # ниже порога считаем, что разбор сломался, а не что типов мало
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
MARKUP_RE = re.compile(r"\*\*.+?\*\*|<[a-zA-Z/][^>]*>|\[.+?\]\(.+?\)")


def die(msg):
    print(f"🛑 {msg}", file=sys.stderr)
    sys.exit(2)


def code_types():
    """Ключи реестра RENDERERS — источник правды по типам (§ 7)."""
    src = RENDERERS_JS.read_text(encoding="utf-8")
    m = re.search(r"const RENDERERS = \{(.+?)\n  \};", src, re.S)
    if not m:
        die(f"не нашёл блок RENDERERS в {RENDERERS_JS}")
    types = set(re.findall(r"^    (\w+)\(", m.group(1), re.M))
    if len(types) < MIN_TYPES:
        die(f"из RENDERERS вынуто {len(types)} типов — разбор сломан, а не каталог пуст")
    return types


def pattern_classes():
    """Классы doc-*, которые строит доработчик текстовой проекции."""
    src = PATTERNS_JS.read_text(encoding="utf-8")
    return set(re.findall(r'el\(\s*"[a-z]+"\s*,\s*"(doc-[a-z]+)(?:__[a-z-]+)?"', src))


def spec_rules():
    """Таблица § 4: тип → (обязательные корневые слоты, поэлементные, особый случай)."""
    src = SPEC_MD.read_text(encoding="utf-8")
    # ТОЛЬКО раздел § 4: таблица § 2 (корневые поля) тоже четырёхколоночная
    # и с полем в обратных кавычках — без среза version/blocks уезжают в каталог типов
    m = re.search(r"^## 4\..*?(?=^## )", src, re.S | re.M)
    if not m:
        die("не нашёл раздел § 4 в PAGE_FORMAT.md")
    rules = {}
    for line in m.group(0).split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        m = re.fullmatch(r"`(\w+)`", cells[0])
        if not m:
            continue
        root, per_item, special = [], [], None
        for tok in cells[2].split(","):
            tok = tok.strip()
            if not tok or tok == "—":
                continue
            if tok == "одно из двух":
                special = "one_of"
                continue
            m2 = re.fullmatch(r"`(\w+)`(\s+в каждом)?", tok)
            if not m2:
                continue
            (per_item if m2.group(2) else root).append(m2.group(1))
        rules[m.group(1)] = {"root": root, "per_item": per_item, "special": special}
    if len(rules) < MIN_TYPES:
        die(f"из таблицы § 4 вынуто {len(rules)} типов — разбор сломан, а не спецификация пуста")
    return rules


def walk_strings(value, path):
    """Все строковые значения с путями — для проверки на разметку."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from walk_strings(v, f"{path}.{k}")


def check_root(page, errs, warns):
    if not isinstance(page.get("version"), int):
        errs.append("version — не целое число")
    built = page.get("built_at")
    if not isinstance(built, str) or not ISO_RE.match(built):
        errs.append("built_at — не строка вида ГГГГ-ММ-ДДTчч:мм:сс")
    name = page.get("source_name")
    if not isinstance(name, str) or not name.endswith(".md"):
        errs.append("source_name — не имя markdown-файла")
    h = page.get("source_hash")
    if not isinstance(h, str) or not HEX64_RE.match(h):
        errs.append("source_hash — не 64 шестнадцатеричных символа в нижнем регистре")
    if not isinstance(page.get("blocks"), list):
        errs.append("blocks — не массив")
    elif not page["blocks"]:
        warns.append("blocks пуст — портал покажет «страница пуста»")


def check_block(b, i, known, rules, errs, warns):
    at = f"blocks[{i}]"
    if not isinstance(b, dict):
        errs.append(f"{at} — не объект")
        return
    t = b.get("type")
    if not isinstance(t, str) or not t:
        errs.append(f"{at}.type — отсутствует или пуст")
        return
    if t not in known:
        errs.append(f"{at}.type = «{t}» — нет в реестре RENDERERS, портал покажет жёлтую врезку")
        return
    rule = rules.get(t)
    if rule is None:
        return  # расхождение уже сообщено сверкой каталогов

    if rule["special"] == "one_of":
        if not (b.get("paragraphs") or b.get("text")):
            errs.append(f"{at} — нужен хотя бы один из слотов paragraphs / text")

    container = None
    for slot in rule["root"]:
        v = b.get(slot)
        if v is None or v == "" or v == [] or v == {}:
            errs.append(f"{at}.{slot} — обязательный слот пуст")
            continue
        if isinstance(v, list):
            container = (slot, v)

    if rule["per_item"] and container:
        slot, items = container
        for j, it in enumerate(items):
            if not isinstance(it, dict):
                errs.append(f"{at}.{slot}[{j}] — не объект")
                continue
            for key in rule["per_item"]:
                if not it.get(key):
                    errs.append(f"{at}.{slot}[{j}].{key} — обязательное поле пусто")

    for path, s in walk_strings(b, at):
        if path.endswith(".src") or path.endswith(".type"):
            continue
        if MARKUP_RE.search(s):
            warns.append(f"{path} — разметка внутри значения, по § 5 отрисуется буквально")


def check_hash(page, src_path, errs, warns):
    name = page.get("source_name")
    if not isinstance(name, str):
        return
    md = src_path.parent / name
    if not md.is_file():
        warns.append(f"исходник «{name}» не найден рядом — отпечаток не сверен")
        return
    actual = hashlib.sha256(md.read_bytes()).hexdigest()
    if actual != page.get("source_hash"):
        warns.append(f"отпечаток не совпадает с «{name}» — страница собрана до правок исходника")


def validate(path, known, rules):
    errs, warns = [], []
    try:
        page = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"файл не разбирается как JSON: {e}"], []
    if not isinstance(page, dict):
        return ["корень файла — не объект"], []

    check_root(page, errs, warns)
    for i, b in enumerate(page.get("blocks") or []):
        check_block(b, i, known, rules, errs, warns)
    check_hash(page, path, errs, warns)
    return errs, warns


def main():
    argv = sys.argv[1:]
    expect_fail = "--expect-fail" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        print("Использование: validate_page.py файл.page.json [...] [--expect-fail]", file=sys.stderr)
        return 2

    known, rules = code_types(), spec_rules()

    # Сверка каталогов: реестр в коде против таблицы § 4
    drift = []
    for t in sorted(known - set(rules)):
        drift.append(f"тип «{t}» есть в RENDERERS, нет в таблице § 4 — спецификация отстала")
    for t in sorted(set(rules) - known):
        drift.append(f"тип «{t}» есть в таблице § 4, нет в RENDERERS — портал его не нарисует")
    # Сверка двух движков: у документа две проекции, и конструкция, доступная
    # только в одной, делает вторую беднее — ровно это увидел пользователь.
    engine_gap = []
    for cls in sorted(pattern_classes()):
        want = PATTERN_TO_TYPE.get(cls)
        if want is None:
            engine_gap.append(f"класс «{cls}» из doc-patterns.js не сопоставлен ни одному типу — дополнить PATTERN_TO_TYPE")
        elif want not in known:
            engine_gap.append(f"текстовая проекция умеет «{cls}», а в каталоге блоков нет типа «{want}» — страница выйдет беднее")
    for g in engine_gap:
        print(f"🛑 движки: {g}")
    if not engine_gap:
        print("✅ движки: каждая конструкция текстовой проекции имеет пару в каталоге")

    for d in drift:
        print(f"🛑 каталог: {d}")
    if not drift:
        print(f"✅ каталог: {len(known)} типов, реестр и спецификация совпадают")

    total_err = len(drift) + len(engine_gap)
    for p in paths:
        if not p.is_file():
            print(f"🛑 {p} — файла нет")
            total_err += 1
            continue
        errs, warns = validate(p, known, rules)
        print(f"\n— {p.name}")
        for e in errs:
            print(f"  🛑 {e}")
        for w in warns:
            print(f"  ⚠️  {w}")
        if not errs and not warns:
            print("  ✅ без замечаний")
        total_err += len(errs)

    print(f"\nИтого ошибок: {total_err}")
    if expect_fail:
        if total_err:
            print("Ожидался отказ — получен. Проверка засчитана.")
            return 0
        print("🛑 Ожидался отказ, файл прошёл чисто — фикстура перестала проверять § 6.")
        return 1
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
