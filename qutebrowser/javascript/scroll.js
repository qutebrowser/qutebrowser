/**
 * Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
 *
 * This file is part of qutebrowser.
 *
 * qutebrowser is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * qutebrowser is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.
 */

function scroll_to_perc(x, y) {
    var elem = document.documentElement;
    var x_px = window.scrollX;
    var y_px = window.scrollY;

    if (x !== undefined) {
        x_px = (elem.scrollWidth - elem.clientWidth) / 100 * x;
    }

    if (y !== undefined) {
        y_px  = (elem.scrollHeight - elem.clientHeight) / 100 * y;
    }

    window.scroll(x_px, y_px);
}

function scroll_delta_page(x, y) {
    var dx = document.documentElement.clientWidth * x;
    var dy = document.documentElement.clientHeight * y;
    window.scrollBy(dx, dy);
}

function scroll_pos() {
    var elem = document.documentElement;
    var dx = (elem.scrollWidth - elem.clientWidth);
    var dy = (elem.scrollHeight - elem.clientHeight);

    var perc_x, perc_y;

    if (dx === 0) {
        perc_x = 0;
    } else {
        perc_x = 100 / dx * window.scrollX;
    }

    if (dy === 0) {
        perc_y = 0;
    } else {
        perc_y = 100 / dy * window.scrollY;
    }

    var pos_perc = {'x': perc_x, 'y': perc_y};
    var pos_px = {'x': window.scrollX, 'y': window.scrollY};
    var pos = {'perc': pos_perc, 'px': pos_px};

    // console.log(JSON.stringify(pos));
    return pos;
}
