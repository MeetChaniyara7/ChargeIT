# database/

Everything about ChargeSpot's PostgreSQL database (hosted on Supabase). The design is in [docs/architecture.md](../docs/architecture.md), section 5; where the data comes from is in [docs/data.md](../docs/data.md); how to run it is in [docs/setup.md](../docs/setup.md), section 4.

| Path | What it is |
|---|---|
| `pipeline.py` | **Start here.** Builds or updates everything in order: `python -m database.pipeline` |
| `migrate.py` | Applies `migrations/` in order and records them in `schema_migrations` |
| `migrations/` | Numbered SQL files that define the schema. Each explains its rules in comments. **Never edit one that has been applied**; add a new numbered file instead. |
| `imports/` | Loading real stations (`import_osm.py`, `import_ocm.py`, `import_legacy_manual.py`), cleaning rules (`normalize.py`), duplicate removal (`dedupe.py`), the Gujarat boundary check (`regions.py`) and a one-off user copy (`migrate_users.py`) |
| `seeds/` | Generated data: per-operator charger profiles (`profiles.py`), gap filling (`synthetic.py`), demo accounts, bookings and kiosks (`demo_data.py`) |
| `queries/` | Read-only SQL to open in DBeaver: today's bookings, a booking's history, no-shows, data quality |
| `tests/` | Proof that the rules hold (no double booking, legal status changes only, row-level security) plus unit tests for cleaning and duplicates. They run against a throwaway local database. |

Run every command from the **repository root** with the backend's virtual environment active.

Raw downloads and old exports are **not** stored here. They go in `data/` at the repository root, which is git-ignored.
