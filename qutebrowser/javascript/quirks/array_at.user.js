// Based on: https://github.com/tc39/proposal-relative-indexing-method#polyfill

/*
Copyright (c) 2020 Tab Atkins Jr.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

/* eslint-disable no-invalid-this */

"use strict";

(function() {
    function at(idx) {
        // ToInteger() abstract op
        let n = Math.trunc(idx) || 0;
        // Allow negative indexing from the end
        if (n < 0) {
            n += this.length;
        }
        // OOB access is guaranteed to return undefined
        if (n < 0 || n >= this.length) {
            return undefined;
        }
        // Otherwise, this is just normal property access
        return this[n];
    }

    const TypedArray = Reflect.getPrototypeOf(Int8Array);
    for (const type of [Array, String, TypedArray]) {
        Object.defineProperty(
            type.prototype,
            "at",
            {
                "value": at,
                "writable": true,
                "enumerable": false,
                "configurable": true,
            }
        );
    }
})();
