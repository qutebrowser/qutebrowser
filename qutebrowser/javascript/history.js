/**
 * Container for global stuff
 */
var global = {
    // The last history item that was seen.
    lastItem: null,
    // The next time to load
    nextTime: null,
    // The cutoff interval for session-separator (30 minutes)
    SESSION_CUTOFF: 30*60
};

/**
 * Finds or creates the session table>tbody to which item with given date
 * should be added.
 *
 * @param {Date} date - the date of the item being added.
 */
var getSessionNode = function(date) {
    var histContainer = document.getElementById('hist-container');

    // Find/create table
    var tableId = "hist-" + date.getDate() + date.getMonth() + date.getYear();
    var table = document.getElementById(tableId);
    if (table === null) {
        table = document.createElement("table");
        table.id = tableId;

        caption = document.createElement("caption");
        caption.className = "date";
        var options = {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'};
        caption.innerHTML = date.toLocaleDateString('en-US', options);
        table.appendChild(caption);

        // Add table to page
        histContainer.appendChild(table);
    }

    // Find/create tbody
    var tbody = table.lastChild;
    if (tbody.tagName !== "TBODY") { // this is the caption
        tbody = document.createElement("tbody");
        table.appendChild(tbody);
    }

    // Create session-separator and new tbody if necessary
    if (tbody.lastChild !== null && global.lastItem !== null) {
        lastItemDate = new Date(parseInt(global.lastItem.time)*1000);
        var interval = (lastItemDate.getTime() - date.getTime())/1000.00;
        if (interval > global.SESSION_CUTOFF) {
            // Add session-separator
            var sessionSeparator = document.createElement('td');
            sessionSeparator.className = "session-separator";
            sessionSeparator.colSpan = 2;
            sessionSeparator.innerHTML = "&#167;";
            table.appendChild(document.createElement('tr'));
            table.lastChild.appendChild(sessionSeparator);

            // Create new tbody
            tbody = document.createElement("tbody");
            table.appendChild(tbody);
        }
    }

    return tbody;
}

/**
 * Given a history item, create and return <tr> for it.
 * param {string} itemUrl - The url for this item
 * param {string} itemTitle - The title for this item
 * param {string} itemTime - The formatted time for this item
 */
var makeHistoryRow = function(itemUrl, itemTitle, itemTime) {
    var row = document.createElement('tr');

    var title = document.createElement('td');
    title.className = "title";
    var link = document.createElement('a');
    link.href = itemUrl;
    link.innerHTML = itemTitle;
    title.appendChild(link);

    var time = document.createElement('td');
    time.className = "time";
    time.innerHTML = itemTime;

    row.appendChild(title);
    row.appendChild(time);

    return row;
}

var getJSON = function(url, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = 'json';
    xhr.onload = function() {
        var status = xhr.status;
        callback(status, xhr.response);
    };
    xhr.send();
};

/**
 * Load new history.
 */
var loadHistory = function() {
    url = "qute://history/data";
    if (global.nextTime !== null) {
        startTime = global.nextTime;
        url = "qute://history/data?start_time=" + startTime.toString();
    }

    getJSON(url, function(status, history) {
        if (history !== undefined) {
            for (item of history) {
                if (item.next === -1) {
                    // Reached end of history
                    window.onscroll = null;
                    document.getElementById('eof').style.display = "block";
                    document.getElementById('load').style.display = "none";
                    continue;
                } else if (item.next !== undefined) {
                    global.nextTime = parseInt(item.next);
                    continue;
                }

                atime = new Date(parseInt(item.time)*1000);
                var session = getSessionNode(atime);
                var row = makeHistoryRow(item.url, item.title, atime.toLocaleTimeString());
                session.appendChild(row);
                global.lastItem = item;
            }
        }
    });
}

