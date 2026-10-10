# ChargeSpot: Station Data

Where ChargeSpot's charging-station data comes from, how it is cleaned, and which parts are real or generated. Code: `database/imports/` and `database/seeds/`. Design: [architecture.md, section 13](architecture.md#13-station-data-strategy).

## Sources

| Source | What it gives us | Licence | Tag |
|---|---|---|---|
| **Team-verified stations** | 10 Ahmedabad stations checked by hand (old database, `data/legacy/`) | our own | `manual` |
| **Open Charge Map** | Most stations in Gujarat: location, operator, often plug type and power, sometimes price | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | `ocm` |
| **OpenStreetMap** | A few more stations; plug details where mappers added them | [ODbL](https://opendatacommons.org/licenses/odbl/) | `osm` |
| **Generated** | Plausible chargers, power, prices and ratings where real data is missing | — | `synthetic` / estimated |

Both open data sources must be credited wherever their data is shown. The app footer and README do this.

The region is a setting (`IMPORT_REGION`, default `gujarat`). Other states can be added later by adding them to `database/imports/regions.py`.

## Cleaning, step by step

1. **Inside the region?** Each point is tested against Gujarat's official boundary from OpenStreetMap, not a rectangle, so places just over the border (Udaipur, Silvassa) are left out.
2. **Location believable?** If a record's address names a *different state* (a "Bengaluru, Karnataka" charger pinned in Ahmedabad), its coordinates are wrong and it is skipped.
3. **Actually a bookable charger?** Battery-swap points (Honda e:swap, Battery Smart, Sun Mobility), bike stations (Yulu) and phone chargers are dropped.
4. **Car or scooter?** Stations of two-wheeler networks (Ather Grid, Ola, …) or with only scooter plugs ("Type M") are kept but tagged `TWO_WHEELER`. The app currently shows only `FOUR_WHEELER` stations; the tag makes a future two-wheeler section possible without re-importing.
5. **Operator names merged**: `tata`, `TATA`, `Tata power`, `Tata Power EZ Charge` → **Tata Power**, and the same for Jio-bp, ChargeZone, MobiLane and others. A station's own name can identify a known operator ("MobiLane AMC Kankariya" → MobiLane) but never becomes an operator itself.
6. **Plug names standardised**: "CCS (Type 2)", `socket:type2_combo` → `CCS2`; "IEC 60309" → `BHARAT_AC001`; GB/T DC → `BHARAT_DC001`.
7. **Junk names replaced**: "Unknown Charging Station" becomes "<operator> – <area>".
8. **Prices read carefully**: free text like "21/kWh", "Rs 14", "21rs" is accepted only when it is a believable ₹/kWh (5–40). Anything else counts as unknown.
9. **Duplicates merged**: stations within ~50 m with similar names (or a generic name, or the same operator) are one place. The survivor is chosen by source: manual > ocm > osm. Every merge is listed in `data/raw/dedupe_report.csv` for a person to check.

## What "synthetic" and "estimated" mean

Public Indian data rarely includes prices, and often leaves out power or plug details. Rather than leave stations unbookable, we fill the gaps from per-operator profiles of what each network typically installs (`database/seeds/profiles.py`):

| Situation | What we do | Shown as |
|---|---|---|
| A station has no charger details at all | Generate a typical set for its operator, e.g. Tata Power: CCS2 30–60 kW at ₹18–22/kWh | charger `data_source = synthetic` |
| A real charger has no power or price | Estimate it from the plug type and power band | `estimated_fields` lists the field |
| A station has no rating | Generate one | `estimated_fields` contains `rating` |
| The team recorded more chargers than they described (e.g. CESL Kankaria: 6 declared, 1 described) | Generate the missing ones | `synthetic` |

Generated values are **repeatable**: they are seeded by the station's ID, so re-running gives the same result. They **never overwrite real values**. The app shows an **"approximate data"** badge on anything synthetic or estimated, and never invents values on screen.

To see the current mix, run `database/queries/data_quality.sql`.

## Re-running imports

Every step is safe to repeat. Each outside record is remembered in `station_sources` (e.g. `ocm / 257048`), so a re-import updates the existing station instead of creating a copy. Records merged into another station keep pointing at the survivor. Chargers are matched by label (`CCS2-1`) and are never deleted, because bookings may refer to them.

Downloads are cached in `data/raw/` (git-ignored); `python -m database.pipeline --refresh` fetches fresh data.

## Snapshot (first import, October 2026)

| | Stations | Notes |
|---|---|---|
| Team-verified (`manual`) | 10 | all in Ahmedabad |
| Open Charge Map | 66 car + 2 scooter | 12 outside Gujarat and 3 with contradicting addresses skipped |
| OpenStreetMap | 6 | OpenStreetMap coverage of Gujarat is thin |
| Merged as duplicates | 1 | |
| Within 25 km of Ahmedabad | 42 car stations | where the demo bookings are |
