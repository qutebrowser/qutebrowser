"use strict";

(function() {
    // Generate a unique storage key based on the current URL
    // (origin + pathname). This ensures different websites/pages
    // have separate settings.
    function getStorageKey() {
        const url = window.location.origin + window.location.pathname;

        const encoded = btoa(url)
            .replace(/[^a-zA-Z0-9_-]/g, "_")
            .slice(0, 50);

        return `__qute_zapper_persist_${encoded}`;
    }

    const STORAGE_KEY = getStorageKey();
    const PERSIST_CLASS = "__qute_zapper_persist";
    const HIDDEN_CLASS = "__qute_zapper_hidden";

    // Escape an id for use in a selector
    function escape_id(id) {
        if (window.CSS && CSS.escape) {
            return `#${CSS.escape(id)}`;
        }
        return `#${id.replace(
            /([\\"'\s.#>+~:[\]()])/g,
            "\\$1"
        )}`;
    }

    // Create a selector for an element
    function get_selector(element) {
        if (!element || element.nodeType !== 1) {
            return null;
        }
        if (element.id) {
            return escape_id(element.id);
        }

        const parts = [];
        let node = element;

        while (
            node &&
            node.nodeType === 1 &&
            node.parentElement
        ) {
            const tag = node.tagName.toLowerCase();

            let nth = 1;
            let sibling = node;

            while (
                (sibling = sibling.previousElementSibling) !== null
            ) {
                if (sibling.tagName === node.tagName) {
                    nth++;
                }
            }

            parts.unshift(`${tag}:nth-of-type(${nth})`);
            node = node.parentElement;
        }

        return parts.join(" > ");
    }

    // Create selectors for elements marked for hiding
    function collect_selectors(selector) {
        const nodes = [];

        nodes.push(...document.querySelectorAll(selector));

        const selectors = [];
        const seen = {};

        for (let index = 0; index < nodes.length; index++) {
            try {
                const selectorStr = get_selector(nodes[index]);

                if (selectorStr && !seen[selectorStr]) {
                    selectors.push(selectorStr);
                    seen[selectorStr] = true;
                }
            } catch (error) {
                // Ignore invalid node errors
            }
        }

        return selectors;
    }

    // Collect new selectors
    const persistSelectors = collect_selectors(
        `.${PERSIST_CLASS}`
    );

    const hiddenSelectors = collect_selectors(
        `.${HIDDEN_CLASS}`
    );

    // Merge with existing selectors
    let allSelectors = persistSelectors.concat(hiddenSelectors);

    try {
        const existing = localStorage.getItem(STORAGE_KEY);

        if (existing) {
            const existingSelectors = JSON.parse(existing);

            if (Array.isArray(existingSelectors)) {
                // Combine and deduplicate
                const combined = {};

                for (
                    let index = 0;
                    index < existingSelectors.length;
                    index++
                ) {
                    combined[existingSelectors[index]] = true;
                }

                for (
                    let index = 0;
                    index < persistSelectors.length;
                    index++
                ) {
                    combined[persistSelectors[index]] = true;
                }

                for (
                    let index = 0;
                    index < hiddenSelectors.length;
                    index++
                ) {
                    combined[hiddenSelectors[index]] = true;
                }

                allSelectors = Object.keys(combined);
            }
        }
    } catch (error) {
        // Ignore localStorage parsing errors
    }

    try {
        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(allSelectors)
        );
    } catch (error) {
        // Ignore localStorage write errors
    }

    return allSelectors;
})();

