// ==UserScript==
// @include https://web.whatsapp.com/
// ==/UserScript==

// Quirk for WhatsApp Web, based on:
// https://github.com/jiahaog/nativefier/issues/719#issuecomment-443809630

"use strict";

if (document.querySelector("a[href='https://support.google.com/chrome/answer/95414']")) {
    navigator.serviceWorker.getRegistration().then((registration) => {
        if (registration) {
            registration.unregister();
        }
        document.location.reload();
    });
}
