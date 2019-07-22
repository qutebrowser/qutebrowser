/**
 * Copyright 2019 Jay Kamat <jaygkamat@gmail.com>
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

/*
 * This file will get imported into the JS mainworld. Because of this, it is
 * accessible to the page completely, and anything done here should be treated
 * as public and exploitable for security purposes.
 */

"use strict";

window._qutebrowser.inject = (function() {
    const funcs = {};

    function hijackEventListener() {
        // -- Hijack addEventListener to give us something to search for --
        // http://www.github.com/philc/vimium/blob/8c9404f84fd4310b89818e132c0ef0822cbcd059/content_scripts/injected.coffee

        const EL = typeof Element === "function" ? Element : HTMLElement;
        const _addEventListener = EventTarget.prototype.addEventListener;
        const _toString = Function.prototype.toString;

        /* eslint-disable no-invalid-this, no-extend-native, consistent-this */

        function newAddEventListener(...args) {
            const type = args[0];
            if ((type === "click") && this instanceof EL) {
                if (!(this instanceof HTMLAnchorElement)) { // Just skip <a>.
                    try {
                        this.classList.add("__qute_has_onclick_listener");
                    } catch (error) {
                        // we can't afford this to fail for any reason and the
                        // hook not to get run.
                    }
                }
            }
            return (_addEventListener === null
                ? undefined
                : _addEventListener.apply(this, args));
        }

        // We need to cover our tracks, as some js gets annoyed that
        // addEventListener is overridden.
        // http://github.com/philc/vimium/blob/8c9404f84fd4310b89818e132c0ef0822cbcd059/content_scripts/injected.coffee#L34
        function newToString(...args) {
            let real = this;
            if (this === newToString) {
                real = _toString;
            } else if (this === newAddEventListener) {
                real = _addEventListener;
            }
            return _toString.apply(real, args);
        }

        EventTarget.prototype.addEventListener = newAddEventListener;
        Function.prototype.toString = newToString;
    }
    hijackEventListener();

    return funcs;
})();
