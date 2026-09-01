# Changelog — saffron-graphite

## v1.0.0 — 2026-07-31

### Added
- Initial release. Первая тема vschk-lab по THEMES_MANIFEST v1.0.
- 11 mandatory CSS vars объявлены: `--bg`, `--bg-2`, `--text`, `--text-muted`, `--brand`, `--brand-hover`, `--border`, `--danger`, `--success`, `--warning`, `--link`.
- Optional surface набор: `--surface-elevated`, `--surface-sunken`.
- Optional `[data-theme="light"]` базовый override (bg/text инверт, brand saffron консистентен).

### Palette anchors
- **Brand:** `#F4A300` (saffron) — общий с продуктами brand-showcase (vschk-site, aihub, blog, academy, aihunter, vasechka-ai umbrella).
- **Bg dark:** `#0f1117` (graphite dark) — совпадает с indigo palette existing `admin/app.css` (мягкий переход, retrofit будет тривиальный).
- **Link:** `#3aa7e2` (blue accent) — общий вспомогательный blue экосистемы.

### Consumers (planned)
- vschk-flow-ui (партнёрский портал Антона + Alex + все будущие)
- Digital Academy landing
- Blog
- AIHub

### Notes
- Единственная тема на 2026-07-31. Следующие: radar-os-blue (planned), radar-self-indigo (planned).
- Compliance: THEMES_MANIFEST §8 checklist — все 11 mandatory vars присутствуют, значения hex-only, один `:root` блок + опциональный `[data-theme="light"]`.
