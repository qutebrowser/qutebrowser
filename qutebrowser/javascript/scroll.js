// SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
//
// SPDX-License-Identifier: GPL-3.0-or-later

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
