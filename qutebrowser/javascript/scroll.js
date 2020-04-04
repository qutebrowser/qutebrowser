/**
 * Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
    const funcs = {};

    funcs.to_perc = (x, y) => {
        let x_px = window.scrollX;
        let y_px = window.scrollY;

        const width = Math.max(
            document.body.scrollWidth,
            document.body.offsetWidth,
            document.documentElement.scrollWidth,
            document.documentElement.offsetWidth
        );
        const height = Math.max(
            document.body.scrollHeight,
            document.body.offsetHeight,
            document.documentElement.scrollHeight,
            document.documentElement.offsetHeight
        );

        if (x !== undefined) {
            x_px = (width - window.innerWidth) / 100 * x;
        }

        if (y !== undefined) {
            y_px = (height - window.innerHeight) / 100 * y;
        }

        /*
        console.log(JSON.stringify({
            "x": x,
            "window.scrollX": window.scrollX,
            "window.innerWidth": window.innerWidth,
            "elem.scrollWidth": document.documentElement.scrollWidth,
            "x_px": x_px,
            "y": y,
            "window.scrollY": window.scrollY,
            "window.innerHeight": window.innerHeight,
            "elem.scrollHeight": document.documentElement.scrollHeight,
            "y_px": y_px,
        }));
        */

        window.scroll(x_px, y_px);
    };

    funcs.delta_page = (x, y) => {
        const dx = window.innerWidth * x;
        const dy = window.innerHeight * y;
        window.scrollBy(dx, dy);
    };

    return funcs;
})();
