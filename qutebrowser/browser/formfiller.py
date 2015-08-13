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

import os

from yaml import Dumper, Loader, dump, load

from PyQt5.QtCore import QUrl

from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import objreg, standarddir

class FormManager:
    def load(self, urlstring):
        raise NotImplemented

    def save(self, urlstring, form_data):
        raise NotImplemented

class YamlFormManager(FormManager):
    def __init__(self, filename):
        self._filename = filename

    def load(self, urlstring):
        with open(self._filename, "r") as form_file:
            data = load(form_file)
        return data[urlstring]

    def save(self, urlstring, form_data):
        new_data = {
            urlstring: form_data,
        }
        with open(self._filename, "a") as form_file:
            dump(new_data, form_file)

class FormFiller:
    def __init__(self):
        self._filename = os.path.join(standarddir.config(), 'forms.yaml')

    def _find_form(self, elem):
        form = elem
        while not form.isNull() and form.tagName() != 'FORM':
            form = form.parent()
        return form

    def _find_form_data(self, elem):
        form = self._find_form(elem)
        elems = form.findAll('input[type="checkbox"], input[type="text"],'
                'input[type="password"], textarea')
        data = []
        for element in elems:
            name = element.attribute("name")
            id = element.attribute("id")
            checked = element.evaluateJavaScript("this.checked")

            # TODO: support when JavaScript is disabled.
            if len(id) > 0:
                selector = "#" + id
            elif len(name) > 0:
                selector = "[name=" + name + "]"

            if element.attribute("type") == "checkbox":
                value = element.evaluateJavaScript("this.checked")
            else:
                value = element.evaluateJavaScript("this.value")

            data.append({
                'selector': selector,
                'value': value,
            })
        return data

    def _get_form_data(self):
        mainframe = self._get_frame()
        elem = mainframe.findFirstElement("input:focus")
        return self._find_form_data(elem)

    def _get_frame(self):
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        widget = tabbed_browser.currentWidget()
        if widget is None:
            raise cmdexc.CommandError("No WebView available yet!")
        return widget.page().mainFrame()

    def _get_url(self):
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        return tabbed_browser.current_url().toString(
            QUrl.FullyEncoded | QUrl.RemovePassword | QUrl.RemoveQuery)

    def _load(self, url):
        form_manager = YamlFormManager(self._filename)
        return form_manager.load(url)

    @cmdutils.register(instance='form-filler', win_id='win_id')
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
                elem.evaluateJavaScript("this.checked = " + str(data["value"]).lower())
            else:
                elem.evaluateJavaScript("this.value = '" + data["value"] + "'")

    @cmdutils.register(instance='form-filler', win_id='win_id')
    def load_form_submit(self, win_id):
        """Load the form from the current URL and submit the form."""
        self.load_form(win_id)
        mainframe = self._get_frame()
        elem = mainframe.findFirstElement("input:focus")
        form = self._find_form(elem)
        self._submit(form)

    def _save(self, url, form_data):
        form_manager = YamlFormManager(self._filename)
        form_manager.save(url, form_data)

    @cmdutils.register(instance='form-filler', win_id='win_id')
    def save_form(self, win_id):
        """Save the form from the current URL."""
        self._win_id = win_id

        form_data = self._get_form_data()
        url = self._get_url()
        self._save(url, form_data)

    def _submit(self, form):
        form.evaluateJavaScript("this.submit()")
