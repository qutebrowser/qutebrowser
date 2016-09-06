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

"""QWebHistory serializer for QtWebEngine."""

import time

from PyQt5.QtCore import QByteArray, QDataStream, QIODevice, QUrl

from qutebrowser.utils import qtutils


HISTORY_STREAM_VERSION = 3


def _serialize_item(item, stream):
    """Serialize a single WebHistoryItem into a QDataStream.

    Args:
        item: The WebHistoryItem to write.
        stream: The QDataStream to write to.
    """
    ### Thanks to Otter Browser:
    ### https://github.com/OtterBrowser/otter-browser/blob/v0.9.10/src/modules/backends/web/qtwebengine/QtWebEngineWebWidget.cpp#L1210
    ### src/core/web_contents_adapter.cpp serializeNavigationHistory
    ## toQt(entry->GetVirtualURL());
    qtutils.serialize_stream(stream, item.url)
    ## toQt(entry->GetTitle());
    stream.writeQString(item.title)
    ## QByteArray(encodedPageState.data(), encodedPageState.size());
    qtutils.serialize_stream(stream, QByteArray())
    ## static_cast<qint32>(entry->GetTransitionType());
    # chromium/ui/base/page_transition_types.h
    stream.writeInt32(0)  # PAGE_TRANSITION_LINK
    ## entry->GetHasPostData();
    stream.writeBool(False)
    ## toQt(entry->GetReferrer().url);
    qtutils.serialize_stream(stream, QUrl())
    ## static_cast<qint32>(entry->GetReferrer().policy);
    # chromium/third_party/WebKit/public/platform/WebReferrerPolicy.h
    stream.writeInt32(0)  # WebReferrerPolicyAlways
    ## toQt(entry->GetOriginalRequestURL());
    qtutils.serialize_stream(stream, item.original_url)
    ## entry->GetIsOverridingUserAgent();
    stream.writeBool(False)
    ## static_cast<qint64>(entry->GetTimestamp().ToInternalValue());
    stream.writeInt64(int(time.time()))
    ## entry->GetHttpStatusCode();
    stream.writeInt(200)


def serialize(items):
    """Serialize a list of QWebHistoryItems to a data stream.

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
    # kHistoryStreamVersion
    stream.writeInt(HISTORY_STREAM_VERSION)
    # count
    stream.writeInt(len(items))
    # currentIndex
    stream.writeInt(current_idx)

    for item in items:
        _serialize_item(item, stream)

    stream.device().reset()
    qtutils.check_qdatastream(stream)
    return stream, data, cur_user_data
