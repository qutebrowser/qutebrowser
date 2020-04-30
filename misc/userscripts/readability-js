#!/usr/bin/env node
// 
// # Description
// 
// Summarize the current page in a new tab, by processing it with the standalone readability
// library used for Firefox Reader View.
// 
// # Prerequisites
// 
//   - NODE_PATH might be required to point to your global node libraries:
//     export NODE_PATH=$NODE_PATH:$(npm root -g)
//   - Mozilla's readability library (npm install -g https://github.com/mozilla/readability.git)
//     NOTE: You might have to *login* as root for a system-wide installation to work (e.g. sudo -s)
//   - jsdom (npm install -g jsdom)
//   - qutejs (npm install -g qutejs)
// 
// # Usage
// 
// :spawn --userscript readability-js
// 
// One may wish to define an easy to type command alias in Qutebrowser's configuration file:
// c.aliases = {"readability" : "spawn --userscript readability-js", ...}

const Readability = require('readability');
const qute = require('qutejs');
const JSDOM = require('jsdom').JSDOM;
const fs = require('fs');
const path = require('path');
const util = require('util');

const HEADER = `
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1, text/html, charset=UTF-8" http-equiv="Content-Type">
    </meta>
    <title>%s</title>
    <style type="text/css">
        body {
            margin: 30px auto;
            max-width: 650px;
            line-height: 1.4;
            padding: 0 10px;
        }
        h1, h2, h3 {
            line-height: 1.2;
        }
    </style>
    <!-- This icon is licensed under the Mozilla Public License 2.0 (available at: https://www.mozilla.org/en-US/MPL/2.0/).
    The original icon can be found here: https://dxr.mozilla.org/mozilla-central/source/browser/themes/shared/reader/readerMode.svg -->
    <link rel="shortcut icon" href="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjRweCIgaGVpZ2h0PSI2NHB4IiB2ZXJzaW9uPSIxLjEiI
    HZpZXdCb3g9IjAgMCA2NCA2NCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGcgZmlsbD0iI2ZmZiI+CjxwYXRoIGQ9Im01MiAwaC00
    MGMtNC40MiAwLTggMy41OC04IDh2NDhjMCA0LjQyIDMuNTggOCA4IDhoNDBjNC40MiAwIDgtMy41OCA4LTh2LTQ4YzAtNC40Mi0zLjU4LTgtOC04em0wIDU
    yYzAgMi4yMS0xLjc5IDQtNCA0aC0zMmMtMi4yMSAwLTQtMS43OS00LTR2LTQwYzAtMi4yMSAxLjc5LTQgNC00aDMyYzIuMjEgMCA0IDEuNzkgNCA0em0tMT
    AtMzZoLTIwYy0xLjExIDAtMiAwLjg5NS0yIDJzMC44OTUgMiAyIDJoMjBjMS4xMSAwIDItMC44OTUgMi0ycy0wLjg5NS0yLTItMnptMCA4aC0yMGMtMS4xM
    SAwLTIgMC44OTUtMiAyczAuODk1IDIgMiAyaDIwYzEuMTEgMCAyLTAuODk1IDItMnMtMC44OTUtMi0yLTJ6bTAgOGgtMjBjLTEuMTEgMC0yIDAuODk1LTIg
    MnMwLjg5NSAyIDIgMmgyMGMxLjExIDAgMi0wLjg5NSAyLTJzLTAuODk1LTItMi0yem0tMTIgOGgtOGMtMS4xMSAwLTIgMC44OTUtMiAyczAuODk1IDIgMiA
    yaDhjMS4xMSAwIDItMC44OTUgMi0ycy0wLjg5NS0yLTItMnoiIGZpbGw9IiNmZmYiLz4KPC9nPgo8L3N2Zz4K"/>
</head>`;
const scriptsDir = path.join(process.env.QUTE_DATA_DIR, 'userscripts');
const tmpFile = path.join(scriptsDir, '/readability.html');
const domOpts = {url: process.env.QUTE_URL, contentType: "text/html; charset=utf-8"};

if (!fs.existsSync(scriptsDir)){
    fs.mkdirSync(scriptsDir);
}

JSDOM.fromFile(process.env.QUTE_HTML, domOpts).then(dom => {
    let reader = new Readability(dom.window.document);
    let article = reader.parse();
    let content = util.format(HEADER, article.title) + article.content;

    fs.writeFile(tmpFile, content, (err) => {
        if (err) {
            qute.messageError([`"${err}"`])
            return 1;
        }
        // Success
        qute.open(['-t', '-r', tmpFile]);
    })
});
