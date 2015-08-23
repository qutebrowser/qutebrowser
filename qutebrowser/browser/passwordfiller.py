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

"""Password filler."""

import os
import shlex
import subprocess
from urllib.parse import quote_plus, unquote_plus

from yaml import dump, load

from qutebrowser.browser import webelem
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.config import config
from qutebrowser.utils import message, objreg, standarddir, usertypes


class PasswordManager:

    """Base abstract class for password storage."""

    def get_usernames(self, host):
        """Get a list of usernames stored for a specific URL host.

        Args:
            host: The URL host to check.

        Return:
            A list of usernames.
        """
        raise NotImplementedError

    def load(self, host, username):
        """Load the password data stored for a specific URL host and username.

        Args:
            host: The URL host.
            username: The username.

        Return:
            The password data as a dict containing the password and optionaly
            the checkbox keys.
        """
        raise NotImplementedError

    def save(self, host, password_data):
        """Save the password data for the specified host.

        Args:
            host: The URL host from where the data is coming.
            password_data: The password data to save.
        """
        raise NotImplementedError


class YamlPasswordManager(PasswordManager):

    """YAML password storage."""

    def __init__(self):
        self._filename = os.path.join(standarddir.config(), "passwords.yaml")

    def get_usernames(self, host):
        with open(self._filename, "r", encoding="utf-8") as password_file:
            data = load(password_file)
            if data is None:
                data = {}
        password_data = data[host]
        return list(password_data.keys())

    def load(self, host, username):
        with open(self._filename, "r", encoding="utf-8") as password_file:
            data = load(password_file)
            if data is None:
                data = {}
        password_data = data[host]
        return password_data[username]

    def save(self, host, password_data):
        if not os.path.isfile(self._filename):
            os.mknod(self._filename)

        with open(self._filename, "r+", encoding="utf-8") as password_file:
            data = load(password_file)
            if data is None:
                data = {}
            if host not in data:
                data[host] = {}
            username = password_data["username"]["value"]
            data[host][username] = {
                "password": password_data["password"]["value"],
            }
            if "checkbox" in password_data:
                data[host][username]["checkbox"] = (
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

    def get_usernames(self, host):
        key = "qutebrowser/%s" % shlex.quote(host)
        result = self._exec_pass([key])
        lines = result.split("\n")[1:]
        usernames = []
        for line in lines:
            if len(line) > 0:
                username = unquote_plus(line[4:])
                usernames.append(username)
        return usernames

    def load(self, host, username):
        username = quote_plus(username)
        key = "qutebrowser/%s/%s" % (shlex.quote(host), username)
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

    def save(self, host, password_data):
        key = shlex.quote(host)
        username = password_data["username"]["value"]
        username = quote_plus(username)
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

    def _choose_username(self, host):
        """Ask to user which username to use.

        If there is only one username for the specified host, use this
        username without asking.

        Args:
            host: The URL host.

        Return:
            The username chosen by the user.
        """
        usernames = self._password_manager.get_usernames(host)
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

    def _find_best_form(self, login_forms):
        """Return the best login form."""
        # Return the form containing data if a form contains data.
        for form in login_forms:
            elem = form.findFirst('input[type="password"]')
            value = elem.evaluateJavaScript("this.value")
            if len(value) > 0:
                return form

        # Return the form containing "login" in its attributes.
        for form in login_forms:
            attributes = ["class", "id", "name"]
            for attribute in attributes:
                if "login" in form.attribute(attribute):
                    return form

        # Select the form with the fewest number of input fields because
        # login forms usually contains fewer fields than register forms.
        min_element_count = 10
        best_form = None
        for form in login_forms:
            elems = form.findAll('input[type="email"], input[type="text"],'
                                 'input[type="password"], input:not([type])')
            if elems.count() < min_element_count:
                min_element_count = elems.count()
                best_form = form

        return best_form

    def _find_form(self):
        """Find the login form element.

        Return:
            The login form element.
        """
        frames = self._get_frames()
        login_forms = []
        for frame in frames:
            # TODO: fix when there is more than one login form
            elements = frame.findAllElements('input[type="password"]')
            for elem in elements:
                form = elem
                while not form.isNull() and (form.tagName() != "FORM" and
                                             form.tagName() != "BODY"):
                    form = form.parent()
                password_fields = form.findAll('input[type="password"]')
                # Return forms with one password field.
                if password_fields.count() == 1:
                    login_forms.append(form)

        if len(login_forms) > 0:
            return self._find_best_form(login_forms)

    def _find_login_form_elements(self):
        """Find the login form.

        Return:
            A dict containing the username, password and checkbox (if present
            in the form) elements and values.
        """
        form = self._find_form()

        if form is None:
            raise RuntimeError

        username_element = None
        password_element = None
        checkbox_element = None

        # Check for email first as text field may be a captcha.
        email_fields = form.findAll('input[type="email"]')

        if email_fields.count() > 0:
            username_element = email_fields[0]

        elems = form.findAll('input:not([type]), input[type="checkbox"],'
                             'input[type="password"], input[type="text"]')
        for element in elems:
            elem_type = element.attribute("type")
            if len(elem_type) == 0:
                elem_type = "text"

            if elem_type == "checkbox":
                checkbox_element = element
            elif elem_type == "password":
                password_element = element
            elif elem_type == "text" and username_element is None:
                username_element = element

        if username_element is None or password_element is None:
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

    def _get_frames(self):
        """Get the current frame."""
        tabbed_browser = objreg.get("tabbed-browser", scope="window",
                                    window=self._win_id)
        widget = tabbed_browser.currentWidget()
        if widget is None:
            raise cmdexc.CommandError("No WebView available yet!")
        return webelem.get_child_frames(widget.page().mainFrame())

    def _get_host(self):
        """Get the current URL host."""
        tabbed_browser = objreg.get("tabbed-browser", scope="window",
                                    window=self._win_id)
        return tabbed_browser.current_url().host()

    def _load(self, host, username):
        """Load the password data for a specific URL host and username.

        Args:
            host: The URL host.
            username: The username.

        Return:
            The password data.
        """
        return self._password_manager.load(host, username)

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
        try:
            form_elements = self._find_login_form_elements()
        except RuntimeError:
            raise cmdexc.CommandError(
                "No login form found in the current page!")
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

    def _password_exists(self, host, username):
        """Check if a password exists for the current URL and username.

        Args:
            host: The URL host to check.
            username: The username to check.

        Return:
            Whether a password exists or not.
        """
        password_exists = True
        try:
            self._load(host, username)
        except (KeyError, FileNotFoundError):
            password_exists = False
        return password_exists

    def _save(self, host, password_data):
        """Save the password data for the current URL.

        This uses the right password manager.

        Args:
            host: The URL host for the password data to save.
            password_data: The password data.
        """
        if len(password_data["username"]["value"]) == 0:
            raise cmdexc.CommandError(
                "Enter your username to be able to save your credentials.")
        if len(password_data["password"]["value"]) == 0:
            raise cmdexc.CommandError(
                "Enter your password to be able to save your credentials.")
        self._password_manager.save(host, password_data)

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
        """Submit the specified form."""
        # Fix for angularjs.
        elems = form.findAll('input[type="text"], input[type="email"],'
                             'input[type="password"], input:not([type])')

        js = ("var event = document.createEvent('HTMLEvents');"
              "event.initEvent('change', false, true);"
              "this.dispatchEvent(event);")
        for elem in elems:
            elem.evaluateJavaScript(js)

        # Fix for forms needing two submission (like Gmail).
        password_field = form.findFirst('input[type="password"]')
        password_was_visible = password_field.evaluateJavaScript(
            "this.offsetWidth > 0 && element.offsetHeight > 0")

        if not password_was_visible:
            # TODO: find a way of doing this in Python.
            password_field.evaluateJavaScript("""setTimeout(function() {
                    var submit_button = document.querySelector('input[type="submit"], button[type="submit"]');
                    submit_button.click();
                }, 500);
                """)

        submit_button = form.findFirst(
            'input[type="submit"], button[type="submit"]'
        )

        # Submit with the submit button if it exists.
        # Otherwise, send the submit event to the form.
        if submit_button.isNull():
            form.evaluateJavaScript("this.submit()")
        else:
            submit_button.evaluateJavaScript("this.click()")
