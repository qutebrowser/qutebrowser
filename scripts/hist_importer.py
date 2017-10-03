#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# This file is part of qutebrowser.

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


'''Tool to import browser history data from other browsers. Although, safari
support is still on the way.'''


import argparse
import sqlite3
import sys


def parser():
    """Parse command line arguments."""
    description = 'This program is meant to extract browser history from your'\
                  'previous browser and import them into qutebrowser.'
    epilog = 'Databases:\n\tQute: Is named "history.sqlite" and can be found '\
             'at your --basedir. In order to find where your basedir is you '\
             'can run ":open qute:version" inside qutebrowser.'\
             '\n\tFirerox: Is named "places.sqlite", and can be found at your'\
             'system\'s profile folder. Check this link for where it is locat'\
             'ed: http://kb.mozillazine.org/Profile_folder'\
             '\n\tChrome: Is named "History", and can be found at the respec'\
             'tive User Data Directory. Check this link for where it is locat'\
             'ed: https://chromium.googlesource.com/chromium/src/+/master/'\
             'docs/user_data_dir.md\n\n'\
             'Example: $this_script.py -b firefox -s /Firefox/Profile/places.'\
             'sqlite -d /qutebrowser/data/history.sqlite'
    parsed = argparse.ArgumentParser(
        description=description, epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parsed.add_argument('-b', '--browser', dest='browser', required=True,
                        type=str, help='Browsers: {firefox, chrome, safari}')
    parsed.add_argument('-s', '--source', dest='source', required=True,
                        type=str, help='Source: fullpath to the sqlite data'
                        'base file from the source browser.')
    parsed.add_argument('-d', '--dest', dest='dest', required=True, type=str,
                        help='Destination: The fullpath to the qutebrowser '
                        'sqlite database')
    return parsed.parse_args()


def open_db(data_base):
    """Open connection with database."""
    try:
        conn = sqlite3.connect(data_base)
        return conn
    except Exception as any_e:
        print('Error: {}'.format(any_e))
        raise('Error: There was some error trying to to connect with the [{}]'
              'database. Verify if the filepath is correct or is being used.'.
              format(data_base))


def extract(source, query):
    """Performs extraction of (datetime,url,title) from source."""
    try:
        conn = open_db(source)
        cursor = conn.cursor()
        cursor.execute(query)
        history = cursor.fetchall()
        conn.close()
        return history
    except Exception as any_e:
        print('Error: {}'.format(any_e))
        print(type(source))
        raise('Error: There was some error trying to to connect with the [{}]'
              'database. Verify if the filepath is correct or is being used.'.
              format(str(source)))


def clean(history):
    """Receives a list of records:(datetime,url,title). And clean all records
    in place, that has a NULL/None datetime attribute. Otherwise Qutebrowser
    will throw errors."""
    nulls = [record for record in history if record[0] is None]
    for null_datetime in nulls:
        history.remove(null_datetime)
    return history


def insert_qb(history, dest):
    """Given a list of records in history and a dest db, insert all records in
    the dest db."""
    conn = open_db(dest)
    cursor = conn.cursor()
    cursor.executemany(
        'INSERT INTO History (url,title,atime) VALUES (?,?,?)', history
    )
    cursor.executemany(
        'INSERT INTO CompletionHistory (url,title,last_atime) VALUES (?,?,?)',
        history
    )
    conn.commit()
    conn.close()


def main():
    """Main control flux of the script."""
    args = parser()
    browser = args.browser.lower()
    source, dest = args.source, args.dest
    query = {
        'firefox': 'select url,title,last_visit_date/1000000 as date '
                   'from moz_places',
        'chrome': 'select url,title,last_visit_time/10000000 as date '
                  'from urls',
        'safari': None
    }
    if browser not in query:
        sys.exit('Sorry, the selected browser: "{}" is not supported.'.format(
            browser))
    else:
        if browser == 'safari':
            print('Sorry, currently we do not support this browser.')
            sys.exit(1)
        history = extract(source, query[browser])
        history = clean(history)
        insert_qb(history, dest)


if __name__ == "__main__":
    main()
