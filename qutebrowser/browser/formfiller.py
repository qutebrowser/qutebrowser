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

from PyQt5.QtCore import QUrl

from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.config import config
from qutebrowser.utils import message, objreg, standarddir, usertypes


class FormManager:

    """Base abstract class for form storage."""

    def load(self, urlstring):
        raise NotImplementedError

    def save(self, urlstring, form_data):
        raise NotImplementedError


class YamlFormManager(FormManager):

    """YAML form storage."""

    def __init__(self):
        self._filename = os.path.join(standarddir.config(), "forms.yaml")

    def load(self, urlstring):
        with open(self._filename, "r", encoding="utf-8") as form_file:
            data = load(form_file)
            if data is None:
                data = {}
        return data[urlstring]

    def save(self, urlstring, form_data):
        if not os.path.isfile(self._filename):
            os.mknod(self._filename)

        with open(self._filename, "r+", encoding="utf-8") as form_file:
            data = load(form_file)
            if data is None:
                data = {}
            data[urlstring] = form_data
            form_file.seek(0)
            dump(data, form_file)
            form_file.truncate()


class PassFormManager(FormManager):

    """Pass form storage."""

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
        return result

    def _escape_url(self, urlstring):
        return shlex.quote(urlstring.replace("/", ""))

    def load(self, urlstring):
        key = self._escape_url(urlstring)
        yaml_data = self._exec_pass(["qutebrowser/" + key])
        result = load(yaml_data)
        if result is None:
            raise KeyError
        return result

    def save(self, urlstring, form_data):
        key = self._escape_url(urlstring)
        self._exec_pass(["insert", "-m", "qutebrowser/" + key],
                        dump(form_data))


class FormFiller:

    """Save and load form data."""

    def __init__(self):
        self._win_id = 0
        password_storage = config.get("general", "password-storage")
        storages = {
            "pass": PassFormManager,
            "default": YamlFormManager,
        }
        self._form_manager = storages[password_storage]()

    def _find_form(self, elem):
        """Find the form element from the input elem.

        Args:
            elem: The input element.

        Return:
            The form element.
        """
        form = elem
        while not form.isNull() and form.tagName() != "FORM":
            form = form.parent()
        return form

    def _find_form_data(self, elem):
        """Find the data from the form containing the specified input element.

        Args:
            elem: The input element.

        Return:
            The form data.
        """
        # TODO: have a workaround for when there is no form element.
        form = self._find_form(elem)
        elems = form.findAll('input[type="checkbox"], input[type="text"],'
                             'input[type="password"], textarea')
        data = []
        for element in elems:
            name = element.attribute("name")
            elem_id = element.attribute("id")

            # TODO: support when JavaScript is disabled.
            if len(elem_id) > 0:
                selector = "#" + elem_id
            elif len(name) > 0:
                selector = "[name=" + name + "]"

            if element.attribute("type") == "checkbox":
                value = element.evaluateJavaScript("this.checked")
            else:
                value = element.evaluateJavaScript("this.value")

            data.append({
                "selector": selector,
                "value": value,
            })
        return data

    def _get_form_data(self):
        """Get the data from the form containing the focused element."""
        mainframe = self._get_frame()
        elem = mainframe.findFirstElement("input:focus")
        return self._find_form_data(elem)

    def _get_frame(self):
        """Get the current frame."""
        tabbed_browser = objreg.get("tabbed-browser", scope="window",
                                    window=self._win_id)
        widget = tabbed_browser.currentWidget()
        if widget is None:
            raise cmdexc.CommandError("No WebView available yet!")
        return widget.page().mainFrame()

    def _get_url(self):
        """Get the current URL."""
        tabbed_browser = objreg.get("tabbed-browser", scope="window",
                                    window=self._win_id)
        return tabbed_browser.current_url().toString(
            QUrl.FullyEncoded | QUrl.RemovePassword | QUrl.RemoveQuery)

    def _load(self, url):
        return self._form_manager.load(url)

    @cmdutils.register(instance="form-filler", win_id="win_id")
    def load_form(self, win_id):
        """Load the form from the current URL."""
        self._win_id = win_id

        url = self._get_url()
        try:
            form_data = self._load(url)
        except (KeyError, FileNotFoundError):
            raise cmdexc.CommandError("No form for the current URL!")

        mainframe = self._get_frame()

        for data in form_data:
            elem = mainframe.findFirstElement(data["selector"])
            if elem.attribute("type") == "checkbox":
                elem.evaluateJavaScript("this.checked = " +
                                        str(data["value"]).lower())
            else:
                elem.evaluateJavaScript("this.value = '" + data["value"] + "'")

    @cmdutils.register(instance="form-filler", win_id="win_id")
    def load_form_submit(self, win_id):
        """Load the form from the current URL and submit the form."""
        self.load_form(win_id)
        mainframe = self._get_frame()
        elem = mainframe.findFirstElement("input:focus")
        form = self._find_form(elem)
        self._submit(form)

    def _save(self, url, form_data):
        self._form_manager.save(url, form_data)

    @cmdutils.register(instance="form-filler", win_id="win_id")
    def save_form(self, win_id):
        """Save the form from the current URL."""
        self._win_id = win_id
        url = self._get_url()

        form_exists = True
        try:
            form_data = self._load(url)
        except (KeyError, FileNotFoundError):
            form_exists = False

        save = False
        if form_exists:
            text = ("A password for this page already exists. "
                    "Do you want to override it?")
            save = message.ask(self._win_id, text,
                               usertypes.PromptMode.yesno,
                               default=True)
        else:
            save = True

        if save:
            form_data = self._get_form_data()
            self._save(url, form_data)

    def _submit(self, form):
        # TODO: have a workaround for when submiting the form does not work.
        # e.g. click on the submit button.
        form.evaluateJavaScript("this.submit()")
