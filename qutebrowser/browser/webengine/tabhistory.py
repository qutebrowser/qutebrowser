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

"""QWebHistory serializer for QtWebEngine."""

import time

from PyQt5.QtCore import QByteArray, QDataStream, QIODevice, QUrl

from qutebrowser.utils import qtutils


# kHistoryStreamVersion = 3 was originally set when history serializing was
# implemented in QtWebEngine:
# https://codereview.qt-project.org/c/qt/qtwebengine/+/81529
#
# Qt 5.14 added version 4 which also serializes favicons:
# https://codereview.qt-project.org/c/qt/qtwebengine/+/279407
# However, we don't care about those, so let's keep it at 3.
HISTORY_STREAM_VERSION = 3


def _serialize_item(item, stream):
    """Serialize a single WebHistoryItem into a QDataStream.

    Args:
        item: The WebHistoryItem to write.
        stream: The QDataStream to write to.
    """
    # Thanks to Otter Browser:
    # https://github.com/OtterBrowser/otter-browser/blob/v1.0.01/src/modules/backends/web/qtwebengine/QtWebEnginePage.cpp#L260
    #
    # Relevant QtWebEngine source:
    # src/core/web_contents_adapter.cpp serializeNavigationHistory
    #
    # Sample data:
    # [TabHistoryItem(active=True,
    #                 original_url=QUrl('file:///home/florian/proj/qutebrowser/git/tests/end2end/data/numbers/1.txt'),
    #                 title='1.txt',
    #                 url=QUrl('file:///home/florian/proj/qutebrowser/git/tests/end2end/data/numbers/1.txt'),
    #                 user_data={'zoom': 1.0, 'scroll-pos': QPoint()})]

    ## toQt(entry->GetVirtualURL());
    # \x00\x00\x00Jfile:///home/florian/proj/qutebrowser/git/tests/end2end/data/numbers/1.txt
    qtutils.serialize_stream(stream, item.url)

    ## toQt(entry->GetTitle());
    # \x00\x00\x00\n\x001\x00.\x00t\x00x\x00t
    stream.writeQString(item.title)

    ## QByteArray(encodedPageState.data(), encodedPageState.size());
    # \xff\xff\xff\xff
    qtutils.serialize_stream(stream, QByteArray())

    ## static_cast<qint32>(entry->GetTransitionType());
    # chromium/ui/base/page_transition_types.h
    # \x00\x00\x00\x00
    stream.writeInt32(0)  # PAGE_TRANSITION_LINK

    ## entry->GetHasPostData();
    # \x00
    stream.writeBool(False)

    ## toQt(entry->GetReferrer().url);
    # \xff\xff\xff\xff
    qtutils.serialize_stream(stream, QUrl())

    ## static_cast<qint32>(entry->GetReferrer().policy);
    # chromium/third_party/WebKit/public/platform/WebReferrerPolicy.h
    # \x00\x00\x00\x00
    stream.writeInt32(0)  # WebReferrerPolicyAlways

    ## toQt(entry->GetOriginalRequestURL());
    # \x00\x00\x00Jfile:///home/florian/proj/qutebrowser/git/tests/end2end/data/numbers/1.txt
    qtutils.serialize_stream(stream, item.original_url)

    ## entry->GetIsOverridingUserAgent();
    # \x00
    stream.writeBool(False)

    ## static_cast<qint64>(entry->GetTimestamp().ToInternalValue());
    # \x00\x00\x00\x00^\x97$\xe7
    stream.writeInt64(int(time.time()))

    ## entry->GetHttpStatusCode();
    # \x00\x00\x00\xc8
    stream.writeInt(200)


def serialize(items):
    """Serialize a list of WebHistoryItems to a data stream.

    Args:
        items: An iterable of WebHistoryItems.

    Return:
        A (stream, data, user_data) tuple.
            stream: The reset QDataStream.
            data: The QByteArray with the raw data.
            cur_user_data: The user data for the current item or None.

    Warning:
        If 'data' goes out of scope, reading from 'stream' will result in a
        segfault!
    """
    data = QByteArray()
    stream = QDataStream(data, QIODevice.ReadWrite)
    cur_user_data = None

    current_idx = None

    for i, item in enumerate(items):
        if item.active:
            if current_idx is not None:
                raise ValueError("Multiple active items ({} and {}) "
                                 "found!".format(current_idx, i))
            current_idx = i
            cur_user_data = item.user_data

    if items:
        if current_idx is None:
            raise ValueError("No active item found!")
    else:
        current_idx = -1

    ### src/core/web_contents_adapter.cpp serializeNavigationHistory
    #                                          sample data:
    # kHistoryStreamVersion
    stream.writeInt(HISTORY_STREAM_VERSION)  # \x00\x00\x00\x03
    # count
    stream.writeInt(len(items))              # \x00\x00\x00\x01
    # currentIndex
    stream.writeInt(current_idx)             # \x00\x00\x00\x00

    for item in items:
        _serialize_item(item, stream)

    stream.device().reset()
    qtutils.check_qdatastream(stream)
    return stream, data, cur_user_data
