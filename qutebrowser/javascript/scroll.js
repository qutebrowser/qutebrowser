/**
 * Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

    const utils = window._qutebrowser.utils;

    function build_scroll_options(x, y, smooth) {
        return {
            "behavior": smooth
                ? "smooth"
                : "auto",
            "left": x,
            "top": y,
        };
    }

    function smooth_supported() {
        return "scrollBehavior" in document.documentElement.style;
    }

    // Helper function which scrolls an element to x, y
    function scroll_to_perc(elt, x, y) {
        let x_px = elt.scrollLeft;
        let y_px = elt.scrollTop;

        const width = Math.max(
            elt.scrollWidth,
            elt.offsetWidth
        );
        const height = Math.max(
            elt.scrollHeight,
            elt.offsetHeight
        );

        if (x !== undefined) {
            x_px = (width - elt.clientWidth) / 100 * x;
        }
        if (y !== undefined) {
            y_px = (height - elt.clientHeight) / 100 * y;
        }

        elt.scroll(x_px, y_px);
    }

    function scroll_element(element, x, y, smooth = false) {
        const pre_x = element.scrollTop;
        const pre_y = element.scrollLeft;
        if (smooth_supported()) {
            element.scrollBy(build_scroll_options(x, y, smooth));
        } else {
            element.scrollBy(x, y);
        }
        // Return true if we scrolled at all
        return pre_x !== element.scrollLeft || pre_y !== element.scrollTop;
    }

    // Scroll a provided window's element by x,y as a percent
    function scroll_window_elt(x, y, smooth, win, elt) {
        const dx = win.innerWidth * x;
        const dy = win.innerHeight * y;
        scroll_element(elt, dx, dy, smooth);
    }

    function should_scroll(elt) {
        const cs = window.getComputedStyle(elt);
        return (cs.getPropertyValue("overflow-#{direction}") !== "hidden" &&
            !(cs.getPropertyValue("visibility") in ["hidden", "collapse"]) &&
            cs.getPropertyValue("display") !== "none");
    }

    function can_scroll(element, x, y) {
        const x_sign = Math.sign(x);
        const y_sign = Math.sign(y);
        return (scroll_element(element, x_sign, y_sign) &&
                scroll_element(element, -x_sign, -y_sign));
    }

    function is_scrollable(elt, x, y) {
        return should_scroll(elt) && can_scroll(elt, x, y);
    }

    // Recurse up the DOM and get the first element which is scrollable.
    // We cannot use scrollHeight and clientHeight due to a chrome bug (110149)
    // Heavily inspired from Vimium's implementation:
    // https://github.com/philc/vimium/blob/026c90ccff6/content_scripts/scroller.coffee#L253-L270
    function scrollable_parent(element, x, y) {
        let elt = element;
        while (elt !== document.scrollingElement &&
               !is_scrollable(elt, x, y)) {
            elt = elt.parentElement;
        }
        return elt;
    }

    funcs.to_perc = (x, y) => {
        // If we are in a frame, scroll that frame
        const frame_win = utils.get_frame_window(document.activeElement);
        if (frame_win === window) {
            const scroll_elt = scrollable_parent(document.activeElement, x, y);
            scroll_to_perc(scroll_elt, x, y);
        } else {
            scroll_to_perc(frame_win.document.scrollingElement, x, y);
        }
    };

    funcs.delta_page = (x, y, smooth) => {
        const frame_win = utils.get_frame_window(document.activeElement);
        if (frame_win === window) {
            const scroll_elt = scrollable_parent(document.activeElement, x, y);
            scroll_window_elt(x, y, smooth, frame_win, scroll_elt);
        } else {
            scroll_window_elt(x, y, smooth, frame_win, frame_win);
        }
    };

    funcs.delta_px = (x, y, smooth) => {
        const frame_win = utils.get_frame_window(document.activeElement);
        // Scroll by raw pixels, rather than by page
        if (frame_win === window) {
            const scroll_elt = scrollable_parent(document.activeElement, x, y);
            scroll_element(scroll_elt, x, y, smooth);
        } else {
            scroll_element(frame_win, x, y, smooth);
        }
    };

    return funcs;
})();
