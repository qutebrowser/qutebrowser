#!/usr/bin/env python3

# Copyright 2017 Chris Braun (cryzed) <cryzed@googlemail.com>
# Adapted for Bitwarden by Jonathan Haylett (JonnyHaystack) <jonathan@haylett.dev>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""
Insert login information using Bitwarden CLI and a dmenu-compatible application
(e.g. dmenu, rofi -dmenu, ...).
"""

USAGE = """The domain of the site has to be in the name of the Bitwarden entry, for example: "github.com/cryzed" or
"websites/github.com".  The login information is inserted by emulating key events using qutebrowser's fake-key command in this manner:
[USERNAME]<Tab>[PASSWORD], which is compatible with almost all login forms.

If enabled, with the `--totp` flag, it will also move the TOTP code to the
clipboard, much like the Firefox add-on.

You must log into Bitwarden CLI using `bw login` prior to use of this script.
The session key will be stored using keyctl for the number of seconds passed to
the --auto-lock option.

To use in qutebrowser, run: `spawn --userscript qute-bitwarden`
"""

EPILOG = """Dependencies: tldextract (Python 3 module), pyperclip (optional
Python module, used for TOTP codes), Bitwarden CLI (1.7.4 is known to work
but older versions may well also work)

WARNING: The login details are viewable as plaintext in qutebrowser's debug log
(qute://log) and might be shared if you decide to submit a crash report!"""

import argparse
import enum
import functools
import os
import shlex
import subprocess
import sys
import json
import tldextract

argument_parser = argparse.ArgumentParser(
    description=__doc__,
    usage=USAGE,
    epilog=EPILOG,
)
argument_parser.add_argument('url', nargs='?', default=os.getenv('QUTE_URL'))
argument_parser.add_argument('--dmenu-invocation', '-d', default='rofi -dmenu -i -p Bitwarden',
                             help='Invocation used to execute a dmenu-provider')
argument_parser.add_argument('--password-prompt-invocation', '-p', default='rofi -dmenu -p "Master Password" -password -lines 0',
                             help='Invocation used to prompt the user for their Bitwarden password')
argument_parser.add_argument('--no-insert-mode', '-n', dest='insert_mode', action='store_false',
                             help="Don't automatically enter insert mode")
argument_parser.add_argument('--totp', '-t', action='store_true',
                             help="Copy TOTP key to clipboard")
argument_parser.add_argument('--io-encoding', '-i', default='UTF-8',
                             help='Encoding used to communicate with subprocesses')
argument_parser.add_argument('--merge-candidates', '-m', action='store_true',
                             help='Merge pass candidates for fully-qualified and registered domain name')
argument_parser.add_argument('--auto-lock', type=int, default=900,
                             help='Automatically lock the vault after this many seconds')
group = argument_parser.add_mutually_exclusive_group()
group.add_argument('--username-only', '-e',
                   action='store_true', help='Only insert username')
group.add_argument('--password-only', '-w',
                   action='store_true', help='Only insert password')
group.add_argument('--totp-only', '-T',
                   action='store_true', help='Only insert totp code')

stderr = functools.partial(print, file=sys.stderr)


class ExitCodes(enum.IntEnum):
    SUCCESS = 0
    FAILURE = 1
    # 1 is automatically used if Python throws an exception
    NO_PASS_CANDIDATES = 2
    COULD_NOT_MATCH_USERNAME = 3
    COULD_NOT_MATCH_PASSWORD = 4


def qute_command(command):
    with open(os.environ['QUTE_FIFO'], 'w') as fifo:
        fifo.write(command + '\n')
        fifo.flush()


def ask_password(password_prompt_invocation):
    process = subprocess.run(
        shlex.split(password_prompt_invocation),
        text=True,
        stdout=subprocess.PIPE,
    )
    if process.returncode > 0:
        raise Exception('Could not unlock vault')
    master_pass = process.stdout.strip()
    return subprocess.check_output(
        ['bw', 'unlock', '--raw', master_pass],
        text=True,
    ).strip()


def get_session_key(auto_lock, password_prompt_invocation):
    if auto_lock == 0:
        subprocess.call(['keyctl', 'purge', 'user', 'bw_session'])
        return ask_password(password_prompt_invocation)
    else:
        process = subprocess.run(
            ['keyctl', 'request', 'user', 'bw_session'],
            text=True,
            stdout=subprocess.PIPE,
        )
        key_id = process.stdout.strip()
        if process.returncode > 0:
            session = ask_password(password_prompt_invocation)
            if not session:
                raise Exception('Could not unlock vault')
            key_id = subprocess.check_output(
                ['keyctl', 'add', 'user', 'bw_session', session, '@u'],
                text=True,
            ).strip()

        if auto_lock > 0:
            subprocess.call(['keyctl', 'timeout', str(key_id), str(auto_lock)])
        return subprocess.check_output(
            ['keyctl', 'pipe', str(key_id)],
            text=True,
        ).strip()


def pass_(domain, encoding, auto_lock, password_prompt_invocation):
    session_key = get_session_key(auto_lock, password_prompt_invocation)
    process = subprocess.run(
        ['bw', 'list', 'items', '--session', session_key, '--url', domain],
        capture_output=True,
    )

    err = process.stderr.decode(encoding).strip()
    if err:
        msg = 'Bitwarden CLI returned for {:s} - {:s}'.format(domain, err)
        stderr(msg)

    if process.returncode:
        return '[]'

    out = process.stdout.decode(encoding).strip()

    return out


def get_totp_code(selection_id, domain_name, encoding, auto_lock, password_prompt_invocation):
    session_key = get_session_key(auto_lock, password_prompt_invocation)
    process = subprocess.run(
        ['bw', 'get', 'totp', '--session', session_key, selection_id],
        capture_output=True,
    )

    err = process.stderr.decode(encoding).strip()
    if err:
        # domain_name instead of selection_id to make it more user-friendly
        msg = 'Bitwarden CLI returned for {:s} - {:s}'.format(domain_name, err)
        stderr(msg)

    if process.returncode:
        return '[]'

    out = process.stdout.decode(encoding).strip()

    return out


def dmenu(items, invocation, encoding):
    command = shlex.split(invocation)
    process = subprocess.run(command, input='\n'.join(
        items).encode(encoding), stdout=subprocess.PIPE)
    return process.stdout.decode(encoding).strip()


def fake_key_raw(text):
    for character in text:
        # Escape all characters by default, space requires special handling
        sequence = '" "' if character == ' ' else r'\{}'.format(character)
        qute_command('fake-key {}'.format(sequence))


def main(arguments):
    if not arguments.url:
        argument_parser.print_help()
        return ExitCodes.FAILURE

    extract_result = tldextract.extract(arguments.url)

    # Try to find candidates using targets in the following order: fully-qualified domain name (includes subdomains),
    # the registered domain name and finally: the IPv4 address if that's what
    # the URL represents
    candidates = []
    for target in filter(None, [
                extract_result.fqdn,
                extract_result.registered_domain,
                extract_result.subdomain + '.' + extract_result.domain,
                extract_result.domain,
                extract_result.ipv4]):
        target_candidates = json.loads(
            pass_(
                target,
                arguments.io_encoding,
                arguments.auto_lock,
                arguments.password_prompt_invocation,
            )
        )
        if not target_candidates:
            continue

        candidates = candidates + target_candidates
        if not arguments.merge_candidates:
            break
    else:
        if not candidates:
            stderr('No pass candidates for URL {!r} found!'.format(
                arguments.url))
            return ExitCodes.NO_PASS_CANDIDATES

    if len(candidates) == 1:
        selection = candidates.pop()
    else:
        choices = ['{:s} | {:s}'.format(c['name'], c['login']['username']) for c in candidates]
        choice = dmenu(choices, arguments.dmenu_invocation, arguments.io_encoding)
        choice_tokens = choice.split('|')
        choice_name = choice_tokens[0].strip()
        choice_username = choice_tokens[1].strip()
        selection = next((c for (i, c) in enumerate(candidates)
                          if c['name'] == choice_name
                          and c['login']['username'] == choice_username),
                         None)

    # Nothing was selected, simply return
    if not selection:
        return ExitCodes.SUCCESS

    username = selection['login']['username']
    password = selection['login']['password']
    totp = selection['login']['totp']

    if arguments.username_only:
        fake_key_raw(username)
    elif arguments.password_only:
        fake_key_raw(password)
    elif arguments.totp_only:
        # No point in moving it to the clipboard in this case
        fake_key_raw(
            get_totp_code(
                selection['id'],
                selection['name'],
                arguments.io_encoding,
                arguments.auto_lock,
                arguments.password_prompt_invocation,
            )
        )
    else:
        # Enter username and password using fake-key and <Tab> (which seems to work almost universally), then switch
        # back into insert-mode, so the form can be directly submitted by
        # hitting enter afterwards
        fake_key_raw(username)
        qute_command('fake-key <Tab>')
        fake_key_raw(password)

    if arguments.insert_mode:
        qute_command('mode-enter insert')

    # If it finds a TOTP code, it copies it to the clipboard,
    # which is the same behavior as the Firefox add-on.
    if not arguments.totp_only and totp and arguments.totp:
        # The import is done here, to make pyperclip an optional dependency
        import pyperclip
        pyperclip.copy(
            get_totp_code(
                selection['id'],
                selection['name'],
                arguments.io_encoding,
                arguments.auto_lock,
                arguments.password_prompt_invocation,
            )
        )

    return ExitCodes.SUCCESS


if __name__ == '__main__':
    arguments = argument_parser.parse_args()
    sys.exit(main(arguments))
