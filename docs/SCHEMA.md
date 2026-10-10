# Data schema

Silver is the one table both pipelines share: **one row per authorship**, meaning one row per (paper, DBLP author position). Each row carries the gender fields and the geo fields together, so gender × region questions need no extra join. Gold tables are built from silver, and each one states the unit it counts.

Silver is stored as a JSON array of row objects. The worked example is `tests/fixtures/silver_rows.json`, and `tests/test_fixtures.py` checks it against this document.

## Which papers get rows

- Only main-track `inproceedings` records, using the crossref rule in `MAIN_TRACK_CROSSREF` (see `docs/LIMITATIONS.md`). Companion, workshop and `proceedings` records get no rows.
- Author names and their order come from **DBLP**, not OpenAlex. The Genderize cache is keyed on DBLP names, and OpenAlex names only match DBLP exactly about 73% of the time.
- A main-track paper **with no DOI keeps its rows**, so its authors still count for gender. It can't be looked up in OpenAlex, so it has `affiliations: []`, region `unknown` and `primary_topic: null`.

## Silver fields

| Field | Type | Null? | Source | Rule |
|---|---|---|---|---|
| `doi` | string | yes | DBLP `ee` | DOI as DBLP gives it. `null` when DBLP has no doi.org link |
| `title` | string | no | DBLP | As DBLP gives it, trailing period included |
| `venue` | string | no | DBLP crossref | One of `VENUES`: `ICSE`, `ECSA`, `ICSA`. WICSA papers are stored as `ICSA` (`ICSA_LINEAGE`) |
| `year` | int | no | DBLP | In `YEARS` (2007–2025) |
| `author_name` | string | no | DBLP | DBLP name after `clean_name()` (`&apos;` → `'`, strip ` 0001`-style suffixes). This is the Genderize cache key |
| `author_position` | int | no | DBLP | 0-based index in DBLP's author list. `0` is the first author |
| `joint_wicsa_ecsa` | bool | no | DBLP crossref | `true` for the joint WICSA/ECSA years, `conf/wicsa/2009` and `conf/wicsa/2012`. Those papers have venue `ICSA`. Each chart decides whether to drop them |
| `affiliations` | list of `{institution, country_code}` | no (may be `[]`) | OpenAlex `authorships[].institutions[]` | Every institution, in OpenAlex order. `institution` is `display_name` (string). `country_code` is ISO 3166-1 alpha-2, or `null` |
| `primary_affiliation` | string | yes | derived | `affiliations[0].institution`, or `null` when there are no affiliations |
| `country_code` | string | yes | derived | `affiliations[0].country_code`, or `null` |
| `region` | string | no | derived | `REGION_MAP[country_code]`. A code missing from the map → `Other`. No country code → `unknown` |
| `gender_label` | string | no | Genderize cache | See [Gender](#gender) |
| `gender_confidence` | float 0–1 | yes | Genderize cache | Genderize `probability`. `null` when the name isn't in the cache |
| `position_mismatch` | bool | no | DBLP + OpenAlex | See [Matching DBLP to OpenAlex](#matching-dblp-to-openalex) |
| `primary_topic` | string | yes | OpenAlex `primary_topic.display_name` | `null` when there's no DOI, no OpenAlex work, or no topic |

`doi`, `title`, `venue`, `year`, `joint_wicsa_ecsa` and `primary_topic` are paper-level fields, so they're the same on every row of a paper. Group by `doi`, or by `title` for papers with no DOI.

## Allowed values

**`gender_label`:** exactly four labels.

| Label | When |
|---|---|
| `female-presenting` | Genderize says `female` with probability ≥ 0.70 |
| `male-presenting` | Genderize says `male` with probability ≥ 0.70 |
| `unclassified` | A gender came back, but below 0.70, or something other than female/male |
| `unknown` | Genderize returned `gender: null`, or the name isn't in the cache |

**`region`:** the eight values in `config.REGIONS`, plus `unknown`:
`North America`, `W. Europe`, `E. Europe`, `Asia-Pacific`, `Latin America`, `Middle East`, `Africa`, `Other`, `unknown`.

- `Other` means the author **has** a country code that `REGION_MAP` doesn't cover.
- `unknown` means **no** country code: no institution, no OpenAlex match, or no DOI.
- geo_data put both of these under "Other". Keeping them apart stops authors with no country from showing up as a region.
- Never store the merged `Middle East & Africa` label in silver or gold. It's for chart display only (`REGION_ROLLUPS`).

**`venue`:** `ICSE`, `ECSA`, `ICSA`.

## Gender

- The rule is the gender repo's `classify_gender()` from `src/gold/synthesize_gold.py`. The labels and the 0.70 threshold carry over unchanged.
- The difference: the gender repo computed the label at gold, but here it's stored in silver, next to the raw probability, so gold tables don't each recompute it.
- Genderize's `count` isn't kept in silver. It's still in the bronze cache if anyone needs it.

## Matching DBLP to OpenAlex

The join key is DOI, then author.

1. Each DBLP author is matched by name to an authorship in the OpenAlex work. The exact name-normalisation rule belongs to the ingest ticket. It needs to cope with accents, `0001`-style suffixes and swapped given/family names (OpenAlex has e.g. `Nomura Jun` for DBLP's `Jun Nomura`).
2. `affiliations` come from the **matched** authorship, not from whichever authorship sits at the same index.
3. `position_mismatch` is:
   - `false` when the matched authorship's index equals `author_position`;
   - `true` when it's at a different index (the OpenAlex order differs from DBLP);
   - `true` when no authorship matches. Then `affiliations` is `[]` and region is `unknown`;
   - `false` when there's no OpenAlex work at all (no DOI, or the DOI wasn't found). There's nothing to mismatch against.

Use `position_mismatch` to measure how often the two sources disagree, and to filter rows if a chart needs strict matching.

## Gold files (outline)

Gold files are what the dashboard reads. Each one names its unit, so gender shares and region shares are never compared across different units. The exact file layout is left to the gender, geo and dashboard tickets. What's fixed here is the unit.

| File | Unit | What it counts |
|---|---|---|
| `gender_by_year.json` | **authors** (author slots: one per silver row, so someone with three papers counts three times) | Per venue × year: count of each `gender_label`, plus the same breakdown for first authors (`author_position == 0`) |
| `region_by_year.json` | **papers** | Per venue × year: number of papers with at least one author in each region (geo_data's method). A paper counts once in every region it touches, so shares add up to more than 100%. The denominator is all papers. Papers whose authors are all `unknown` are reported as their own count |
| `gender_by_region.json` | **authors** (author slots) | Region (from `country_code`, i.e. primary affiliation) × `gender_label`, per venue × year |
| `topic_stats.json` | **authors** (author slots) | `primary_topic` × `gender_label`, per venue |

Notes for whoever builds these:

- `joint_wicsa_ecsa` rows are left out of per-venue trend lines by default, and counted once in combined totals.
- ICSE 2011–2013 cover every track (see `docs/LIMITATIONS.md`). Gold keeps them, and charts flag them.
- Per-region author counts use the primary affiliation. Per-region paper counts use **all** affiliations of every author.

## Fixtures

All in `tests/fixtures/`, shared by every ticket:

| File | What it holds |
|---|---|
| `dblp_records.json` | 10 records in the same shape as `data/bronze/dblp/icse_ecsa_icsa_filtered.json`: ICSE 2020 main track, ICSE 2020 companion (`2020c`), ICSE 2010 volume 1 (`2010-1`, kept) and volume 2 (`2010-2`, excluded), WICSA 2009 (joint with ECSA), ECSA 2013, ICSA 2017 main track with no DOI, ECSA 2021 companion with no DOI, the ICSE 2020 `proceedings` record, and an ICSA 2024 companion paper |
| `openalex_works/` | 4 OpenAlex works, one file per DOI (`/` replaced by `_`), trimmed to the fields silver uses: a normal paper (ICSE 2020), an author with two institutions (ICSE 2010, Romain Robbes), authors with no institution (ECSA 2013), and an author order that differs from DBLP (WICSA 2009) |
| `gender_lookup_sample.json` | 10 entries copied from the real Genderize cache (`{name: {gender, probability, count}}`). It includes a `gender: null` entry (Rijnard van Tonder) and two below 0.70 (Michele Lanza, Zhao Li). Qing Gu is left out on purpose, to cover a name that isn't in the cache |
| `silver_rows.json` | The expected silver output for the fixtures above, worked out by hand and ordered by `doi` then `author_position` (no-DOI paper last) |

All of it is real data except two hand edits:

- The ICSA 2017 paper (`conf/icsa/PatersonC17`) had its `doi` and `ee` removed. Every real record with no DOI is a companion paper, and the no-DOI rule needs a main-track one.
- The WICSA 2009 OpenAlex work has its two authorships swapped. A scan of about 300 real papers found no case where OpenAlex lists the same authors in a different order. Every difference was name spelling.

## Review

- [ ] Reviewed by someone working on gender
- [ ] Reviewed by someone working on geo
