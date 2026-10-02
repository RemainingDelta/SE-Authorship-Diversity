# SE-Authorship-Diversity

A combined analysis of **gender and geographic diversity** in software engineering conference authorship. For each paper we look at who the authors are: inferred gender (from first names) and country/region (from institutional affiliation). We study how both have changed over time at ICSE, ECSA, and ICSA (WICSA before 2017), from 2007 to 2025. MSR is a stretch venue.

This repo merges two earlier projects into one shared pipeline:

- [se-author-gender-diversity](https://github.com/RemainingDelta/se-author-gender-diversity): gender of authors, using a bronze/silver/gold pipeline and a React dashboard
- [geo_data](https://github.com/amyhoyt625/geo_data): geography of authors, using DBLP scraping, OpenAlex affiliations, and analysis notebooks

> **Status: baseline scaffold only.** This repo has the folder structure, shared config, and testing/CI setup, and nothing else yet. None of the pipeline code from either source repo has been moved over. See [TODO](#todo-not-yet-done).

## Structure

```
SE-Authorship-Diversity/
├── src/
│   ├── ingest/        # Shared code that pulls data from DBLP and OpenAlex (used by both gender and geo)
│   ├── gender/        # Gender-only steps: cleaning names, Genderize lookups, classification
│   ├── geo/           # Geo-only steps: affiliation → country → region, regional statistics
│   └── shared/
│       └── config.py  # Single source of truth: venues, year range, region taxonomy
├── data/
│   ├── bronze/        # Raw API responses, stored unchanged (DBLP, OpenAlex, Genderize)
│   ├── silver/        # Cleaned data joined into one row per author per paper
│   └── gold/          # Summary tables that the analysis and dashboard read
├── app/               # Dashboard (empty, see TODO)
├── tests/             # pytest suite; conftest.py puts src/ on sys.path
├── docs/              # Methodology, data dictionary, limitations
└── .github/workflows/ # CI: ruff lint/format on src/, pytest on tests/
```

**Rule:** do not hard-code venues, years, or region labels inside a module. Import them from `shared.config`. Both source repos defined these separately in each script, and that's how they ended up disagreeing.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
make install
cp .env.example .env   # add your GENDERIZE_API_KEY
make ci                # ruff lint + format check + pytest (same as GitHub Actions)
```

Other targets: `make lint`, `make fix` (auto-format), `make test`, `make clean`, `make help`.

### DBLP data (one-time, only needed to re-run ingestion)

The filtered DBLP records are committed at `data/bronze/dblp/icse_ecsa_icsa_filtered.json`, so most work doesn't need this. To regenerate them, download DBLP's bulk dump into the repo root (both files are gitignored). Don't use `curl -i`, because it writes HTTP headers into the file and corrupts it.

```bash
curl -L -o dblp.xml.gz https://dblp.org/xml/dblp.xml.gz   # ~1.1 GB
curl -L -o dblp.dtd https://dblp.org/xml/dblp.dtd
PYTHONPATH=src python -m ingest.dblp_dump                # writes data/bronze/dblp/icse_ecsa_icsa_filtered.json
```

DBLP's search API and HTML pages are behind an anti-bot check that blocks plain HTTP clients, but the bulk dump downloads fine with `curl`. DBLP rebuilds the dump regularly, so record counts can drift slightly between downloads.

## Shared config decisions

All of these live in `src/shared/config.py`, and the reasoning is written out in comments there.

- **Regions:** Middle East and Africa are kept as **separate** regions, giving seven regions plus `Other`. `geo_data` used three versions of this split. The data it actually produced, and its written methodology, both use separate regions. The merged label `Middle East & Africa` can be applied when making charts (`REGION_ROLLUPS`), but it should never be stored in silver/gold data.
- **ICSA lineage:** ICSA is WICSA before 2017 and ICSA from 2017 on. `geo_data` filled the years with no WICSA (2010, 2013) using ECSA. We don't do that here, because ECSA is now its own venue and those papers would be counted twice. This is still a provisional default (see TODO).

## TODO (not yet done)

Each item below is meant to become its own GitHub issue.

1. **Choose one DBLP collection method.** The gender repo uses the DBLP search API (`venue:X:`), and the geo repo scrapes DBLP table-of-contents pages for each year (and handles volume-split years like ICSE 2010/2015). Pick one, implement it in `src/ingest/`, and make it read `VENUES` / `YEARS` from config.
2. **Merge the OpenAlex code.** Both repos call OpenAlex: gender for topics, geo for affiliations and country codes. Build one shared fetcher in `src/ingest/` that gets topics, institutions, and country codes for each DOI in a single pass, and caches the results in `data/bronze/`.
3. **Settle how ICSA/WICSA/ECSA years are counted.** Check `ICSA_LINEAGE` against DBLP. Decide which venue the joint WICSA/ECSA years (2009, 2012) count toward. The gender repo dropped those years entirely.
4. **Move the gender pipeline over.** Port name cleaning, Genderize lookup with caching, and gender classification into `src/gender/`, and bring their existing tests with them.
   - **Genderize costs money, so reuse the existing cache.** Seed `data/bronze/genderize/gender_lookup.json` from the gender repo, which has 10,822 names already looked up. Only send names that aren't in the cache to the API.
   - The cache is keyed by the full DBLP name after `clean_name()`. Port `clean_name()` without any changes in behavior. If it changes, the keys stop matching and names that were already paid for get queried again.
   - Have the fetcher print how many names it would send to the API, and require confirmation before running a paid batch.
5. **Move the geo pipeline over.** Port the region assignment and the proportion/count scripts into `src/geo/`, using `REGION_MAP` from config. Rewrite the notebooks so they read gold data instead of keeping their own `REGION_ORDER` and color settings.
6. **Define the silver/gold data formats.** Agree on one author-paper record that holds both gender and region fields, and document it in `docs/`.
7. **Decide on the dashboard.** Options: extend the gender repo's React/Vite app, adapt the geo notebooks/maps, or build something new. Then fill in `app/` and add the frontend lint workflow back (`lint-frontend.yml` from the gender repo was left out for now because `app/` is empty).
8. **Combine the dependencies.** `requirements.txt` is copied from the gender repo and only has requests, python-dotenv, ruff, and pytest. Add only the geo packages that are actually used (probably pandas, plus geopandas/folium if the maps are kept). Also change `test.yml` to install from `requirements.txt`.
9. **Add MSR as a stretch venue.** Once the pipeline is stable, run it with `STRETCH_VENUES` included.
10. **Write the docs.** Combine the methodology and limitations notes from both repos into `docs/` (DATA, LIMITATIONS, RESULTS).
11. **Move the data over or regenerate it.** Decide whether to copy the existing bronze data from both repos or fetch it again for the new 2007–2025 range. The gender repo covers 2008–2023 and the geo repo covers 2010–2025. DBLP and OpenAlex are free to fetch again, but the Genderize cache must be copied over, not regenerated (see #4).

## Credits

This project builds on work by two teams:

- **Gender diversity**: [se-author-gender-diversity](https://github.com/RemainingDelta/se-author-gender-diversity). Contributors: Shiven Ajwaliya, Cheesepuff43, MaxoTaco, TimZeliff
- **Geographic diversity**: [geo_data](https://github.com/amyhoyt625/geo_data). Contributors: Amy Hoyt, Rona Liu-Zhong, Tina Jiang, mnz15
