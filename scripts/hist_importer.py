#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2017-2018 Josefson Souza <josefson.br@gmail.com>

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


class Error(Exception):

    """Exception for errors in this module."""


def parse():
    """Parse command line arguments."""
    description = ("This program is meant to extract browser history from your"
                   " previous browser and import them into qutebrowser.")
    epilog = ("Databases:\n\n\tqutebrowser: Is named 'history.sqlite' and can "
              "be found at your --basedir. In order to find where your "
              "basedir is you can run ':open qute:version' inside qutebrowser."
              "\n\n\tFirefox: Is named 'places.sqlite', and can be found at "
              "your system's profile folder. Check this link for where it is "
              "located: http://kb.mozillazine.org/Profile_folder"
              "\n\n\tChrome: Is named 'History', and can be found at the "
              "respective User Data Directory. Check this link for where it is"
              "located: https://chromium.googlesource.com/chromium/src/+/"
              "master/docs/user_data_dir.md\n\n"
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
                        help='\nDestination: Full path to the qutebrowser '
                        'sqlite database')
    return parser.parse_args()


def open_db(data_base):
    """Open connection with database."""
    if os.path.isfile(data_base):
        return sqlite3.connect(data_base)
    raise Error('The file {} does not exist.'.format(data_base))


def extract(source, query):
    """Get records from source database.

    Args:
        source: File path to the source database where we want to extract the
        data from.
        query: The query string to be executed in order to retrieve relevant
        attributes as (datetime, url, time) from the source database according
        to the browser chosen.
    """
    try:
        conn = open_db(source)
        cursor = conn.cursor()
        cursor.execute(query)
        history = cursor.fetchall()
        conn.close()
        return history
    except sqlite3.OperationalError as op_e:
        raise Error('Could not perform queries on the source database: '
                    '{}'.format(op_e))


def clean(history):
    """Clean up records from source database.

    Receives a list of record and sanityze them in order for them to be
    properly imported to qutebrowser. Sanitation requires adding a 4th
    attribute 'redirect' which is filled with '0's, and also purging all
    records that have a NULL/None datetime attribute.

    Args:
        history: List of records (datetime, url, title) from source database.
    """
    # replace missing titles with an empty string
    for index, record in enumerate(history):
        if record[1] is None:
            cleaned = list(record)
            cleaned[1] = ''
            history[index] = tuple(cleaned)

    nulls = [record for record in history if None in record]
    for null_record in nulls:
        history.remove(null_record)
    history = [list(record) for record in history]
    for record in history:
        record.append('0')
    return history


def insert_qb(history, dest):
    """Insert history into dest database.

    Args:
        history: List of records.
        dest: File path to the destination database, where history will be
        inserted.
    """
    conn = open_db(dest)
    cursor = conn.cursor()
    cursor.executemany(
        'INSERT INTO History (url,title,atime,redirect) VALUES (?,?,?,?)',
        history
    )
    cursor.execute('DROP TABLE CompletionHistory')
    conn.commit()
    conn.close()


def run():
    """Main control flux of the script."""
    args = parse()
    browser = args.browser.lower()
    source, dest = args.source, args.dest
    query = {
        'firefox': 'select url,title,last_visit_date/1000000 as date '
                   'from moz_places where url like "http%" or url '
                   'like "ftp%" or url like "file://%"',
        'chrome': 'select url,title,last_visit_time/10000000 as date '
                  'from urls',
    }
    if browser not in query:
        raise Error('Sorry, the selected browser: "{}" is not '
                    'supported.'.format(browser))

    history = extract(source, query[browser])
    history = clean(history)
    insert_qb(history, dest)


def main():
    try:
        run()
    except Error as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
