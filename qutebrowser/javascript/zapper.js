"use strict";

(function() {
    const CLASS = "__qute_zapper_hover";
    const HIDDEN_CLASS = "__qute_zapper_hidden";
    const STYLE_ID = "__qute_zapper_style";
    const STATE_KEY = "__qute_zapper_state";
    const PERSIST_CLASS = "__qute_zapper_persist";

    if (!window[STATE_KEY]) {
        window[STATE_KEY] = {
            enabled: false,
            current: null,
            handler: null,
            clickHandler: null,
            keyHandler: null,
            downHandler: null,
            persisted: [],
        };
    }
    const state = window[STATE_KEY];

    function ensure_style() {
        if (document.getElementById(STYLE_ID)) {
            return;
        }

        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            .${CLASS} {
                outline: 2px solid #ff0000 !important;
                outline-offset: 2px !important;
                cursor: crosshair !important;
            }
            .__qute_zapper_persist {
                outline: 3px solid #4caf50 !important;
                outline-offset: 3px !important;
                cursor: default !important;
            }
            .${HIDDEN_CLASS} {
                display: none !important;
            }
        `;
        (document.head || document.documentElement).appendChild(style);
    }

    function clear_current() {
        if (state.current) {
            state.current.classList.remove(CLASS);
            state.current = null;
        }
    }

    function add_persist(elem) {
        if (!elem ||
            elem === document.documentElement ||
            elem === document.body) {
            return;
        }
        elem.classList.remove(HIDDEN_CLASS);
        if (state.persisted.indexOf(elem) !== -1) {
            return;
        }
        state.persisted.push(elem);
        elem.classList.add(PERSIST_CLASS);
    }

    function remove_persist(elem) {
        const idx = state.persisted.indexOf(elem);
        if (idx === -1) {return;}
        state.persisted.splice(idx, 1);
        elem.classList.remove(PERSIST_CLASS);
        elem.classList.remove(HIDDEN_CLASS);
    }

    function hide_persist(elem) {
        if (!elem ||
            elem === document.documentElement ||
            elem === document.body) {
            return;
        }
        elem.classList.remove(PERSIST_CLASS);
        elem.classList.add(HIDDEN_CLASS);
        try {
            elem.style.setProperty("display", "none", "important");
        } catch (err) {
            // ignore
        }
    }

    function update_current(elem) {
        if (elem === state.current) {
            return;
        }

        clear_current();
        if (!elem || elem === document.documentElement ||
                elem === document.body) {
            return;
        }

        state.current = elem;
        elem.classList.add(CLASS);
    }

    function cleanup_zapper() {
        if (state.handler) {
            window.removeEventListener("mousemove", state.handler, true);
        }
        if (state.clickHandler) {
            window.removeEventListener("click", state.clickHandler, true);
        }
        if (state.keyHandler) {
            window.removeEventListener("keydown", state.keyHandler, true);
        }
        if (state.downHandler) {
            window.removeEventListener("pointerdown", state.downHandler, true);
            window.removeEventListener("mousedown", state.downHandler, true);
        }
        clear_current();
        state.handler = null;
        state.clickHandler = null;
        state.keyHandler = null;
        state.downHandler = null;
        state.persisted = [];
        state.enabled = false;
    }

    if (state.enabled) {
        // Hide persisted elements that the user added while zapper was active.
        // Keeping them in the DOM allows :zapper-save to collect them later.
        try {
            for (let i = 0; i < state.persisted.length; i++) {
                hide_persist(state.persisted[i]);
            }
        } catch (err) {
            // ignore
        }
        cleanup_zapper();
        return "zapper disabled";
    }

    ensure_style();
    state.handler = function(event) {
        const elem = document.elementFromPoint(event.clientX, event.clientY);
        update_current(elem);
    };

    state.clickHandler = function(event) {
        try {
            const elem = state.current;
            if (!elem ||
                elem === document.documentElement ||
                elem === document.body) {
                return;
            }
            // Toggle persisted highlight on click
            if (state.persisted.indexOf(elem) !== -1) {
                remove_persist(elem);
            } else {
                add_persist(elem);
            }
            event.preventDefault();
            event.stopPropagation();
        } catch (err) {
            // ignore
        }
    };

    state.downHandler = function(event) {
        try {
            // Prevent activation of buttons/inputs when interacting with zapper
            event.preventDefault();
            event.stopPropagation();
        } catch (err) {
            // ignore
        }
    };

    state.keyHandler = function(event) {
    try {
        if (event.key === "Enter" || event.keyCode === 13) {
            event.preventDefault();
            event.stopPropagation();

            // Save selectors to localStorage for the restore script
            try {
                const selectors = state.persisted
                    .filter(el => el && el.parentNode)
                    .map(el => {
                        if (el.id) {
                            return `#${ el.id}`;
                        }
                        if (el.className) {
                            const classes = [...el.classList]
                                .filter(cls => cls !== "__qute_zapper_persist")
                                .join(".");
                            return `${el.tagName.toLowerCase() }.${ classes}`;
                        }
                        return el.tagName.toLowerCase();
                    })
                    .filter(Boolean);

                const url = window.location.origin + window.location.pathname;
                const encoded = btoa(url)
                    .replace(/[^a-zA-Z0-9_-]/g, "_")
                    .slice(0, 50);
                const key = `__qute_zapper_persist_${ encoded}`;
                localStorage.setItem(key, JSON.stringify(selectors));
            } catch (err) {
                /* ignore */
            }

            // Hide persisted elements via style
            for (let i = 0; i < state.persisted.length; i++) {
                hide_persist(state.persisted[i]);
            }

            cleanup_zapper();
        }
    } catch (err) {
        /* ignore */
    }
};

    window.addEventListener("mousemove", state.handler, true);
    window.addEventListener("click", state.clickHandler, true);
    window.addEventListener("keydown", state.keyHandler, true);
    window.addEventListener("pointerdown", state.downHandler, true);
    window.addEventListener("mousedown", state.downHandler, true);
    state.enabled = true;
    return "zapper enabled";
})();

