#!/usr/bin/env python3
"""Панели документа кабинета → задачи кабинета.

ЗАЧЕМ. Документ кабинета состоит из панелей — разделов с ключом. Каждой панели
соответствует задача клиента: он открывает её из документа по ссылке. Раньше связь
делалась руками, а выгрузка описаний — разовым скриптом, который потерялся вместе
со сборщиком (задача 706, блок 2372). На двухстах кабинетах ручная связь это не
работа, а её видимость.

СУХОЙ ПРОГОН ПО УМОЛЧАНИЮ. Скрипт печатает, что сделает, и ничего не пишет.
Запись включается ключом --apply. Это не удобство: в задаче 706 сухой прогон
с первого раза показал, что описания легли бы не в те задачи, и заметить это
можно было только открыв каждую.

ИДЕМПОТЕНТНОСТЬ ПО КЛЮЧУ. Повторный прогон ищет задачу по ключу панели и обновляет
её. Задача без ключа — не наша: её мог завести клиент руками, и трогать её значит
затереть его работу.

СВОЕГО КОДА ЗАПИСИ НЕТ. Всё идёт через три ручки портала по магик-токену. Это
прямое правило семьи go-extranet-*: писать свою запись запрещено антипаттерном.

Задача 721, блок 105.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

BASE = "https://flow.vschk.online"
# Порядок атрибутов не несущий: `data-key` может стоять не первым. Блок 303
# добавил разделам `id` для якорей оглавления, и он встал перед ключом —
# разбор перестал видеть панели вовсе, не сообщив об этом ни словом. Регулярка,
# завязанная на порядок атрибутов, ломается от любой правки разметки.
PANEL_RE = re.compile(
    r'<section\s[^>]*?data-key="(?P<key>[^"]+)"[^>]*>(?P<body>.*?)</section>',
    re.S,
)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def text_of(html):
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", html)).strip()


def parse_panels(html):
    """Собранный документ → список панелей. Панель = раздел с ключом."""
    panels = []
    for m in PANEL_RE.finditer(html):
        body = m.group("body")
        h2 = H2_RE.search(body)
        title = text_of(h2.group(1)) if h2 else ""
        panels.append({
            "key": m.group("key").strip(),
            "title": title,
            "description": body.strip(),
        })
    return panels


def api(method, path, token, payload=None):
    url = f"{BASE}/api/tasks/{token}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Портал ответил {e.code} на {method} {path}: {e.read()[:200].decode(errors='replace')}")


def plan_actions(panels, tasks, meeting=None):
    """Что делаем с каждой панелью. Ничего не пишет — только решает.

    Исход «без изменений» существует ради следа клиента. Раньше `PATCH` уходил
    каждой найденной по ключу панели, даже когда посылать было нечего, и метка
    `updated_at` переписывалась служебным прогоном. Аудита изменений в схеме
    портала нет — таблицы `tasks`, `task_comments`, `meetings` и всё, — поэтому
    метка единственный след того, когда задачу трогал человек. Прогон 31 августа
    переписал её всем пятнадцати задачам домашки и стёр время, в которое Артём
    отмечал пункты (задача 721, решение 05).

    ВСТРЕЧА УЧАСТВУЕТ В СРАВНЕНИИ НАРАВНЕ С ТЕКСТОМ. Задача может совпадать
    по тексту и описанию и при этом не иметь встречи — ровно так и было
    с пятнадцатью задачами домашки. Сравнивай мы только два поля, исход
    «без изменений» проглотил бы их, и ключ `--meeting` перестал бы работать
    молча: прогон отчитался бы «без изменений», и это выглядело бы правильно.
    Блок 207 отменился бы сам собой.
    """
    by_key = {t.get("panel_key"): t for t in tasks if t.get("panel_key")}
    actions = []
    for p in panels:
        if not p["key"]:
            actions.append(("пропуск", p, None, "у панели нет ключа"))
        elif p["key"] in by_key:
            task = by_key[p["key"]]
            diff = []
            if (task.get("text") or "").strip() != p["title"].strip():
                diff.append("текст")
            if (task.get("description") or "").strip() != p["description"].strip():
                diff.append("описание")
            if meeting is not None and task.get("meeting_id") != meeting:
                diff.append("встреча")
            if diff:
                actions.append(("обновить", p, task, "расходится: " + ", ".join(diff)))
            else:
                actions.append(("без изменений", p, task, "совпадает с задачей целиком"))
        else:
            actions.append(("завести", p, None, "задачи с таким ключом нет"))
    foreign = [t for t in tasks if not t.get("panel_key")]
    return actions, foreign


def main():
    ap = argparse.ArgumentParser(description="Панели документа кабинета → задачи кабинета")
    ap.add_argument("document", help="Собранный документ кабинета, .html")
    ap.add_argument("--token", required=True, help="Магик-токен кабинета")
    ap.add_argument("--source", default="personal", help="Источник задач кабинета")
    ap.add_argument("--assigned-to", default=None, help="Ответственный за заводимые задачи")
    ap.add_argument("--deadline", default=None, help="Срок заводимых задач")
    ap.add_argument("--meeting", type=int, default=None,
                    help="Встреча, к которой относятся задачи документа")
    ap.add_argument("--apply", action="store_true",
                    help="Писать. Без ключа — сухой прогон, ничего не меняется")
    args = ap.parse_args()

    try:
        html = open(args.document, encoding="utf-8").read()
    except OSError as e:
        raise SystemExit(f"Не читается документ: {e}")

    panels = parse_panels(html)
    if not panels:
        raise SystemExit(
            "В документе нет панелей — разделов с ключом. Задачи заводить не из чего.\n"
            "Панель это <section data-key=\"...\"> по контракту KABINET_DOC_FORMAT §4."
        )

    tasks = api("GET", "/tasks", args.token).get("tasks", [])
    actions, foreign = plan_actions(panels, tasks, args.meeting)

    print(f"Документ: {args.document}")
    print(f"Панелей: {len(panels)}  ·  задач в кабинете: {len(tasks)}")
    print()
    for kind, panel, task, why in actions:
        num = f"#{task['id']}" if task else "—"
        print(f"  {kind:13} {num:>5}  {panel['key']:24} {panel['title'][:44]}   ({why})")
    if foreign:
        print()
        print(f"  Не трогаем {len(foreign)} задач без ключа — их мог завести клиент руками:")
        for t in foreign[:10]:
            print(f"    #{t['id']} {str(t.get('text',''))[:60]}")

    if not args.apply:
        print()
        print("Сухой прогон. Ничего не записано. Повторить с --apply, чтобы применить.")
        return 0

    created = updated = skipped = unchanged = 0
    for kind, panel, task, _ in actions:
        if kind == "пропуск":
            skipped += 1
        elif kind == "без изменений":
            # Ни одной ручки. В этом весь блок 210: служебный прогон не должен
            # выглядеть так, будто задачу трогали, если её не трогали.
            unchanged += 1
        elif kind == "обновить":
            # Встреча идёт и в обновление тоже. Задачи документа заводятся один
            # раз, а привязать их к встрече может понадобиться позже — как и
            # случилось с домашкой 27 августа: пятнадцать задач уже
            # существовали, и починить их можно только этой веткой.
            # Без meeting_id здесь прогон перезапишет текст и молча оставит
            # встречу пустой (задача 721, блок 207).
            body = {"text": panel["title"], "description": panel["description"]}
            if args.meeting:
                body["meeting_id"] = args.meeting
            api("PATCH", f"/task/{task['id']}", args.token, body)
            updated += 1
        else:
            payload = {
                "source_key": args.source,
                "text": panel["title"],
                "description": panel["description"],
                "panel_key": panel["key"],
            }
            if args.assigned_to:
                payload["assigned_to"] = args.assigned_to
            if args.deadline:
                payload["deadline"] = args.deadline
            if args.meeting:
                payload["meeting_id"] = args.meeting
            api("POST", "/task", args.token, payload)
            created += 1

    print()
    print(f"Записано: заведено {created}, обновлено {updated}, "
          f"без изменений {unchanged}, пропущено {skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
