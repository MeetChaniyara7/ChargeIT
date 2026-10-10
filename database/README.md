# database/

Everything about ChargeSpot's PostgreSQL database lives here. The design itself is in [docs/architecture.md](../docs/architecture.md), section 5.

| Folder | What goes in it | Arrives in |
|---|---|---|
| `migrations/` | Numbered SQL files that build the schema, applied in order: `001_extensions.sql`, `002_users_vehicles.sql`, … Each file explains its constraints in comments. | Phase 2 |
| `seeds/` | Scripts that create demo data: synthetic chargers and prices for stations missing them, demo users, demo bookings, demo kiosk devices. Everything they create is tagged `data_source = 'synthetic'`. | Phase 2 |
| `imports/` | Scripts that load real stations from OpenStreetMap and Open Charge Map, plus the cleaning steps (operator-name merging, connector normalisation, duplicate removal). | Phase 2 |
| `queries/` | Ready-made SQL to open in DBeaver: reports, data checks, and queries used in the jury demo (e.g. "today's bookings", "no-shows this week"). Read-only; nothing here changes data. | Phase 2 onward |

The migration runner, `database/migrate.py`, applies `migrations/` and records what has run in a `schema_migrations` table.

Raw downloads and old exports are **not** stored here. They go in `data/` at the repository root, which is git-ignored.
