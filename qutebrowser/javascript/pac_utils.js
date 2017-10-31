/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is mozilla.org code.
 *
 * The Initial Developer of the Original Code is
 * Netscape Communications Corporation.
 * Portions created by the Initial Developer are Copyright (C) 1998
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 *   Akhil Arora <akhil.arora@sun.com>
 *   Tomi Leppikangas <Tomi.Leppikangas@oulu.fi>
 *   Darin Fisher <darin@meer.net>
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */

/*
   Script for Proxy Auto Config in the new world order.
       - Gagan Saksena 04/24/00
*/

function dnsDomainIs(host, domain) {
    return (host.length >= domain.length &&
            host.substring(host.length - domain.length) == domain);
}

function dnsDomainLevels(host) {
    return host.split('.').length-1;
}

function convert_addr(ipchars) {
    const bytes = ipchars.split('.');
    const result = ((bytes[0] & 0xff) << 24) |
                 ((bytes[1] & 0xff) << 16) |
                 ((bytes[2] & 0xff) <<  8) |
                  (bytes[3] & 0xff);
    return result;
}

function isInNet(ipaddr, pattern, maskstr) {
    const test = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/
               .exec(ipaddr);
    if (test == null) {
        ipaddr = dnsResolve(ipaddr);
        if (ipaddr == null)
            return false;
    } else if (test[1] > 255 || test[2] > 255 ||
               test[3] > 255 || test[4] > 255) {
        return false;    // not an IP address
    }
    const host = convert_addr(ipaddr);
    const pat  = convert_addr(pattern);
    const mask = convert_addr(maskstr);
    return ((host & mask) == (pat & mask));
}

function isPlainHostName(host) {
    return (host.search('\\.') == -1);
}

function isResolvable(host) {
    const ip = dnsResolve(host);
    return (ip != null);
}

function localHostOrDomainIs(host, hostdom) {
    return (host == hostdom) ||
           (hostdom.lastIndexOf(`${host}.`, 0) == 0);
}

function shExpMatch(url, pattern) {
   pattern = pattern.replace(/\./g, '\\.');
   pattern = pattern.replace(/\*/g, '.*');
   pattern = pattern.replace(/\?/g, '.');
   const newRe = new RegExp(`^${pattern}$`);
   return newRe.test(url);
}

const wdays = {SUN: 0, MON: 1, TUE: 2, WED: 3, THU: 4, FRI: 5, SAT: 6};

const months = {JAN: 0, FEB: 1, MAR: 2, APR: 3, MAY: 4, JUN: 5, JUL: 6,
              AUG: 7, SEP: 8, OCT: 9, NOV: 10, DEC: 11};

function weekdayRange(...args) {
    function getDay(weekday) {
        if (weekday in wdays) {
            return wdays[weekday];
        }
        return -1;
    }
    const date = new Date();
    let argc = args.length;
    let wday;
    if (argc < 1)
        return false;
    if (args[argc - 1] == 'GMT') {
        argc--;
        wday = date.getUTCDay();
    } else {
        wday = date.getDay();
    }
    const wd1 = getDay(args[0]);
    const wd2 = (argc == 2) ? getDay(args[1]) : wd1;
    return (wd1 == -1 || wd2 == -1) ? false
                                    : (wd1 <= wday && wday <= wd2);
}

function dateRange(...args) {
    function getMonth(name) {
        if (name in months) {
            return months[name];
        }
        return -1;
    }
    let date = new Date();
    let argc = args.length;
    if (argc < 1) {
        return false;
    }
    const isGMT = (args[argc - 1] == 'GMT');

    if (isGMT) {
        argc--;
    }
    // function will work even without explict handling of this case
    if (argc == 1) {
        let tmp = parseInt(args[0]);
        if (isNaN(tmp)) {
            return (isGMT ? date.getUTCMonth() : date.getMonth()) ==
                    getMonth(args[0]);
        } else if (tmp < 32) {
            return ((isGMT ? date.getUTCDate() : date.getDate()) == tmp);
        } else {
            return ((isGMT ? date.getUTCFullYear() : date.getFullYear()) ==
                    tmp);
        }
    }
    const year = date.getFullYear();
    let date1, date2;
    date1 = new Date(year,  0,  1,  0,  0,  0);
    date2 = new Date(year, 11, 31, 23, 59, 59);
    let adjustMonth = false;
    for (let i = 0; i < (argc >> 1); i++) {
        let tmp = parseInt(args[i]);
        if (isNaN(tmp)) {
            let mon = getMonth(args[i]);
            date1.setMonth(mon);
        } else if (tmp < 32) {
            adjustMonth = (argc <= 2);
            date1.setDate(tmp);
        } else {
            date1.setFullYear(tmp);
        }
    }
    for (let i = (argc >> 1); i < argc; i++) {
        let tmp = parseInt(args[i]);
        if (isNaN(tmp)) {
            let mon = getMonth(args[i]);
            date2.setMonth(mon);
        } else if (tmp < 32) {
            date2.setDate(tmp);
        } else {
            date2.setFullYear(tmp);
        }
    }
    if (adjustMonth) {
        date1.setMonth(date.getMonth());
        date2.setMonth(date.getMonth());
    }
    if (isGMT) {
    let tmp = date;
        tmp.setFullYear(date.getUTCFullYear());
        tmp.setMonth(date.getUTCMonth());
        tmp.setDate(date.getUTCDate());
        tmp.setHours(date.getUTCHours());
        tmp.setMinutes(date.getUTCMinutes());
        tmp.setSeconds(date.getUTCSeconds());
        date = tmp;
    }
    return ((date1 <= date) && (date <= date2));
}

function timeRange(...args) {
    let argc = args.length;
    const date = new Date();
    let isGMT= false;

    if (argc < 1) {
        return false;
    }
    if (args[argc - 1] == 'GMT') {
        isGMT = true;
        argc--;
    }

    const hour = isGMT ? date.getUTCHours() : date.getHours();
    let date1, date2;
    date1 = new Date();
    date2 = new Date();

    if (argc == 1) {
        return hour == args[0];
    } else if (argc == 2) {
        return (args[0] <= hour) && (hour <= args[1]);
    } else {
        switch (argc) {
        case 6:
            date1.setSeconds(args[2]);
            date2.setSeconds(args[5]);
        case 4:
            const middle = argc >> 1;
            date1.setHours(args[0]);
            date1.setMinutes(args[1]);
            date2.setHours(args[middle]);
            date2.setMinutes(args[middle + 1]);
            if (middle == 2) {
                date2.setSeconds(59);
            }
            break;
        default:
          throw 'timeRange: bad number of arguments'
        }
    }

    if (isGMT) {
        date.setFullYear(date.getUTCFullYear());
        date.setMonth(date.getUTCMonth());
        date.setDate(date.getUTCDate());
        date.setHours(date.getUTCHours());
        date.setMinutes(date.getUTCMinutes());
        date.setSeconds(date.getUTCSeconds());
    }
    return ((date1 <= date) && (date <= date2));
}
