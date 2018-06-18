/**
 * Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
 * this is a hack based on the QupZilla solution, https://github.com/QupZilla/qupzilla/commit/d3f0d766fb052dc504de2426d42f235d96b5eb60
 *
 * We go to a qute://print which triggers the print, then we cancel the request.
 */

"use strict";

window.print = function() {
    window.location = "qute://print";
};
