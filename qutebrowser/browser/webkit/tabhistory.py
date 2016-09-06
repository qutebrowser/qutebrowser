# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


from PyQt5.QtCore import QByteArray, QDataStream, QIODevice, QUrl

from qutebrowser.utils import qtutils


HISTORY_STREAM_VERSION = 2
BACK_FORWARD_TREE_VERSION = 2


def _encode_url(url):
    """Encode a QUrl suitable to pass to QWebHistory."""
    data = bytes(QUrl.toPercentEncoding(url.toString(), b':/#?&+=@%*'))
    return data.decode('ascii')


def _serialize_item(i, item, stream):
    """Serialize a single WebHistoryItem into a QDataStream.

    Args:
        i: The index of the current item.
        item: The WebHistoryItem to write.
        stream: The QDataStream to write to.
    """
    ### Source/WebCore/history/qt/HistoryItemQt.cpp restoreState
    ## urlString
    stream.writeQString(_encode_url(item.url))
    ## title
    stream.writeQString(item.title)
    ## originalURLString
    stream.writeQString(_encode_url(item.original_url))

    ### Source/WebCore/history/HistoryItem.cpp decodeBackForwardTree
    ## backForwardTreeEncodingVersion
    stream.writeUInt32(BACK_FORWARD_TREE_VERSION)
    ## size (recursion stack)
    stream.writeUInt64(0)
    ## node->m_documentSequenceNumber
    # If two HistoryItems have the same document sequence number, then they
    # refer to the same instance of a document.  Traversing history from one
    # such HistoryItem to another preserves the document.
    stream.writeInt64(i + 1)
    ## size (node->m_documentState)
    stream.writeUInt64(0)
    ## node->m_formContentType
    # info used to repost form data
    stream.writeQString(None)
    ## hasFormData
    stream.writeBool(False)
    ## node->m_itemSequenceNumber
    # If two HistoryItems have the same item sequence number, then they are
    # clones of one another.  Traversing history from one such HistoryItem to
    # another is a no-op.  HistoryItem clones are created for parent and
    # sibling frames when only a subframe navigates.
    stream.writeInt64(i + 1)
    ## node->m_referrer
    stream.writeQString(None)
    ## node->m_scrollPoint (x)
    try:
        stream.writeInt32(item.user_data['scroll-pos'].x())
    except (KeyError, TypeError):
        stream.writeInt32(0)
    ## node->m_scrollPoint (y)
    try:
        stream.writeInt32(item.user_data['scroll-pos'].y())
    except (KeyError, TypeError):
        stream.writeInt32(0)
    ## node->m_pageScaleFactor
    stream.writeFloat(1)
    ## hasStateObject
    # Support for HTML5 History
    stream.writeBool(False)
    ## node->m_target
    stream.writeQString(None)

    ### Source/WebCore/history/qt/HistoryItemQt.cpp restoreState
    ## validUserData
    # We could restore the user data here, but we prefer to use the
    # QWebHistoryItem API for that.
    stream.writeBool(False)


def serialize(items):
    """Serialize a list of QWebHistoryItems to a data stream.

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
    user_data = []

    current_idx = None

    for i, item in enumerate(items):
        if item.active:
            if current_idx is not None:
                raise ValueError("Multiple active items ({} and {}) "
                                 "found!".format(current_idx, i))
            else:
                current_idx = i

    if items:
        if current_idx is None:
            raise ValueError("No active item found!")
    else:
        current_idx = 0

    ### Source/WebKit/qt/Api/qwebhistory.cpp operator<<
    stream.writeInt(HISTORY_STREAM_VERSION)
    stream.writeInt(len(items))
    stream.writeInt(current_idx)

    for i, item in enumerate(items):
        _serialize_item(i, item, stream)
        user_data.append(item.user_data)

    stream.device().reset()
    qtutils.check_qdatastream(stream)
    return stream, data, user_data
