/**
 * Copyright 2016-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
    // Store the element we should center on for scrolling. This may not be
    // the element that actually scrolls, but it is the starting point.
    let activatedElement = null;
    // If we guessed an activatedElement, this stores our guess. If null, we
    // were manually set or have no guess.
    let activatedElementGuess = null;
    const funcs = {};

    function build_scroll_options(x, y, smooth) {
        return {
            "behavior": smooth
                ? "smooth"
                : "instant",
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
        const viewDoc = elt.ownerDocument;

        let width = Math.max(
            elt.scrollWidth,
            elt.offsetWidth
        );
        let height = Math.max(
            elt.scrollHeight,
            elt.offsetHeight
        );

        let viewWidth = elt.clientWidth;
        let viewHeight = elt.clientHeight;

        // If elt is scrolling element, use window's height
        if (elt === viewDoc.scrollingElement) {
            const docElt = viewDoc.documentElement;
            const docScr = viewDoc.scrollingElement;
            // If we have the full page, add docElt's dimensions to avoid
            // rounding errors on zoom
            width = Math.max(width, docElt.offsetWidth, docElt.scrollWidth);
            height = Math.max(height, docElt.offsetHeight, docElt.scrollHeight);

            viewWidth = Math.min(docElt.clientWidth, docScr.clientWidth);
            viewHeight = Math.min(docElt.clientHeight, docScr.clientHeight);
        }

        if (x !== undefined) {
            x_px = (width - viewWidth) / 100 * x;
        }
        if (y !== undefined) {
            y_px = (height - viewHeight) / 100 * y;
        }

        elt.scrollTop = y_px;
        elt.scrollLeft = x_px;
    }

    function scroll_element(element, x, y, smooth = false) {
        const pre_y = element.scrollTop;
        const pre_x = element.scrollLeft;
        if (smooth_supported()) {
            element.scrollBy(build_scroll_options(x, y, smooth));
        } else if ("scrollBy" in element) {
            element.scrollBy(x, y);
        } else {
            element.scrollTop += y;
            element.scrollLeft += x;
        }
        // Return true if we scrolled at all
        return pre_x !== element.scrollLeft || pre_y !== element.scrollTop;
    }

    // Scroll a provided window's element by x,y as a percent
    function scroll_window_elt(x, y, smooth, elt) {
        const win = elt.ownerDocument.defaultView;
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

    // Fuzz allows checking both positive and negative scrolling in tests.
    function is_scrollable(elt, x, y, fuzz = false) {
        return should_scroll(elt) && (can_scroll(elt, x, y) ||
                                      (fuzz && can_scroll(elt, -x, -y)));
    }

    function is_scrollable_y(elt) {
        return is_scrollable(elt, 0, 1) || is_scrollable(elt, 0, -1);
    }

    // Recurse up the DOM and get the first element which is scrollable.
    // We cannot use scrollHeight and clientHeight due to a chrome bug (110149)
    // Heavily inspired from Vimium's implementation:
    // https://github.com/philc/vimium/blob/026c90ccff6/content_scripts/scroller.coffee#L253-L270
    function scrollable_parent(element, x, y, fuzz = false) {
        let elt = element;
        while (elt !== document.scrollingElement &&
               !is_scrollable(elt, x, y, fuzz)) {
            elt = elt.parentElement;
        }
        return elt;
    }

    // Attempt to set activatedElement to the largest element.
    // Inspired from firstScrollableElement in vimium:
    // http://github.com/philc/vimium/blob/026c90cc/content_scripts/scroller.coffee#L98-L114
    function firstScrollableElement(ele = null) {
        let element = ele;
        if (element === null) {
            const scrollingElement = document.scrollingElement || document.body;
            if (is_scrollable_y(scrollingElement)) {
                return scrollingElement;
            }
            element = document.body || scrollingElement;
        }

        if (is_scrollable_y(element)) {
            return element;
        }
        const childElements = Array.from(element.children).
            map((child) => ({"element": child,
                "rect": child.getBoundingClientRect()})).
            filter((child) => child.rect).
            map((child) => {
                child.area = child.rect.width * child.rect.height;
                return child;
            }).
            sort((first, second) => second.area - first.area);
        for (let i = 0; i < childElements.length; i++) {
            const result = firstScrollableElement(childElements[i].element);
            if (result !== null) {
                const rect = result.getBoundingClientRect();
                // Some sites have their scrollable element behind elements of
                // size zero. We can't handle this case very well, but
                // refusing to actually pick small elements can help.
                //
                // We pick > 1 since some websites have 1x1 dummy elements
                // that are 'scrollable'.
                if (rect && rect.width > 1 && rect.height > 1) {
                    return result;
                }
            }
        }
        return null;
    }

    // Get the element that should be scrolled currently in the root frame. If
    // activatedElement is set, use that. Otherwise recurse using
    // activeElement.
    function getActivatedElement(x, y, fuzz = false) {
        let elt = document.activeElement;
        // If activated element is no longer present, remove it from
        // consideration
        if (activatedElement !== null &&
            !document.contains(activatedElement) &&
            // If document is not the root one, we may have a frame scrollable
            // TODO handle deletion of frames
            document === activatedElement.ownerDocument) {
            activatedElement = null;
        }

        if (activatedElement === null) {
            const firstScrolling = firstScrollableElement();
            if (firstScrolling) {
                activatedElement = firstScrolling;
                activatedElementGuess = firstScrolling;
                elt = activatedElement;
            }
        } else {
            elt = activatedElement;
        }
        const scrollingElt = scrollable_parent(elt, x, y, fuzz);
        if (activatedElementGuess !== null &&
                scrollingElt !== elt &&
                elt === activatedElementGuess) {
            // We made a bad guess!
            // Keep going right now, but guess again next time.
            activatedElement = null;
            activatedElementGuess = null;
        }
        return scrollingElt;
    }

    funcs.to_perc = (x, y) => {
        const detect_x = x === 0 ? 1 : x;
        const detect_y = y === 0 ? 1 : y;
        const scroll_elt = getActivatedElement(detect_x, detect_y, true);
        scroll_to_perc(scroll_elt, x, y);
    };

    funcs.delta_page = (x, y, smooth) => {
        const scroll_elt = getActivatedElement(x, y);
        scroll_window_elt(x, y, smooth, scroll_elt);
    };

    funcs.delta_px = (x, y, smooth) => {
        // Scroll by raw pixels, rather than by page
        const scroll_elt = getActivatedElement(x, y);
        scroll_element(scroll_elt, x, y, smooth);
    };

    funcs.set_activated_element = (elt) => {
        activatedElement = elt;
        activatedElementGuess = null;
    };
    funcs.is_scrollable = is_scrollable;
    funcs.is_scrollable_y = is_scrollable_y;

    return funcs;
})();
