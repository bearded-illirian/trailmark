---
title: Ship-First
pitch: "Финал задачи: отчёт, деплой, smoke test, закрытие"
icon: 🚀
category: session
price: free
publish: true
order: 50
works_with:
  - id: plan-first
    why: Plan-first вызывает ship-first после execute блока
  - id: go-guide
    why: По итогам задачи ship-first может вызвать go-guide для гида
  - id: arch-map
    why: Финальная привязка артефакта к архитектуре (propagate)
  - id: ui-ai-first
    why: Если задача создаёт user-facing операции — ship-first запускает ui-ai-first
---

## Какую проблему решает

Агент написал код и сразу перешёл к следующему — нет отчёта, не сделан коммит, не задеплоено, не проверено на проде, не закрыто в routing.db. Через неделю никто не помнит что было сделано, ship-флоу не воспроизводится.

Без финального протокола — задача «висит» в полузакрытом состоянии: код есть, но никто не подтвердил что работает. STATUS.md устарел, sessions.md не дополнен.

## Как работает

Скилл работает в двух режимах. **Per-block** — закрывает один блок после plan-first: пишет report-NN.md + user-note-NN.md, делает коммит + push + sync, прогоняет smoke test по типам атомов (backend → curl, infra → systemctl, ai-skill → перечитать SKILL.md). UPDATE task_blocks status=done. Затем либо переходит к следующему блоку через flow-first, либо переключается в task-level.

**Task-level** — закрывает всю задачу: проверяет полноту артефактов, опционально запускает ui-ai-first для UX-аудита новых операций, собирает финальный user-note.md, спрашивает «закрываем?», предлагает гид через go-guide, привязку через arch-map, обновляет routing.db (status=done, atom counts), propagate arch_ref вверх по цепочке (epic → tz → brief), пишет STATUS.md и sessions.md.

## Результат работы

Задача — закрыта явно, не висит. Деплой сделан, smoke test пройден. routing.db содержит полную картину (артефакты, блоки, метрики). STATUS.md показывает следующий шаг, sessions.md — историю.

Через неделю любой агент или человек может восстановить контекст задачи за 2 минуты — отчёты, user-note, артефакты лежат в одной папке.

## С какими скиллами работает

| Скилл | Зачем |
|---|---|
| plan-first | Вызывает ship-first после execute блока — атомарный финал per-block |
| go-guide | Если задача даёт знание — ship-first предлагает зафиксировать гид |
| arch-map | Финальная привязка к архитектуре + propagate вверх по цепочке |
| ui-ai-first | При наличии user-facing операций — ship-first запускает UX-аудит |
