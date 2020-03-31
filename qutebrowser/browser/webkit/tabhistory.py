# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Utilities related to QWebHistory."""

import typing

from PyQt5.QtCore import QByteArray, QDataStream, QIODevice, QUrl

from qutebrowser.utils import qtutils


def _serialize_items(items, current_idx, stream):
    # {'currentItemIndex': 0,
    #  'history': [{'children': [],
    #               'documentSequenceNumber': 1485030525573123,
    #               'documentState': [],
    #               'formContentType': '',
    #               'itemSequenceNumber': 1485030525573122,
    #               'originalURLString': 'about:blank',
    #               'pageScaleFactor': 0.0,
    #               'referrer': '',
    #               'scrollPosition': {'x': 0, 'y': 0},
    #               'target': '',
    #               'title': '',
    #               'urlString': 'about:blank'}]}
    data = {'currentItemIndex': current_idx, 'history': []}
    for item in items:
        data['history'].append(_serialize_item(item))

    stream.writeInt(3)  # history stream version
    stream.writeQVariantMap(data)


def _serialize_item(item):
    data = {
        'originalURLString': item.original_url.toString(QUrl.FullyEncoded),
        'scrollPosition': {'x': 0, 'y': 0},
        'title': item.title,
        'urlString': item.url.toString(QUrl.FullyEncoded),
    }
    try:
        data['scrollPosition']['x'] = item.user_data['scroll-pos'].x()
        data['scrollPosition']['y'] = item.user_data['scroll-pos'].y()
    except (KeyError, TypeError):
        pass
    return data


def serialize(items):
    """Serialize a list of WebHistoryItems to a data stream.

    Args:
        items: An iterable of WebHistoryItems.

    Return:
        A (stream, data, user_data) tuple.
            stream: The reset QDataStream.
            data: The QByteArray with the raw data.
            user_data: A list with each item's user data.

    Warning:
        If 'data' goes out of scope, reading from 'stream' will result in a
        segfault!
    """
    data = QByteArray()
    stream = QDataStream(data, QIODevice.ReadWrite)
    user_data = []  # type: typing.List[typing.Mapping[str, typing.Any]]

    current_idx = None

    for i, item in enumerate(items):
        if item.active:
            if current_idx is not None:
                raise ValueError("Multiple active items ({} and {}) "
                                 "found!".format(current_idx, i))
            current_idx = i

    if items:
        if current_idx is None:
            raise ValueError("No active item found!")
    else:
        current_idx = 0

    _serialize_items(items, current_idx, stream)

    user_data += [item.user_data for item in items]

    stream.device().reset()
    qtutils.check_qdatastream(stream)
    return stream, data, user_data
