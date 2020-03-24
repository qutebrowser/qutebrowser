// ==UserScript==
// @include https://web.whatsapp.com/
// ==/UserScript==

// Quirk for WhatsApp Web, based on:
// https://github.com/jiahaog/nativefier/issues/719#issuecomment-443809630

if (document.body.innerText.replace(/\n/g, ' ').search(
        /whatsapp works with.*to use whatsapp.*update/i) !== -1) {
    navigator.serviceWorker.getRegistration().then(function (r) {
        r.unregister();
        document.location.reload();
    });
}
