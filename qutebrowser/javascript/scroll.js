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
