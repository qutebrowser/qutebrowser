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

"use strict";

window._qutebrowser.scroll = (function() {
    var funcs = {};

    funcs.to_perc = function(x, y) {
        var elem = document.documentElement;
        var x_px = window.scrollX;
        var y_px = window.scrollY;

        if (x !== undefined) {
            x_px = (elem.scrollWidth - window.innerWidth) / 100 * x;
        }

        if (y !== undefined) {
            y_px = (elem.scrollHeight - window.innerHeight) / 100 * y;
        }

        /*
        console.log(JSON.stringify({
            "x": x,
            "window.scrollX": window.scrollX,
            "window.innerWidth": window.innerWidth,
            "elem.scrollWidth": elem.scrollWidth,
            "x_px": x_px,
            "y": y,
            "window.scrollY": window.scrollY,
            "window.innerHeight": window.innerHeight,
            "elem.scrollHeight": elem.scrollHeight,
            "y_px": y_px,
        }));
        */

        window.scroll(x_px, y_px);
    };

    funcs.delta_page = function(x, y) {
        var dx = window.innerWidth * x;
        var dy = window.innerHeight * y;
        window.scrollBy(dx, dy);
    };

    funcs.pos = function() {
        var elem = document.documentElement;
        var dx = elem.scrollWidth - window.innerWidth;
        var dy = elem.scrollHeight - window.innerHeight;
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

        var pos = {
            "perc": {"x": perc_x, "y": perc_y},
            "px": {"x": window.scrollX, "y": window.scrollY},
        };

        // console.log(JSON.stringify(pos));
        return pos;
    };

    return funcs;
})();
