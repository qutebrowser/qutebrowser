# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities related to QWebHistory."""

from typing import Any
from collections.abc import Mapping

from qutebrowser.qt.core import QByteArray, QDataStream, QIODevice, QUrl

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
        'originalURLString': item.original_url.toString(QUrl.ComponentFormattingOption.FullyEncoded),
        'scrollPosition': {'x': 0, 'y': 0},
        'title': item.title,
        'urlString': item.url.toString(QUrl.ComponentFormattingOption.FullyEncoded),
    }
    try:
        data['scrollPosition']['x'] = item.user_data['scroll-pos'].x()
        data['scrollPosition']['y'] = item.user_data['scroll-pos'].y()
    except (KeyError, TypeError):
        pass
    return data


def serialize(items):
    """Serialize a list of TabHistoryItems to a data stream.

    Args:
        items: An iterable of TabHistoryItems.

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
    stream = QDataStream(data, QIODevice.OpenModeFlag.ReadWrite)
    user_data: list[Mapping[str, Any]] = []

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
