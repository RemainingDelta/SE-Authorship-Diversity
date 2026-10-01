"""Single source of truth for project-wide constants.

Every ingest / gender / geo module should import venues, years, and the
region taxonomy from here instead of redefining them locally (both source
repos hard-coded these per script, which is how they drifted apart).
"""

# ── Venues ────────────────────────────────────────────────────────────────────

VENUES = ["ICSE", "ECSA", "ICSA"]
STRETCH_VENUES = ["MSR"]

YEAR_START = 2007
YEAR_END = 2025  # inclusive
YEARS = range(YEAR_START, YEAR_END + 1)

# ICSA has been published under different DBLP keys over time. How the two
# source repos handled this:
#
#   gender repo (se-author-gender-diversity, src/bronze/fetch_bronze_dblp.py)
#     - Queried DBLP search with `venue:ECSA:` as a standalone venue, 2008-2023.
#     - Never collected WICSA or ICSA.
#     - Dropped the joint WICSA/ECSA years (2009, 2012) entirely; see
#       docs/LIMITATIONS.md in that repo.
#
#   geo repo (geo_data, src/ingest/fetch_icsa.py)
#     - Scraped DBLP TOC pages and treated ICSA as one series, oldest first:
#         ECSA  2010, 2013               (conf/ecsa, Springer DOIs 10.1007)
#         WICSA 2011, 2012, 2014-2016    (conf/wicsa, IEEE DOIs 10.1109)
#         ICSA  2017-2025                (conf/icsa, IEEE DOIs 10.1109)
#     - So ECSA was used to fill the gap years when no WICSA was held.
#
# Problem: now that ECSA is its own entry in VENUES, keeping geo's mapping
# would count ECSA 2010/2013 twice, once as ECSA and once as ICSA. Default
# below: ICSA = WICSA before 2017, ICSA from 2017 on, no ECSA substitution.
# Gap years then just have no ICSA data.
# TODO(venue-ticket): check this against DBLP, and decide how to attribute
# the joint WICSA/ECSA years 2009 and 2012 (ECSA, ICSA, both, or drop as the
# gender repo did).
ICSA_LINEAGE = {
    "WICSA": range(YEAR_START, 2017),
    "ICSA": range(2017, YEAR_END + 1),
}

# ── Regions ───────────────────────────────────────────────────────────────────

# Copied from geo_data/src/analysis/add_regions.py (ISO 3166-1 alpha-2 codes).
#
# Taxonomy choice: Middle East and Africa are SEPARATE regions.
#
# geo_data used three variants:
#   1. "Middle East" + "Africa" as separate regions. Used by add_regions.py
#      (the script that actually writes the region field), proportions.py,
#      README.md, and data_collection.md ("seven regions").
#   2. "Middle East & Africa" merged. Used by more_proportions.py and the
#      REGION_ORDER / REGION_COLORS in the timeseries, comparison, and
#      topic_diversity notebooks.
#   3. "Africa & Middle East" merged, with "Unknown" as the fallback. Only in
#      the older REGION_MAP in .ipynb_checkpoints/*_timeseries-checkpoint.ipynb.
#
# Why separate:
#   - The region field in the data on disk is built from variant 1, and the
#     documented methodology says seven regions.
#   - Variants 2 and 3 never match that data. For example, the
#     "Middle East & Africa" column in more_proportions.py can only ever be 0,
#     because no row has that label.
#   - You can always merge two regions into one later (see REGION_ROLLUPS),
#     but you can't split a merged region back into two.
#
# Unmapped codes fall back to UNMAPPED_REGION ("Other", as in add_regions.py,
# not the checkpoint's "Unknown"). In the current geo_data output, every row
# labelled "Other" has no country code at all. So "Other" really means "no
# affiliation country", not "a country missing from this map".
REGION_MAP = {
    # North America
    "US": "North America", "CA": "North America", "MX": "North America",
    "BM": "North America", "GL": "North America",
    # Western Europe
    "DE": "W. Europe", "FR": "W. Europe", "GB": "W. Europe",
    "NL": "W. Europe", "IT": "W. Europe", "ES": "W. Europe",
    "SE": "W. Europe", "CH": "W. Europe", "AT": "W. Europe",
    "BE": "W. Europe", "FI": "W. Europe", "DK": "W. Europe",
    "NO": "W. Europe", "PT": "W. Europe", "IE": "W. Europe",
    "LU": "W. Europe", "GR": "W. Europe", "IS": "W. Europe",
    "MT": "W. Europe",
    # Eastern Europe
    "CZ": "E. Europe", "PL": "E. Europe", "HU": "E. Europe",
    "RO": "E. Europe", "SK": "E. Europe", "HR": "E. Europe",
    "RS": "E. Europe", "SI": "E. Europe", "BG": "E. Europe",
    "RU": "E. Europe", "EE": "E. Europe", "MK": "E. Europe",
    # Asia-Pacific
    "CN": "Asia-Pacific", "JP": "Asia-Pacific", "AU": "Asia-Pacific",
    "KR": "Asia-Pacific", "SG": "Asia-Pacific", "HK": "Asia-Pacific",
    "TW": "Asia-Pacific", "IN": "Asia-Pacific", "NZ": "Asia-Pacific",
    "TH": "Asia-Pacific", "MY": "Asia-Pacific", "ID": "Asia-Pacific",
    "PK": "Asia-Pacific", "VN": "Asia-Pacific", "MO": "Asia-Pacific",
    # Latin America
    "BR": "Latin America", "AR": "Latin America", "CL": "Latin America",
    "CO": "Latin America", "UY": "Latin America", "PE": "Latin America",
    "BB": "Latin America", "EC": "Latin America",
    # Middle East
    "IL": "Middle East", "SA": "Middle East", "AE": "Middle East",
    "IR": "Middle East", "KW": "Middle East", "JO": "Middle East",
    "PS": "Middle East", "TR": "Middle East",
    # Africa
    "ZA": "Africa", "EG": "Africa", "TN": "Africa", "DZ": "Africa",
    "LY": "Africa", "MA": "Africa", "NA": "Africa",
}  # fmt: skip

UNMAPPED_REGION = "Other"

# Canonical display / column order (matches geo_data's proportions.py).
REGIONS = [
    "North America",
    "W. Europe",
    "E. Europe",
    "Asia-Pacific",
    "Latin America",
    "Middle East",
    "Africa",
    UNMAPPED_REGION,
]

# Optional coarser grouping for charts where small-n regions are too noisy.
# Apply this at presentation time only. Never store merged labels in silver/gold.
REGION_ROLLUPS = {
    "Middle East & Africa": ["Middle East", "Africa"],
}
