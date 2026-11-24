#!/usr/bin/env python3
"""Build a static OPDS catalog (opds.xml) from a folder of EPUB files.

Usage:
    python3 build_opds.py BOOKS_DIR BASE_URL [OUTPUT_FILE]

Example:
    python3 build_opds.py books https://yourname.github.io/library/ opds.xml

BOOKS_DIR is the folder holding your .epub files. BASE_URL is the public
address of the folder that contains both opds.xml and the books/ folder.
The links in the catalog are written as BASE_URL + the path to each book.
Only the Python standard library is needed.
"""
import sys
import zipfile
import datetime
import posixpath
import urllib.parse
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS = {
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def read_metadata(epub_path):
    """Return (title, author, language, description) for an EPUB."""
    title = epub_path.stem.replace("_", " ").replace("-", " ")
    author, language, description = "Unknown", "", ""
    try:
        with zipfile.ZipFile(epub_path) as z:
            container = ET.fromstring(z.read("META-INF/container.xml"))
            rootfile = container.find(".//c:rootfile", NS).get("full-path")
            opf = ET.fromstring(z.read(rootfile))
            meta = opf.find("opf:metadata", NS)
            if meta is None:
                return title, author, language, description
            t = meta.find("dc:title", NS)
            if t is not None and (t.text or "").strip():
                title = " ".join(t.text.split())
            authors = [
                " ".join(a.text.split())
                for a in meta.findall("dc:creator", NS)
                if a.text and a.text.strip()
            ]
            if authors:
                author = ", ".join(authors)
            lang = meta.find("dc:language", NS)
            if lang is not None and lang.text:
                language = lang.text.strip()
            desc = meta.find("dc:description", NS)
            if desc is not None and desc.text:
                description = " ".join(desc.text.split())[:500]
    except Exception as exc:  # a damaged EPUB should not stop the build
        print(f"warning: could not read metadata from {epub_path.name}: {exc}")
    return title, author, language, description


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    books_dir = Path(sys.argv[1])
    base_url = sys.argv[2].rstrip("/") + "/"
    out_file = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("opds.xml")

    epubs = sorted(books_dir.rglob("*.epub"))
    if not epubs:
        print(f"No .epub files found in {books_dir}")
        sys.exit(1)

    # Path of each book relative to the folder that will hold opds.xml
    site_root = out_file.resolve().parent
    entries = []
    for p in epubs:
        title, author, language, description = read_metadata(p)
        rel = Path(p.resolve()).relative_to(site_root).as_posix()
        href = base_url + urllib.parse.quote(rel)
        entries.append((author.lower(), title.lower(), title, author,
                        language, description, href, p.stat().st_size))
    entries.sort()

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<feed xmlns="http://www.w3.org/2005/Atom" '
               'xmlns:dc="http://purl.org/dc/terms/" '
               'xmlns:opds="http://opds-spec.org/2010/catalog">')
    out.append("  <id>urn:library:all</id>")
    out.append("  <title>Library</title>")
    out.append(f"  <updated>{now}</updated>")
    out.append("  <author><name>Library</name></author>")
    out.append(f'  <link rel="self" href="{escape(base_url + out_file.name)}" '
               'type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>')
    out.append(f'  <link rel="start" href="{escape(base_url + out_file.name)}" '
               'type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>')
    for _, _, title, author, language, description, href, size in entries:
        out.append("  <entry>")
        out.append(f"    <title>{escape(title)}</title>")
        out.append(f"    <id>{escape(href)}</id>")
        out.append(f"    <updated>{now}</updated>")
        out.append(f"    <author><name>{escape(author)}</name></author>")
        if language:
            out.append(f"    <dc:language>{escape(language)}</dc:language>")
        if description:
            out.append(f'    <summary type="text">{escape(description)}</summary>')
        out.append('    <link rel="http://opds-spec.org/acquisition" '
                   f'href="{escape(href)}" type="application/epub+zip" length="{size}"/>')
        out.append("  </entry>")
    out.append("</feed>")
    out_file.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {out_file} with {len(entries)} books.")


if __name__ == "__main__":
    main()
