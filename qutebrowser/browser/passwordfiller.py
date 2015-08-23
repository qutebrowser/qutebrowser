# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Antoni Boucher (antoyo) <bouanto@zoho.com>
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

"""Form filler."""

import os
import shlex
import subprocess

from yaml import dump, load

from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.config import config
from qutebrowser.utils import message, objreg, standarddir, usertypes


class PasswordManager:

    """Base abstract class for password storage."""

    def get_usernames(self, urlstring):
        raise NotImplementedError

    def load(self, urlstring, username):
        raise NotImplementedError

    def save(self, urlstring, password_data):
        raise NotImplementedError


class YamlPasswordManager(PasswordManager):

    """YAML password storage."""

    def __init__(self):
        self._filename = os.path.join(standarddir.config(), "passwords.yaml")

    def get_usernames(self, urlstring):
        with open(self._filename, "r", encoding="utf-8") as password_file:
            data = load(password_file)
            if data is None:
                data = {}
        password_data = data[urlstring]
        return list(password_data.keys())

    def load(self, urlstring, username):
        with open(self._filename, "r", encoding="utf-8") as password_file:
            data = load(password_file)
            if data is None:
                data = {}
        password_data = data[urlstring]
        return password_data[username]

    def save(self, urlstring, password_data):
        if not os.path.isfile(self._filename):
            os.mknod(self._filename)

        with open(self._filename, "r+", encoding="utf-8") as password_file:
            data = load(password_file)
            if data is None:
                data = {}
            if urlstring not in data:
                data[urlstring] = {}
            username = password_data["username"]["value"]
            data[urlstring][username] = {
                "password": password_data["password"]["value"],
            }
            if "checkbox" in password_data:
                data[urlstring][username]["checkbox"] = (
                    password_data["checkbox"]["value"]
                )
            password_file.seek(0)
            dump(data, password_file)
            password_file.truncate()


class PassPasswordManager(PasswordManager):

    """Pass password storage."""

    def _exec_pass(self, args, input_data=None):
        """Exec the pass command with the specified arguments and input.

        Args:
            args: The command-line arguments to send to pass.
            input: The text to send to pass stdin.

        Return:
            The pass output.
        """
        args.insert(0, "pass")
        process = subprocess.Popen(args, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   stdin=subprocess.PIPE)
        if input_data is not None:
            input_data = input_data.encode("utf-8")

        (result, error) = process.communicate(input_data)
        if len(error) > 0:
            raise KeyError
        return result.decode("utf-8")

    def _escape_url(self, urlstring):
        return shlex.quote(urlstring)

    def get_usernames(self, host):
        key = "qutebrowser/" + self._escape_url(host)
        result = self._exec_pass([key])
        lines = result.split("\n")[1:]
        usernames = []
        for line in lines:
            if len(line) > 0:
                username = line[4:]
                usernames.append(username)
        return usernames

    def load(self, urlstring, username):
        key = "qutebrowser/%s/%s" % (self._escape_url(urlstring), username)
        result = self._exec_pass([key])
        if result is None:
            raise KeyError
        lines = result.split("\n")
        password_data = {
            "password": lines[0],
        }

        if len(lines) > 1:
            password_data["checkbox"] = lines[1] == "True"

        return password_data

    def save(self, urlstring, password_data):
        key = self._escape_url(urlstring)
        username = password_data["username"]["value"]
        content = password_data["password"]["value"]
        if "checkbox" in password_data:
            content += "\n" + str(password_data["checkbox"]["value"])
        self._exec_pass(["insert", "-m", "qutebrowser/%s/%s" %
                        (key, username)], content)


class PasswordFiller:

    """Save and load login form data."""

    def __init__(self):
        self._win_id = 0
        password_storage = config.get("general", "password-storage")
        storages = {
            "pass": PassPasswordManager,
            "default": YamlPasswordManager,
        }
        self._password_manager = storages[password_storage]()

    def _choose_username(self, urlstring):
        """Ask to user which username to use.

        If there is only one username, use this username without asking.

        Return:
            The username chosen by the user.
        """
        usernames = self._password_manager.get_usernames(urlstring)
        answer = None
        if len(usernames) > 1:
            text = "Which username:"
            index = 0
            # TODO: show on multiple lines.
            for username in usernames:
                text += " " + str(index) + ". " + username
                index += 1
            answer = message.ask(self._win_id, text,
                                 usertypes.PromptMode.text)
            try:
                answer = int(answer)
            except (TypeError, ValueError):
                answer = None
        else:
            answer = 0

        if answer is None or answer >= len(usernames):
            max_index = len(usernames) - 1
            raise cmdexc.CommandError("Type a number between 0 and %d." %
                                      max_index)

        return usernames[answer]

    def _find_form(self):
        """Find the login form element.

        Return:
            The login form element.
        """
        frame = self._get_frame()
        elem = frame.findFirstElement('input[type="password"]')
        form = elem
        # TODO: find a workaround for when there is no form element around the
        # login form.
        while not form.isNull() and form.tagName() != "FORM":
            form = form.parent()
        return form

    def _find_login_form_elements(self):
        """Find the login form.

        Return:
            A dict containing the username, password and checkbox (if present
            in the form) elements and values.
        """
        form = self._find_form()

        elems = form.findAll('input[type="checkbox"], input[type="text"],'
                             'input[type="password"]')
        username_element = None
        password_element = None
        checkbox_element = None
        for element in elems:
            elem_type = element.attribute("type")
            if elem_type == "checkbox":
                checkbox_element = element
            elif elem_type == "password":
                password_element = element
            elif elem_type == "text" and username_element is None:
                username_element = element

        if username_element is None and password_element is None:
            raise RuntimeError

        data = {
            'username': {
                'element': username_element,
                'value': username_element.evaluateJavaScript("this.value"),
            },
            'password': {
                'element': password_element,
                'value': password_element.evaluateJavaScript("this.value"),
            },
        }
        if checkbox_element is not None:
            data["checkbox"] = {
                "element": checkbox_element,
                "value": checkbox_element.evaluateJavaScript("this.checked"),
            }

        return data

    def _get_frame(self):
        """Get the current frame."""
        tabbed_browser = objreg.get("tabbed-browser", scope="window",
                                    window=self._win_id)
        widget = tabbed_browser.currentWidget()
        if widget is None:
            raise cmdexc.CommandError("No WebView available yet!")
        return widget.page().mainFrame()

    def _get_host(self):
        """Get the current URL host."""
        tabbed_browser = objreg.get("tabbed-browser", scope="window",
                                    window=self._win_id)
        return tabbed_browser.current_url().host()

    def _load(self, url, username):
        return self._password_manager.load(url, username)

    @cmdutils.register(instance="password-filler", win_id="win_id")
    def load_password(self, win_id):
        """Load the password data from the current URL."""
        self._win_id = win_id

        host = self._get_host()

        try:
            username = self._choose_username(host)
            password_data = self._load(host, username)
        except (KeyError, FileNotFoundError):
            raise cmdexc.CommandError("No password data for the current URL!")

        password = password_data["password"]
        form_elements = self._find_login_form_elements()
        self._set_value(form_elements["username"]["element"], username)
        self._set_value(form_elements["password"]["element"], password)

        if "checkbox" in form_elements and "checkbox" in password_data:
            self._set_checkbox_value(form_elements["checkbox"]["element"],
                                     password_data["checkbox"])

    @cmdutils.register(instance="password-filler", win_id="win_id")
    def load_password_submit(self, win_id):
        """Load the password data for the current URL and submit the form."""
        self.load_password(win_id)
        form = self._find_form()
        self._submit(form)

    def _password_exists(self, url, username):
        """Check if a password exists for the current URL and username.

        Args:
            url: The URL to check.
            username: The username to check.

        Return:
            Whether a password exists or not.
        """
        password_exists = True
        try:
            self._load(url, username)
        except (KeyError, FileNotFoundError):
            password_exists = False
        return password_exists

    def _save(self, url, password_data):
        """Save the password data for the current URL.

        This uses the right password manager.

        Args:
            url: The URL for the password data to save.
            password_data: The password data.
        """
        self._password_manager.save(url, password_data)

    @cmdutils.register(instance="password-filler", win_id="win_id")
    def save_password(self, win_id):
        """Save the password for the current URL."""
        self._win_id = win_id
        host = self._get_host()

        try:
            password_data = self._find_login_form_elements()
        except RuntimeError:
            raise cmdexc.CommandError(
                "No login form found in the current page!")
        else:
            username = password_data["username"]["value"]

            save = False
            if self._password_exists(host, username):
                text = ("A password for this page already exists. "
                        "Do you want to override it?")
                save = message.ask(self._win_id, text,
                                   usertypes.PromptMode.yesno,
                                   default=False)
            else:
                save = True

            if save:
                self._save(host, password_data)

    def _set_checkbox_value(self, element, value):
        """Set the checkbox element value.

        Args:
            element: The element to change its value.
            value: The new value.
        """
        element.evaluateJavaScript("this.checked = " + str(value).lower())

    def _set_value(self, element, value):
        """Set the element value.

        Args:
            element: The element to change its value.
            value: The new value.
        """
        element.evaluateJavaScript("this.value = '" + value + "'")

    def _submit(self, form):
        # TODO: have a workaround for when submiting the form does not work.
        # e.g. click on the submit button.
        form.evaluateJavaScript("this.submit()")
