"""Stream DBLP's bulk XML dump and keep records for our target venues and years.

Ported from the standalone filter_dblp.py. DBLP's search API and HTML pages
now sit behind an anti-bot challenge that blocks plain HTTP clients, but the
bulk dump still downloads with plain curl (see README for the two commands).

Main track vs. companion/workshop is NOT decided here. Every record under a
target venue prefix is kept along with its crossref, and the main-track rule
is applied in a later stage.

Usage:
    PYTHONPATH=src python -m ingest.dblp_dump [dump.xml.gz] [dblp.dtd] [out.json]
"""

import argparse
import gzip
import json
import re
import sys
import xml.sax
from xml.sax.handler import ContentHandler, EntityResolver

from shared.config import ICSA_LINEAGE, VENUES, YEAR_END, YEAR_START

# ICSE, ECSA, ICSA from VENUES, plus WICSA (ICSA's name before 2017).
TARGET_PREFIXES = tuple(sorted(f"conf/{v.lower()}/" for v in {*VENUES, *ICSA_LINEAGE}))

RECORD_TAGS = {"inproceedings", "proceedings"}
FIELD_TAGS = {"title", "author", "year", "ee", "crossref", "booktitle"}

# The dump has no <doi> element. DOIs only appear as doi.org links in <ee>.
DOI_URL = re.compile(r"^https?://(?:dx\.)?doi\.org/(.+)$")

DEFAULT_DUMP = "dblp.xml.gz"
DEFAULT_DTD = "dblp.dtd"
DEFAULT_OUT = "data/bronze/dblp/icse_ecsa_icsa_filtered.json"


class _LocalDtdResolver(EntityResolver):
    """Resolve every external reference to the local dblp.dtd.

    The DTD defines the named entities (accented characters) used throughout
    the dump. Always returning the local file, whatever SYSTEM path the XML
    declares, also means enabling external entities can't read anything else.
    """

    def __init__(self, dtd_path):
        self.dtd_path = str(dtd_path)

    def resolveEntity(self, publicId, systemId):
        return self.dtd_path


class _FilterHandler(ContentHandler):
    def __init__(self):
        super().__init__()
        self.records = []
        self.current = None
        self.field = None
        self.buf = []
        self.seen = 0

    def startElement(self, name, attrs):
        if name in RECORD_TAGS:
            self.current = {
                "record_type": name,
                "key": attrs.get("key", ""),
                "year": None,
                "title": None,
                "authors": [],
                "ees": [],
                "crossref": None,
                "booktitle": None,
            }
        elif self.current is not None and self.field is None and name in FIELD_TAGS:
            # Inline markup inside a field (<i>, <sub>, ...) doesn't start a new
            # field, so its text keeps accumulating into the enclosing one.
            self.field = name
            self.buf = []

    def characters(self, content):
        if self.field is not None:
            self.buf.append(content)

    def endElement(self, name):
        if self.current is None:
            return

        if name == self.field:
            self._set_field(name, "".join(self.buf).strip())
            self.field = None
        elif name in RECORD_TAGS:
            self._finish_record()

    def _set_field(self, name, text):
        rec = self.current
        if name == "author":
            rec["authors"].append(text)
        elif name == "ee":
            rec["ees"].append(text)
        elif name == "year":
            rec["year"] = int(text) if text.isdigit() else None
        else:
            rec[name] = text

    def _finish_record(self):
        rec = self.current
        self.current = None
        self.seen += 1
        if self.seen % 500_000 == 0:
            print(
                f"  scanned {self.seen:,} records, kept {len(self.records):,}",
                file=sys.stderr,
            )

        if not rec["key"].startswith(TARGET_PREFIXES):
            return
        if rec["year"] is None or not YEAR_START <= rec["year"] <= YEAR_END:
            return

        ees = rec.pop("ees")
        rec["ee"] = ees[0] if ees else None
        rec["doi"] = next(
            (m.group(1) for m in map(DOI_URL.match, ees) if m),
            None,
        )
        self.records.append(rec)


def filter_dump(xml_gz_path, dtd_path) -> list[dict]:
    """Stream the gzipped dump and return records for the target venues/years.

    Uses SAX so memory stays flat; the uncompressed dump is several GB.
    """
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, False)
    # Off by default in Python; without it every named entity is silently
    # dropped ("José" -> "Jos"), which breaks Genderize cache keys.
    parser.setFeature(xml.sax.handler.feature_external_ges, True)
    parser.setEntityResolver(_LocalDtdResolver(dtd_path))

    handler = _FilterHandler()
    parser.setContentHandler(handler)
    with gzip.open(xml_gz_path, "rb") as fh:
        parser.parse(fh)

    print(
        f"Scanned {handler.seen:,} records, kept {len(handler.records):,}",
        file=sys.stderr,
    )
    return handler.records


def write_records(records, out_path):
    """Write a JSON array with one record per line, so diffs stay readable."""
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("[\n")
        fh.write(",\n".join(json.dumps(r, ensure_ascii=False) for r in records))
        fh.write("\n]\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dump", nargs="?", default=DEFAULT_DUMP)
    ap.add_argument("dtd", nargs="?", default=DEFAULT_DTD)
    ap.add_argument("out", nargs="?", default=DEFAULT_OUT)
    args = ap.parse_args()

    records = filter_dump(args.dump, args.dtd)
    write_records(records, args.out)
    print(f"Wrote {len(records):,} records to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
