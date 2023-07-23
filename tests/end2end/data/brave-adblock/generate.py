#!/usr/bin/env python

# SPDX-FileCopyrightText: Árni Dagur <arni@dagur.eu>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import io
import gzip
import csv
import pathlib
import itertools
import urllib.request
import tempfile
from typing import Optional

URL = "https://raw.githubusercontent.com/brave/adblock-rust/master/data/ublock-matches.tsv"
CACHE_PATH = pathlib.Path(tempfile.gettempdir(), "ublock-matches-cache.tsv")
ROWS_TO_USE = 30_000


def type_rename(type_str: str) -> Optional[str]:
    """Use the same resource type names as QtWebEngine."""
    if type_str == "other":
        return "unknown"
    if type_str == "xmlhttprequest":
        return "xhr"
    if type_str == "font":
        return "font_resource"
    if type_str in ["image", "stylesheet", "media", "script", "sub_frame"]:
        return type_str
    return None


def main():
    # Download file or use cached version
    if CACHE_PATH.is_file():
        print(f"Using cached file {CACHE_PATH}")
        data = io.StringIO(CACHE_PATH.read_text(encoding="utf-8"))
    else:
        request = urllib.request.Request(URL)
        print(f"Downloading {URL} ...")
        with urllib.request.urlopen(request) as response:
            assert response.status == 200
            data_str = response.read().decode("utf-8")
        print(f"Saving to cache file {CACHE_PATH} ...")
        CACHE_PATH.write_text(data_str, encoding="utf-8")
        data = io.StringIO(data_str)

    # We only want the first three columns and the first ROWS_TO_USE rows
    print("Reading rows into memory...")
    reader = csv.DictReader(data, delimiter="\t")
    rows = list(itertools.islice(reader, ROWS_TO_USE))

    print("Writing filtered file to memory...")
    uncompressed_f = io.StringIO()
    writer = csv.DictWriter(
        uncompressed_f, ["url", "source_url", "type"], delimiter="\t"
    )
    writer.writeheader()
    for row in rows:
        type_renamed = type_rename(row["type"])
        if type_renamed is None:
            # Ignore request types we don't recognize
            continue
        writer.writerow(
            {
                "url": row["url"],
                "source_url": row["sourceUrl"],
                "type": type_renamed,
            }
        )
    uncompressed_f.seek(0)

    print("Compressing filtered file and saving to disk...")
    # Compress the data before storing on the filesystem
    with gzip.open("ublock-matches.tsv.gz", "wb", compresslevel=9) as gzip_f:
        gzip_f.write(uncompressed_f.read().encode("utf-8"))


if __name__ == "__main__":
    main()
