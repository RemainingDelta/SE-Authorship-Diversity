# Limitations

## Main-track rule (ICSE)

We count only main research-track papers. A paper counts as main track when its DBLP `crossref`, meaning the proceedings volume it belongs to, is exactly `conf/{venue}/{year}`. Satellite volumes have something after the year: `c` (companion), `w` (workshops), `seip`, `nier`, `seet`, or a workshop acronym like `ast` or `chase`. Those are excluded. The rule is `MAIN_TRACK_CROSSREF` in `src/shared/config.py`.

How well this works depends on how ICSE's proceedings were published each year:

| ICSE year | Main-track count | Notes |
|---|---|---|
| 2007–2009 | 89, 103, 70 | Separate companion volume, excluded |
| 2010 | 65 | Split into two volumes; only volume 1 (research track) is counted. Volume 2 (151 papers, mostly companion material) is excluded |
| **2011–2013** | **214, 239, 242** | **Every track in a single volume, so these years can't be separated by crossref and include short papers, industry, education and demo papers** |
| 2014 | 99 | Separate companion volume, excluded |
| 2015 | 86 | Split into two volumes; only volume 1 counted. Volume 2 (215 papers) excluded |
| 2016–2025 | 101, 68, 153, 109, 129, 138, 199, 211, 237, 245 | Companion and track volumes (`c`, `seip`, `nier`, `seet`, ...) separate and excluded |

**ICSE 2011–2013 are inflated.** Their counts are 2–3 times the research-track size of the years around them, because the extra tracks are mixed in. Any ICSE trend that includes these years compares a broader mix of papers there against research-track-only papers in other years. Treat them with caution, or leave them out of ICSE trend lines.

**Low counts in 2014, 2016 and 2017 are not a data problem.** Those are the actual research-track sizes. Earlier analyses read them as dips, but the higher numbers around them were the ones inflated by companion material.

The geo repo's published ICSE counts match ours for 2016–2025. For 2010 and 2015 they're higher, because it scraped both volumes.
