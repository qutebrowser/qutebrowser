#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2014-2017 Josefson Souza <josefson.br@gmail.com>

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


"""Tool to import browser history from other browsers."""


import argparse
import sqlite3
import sys
import os


def parse():
    """Parse command line arguments."""
    description = ("This program is meant to extract browser history from your"
                   "previous browser and import them into qutebrowser.")
    epilog = ("Databases:\n\tQutebrowser: Is named 'history.sqlite' and can be"
              " found at your --basedir. In order to find where your basedir"
              " is you can run ':open qute:version' inside qutebrowser."
              "\n\tFirerox: Is named 'places.sqlite', and can be found at your"
              "system\"s profile folder. Check this link for where it is locat"
              "ed: http://kb.mozillazine.org/Profile_folder"
              "\n\tChrome: Is named 'History', and can be found at the respec"
              "tive User Data Directory. Check this link for where it is locat"
              "ed: https://chromium.googlesource.com/chromium/src/+/master/"
              "docs/user_data_dir.md\n\n"
              "Example: hist_importer.py -b firefox -s /Firefox/Profile/"
              "places.sqlite -d /qutebrowser/data/history.sqlite")
    parser = argparse.ArgumentParser(
        description=description, epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-b', '--browser', dest='browser', required=True,
                        type=str, help='Browsers: {firefox, chrome}')
    parser.add_argument('-s', '--source', dest='source', required=True,
                        type=str, help='Source: Full path to the sqlite data'
                        'base file from the source browser.')
    parser.add_argument('-d', '--dest', dest='dest', required=True, type=str,
                        help='Destination: The full path to the qutebrowser '
                        'sqlite database')
    return parser.parse_args()


def open_db(data_base):
    """Open connection with database."""
    if os.path.isfile(data_base):
        conn = sqlite3.connect(data_base)
        return conn
    else:
        raise sys.exit('\nDataBaseNotFound: There was some error trying to to'
                       ' connect with the [{}] database. Verify if the'
                       ' filepath is correct or is being used.'
                       .format(data_base))


def extract(source, query):
    """Extracts (datetime,url,title) from source database."""
    try:
        conn = open_db(source)
        cursor = conn.cursor()
        cursor.execute(query)
        history = cursor.fetchall()
        conn.close()
        return history
    except sqlite3.OperationalError as op_e:
        print('\nCould not perform queries into the source database: {}'
              '\nBrowser version is not supported as it have a different sql'
              ' schema.'.format(op_e))


def clean(history):
    """Clean up records from source database.
    Receives a list of records:(datetime,url,title). And clean all records
    in place, that has a NULL/None datetime attribute. Otherwise qutebrowser
    will throw errors. Also, will add a 4th attribute of '0' for the redirect
    field in history.sqlite in qutebrowser."""
    nulls = [record for record in history if record[0] is None]
    for null_datetime in nulls:
        history.remove(null_datetime)
    history = [list(record) for record in history]
    for record in history:
        record.append('0')
    return history


def insert_qb(history, dest):
    """Insert history into dest database
    Given a list of records in history and a dest db, insert all records in
    the dest db."""
    conn = open_db(dest)
    cursor = conn.cursor()
    cursor.executemany(
        'INSERT INTO History (url,title,atime,redirect) VALUES (?,?,?,?)',
        history
    )
    cursor.execute('DROP TABLE CompletionHistory')
    conn.commit()
    conn.close()


def main():
    """Main control flux of the script."""
    args = parse()
    browser = args.browser.lower()
    source, dest = args.source, args.dest
    query = {
        'firefox': 'select url,title,last_visit_date/1000000 as date '
                   'from moz_places',
        'chrome': 'select url,title,last_visit_time/10000000 as date '
                  'from urls',
    }
    if browser not in query:
        sys.exit('Sorry, the selected browser: "{}" is not supported.'.format(
            browser))
    else:
        history = extract(source, query[browser])
        history = clean(history)
        insert_qb(history, dest)


if __name__ == "__main__":
    main()
