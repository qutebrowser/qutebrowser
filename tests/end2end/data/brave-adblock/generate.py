#!/usr/bin/env python
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020 Árni Dagur <arni@dagur.eu>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

import io
import os
import gzip
import csv
import itertools
import urllib.request
from typing import Optional

URL = "https://raw.githubusercontent.com/brave/adblock-rust/master/data/ublock-matches.tsv"
CACHE_LOCATION = "/tmp/ublock-matches.tsv.cache"
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


if __name__ == "__main__":
    # Download file or use cached version
    if os.path.isfile(CACHE_LOCATION):
        print(f"Using cached file {CACHE_LOCATION}")
        with open(CACHE_LOCATION, "r", encoding="utf-8") as cache_f:
            data = io.StringIO(cache_f.read())
    else:
        request = urllib.request.Request(URL)
        print(f"Downloading {URL} ...")
        response = urllib.request.urlopen(request)
        assert response.status == 200
        data_str = response.read().decode("utf-8")
        print(f"Saving to cache file {CACHE_LOCATION} ...")
        with open(CACHE_LOCATION, "w", encoding="utf-8") as cache_f:
            cache_f.write(data_str)
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
