/*
 * Copyright 2016 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * Generated from http://github.com/GoogleChrome/accessibility-developer-tools/tree/7d778f7da58af341a47b3a6f6457c2842b24d4d8
 *
 * See project README for build steps.
 */

// AUTO-GENERATED CONTENT BELOW: DO NOT EDIT! See above for details.

var fn = (function() {
  var COMPILED = !0, goog = goog || {};
goog.global = this;
goog.isDef = function(a) {
  return void 0 !== a;
};
goog.exportPath_ = function(a, b, c) {
  a = a.split(".");
  c = c || goog.global;
  a[0] in c || !c.execScript || c.execScript("var " + a[0]);
  for (var d;a.length && (d = a.shift());) {
    !a.length && goog.isDef(b) ? c[d] = b : c = c[d] ? c[d] : c[d] = {};
  }
};
goog.define = function(a, b) {
  var c = b;
  COMPILED || (goog.global.CLOSURE_UNCOMPILED_DEFINES && Object.prototype.hasOwnProperty.call(goog.global.CLOSURE_UNCOMPILED_DEFINES, a) ? c = goog.global.CLOSURE_UNCOMPILED_DEFINES[a] : goog.global.CLOSURE_DEFINES && Object.prototype.hasOwnProperty.call(goog.global.CLOSURE_DEFINES, a) && (c = goog.global.CLOSURE_DEFINES[a]));
  goog.exportPath_(a, c);
};
goog.DEBUG = !0;
goog.LOCALE = "en";
goog.TRUSTED_SITE = !0;
goog.STRICT_MODE_COMPATIBLE = !1;
goog.DISALLOW_TEST_ONLY_CODE = COMPILED && !goog.DEBUG;
goog.ENABLE_CHROME_APP_SAFE_SCRIPT_LOADING = !1;
goog.provide = function(a) {
  if (goog.isInModuleLoader_()) {
    throw Error("goog.provide can not be used within a goog.module.");
  }
  if (!COMPILED && goog.isProvided_(a)) {
    throw Error('Namespace "' + a + '" already declared.');
  }
  goog.constructNamespace_(a);
};
goog.constructNamespace_ = function(a, b) {
  if (!COMPILED) {
    delete goog.implicitNamespaces_[a];
    for (var c = a;(c = c.substring(0, c.lastIndexOf("."))) && !goog.getObjectByName(c);) {
      goog.implicitNamespaces_[c] = !0;
    }
  }
  goog.exportPath_(a, b);
};
goog.VALID_MODULE_RE_ = /^[a-zA-Z_$][a-zA-Z0-9._$]*$/;
goog.module = function(a) {
  if (!goog.isString(a) || !a || -1 == a.search(goog.VALID_MODULE_RE_)) {
    throw Error("Invalid module identifier");
  }
  if (!goog.isInModuleLoader_()) {
    throw Error("Module " + a + " has been loaded incorrectly.");
  }
  if (goog.moduleLoaderState_.moduleName) {
    throw Error("goog.module may only be called once per module.");
  }
  goog.moduleLoaderState_.moduleName = a;
  if (!COMPILED) {
    if (goog.isProvided_(a)) {
      throw Error('Namespace "' + a + '" already declared.');
    }
    delete goog.implicitNamespaces_[a];
  }
};
goog.module.get = function(a) {
  return goog.module.getInternal_(a);
};
goog.module.getInternal_ = function(a) {
  if (!COMPILED) {
    return goog.isProvided_(a) ? a in goog.loadedModules_ ? goog.loadedModules_[a] : goog.getObjectByName(a) : null;
  }
};
goog.moduleLoaderState_ = null;
goog.isInModuleLoader_ = function() {
  return null != goog.moduleLoaderState_;
};
goog.module.declareLegacyNamespace = function() {
  if (!COMPILED && !goog.isInModuleLoader_()) {
    throw Error("goog.module.declareLegacyNamespace must be called from within a goog.module");
  }
  if (!COMPILED && !goog.moduleLoaderState_.moduleName) {
    throw Error("goog.module must be called prior to goog.module.declareLegacyNamespace.");
  }
  goog.moduleLoaderState_.declareLegacyNamespace = !0;
};
goog.setTestOnly = function(a) {
  if (goog.DISALLOW_TEST_ONLY_CODE) {
    throw a = a || "", Error("Importing test-only code into non-debug environment" + (a ? ": " + a : "."));
  }
};
goog.forwardDeclare = function(a) {
};
COMPILED || (goog.isProvided_ = function(a) {
  return a in goog.loadedModules_ || !goog.implicitNamespaces_[a] && goog.isDefAndNotNull(goog.getObjectByName(a));
}, goog.implicitNamespaces_ = {"goog.module":!0});
goog.getObjectByName = function(a, b) {
  for (var c = a.split("."), d = b || goog.global, e;e = c.shift();) {
    if (goog.isDefAndNotNull(d[e])) {
      d = d[e];
    } else {
      return null;
    }
  }
  return d;
};
goog.globalize = function(a, b) {
  var c = b || goog.global, d;
  for (d in a) {
    c[d] = a[d];
  }
};
goog.addDependency = function(a, b, c, d) {
  if (goog.DEPENDENCIES_ENABLED) {
    var e;
    a = a.replace(/\\/g, "/");
    var f = goog.dependencies_;
    d && "boolean" !== typeof d || (d = d ? {module:"goog"} : {});
    for (var g = 0;e = b[g];g++) {
      f.nameToPath[e] = a, f.loadFlags[a] = d;
    }
    for (d = 0;b = c[d];d++) {
      a in f.requires || (f.requires[a] = {}), f.requires[a][b] = !0;
    }
  }
};
goog.ENABLE_DEBUG_LOADER = !0;
goog.logToConsole_ = function(a) {
  goog.global.console && goog.global.console.error(a);
};
goog.require = function(a) {
  if (!COMPILED) {
    goog.ENABLE_DEBUG_LOADER && goog.IS_OLD_IE_ && goog.maybeProcessDeferredDep_(a);
    if (goog.isProvided_(a)) {
      return goog.isInModuleLoader_() ? goog.module.getInternal_(a) : null;
    }
    if (goog.ENABLE_DEBUG_LOADER) {
      var b = goog.getPathFromDeps_(a);
      if (b) {
        return goog.writeScripts_(b), null;
      }
    }
    a = "goog.require could not find: " + a;
    goog.logToConsole_(a);
    throw Error(a);
  }
};
goog.basePath = "";
goog.nullFunction = function() {
};
goog.abstractMethod = function() {
  throw Error("unimplemented abstract method");
};
goog.addSingletonGetter = function(a) {
  a.getInstance = function() {
    if (a.instance_) {
      return a.instance_;
    }
    goog.DEBUG && (goog.instantiatedSingletons_[goog.instantiatedSingletons_.length] = a);
    return a.instance_ = new a;
  };
};
goog.instantiatedSingletons_ = [];
goog.LOAD_MODULE_USING_EVAL = !0;
goog.SEAL_MODULE_EXPORTS = goog.DEBUG;
goog.loadedModules_ = {};
goog.DEPENDENCIES_ENABLED = !COMPILED && goog.ENABLE_DEBUG_LOADER;
goog.ALWAYS_TRANSPILE = !1;
goog.NEVER_TRANSPILE = !1;
goog.DEPENDENCIES_ENABLED && (goog.dependencies_ = {loadFlags:{}, nameToPath:{}, requires:{}, visited:{}, written:{}, deferred:{}}, goog.inHtmlDocument_ = function() {
  var a = goog.global.document;
  return null != a && "write" in a;
}, goog.findBasePath_ = function() {
  if (goog.isDef(goog.global.CLOSURE_BASE_PATH)) {
    goog.basePath = goog.global.CLOSURE_BASE_PATH;
  } else {
    if (goog.inHtmlDocument_()) {
      for (var a = goog.global.document.getElementsByTagName("SCRIPT"), b = a.length - 1;0 <= b;--b) {
        var c = a[b].src, d = c.lastIndexOf("?"), d = -1 == d ? c.length : d;
        if ("base.js" == c.substr(d - 7, 7)) {
          goog.basePath = c.substr(0, d - 7);
          break;
        }
      }
    }
  }
}, goog.importScript_ = function(a, b) {
  (goog.global.CLOSURE_IMPORT_SCRIPT || goog.writeScriptTag_)(a, b) && (goog.dependencies_.written[a] = !0);
}, goog.IS_OLD_IE_ = !(goog.global.atob || !goog.global.document || !goog.global.document.all), goog.importProcessedScript_ = function(a, b, c) {
  goog.importScript_("", 'goog.retrieveAndExec_("' + a + '", ' + b + ", " + c + ");");
}, goog.queuedModules_ = [], goog.wrapModule_ = function(a, b) {
  return goog.LOAD_MODULE_USING_EVAL && goog.isDef(goog.global.JSON) ? "goog.loadModule(" + goog.global.JSON.stringify(b + "\n//# sourceURL=" + a + "\n") + ");" : 'goog.loadModule(function(exports) {"use strict";' + b + "\n;return exports});\n//# sourceURL=" + a + "\n";
}, goog.loadQueuedModules_ = function() {
  var a = goog.queuedModules_.length;
  if (0 < a) {
    var b = goog.queuedModules_;
    goog.queuedModules_ = [];
    for (var c = 0;c < a;c++) {
      goog.maybeProcessDeferredPath_(b[c]);
    }
  }
}, goog.maybeProcessDeferredDep_ = function(a) {
  goog.isDeferredModule_(a) && goog.allDepsAreAvailable_(a) && (a = goog.getPathFromDeps_(a), goog.maybeProcessDeferredPath_(goog.basePath + a));
}, goog.isDeferredModule_ = function(a) {
  var b = (a = goog.getPathFromDeps_(a)) && goog.dependencies_.loadFlags[a] || {};
  return a && ("goog" == b.module || goog.needsTranspile_(b.lang)) ? goog.basePath + a in goog.dependencies_.deferred : !1;
}, goog.allDepsAreAvailable_ = function(a) {
  if ((a = goog.getPathFromDeps_(a)) && a in goog.dependencies_.requires) {
    for (var b in goog.dependencies_.requires[a]) {
      if (!goog.isProvided_(b) && !goog.isDeferredModule_(b)) {
        return !1;
      }
    }
  }
  return !0;
}, goog.maybeProcessDeferredPath_ = function(a) {
  if (a in goog.dependencies_.deferred) {
    var b = goog.dependencies_.deferred[a];
    delete goog.dependencies_.deferred[a];
    goog.globalEval(b);
  }
}, goog.loadModuleFromUrl = function(a) {
  goog.retrieveAndExec_(a, !0, !1);
}, goog.loadModule = function(a) {
  var b = goog.moduleLoaderState_;
  try {
    goog.moduleLoaderState_ = {moduleName:void 0, declareLegacyNamespace:!1};
    var c;
    if (goog.isFunction(a)) {
      c = a.call(goog.global, {});
    } else {
      if (goog.isString(a)) {
        c = goog.loadModuleFromSource_.call(goog.global, a);
      } else {
        throw Error("Invalid module definition");
      }
    }
    var d = goog.moduleLoaderState_.moduleName;
    if (!goog.isString(d) || !d) {
      throw Error('Invalid module name "' + d + '"');
    }
    goog.moduleLoaderState_.declareLegacyNamespace ? goog.constructNamespace_(d, c) : goog.SEAL_MODULE_EXPORTS && Object.seal && Object.seal(c);
    goog.loadedModules_[d] = c;
  } finally {
    goog.moduleLoaderState_ = b;
  }
}, goog.loadModuleFromSource_ = function(a) {
  eval(a);
  return {};
}, goog.writeScriptSrcNode_ = function(a) {
  goog.global.document.write('<script type="text/javascript" src="' + a + '">\x3c/script>');
}, goog.appendScriptSrcNode_ = function(a) {
  var b = goog.global.document, c = b.createElement("script");
  c.type = "text/javascript";
  c.src = a;
  c.defer = !1;
  c.async = !1;
  b.head.appendChild(c);
}, goog.writeScriptTag_ = function(a, b) {
  if (goog.inHtmlDocument_()) {
    var c = goog.global.document;
    if (!goog.ENABLE_CHROME_APP_SAFE_SCRIPT_LOADING && "complete" == c.readyState) {
      if (/\bdeps.js$/.test(a)) {
        return !1;
      }
      throw Error('Cannot write "' + a + '" after document load');
    }
    if (void 0 === b) {
      if (goog.IS_OLD_IE_) {
        var d = " onreadystatechange='goog.onScriptLoad_(this, " + ++goog.lastNonModuleScriptIndex_ + ")' ";
        c.write('<script type="text/javascript" src="' + a + '"' + d + ">\x3c/script>");
      } else {
        goog.ENABLE_CHROME_APP_SAFE_SCRIPT_LOADING ? goog.appendScriptSrcNode_(a) : goog.writeScriptSrcNode_(a);
      }
    } else {
      c.write('<script type="text/javascript">' + b + "\x3c/script>");
    }
    return !0;
  }
  return !1;
}, goog.needsTranspile_ = function(a) {
  if (goog.ALWAYS_TRANSPILE) {
    return !0;
  }
  if (goog.NEVER_TRANSPILE) {
    return !1;
  }
  if (!goog.transpiledLanguages_) {
    goog.transpiledLanguages_ = {es5:!0, es6:!0, "es6-impl":!0};
    try {
      goog.transpiledLanguages_.es5 = eval("[1,].length!=1"), eval('(()=>{"use strict";let a={};const X=class{constructor(){}x(z){return new Map([...arguments]).get(z[0])==3}};return new X().x([a,3])})()') && (goog.transpiledLanguages_["es6-impl"] = !1), eval('(()=>{"use strict";class X{constructor(){if(new.target!=String)throw 1;this.x=42}}let q=Reflect.construct(X,[],String);if(q.x!=42||!(q instanceof String))throw 1;for(const a of[2,3]){if(a==2)continue;function f(z={a}){let a=0;return z.a}{function f(){return 0;}}return f()==3}})()') && 
      (goog.transpiledLanguages_.es6 = !1);
    } catch (b) {
    }
  }
  return !!goog.transpiledLanguages_[a];
}, goog.transpiledLanguages_ = null, goog.lastNonModuleScriptIndex_ = 0, goog.onScriptLoad_ = function(a, b) {
  "complete" == a.readyState && goog.lastNonModuleScriptIndex_ == b && goog.loadQueuedModules_();
  return !0;
}, goog.writeScripts_ = function(a) {
  function b(a) {
    if (!(a in e.written || a in e.visited)) {
      e.visited[a] = !0;
      if (a in e.requires) {
        for (var f in e.requires[a]) {
          if (!goog.isProvided_(f)) {
            if (f in e.nameToPath) {
              b(e.nameToPath[f]);
            } else {
              throw Error("Undefined nameToPath for " + f);
            }
          }
        }
      }
      a in d || (d[a] = !0, c.push(a));
    }
  }
  var c = [], d = {}, e = goog.dependencies_;
  b(a);
  for (a = 0;a < c.length;a++) {
    var f = c[a];
    goog.dependencies_.written[f] = !0;
  }
  var g = goog.moduleLoaderState_;
  goog.moduleLoaderState_ = null;
  for (a = 0;a < c.length;a++) {
    if (f = c[a]) {
      var h = e.loadFlags[f] || {}, k = goog.needsTranspile_(h.lang);
      "goog" == h.module || k ? goog.importProcessedScript_(goog.basePath + f, "goog" == h.module, k) : goog.importScript_(goog.basePath + f);
    } else {
      throw goog.moduleLoaderState_ = g, Error("Undefined script input");
    }
  }
  goog.moduleLoaderState_ = g;
}, goog.getPathFromDeps_ = function(a) {
  return a in goog.dependencies_.nameToPath ? goog.dependencies_.nameToPath[a] : null;
}, goog.findBasePath_(), goog.global.CLOSURE_NO_DEPS || goog.importScript_(goog.basePath + "deps.js"));
goog.normalizePath_ = function(a) {
  a = a.split("/");
  for (var b = 0;b < a.length;) {
    "." == a[b] ? a.splice(b, 1) : b && ".." == a[b] && a[b - 1] && ".." != a[b - 1] ? a.splice(--b, 2) : b++;
  }
  return a.join("/");
};
goog.loadFileSync_ = function(a) {
  if (goog.global.CLOSURE_LOAD_FILE_SYNC) {
    return goog.global.CLOSURE_LOAD_FILE_SYNC(a);
  }
  try {
    var b = new goog.global.XMLHttpRequest;
    b.open("get", a, !1);
    b.send();
    return 0 == b.status || 200 == b.status ? b.responseText : null;
  } catch (c) {
    return null;
  }
};
goog.retrieveAndExec_ = function(a, b, c) {
  if (!COMPILED) {
    var d = a;
    a = goog.normalizePath_(a);
    var e = goog.global.CLOSURE_IMPORT_SCRIPT || goog.writeScriptTag_, f = goog.loadFileSync_(a);
    if (null == f) {
      throw Error('Load of "' + a + '" failed');
    }
    c && (f = goog.transpile_.call(goog.global, f, a));
    f = b ? goog.wrapModule_(a, f) : f + ("\n//# sourceURL=" + a);
    goog.IS_OLD_IE_ ? (goog.dependencies_.deferred[d] = f, goog.queuedModules_.push(d)) : e(a, f);
  }
};
goog.transpile_ = function(a, b) {
  var c = goog.global.$jscomp;
  c || (goog.global.$jscomp = c = {});
  var d = c.transpile;
  if (!d) {
    var e = goog.basePath + "transpile.js", f = goog.loadFileSync_(e);
    f && (eval(f + "\n//# sourceURL=" + e), c = goog.global.$jscomp, d = c.transpile);
  }
  d || (d = c.transpile = function(a, b) {
    goog.logToConsole_(b + " requires transpilation but no transpiler was found.");
    return a;
  });
  return d(a, b);
};
goog.typeOf = function(a) {
  var b = typeof a;
  if ("object" == b) {
    if (a) {
      if (a instanceof Array) {
        return "array";
      }
      if (a instanceof Object) {
        return b;
      }
      var c = Object.prototype.toString.call(a);
      if ("[object Window]" == c) {
        return "object";
      }
      if ("[object Array]" == c || "number" == typeof a.length && "undefined" != typeof a.splice && "undefined" != typeof a.propertyIsEnumerable && !a.propertyIsEnumerable("splice")) {
        return "array";
      }
      if ("[object Function]" == c || "undefined" != typeof a.call && "undefined" != typeof a.propertyIsEnumerable && !a.propertyIsEnumerable("call")) {
        return "function";
      }
    } else {
      return "null";
    }
  } else {
    if ("function" == b && "undefined" == typeof a.call) {
      return "object";
    }
  }
  return b;
};
goog.isNull = function(a) {
  return null === a;
};
goog.isDefAndNotNull = function(a) {
  return null != a;
};
goog.isArray = function(a) {
  return "array" == goog.typeOf(a);
};
goog.isArrayLike = function(a) {
  var b = goog.typeOf(a);
  return "array" == b || "object" == b && "number" == typeof a.length;
};
goog.isDateLike = function(a) {
  return goog.isObject(a) && "function" == typeof a.getFullYear;
};
goog.isString = function(a) {
  return "string" == typeof a;
};
goog.isBoolean = function(a) {
  return "boolean" == typeof a;
};
goog.isNumber = function(a) {
  return "number" == typeof a;
};
goog.isFunction = function(a) {
  return "function" == goog.typeOf(a);
};
goog.isObject = function(a) {
  var b = typeof a;
  return "object" == b && null != a || "function" == b;
};
goog.getUid = function(a) {
  return a[goog.UID_PROPERTY_] || (a[goog.UID_PROPERTY_] = ++goog.uidCounter_);
};
goog.hasUid = function(a) {
  return !!a[goog.UID_PROPERTY_];
};
goog.removeUid = function(a) {
  null !== a && "removeAttribute" in a && a.removeAttribute(goog.UID_PROPERTY_);
  try {
    delete a[goog.UID_PROPERTY_];
  } catch (b) {
  }
};
goog.UID_PROPERTY_ = "closure_uid_" + (1E9 * Math.random() >>> 0);
goog.uidCounter_ = 0;
goog.getHashCode = goog.getUid;
goog.removeHashCode = goog.removeUid;
goog.cloneObject = function(a) {
  var b = goog.typeOf(a);
  if ("object" == b || "array" == b) {
    if (a.clone) {
      return a.clone();
    }
    var b = "array" == b ? [] : {}, c;
    for (c in a) {
      b[c] = goog.cloneObject(a[c]);
    }
    return b;
  }
  return a;
};
goog.bindNative_ = function(a, b, c) {
  return a.call.apply(a.bind, arguments);
};
goog.bindJs_ = function(a, b, c) {
  if (!a) {
    throw Error();
  }
  if (2 < arguments.length) {
    var d = Array.prototype.slice.call(arguments, 2);
    return function() {
      var c = Array.prototype.slice.call(arguments);
      Array.prototype.unshift.apply(c, d);
      return a.apply(b, c);
    };
  }
  return function() {
    return a.apply(b, arguments);
  };
};
goog.bind = function(a, b, c) {
  Function.prototype.bind && -1 != Function.prototype.bind.toString().indexOf("native code") ? goog.bind = goog.bindNative_ : goog.bind = goog.bindJs_;
  return goog.bind.apply(null, arguments);
};
goog.partial = function(a, b) {
  var c = Array.prototype.slice.call(arguments, 1);
  return function() {
    var b = c.slice();
    b.push.apply(b, arguments);
    return a.apply(this, b);
  };
};
goog.mixin = function(a, b) {
  for (var c in b) {
    a[c] = b[c];
  }
};
goog.now = goog.TRUSTED_SITE && Date.now || function() {
  return +new Date;
};
goog.globalEval = function(a) {
  if (goog.global.execScript) {
    goog.global.execScript(a, "JavaScript");
  } else {
    if (goog.global.eval) {
      if (null == goog.evalWorksForGlobals_) {
        if (goog.global.eval("var _evalTest_ = 1;"), "undefined" != typeof goog.global._evalTest_) {
          try {
            delete goog.global._evalTest_;
          } catch (d) {
          }
          goog.evalWorksForGlobals_ = !0;
        } else {
          goog.evalWorksForGlobals_ = !1;
        }
      }
      if (goog.evalWorksForGlobals_) {
        goog.global.eval(a);
      } else {
        var b = goog.global.document, c = b.createElement("SCRIPT");
        c.type = "text/javascript";
        c.defer = !1;
        c.appendChild(b.createTextNode(a));
        b.body.appendChild(c);
        b.body.removeChild(c);
      }
    } else {
      throw Error("goog.globalEval not available");
    }
  }
};
goog.evalWorksForGlobals_ = null;
goog.getCssName = function(a, b) {
  var c = function(a) {
    return goog.cssNameMapping_[a] || a;
  }, d = function(a) {
    a = a.split("-");
    for (var b = [], d = 0;d < a.length;d++) {
      b.push(c(a[d]));
    }
    return b.join("-");
  }, d = goog.cssNameMapping_ ? "BY_WHOLE" == goog.cssNameMappingStyle_ ? c : d : function(a) {
    return a;
  };
  return b ? a + "-" + d(b) : d(a);
};
goog.setCssNameMapping = function(a, b) {
  goog.cssNameMapping_ = a;
  goog.cssNameMappingStyle_ = b;
};
!COMPILED && goog.global.CLOSURE_CSS_NAME_MAPPING && (goog.cssNameMapping_ = goog.global.CLOSURE_CSS_NAME_MAPPING);
goog.getMsg = function(a, b) {
  b && (a = a.replace(/\{\$([^}]+)}/g, function(a, d) {
    return null != b && d in b ? b[d] : a;
  }));
  return a;
};
goog.getMsgWithFallback = function(a, b) {
  return a;
};
goog.exportSymbol = function(a, b, c) {
  goog.exportPath_(a, b, c);
};
goog.exportProperty = function(a, b, c) {
  a[b] = c;
};
goog.inherits = function(a, b) {
  function c() {
  }
  c.prototype = b.prototype;
  a.superClass_ = b.prototype;
  a.prototype = new c;
  a.prototype.constructor = a;
  a.base = function(a, c, f) {
    for (var g = Array(arguments.length - 2), h = 2;h < arguments.length;h++) {
      g[h - 2] = arguments[h];
    }
    return b.prototype[c].apply(a, g);
  };
};
goog.base = function(a, b, c) {
  var d = arguments.callee.caller;
  if (goog.STRICT_MODE_COMPATIBLE || goog.DEBUG && !d) {
    throw Error("arguments.caller not defined.  goog.base() cannot be used with strict mode code. See http://www.ecma-international.org/ecma-262/5.1/#sec-C");
  }
  if (d.superClass_) {
    for (var e = Array(arguments.length - 1), f = 1;f < arguments.length;f++) {
      e[f - 1] = arguments[f];
    }
    return d.superClass_.constructor.apply(a, e);
  }
  e = Array(arguments.length - 2);
  for (f = 2;f < arguments.length;f++) {
    e[f - 2] = arguments[f];
  }
  for (var f = !1, g = a.constructor;g;g = g.superClass_ && g.superClass_.constructor) {
    if (g.prototype[b] === d) {
      f = !0;
    } else {
      if (f) {
        return g.prototype[b].apply(a, e);
      }
    }
  }
  if (a[b] === d) {
    return a.constructor.prototype[b].apply(a, e);
  }
  throw Error("goog.base called from a method of one name to a method of a different name");
};
goog.scope = function(a) {
  if (goog.isInModuleLoader_()) {
    throw Error("goog.scope is not supported within a goog.module.");
  }
  a.call(goog.global);
};
COMPILED || (goog.global.COMPILED = COMPILED);
goog.defineClass = function(a, b) {
  var c = b.constructor, d = b.statics;
  c && c != Object.prototype.constructor || (c = function() {
    throw Error("cannot instantiate an interface (no constructor defined).");
  });
  c = goog.defineClass.createSealingConstructor_(c, a);
  a && goog.inherits(c, a);
  delete b.constructor;
  delete b.statics;
  goog.defineClass.applyProperties_(c.prototype, b);
  null != d && (d instanceof Function ? d(c) : goog.defineClass.applyProperties_(c, d));
  return c;
};
goog.defineClass.SEAL_CLASS_INSTANCES = goog.DEBUG;
goog.defineClass.createSealingConstructor_ = function(a, b) {
  if (!goog.defineClass.SEAL_CLASS_INSTANCES) {
    return a;
  }
  var c = !goog.defineClass.isUnsealable_(b), d = function() {
    var b = a.apply(this, arguments) || this;
    b[goog.UID_PROPERTY_] = b[goog.UID_PROPERTY_];
    this.constructor === d && c && Object.seal instanceof Function && Object.seal(b);
    return b;
  };
  return d;
};
goog.defineClass.isUnsealable_ = function(a) {
  return a && a.prototype && a.prototype[goog.UNSEALABLE_CONSTRUCTOR_PROPERTY_];
};
goog.defineClass.OBJECT_PROTOTYPE_FIELDS_ = "constructor hasOwnProperty isPrototypeOf propertyIsEnumerable toLocaleString toString valueOf".split(" ");
goog.defineClass.applyProperties_ = function(a, b) {
  for (var c in b) {
    Object.prototype.hasOwnProperty.call(b, c) && (a[c] = b[c]);
  }
  for (var d = 0;d < goog.defineClass.OBJECT_PROTOTYPE_FIELDS_.length;d++) {
    c = goog.defineClass.OBJECT_PROTOTYPE_FIELDS_[d], Object.prototype.hasOwnProperty.call(b, c) && (a[c] = b[c]);
  }
};
goog.tagUnsealableClass = function(a) {
  !COMPILED && goog.defineClass.SEAL_CLASS_INSTANCES && (a.prototype[goog.UNSEALABLE_CONSTRUCTOR_PROPERTY_] = !0);
};
goog.UNSEALABLE_CONSTRUCTOR_PROPERTY_ = "goog_defineClass_legacy_unsealable";
var axs = {};
axs.browserUtils = {};
axs.browserUtils.matchSelector = function(a, b) {
  return a.matches ? a.matches(b) : a.webkitMatchesSelector ? a.webkitMatchesSelector(b) : a.mozMatchesSelector ? a.mozMatchesSelector(b) : a.msMatchesSelector ? a.msMatchesSelector(b) : !1;
};
axs.constants = {};
axs.constants.ARIA_ROLES = {alert:{namefrom:["author"], parent:["region"]}, alertdialog:{namefrom:["author"], namerequired:!0, parent:["alert", "dialog"]}, application:{namefrom:["author"], namerequired:!0, parent:["landmark"]}, article:{namefrom:["author"], parent:["document", "region"]}, banner:{namefrom:["author"], parent:["landmark"]}, button:{childpresentational:!0, namefrom:["contents", "author"], namerequired:!0, parent:["command"], properties:["aria-expanded", "aria-pressed"]}, checkbox:{namefrom:["contents", 
"author"], namerequired:!0, parent:["input"], requiredProperties:["aria-checked"], properties:["aria-checked"]}, columnheader:{namefrom:["contents", "author"], namerequired:!0, parent:["gridcell", "sectionhead", "widget"], properties:["aria-sort"], scope:["row"]}, combobox:{mustcontain:["listbox", "textbox"], namefrom:["author"], namerequired:!0, parent:["select"], requiredProperties:["aria-expanded"], properties:["aria-expanded", "aria-autocomplete", "aria-required"]}, command:{"abstract":!0, namefrom:["author"], 
parent:["widget"]}, complementary:{namefrom:["author"], parent:["landmark"]}, composite:{"abstract":!0, childpresentational:!1, namefrom:["author"], parent:["widget"], properties:["aria-activedescendant"]}, contentinfo:{namefrom:["author"], parent:["landmark"]}, definition:{namefrom:["author"], parent:["section"]}, dialog:{namefrom:["author"], namerequired:!0, parent:["window"]}, directory:{namefrom:["contents", "author"], parent:["list"]}, document:{namefrom:[" author"], namerequired:!0, parent:["structure"], 
properties:["aria-expanded"]}, form:{namefrom:["author"], parent:["landmark"]}, grid:{mustcontain:["row", "rowgroup"], namefrom:["author"], namerequired:!0, parent:["composite", "region"], properties:["aria-level", "aria-multiselectable", "aria-readonly"]}, gridcell:{namefrom:["contents", "author"], namerequired:!0, parent:["section", "widget"], properties:["aria-readonly", "aria-required", "aria-selected"], scope:["row"]}, group:{namefrom:[" author"], parent:["section"], properties:["aria-activedescendant"]}, 
heading:{namerequired:!0, parent:["sectionhead"], properties:["aria-level"]}, img:{childpresentational:!0, namefrom:["author"], namerequired:!0, parent:["section"]}, input:{"abstract":!0, namefrom:["author"], parent:["widget"]}, landmark:{"abstract":!0, namefrom:["contents", "author"], namerequired:!1, parent:["region"]}, link:{namefrom:["contents", "author"], namerequired:!0, parent:["command"], properties:["aria-expanded"]}, list:{mustcontain:["group", "listitem"], namefrom:["author"], parent:["region"]}, 
listbox:{mustcontain:["option"], namefrom:["author"], namerequired:!0, parent:["list", "select"], properties:["aria-multiselectable", "aria-required"]}, listitem:{namefrom:["contents", "author"], namerequired:!0, parent:["section"], properties:["aria-level", "aria-posinset", "aria-setsize"], scope:["list"]}, log:{namefrom:[" author"], namerequired:!0, parent:["region"]}, main:{namefrom:["author"], parent:["landmark"]}, marquee:{namerequired:!0, parent:["section"]}, math:{childpresentational:!0, namefrom:["author"], 
parent:["section"]}, menu:{mustcontain:["group", "menuitemradio", "menuitem", "menuitemcheckbox"], namefrom:["author"], namerequired:!0, parent:["list", "select"]}, menubar:{namefrom:["author"], parent:["menu"]}, menuitem:{namefrom:["contents", "author"], namerequired:!0, parent:["command"], scope:["menu", "menubar"]}, menuitemcheckbox:{namefrom:["contents", "author"], namerequired:!0, parent:["checkbox", "menuitem"], scope:["menu", "menubar"]}, menuitemradio:{namefrom:["contents", "author"], namerequired:!0, 
parent:["menuitemcheckbox", "radio"], scope:["menu", "menubar"]}, navigation:{namefrom:["author"], parent:["landmark"]}, note:{namefrom:["author"], parent:["section"]}, option:{namefrom:["contents", "author"], namerequired:!0, parent:["input"], properties:["aria-checked", "aria-posinset", "aria-selected", "aria-setsize"]}, presentation:{parent:["structure"]}, progressbar:{childpresentational:!0, namefrom:["author"], namerequired:!0, parent:["range"]}, radio:{namefrom:["contents", "author"], namerequired:!0, 
parent:["checkbox", "option"]}, radiogroup:{mustcontain:["radio"], namefrom:["author"], namerequired:!0, parent:["select"], properties:["aria-required"]}, range:{"abstract":!0, namefrom:["author"], parent:["widget"], properties:["aria-valuemax", "aria-valuemin", "aria-valuenow", "aria-valuetext"]}, region:{namefrom:[" author"], parent:["section"]}, roletype:{"abstract":!0, properties:"aria-atomic aria-busy aria-controls aria-describedby aria-disabled aria-dropeffect aria-flowto aria-grabbed aria-haspopup aria-hidden aria-invalid aria-label aria-labelledby aria-live aria-owns aria-relevant".split(" ")}, 
row:{mustcontain:["columnheader", "gridcell", "rowheader"], namefrom:["contents", "author"], parent:["group", "widget"], properties:["aria-level", "aria-selected"], scope:["grid", "rowgroup", "treegrid"]}, rowgroup:{mustcontain:["row"], namefrom:["contents", "author"], parent:["group"], scope:["grid"]}, rowheader:{namefrom:["contents", "author"], namerequired:!0, parent:["gridcell", "sectionhead", "widget"], properties:["aria-sort"], scope:["row"]}, search:{namefrom:["author"], parent:["landmark"]}, 
section:{"abstract":!0, namefrom:["contents", "author"], parent:["structure"], properties:["aria-expanded"]}, sectionhead:{"abstract":!0, namefrom:["contents", "author"], parent:["structure"], properties:["aria-expanded"]}, select:{"abstract":!0, namefrom:["author"], parent:["composite", "group", "input"]}, separator:{childpresentational:!0, namefrom:["author"], parent:["structure"], properties:["aria-expanded", "aria-orientation"]}, scrollbar:{childpresentational:!0, namefrom:["author"], namerequired:!1, 
parent:["input", "range"], requiredProperties:["aria-controls", "aria-orientation", "aria-valuemax", "aria-valuemin", "aria-valuenow"], properties:["aria-controls", "aria-orientation", "aria-valuemax", "aria-valuemin", "aria-valuenow"]}, slider:{childpresentational:!0, namefrom:["author"], namerequired:!0, parent:["input", "range"], requiredProperties:["aria-valuemax", "aria-valuemin", "aria-valuenow"], properties:["aria-valuemax", "aria-valuemin", "aria-valuenow", "aria-orientation"]}, spinbutton:{namefrom:["author"], 
namerequired:!0, parent:["input", "range"], requiredProperties:["aria-valuemax", "aria-valuemin", "aria-valuenow"], properties:["aria-valuemax", "aria-valuemin", "aria-valuenow", "aria-required"]}, status:{parent:["region"]}, structure:{"abstract":!0, parent:["roletype"]}, tab:{namefrom:["contents", "author"], parent:["sectionhead", "widget"], properties:["aria-selected"], scope:["tablist"]}, tablist:{mustcontain:["tab"], namefrom:["author"], parent:["composite", "directory"], properties:["aria-level"]}, 
tabpanel:{namefrom:["author"], namerequired:!0, parent:["region"]}, textbox:{namefrom:["author"], namerequired:!0, parent:["input"], properties:["aria-activedescendant", "aria-autocomplete", "aria-multiline", "aria-readonly", "aria-required"]}, timer:{namefrom:["author"], namerequired:!0, parent:["status"]}, toolbar:{namefrom:["author"], parent:["group"]}, tooltip:{namerequired:!0, parent:["section"]}, tree:{mustcontain:["group", "treeitem"], namefrom:["author"], namerequired:!0, parent:["select"], 
properties:["aria-multiselectable", "aria-required"]}, treegrid:{mustcontain:["row"], namefrom:["author"], namerequired:!0, parent:["grid", "tree"]}, treeitem:{namefrom:["contents", "author"], namerequired:!0, parent:["listitem", "option"], scope:["group", "tree"]}, widget:{"abstract":!0, parent:["roletype"]}, window:{"abstract":!0, namefrom:[" author"], parent:["roletype"], properties:["aria-expanded"]}};
axs.constants.WIDGET_ROLES = {};
axs.constants.addAllParentRolesToSet_ = function(a, b) {
  if (a.parent) {
    for (var c = a.parent, d = 0;d < c.length;d++) {
      var e = c[d];
      b[e] = !0;
      axs.constants.addAllParentRolesToSet_(axs.constants.ARIA_ROLES[e], b);
    }
  }
};
axs.constants.addAllPropertiesToSet_ = function(a, b, c) {
  var d = a[b];
  if (d) {
    for (var e = 0;e < d.length;e++) {
      c[d[e]] = !0;
    }
  }
  if (a.parent) {
    for (a = a.parent, d = 0;d < a.length;d++) {
      axs.constants.addAllPropertiesToSet_(axs.constants.ARIA_ROLES[a[d]], b, c);
    }
  }
};
for (var roleName in axs.constants.ARIA_ROLES) {
  var role = axs.constants.ARIA_ROLES[roleName], propertiesSet = {};
  axs.constants.addAllPropertiesToSet_(role, "properties", propertiesSet);
  role.propertiesSet = propertiesSet;
  var requiredPropertiesSet = {};
  axs.constants.addAllPropertiesToSet_(role, "requiredProperties", requiredPropertiesSet);
  role.requiredPropertiesSet = requiredPropertiesSet;
  var parentRolesSet = {};
  axs.constants.addAllParentRolesToSet_(role, parentRolesSet);
  role.allParentRolesSet = parentRolesSet;
  "widget" in parentRolesSet && (axs.constants.WIDGET_ROLES[roleName] = role);
}
axs.constants.ARIA_PROPERTIES = {activedescendant:{type:"property", valueType:"idref"}, atomic:{defaultValue:"false", type:"property", valueType:"boolean"}, autocomplete:{defaultValue:"none", type:"property", valueType:"token", values:["inline", "list", "both", "none"]}, busy:{defaultValue:"false", type:"state", valueType:"boolean"}, checked:{defaultValue:"undefined", type:"state", valueType:"token", values:["true", "false", "mixed", "undefined"]}, controls:{type:"property", valueType:"idref_list"}, 
describedby:{type:"property", valueType:"idref_list"}, disabled:{defaultValue:"false", type:"state", valueType:"boolean"}, dropeffect:{defaultValue:"none", type:"property", valueType:"token_list", values:"copy move link execute popup none".split(" ")}, expanded:{defaultValue:"undefined", type:"state", valueType:"token", values:["true", "false", "undefined"]}, flowto:{type:"property", valueType:"idref_list"}, grabbed:{defaultValue:"undefined", type:"state", valueType:"token", values:["true", "false", 
"undefined"]}, haspopup:{defaultValue:"false", type:"property", valueType:"boolean"}, hidden:{defaultValue:"false", type:"state", valueType:"boolean"}, invalid:{defaultValue:"false", type:"state", valueType:"token", values:["grammar", "false", "spelling", "true"]}, label:{type:"property", valueType:"string"}, labelledby:{type:"property", valueType:"idref_list"}, level:{type:"property", valueType:"integer"}, live:{defaultValue:"off", type:"property", valueType:"token", values:["off", "polite", "assertive"]}, 
multiline:{defaultValue:"false", type:"property", valueType:"boolean"}, multiselectable:{defaultValue:"false", type:"property", valueType:"boolean"}, orientation:{defaultValue:"vertical", type:"property", valueType:"token", values:["horizontal", "vertical"]}, owns:{type:"property", valueType:"idref_list"}, posinset:{type:"property", valueType:"integer"}, pressed:{defaultValue:"undefined", type:"state", valueType:"token", values:["true", "false", "mixed", "undefined"]}, readonly:{defaultValue:"false", 
type:"property", valueType:"boolean"}, relevant:{defaultValue:"additions text", type:"property", valueType:"token_list", values:["additions", "removals", "text", "all"]}, required:{defaultValue:"false", type:"property", valueType:"boolean"}, selected:{defaultValue:"undefined", type:"state", valueType:"token", values:["true", "false", "undefined"]}, setsize:{type:"property", valueType:"integer"}, sort:{defaultValue:"none", type:"property", valueType:"token", values:["ascending", "descending", "none", 
"other"]}, valuemax:{type:"property", valueType:"decimal"}, valuemin:{type:"property", valueType:"decimal"}, valuenow:{type:"property", valueType:"decimal"}, valuetext:{type:"property", valueType:"string"}};
(function() {
  for (var a in axs.constants.ARIA_PROPERTIES) {
    var b = axs.constants.ARIA_PROPERTIES[a];
    if (b.values) {
      for (var c = {}, d = 0;d < b.values.length;d++) {
        c[b.values[d]] = !0;
      }
      b.valuesSet = c;
    }
  }
})();
axs.constants.GLOBAL_PROPERTIES = axs.constants.ARIA_ROLES.roletype.propertiesSet;
axs.constants.NO_ROLE_NAME = " ";
axs.constants.WIDGET_ROLE_TO_NAME = {alert:"aria_role_alert", alertdialog:"aria_role_alertdialog", button:"aria_role_button", checkbox:"aria_role_checkbox", columnheader:"aria_role_columnheader", combobox:"aria_role_combobox", dialog:"aria_role_dialog", grid:"aria_role_grid", gridcell:"aria_role_gridcell", link:"aria_role_link", listbox:"aria_role_listbox", log:"aria_role_log", marquee:"aria_role_marquee", menu:"aria_role_menu", menubar:"aria_role_menubar", menuitem:"aria_role_menuitem", menuitemcheckbox:"aria_role_menuitemcheckbox", 
menuitemradio:"aria_role_menuitemradio", option:axs.constants.NO_ROLE_NAME, progressbar:"aria_role_progressbar", radio:"aria_role_radio", radiogroup:"aria_role_radiogroup", rowheader:"aria_role_rowheader", scrollbar:"aria_role_scrollbar", slider:"aria_role_slider", spinbutton:"aria_role_spinbutton", status:"aria_role_status", tab:"aria_role_tab", tabpanel:"aria_role_tabpanel", textbox:"aria_role_textbox", timer:"aria_role_timer", toolbar:"aria_role_toolbar", tooltip:"aria_role_tooltip", treeitem:"aria_role_treeitem"};
axs.constants.STRUCTURE_ROLE_TO_NAME = {article:"aria_role_article", application:"aria_role_application", banner:"aria_role_banner", columnheader:"aria_role_columnheader", complementary:"aria_role_complementary", contentinfo:"aria_role_contentinfo", definition:"aria_role_definition", directory:"aria_role_directory", document:"aria_role_document", form:"aria_role_form", group:"aria_role_group", heading:"aria_role_heading", img:"aria_role_img", list:"aria_role_list", listitem:"aria_role_listitem", 
main:"aria_role_main", math:"aria_role_math", navigation:"aria_role_navigation", note:"aria_role_note", region:"aria_role_region", rowheader:"aria_role_rowheader", search:"aria_role_search", separator:"aria_role_separator"};
axs.constants.ATTRIBUTE_VALUE_TO_STATUS = [{name:"aria-autocomplete", values:{inline:"aria_autocomplete_inline", list:"aria_autocomplete_list", both:"aria_autocomplete_both"}}, {name:"aria-checked", values:{"true":"aria_checked_true", "false":"aria_checked_false", mixed:"aria_checked_mixed"}}, {name:"aria-disabled", values:{"true":"aria_disabled_true"}}, {name:"aria-expanded", values:{"true":"aria_expanded_true", "false":"aria_expanded_false"}}, {name:"aria-invalid", values:{"true":"aria_invalid_true", 
grammar:"aria_invalid_grammar", spelling:"aria_invalid_spelling"}}, {name:"aria-multiline", values:{"true":"aria_multiline_true"}}, {name:"aria-multiselectable", values:{"true":"aria_multiselectable_true"}}, {name:"aria-pressed", values:{"true":"aria_pressed_true", "false":"aria_pressed_false", mixed:"aria_pressed_mixed"}}, {name:"aria-readonly", values:{"true":"aria_readonly_true"}}, {name:"aria-required", values:{"true":"aria_required_true"}}, {name:"aria-selected", values:{"true":"aria_selected_true", 
"false":"aria_selected_false"}}];
axs.constants.INPUT_TYPE_TO_INFORMATION_TABLE_MSG = {button:"input_type_button", checkbox:"input_type_checkbox", color:"input_type_color", datetime:"input_type_datetime", "datetime-local":"input_type_datetime_local", date:"input_type_date", email:"input_type_email", file:"input_type_file", image:"input_type_image", month:"input_type_month", number:"input_type_number", password:"input_type_password", radio:"input_type_radio", range:"input_type_range", reset:"input_type_reset", search:"input_type_search", 
submit:"input_type_submit", tel:"input_type_tel", text:"input_type_text", url:"input_type_url", week:"input_type_week"};
axs.constants.TAG_TO_INFORMATION_TABLE_VERBOSE_MSG = {A:"tag_link", BUTTON:"tag_button", H1:"tag_h1", H2:"tag_h2", H3:"tag_h3", H4:"tag_h4", H5:"tag_h5", H6:"tag_h6", LI:"tag_li", OL:"tag_ol", SELECT:"tag_select", TEXTAREA:"tag_textarea", UL:"tag_ul", SECTION:"tag_section", NAV:"tag_nav", ARTICLE:"tag_article", ASIDE:"tag_aside", HGROUP:"tag_hgroup", HEADER:"tag_header", FOOTER:"tag_footer", TIME:"tag_time", MARK:"tag_mark"};
axs.constants.TAG_TO_INFORMATION_TABLE_BRIEF_MSG = {BUTTON:"tag_button", SELECT:"tag_select", TEXTAREA:"tag_textarea"};
axs.constants.MIXED_VALUES = {"true":!0, "false":!0, mixed:!0};
axs.constants.Severity = {INFO:"Info", WARNING:"Warning", SEVERE:"Severe"};
axs.constants.AuditResult = {PASS:"PASS", FAIL:"FAIL", NA:"NA"};
axs.constants.InlineElements = {TT:!0, I:!0, B:!0, BIG:!0, SMALL:!0, EM:!0, STRONG:!0, DFN:!0, CODE:!0, SAMP:!0, KBD:!0, VAR:!0, CITE:!0, ABBR:!0, ACRONYM:!0, A:!0, IMG:!0, OBJECT:!0, BR:!0, SCRIPT:!0, MAP:!0, Q:!0, SUB:!0, SUP:!0, SPAN:!0, BDO:!0, INPUT:!0, SELECT:!0, TEXTAREA:!0, LABEL:!0, BUTTON:!0};
axs.constants.NATIVELY_DISABLEABLE = {BUTTON:!0, INPUT:!0, SELECT:!0, TEXTAREA:!0, FIELDSET:!0, OPTGROUP:!0, OPTION:!0};
axs.constants.ARIA_TO_HTML_ATTRIBUTE = {"aria-checked":"checked", "aria-disabled":"disabled", "aria-hidden":"hidden", "aria-expanded":"open", "aria-valuemax":"max", "aria-valuemin":"min", "aria-readonly":"readonly", "aria-required":"required", "aria-selected":"selected", "aria-valuenow":"value"};
axs.constants.TAG_TO_IMPLICIT_SEMANTIC_INFO = {A:[{role:"link", allowed:"button checkbox menuitem menuitemcheckbox menuitemradio tab treeitem".split(" "), selector:"a[href]"}], ADDRESS:[{role:"", allowed:["contentinfo", "presentation"]}], AREA:[{role:"link", selector:"area[href]"}], ARTICLE:[{role:"article", allowed:["presentation", "article", "document", "application", "main"]}], ASIDE:[{role:"complementary", allowed:["note", "complementary", "search", "presentation"]}], AUDIO:[{role:"", allowed:["application", 
"presentation"]}], BASE:[{role:"", reserved:!0}], BODY:[{role:"document", allowed:["presentation"]}], BUTTON:[{role:"button", allowed:["link", "menuitem", "menuitemcheckbox", "menuitemradio", "radio"], selector:'button:not([aria-pressed]):not([type="menu"])'}, {role:"button", allowed:["button"], selector:"button[aria-pressed]"}, {role:"button", attributes:{"aria-haspopup":!0}, allowed:["link", "menuitem", "menuitemcheckbox", "menuitemradio", "radio"], selector:'button[type="menu"]'}], CAPTION:[{role:"", 
allowed:["presentation"]}], COL:[{role:"", reserved:!0}], COLGROUP:[{role:"", reserved:!0}], DATALIST:[{role:"listbox", attributes:{"aria-multiselectable":!1}, allowed:["presentation"]}], DEL:[{role:"", allowed:["*"]}], DD:[{role:"", allowed:["presentation"]}], DT:[{role:"", allowed:["presentation"]}], DETAILS:[{role:"group", allowed:["group", "presentation"]}], DIALOG:[{role:"dialog", allowed:"dialog alert alertdialog application log marquee status".split(" "), selector:"dialog[open]"}, {role:"dialog", 
attributes:{"aria-hidden":!0}, allowed:"dialog alert alertdialog application log marquee status".split(" "), selector:"dialog:not([open])"}], DIV:[{role:"", allowed:["*"]}], DL:[{role:"list", allowed:["presentation"]}], EMBED:[{role:"", allowed:["application", "document", "img", "presentation"]}], FIGURE:[{role:"", allowed:["*"]}], FOOTER:[{role:"", allowed:["contentinfo", "presentation"]}], FORM:[{role:"form", allowed:["presentation"]}], P:[{role:"", allowed:["*"]}], PRE:[{role:"", allowed:["*"]}], 
BLOCKQUOTE:[{role:"", allowed:["*"]}], H1:[{role:"heading"}], H2:[{role:"heading"}], H3:[{role:"heading"}], H4:[{role:"heading"}], H5:[{role:"heading"}], H6:[{role:"heading"}], HEAD:[{role:"", reserved:!0}], HEADER:[{role:"", allowed:["banner", "presentation"]}], HR:[{role:"separator", allowed:["presentation"]}], HTML:[{role:"", reserved:!0}], IFRAME:[{role:"", allowed:["application", "document", "img", "presentation"], selector:"iframe:not([seamless])"}, {role:"", allowed:["application", "document", 
"img", "presentation", "group"], selector:"iframe[seamless]"}], IMG:[{role:"presentation", reserved:!0, selector:'img[alt=""]'}, {role:"img", allowed:["*"], selector:'img[alt]:not([alt=""])'}], INPUT:[{role:"button", allowed:["link", "menuitem", "menuitemcheckbox", "menuitemradio", "radio"], selector:'input[type="button"]:not([aria-pressed])'}, {role:"button", allowed:["button"], selector:'input[type="button"][aria-pressed]'}, {role:"checkbox", allowed:["checkbox"], selector:'input[type="checkbox"]'}, 
{role:"", selector:'input[type="color"]'}, {role:"", selector:'input[type="date"]'}, {role:"", selector:'input[type="datetime"]'}, {role:"textbox", selector:'input[type="email"]:not([list])'}, {role:"", selector:'input[type="file"]'}, {role:"", reserved:!0, selector:'input[type="hidden"]'}, {role:"button", allowed:["button"], selector:'input[type="image"][aria-pressed]'}, {role:"button", allowed:["link", "menuitem", "menuitemcheckbox", "menuitemradio", "radio"], selector:'input[type="image"]:not([aria-pressed])'}, 
{role:"", selector:'input[type="month"]'}, {role:"", selector:'input[type="number"]'}, {role:"textbox", selector:'input[type="password"]'}, {role:"radio", allowed:["menuitemradio"], selector:'input[type="radio"]'}, {role:"slider", selector:'input[type="range"]'}, {role:"button", selector:'input[type="reset"]'}, {role:"combobox", selector:'input[type="search"][list]'}, {role:"textbox", selector:'input[type="search"]:not([list])'}, {role:"button", selector:'input[type="submit"]'}, {role:"combobox", 
selector:'input[type="tel"][list]'}, {role:"textbox", selector:'input[type="tel"]:not([list])'}, {role:"combobox", selector:'input[type="text"][list]'}, {role:"textbox", selector:'input[type="text"]:not([list])'}, {role:"textbox", selector:"input:not([type])"}, {role:"", selector:'input[type="time"]'}, {role:"combobox", selector:'input[type="url"][list]'}, {role:"textbox", selector:'input[type="url"]:not([list])'}, {role:"", selector:'input[type="week"]'}], INS:[{role:"", allowed:["*"]}], KEYGEN:[{role:""}], 
LABEL:[{role:"", allowed:["presentation"]}], LI:[{role:"listitem", allowed:"menuitem menuitemcheckbox menuitemradio option tab treeitem presentation".split(" "), selector:'ol:not([role="presentation"])>li, ul:not([role="presentation"])>li'}, {role:"listitem", allowed:"listitem menuitem menuitemcheckbox menuitemradio option tab treeitem presentation".split(" "), selector:'ol[role="presentation"]>li, ul[role="presentation"]>li'}], LINK:[{role:"link", reserved:!0, selector:"link[href]"}], MAIN:[{role:"", 
allowed:["main", "presentation"]}], MAP:[{role:"", reserved:!0}], MATH:[{role:"", allowed:["presentation"]}], MENU:[{role:"toolbar", selector:'menu[type="toolbar"]'}], MENUITEM:[{role:"menuitem", selector:'menuitem[type="command"]'}, {role:"menuitemcheckbox", selector:'menuitem[type="checkbox"]'}, {role:"menuitemradio", selector:'menuitem[type="radio"]'}], META:[{role:"", reserved:!0}], METER:[{role:"progressbar", allowed:["presentation"]}], NAV:[{role:"navigation", allowed:["navigation", "presentation"]}], 
NOSCRIPT:[{role:"", reserved:!0}], OBJECT:[{role:"", allowed:["application", "document", "img", "presentation"]}], OL:[{role:"list", allowed:"directory group listbox menu menubar tablist toolbar tree presentation".split(" ")}], OPTGROUP:[{role:"", allowed:["presentation"]}], OPTION:[{role:"option"}], OUTPUT:[{role:"status", allowed:["*"]}], PARAM:[{role:"", reserved:!0}], PICTURE:[{role:"", reserved:!0}], PROGRESS:[{role:"progressbar", allowed:["presentation"]}], SCRIPT:[{role:"", reserved:!0}], 
SECTION:[{role:"region", allowed:"alert alertdialog application contentinfo dialog document log marquee search status presentation".split(" ")}], SELECT:[{role:"listbox"}], SOURCE:[{role:"", reserved:!0}], SPAN:[{role:"", allowed:["*"]}], STYLE:[{role:"", reserved:!0}], SVG:[{role:"", allowed:["application", "document", "img", "presentation"]}], SUMMARY:[{role:"", allowed:["presentation"]}], TABLE:[{role:"", allowed:["*"]}], TEMPLATE:[{role:"", reserved:!0}], TEXTAREA:[{role:"textbox"}], TBODY:[{role:"rowgroup", 
allowed:["*"]}], THEAD:[{role:"rowgroup", allowed:["*"]}], TFOOT:[{role:"rowgroup", allowed:["*"]}], TITLE:[{role:"", reserved:!0}], TD:[{role:"", allowed:["*"]}], TH:[{role:"", allowed:["*"]}], TR:[{role:"", allowed:["*"]}], TRACK:[{role:"", reserved:!0}], UL:[{role:"list", allowed:"directory group listbox menu menubar tablist toolbar tree presentation".split(" ")}], VIDEO:[{role:"", allowed:["application", "presentation"]}]};
axs.color = {};
axs.color.Color = function(a, b, c, d) {
  this.red = a;
  this.green = b;
  this.blue = c;
  this.alpha = d;
};
axs.color.YCbCr = function(a) {
  this.luma = this.z = a[0];
  this.Cb = this.x = a[1];
  this.Cr = this.y = a[2];
};
axs.color.YCbCr.prototype = {multiply:function(a) {
  return new axs.color.YCbCr([this.luma * a, this.Cb * a, this.Cr * a]);
}, add:function(a) {
  return new axs.color.YCbCr([this.luma + a.luma, this.Cb + a.Cb, this.Cr + a.Cr]);
}, subtract:function(a) {
  return new axs.color.YCbCr([this.luma - a.luma, this.Cb - a.Cb, this.Cr - a.Cr]);
}};
axs.color.calculateContrastRatio = function(a, b) {
  1 > a.alpha && (a = axs.color.flattenColors(a, b));
  var c = axs.color.calculateLuminance(a), d = axs.color.calculateLuminance(b);
  return (Math.max(c, d) + .05) / (Math.min(c, d) + .05);
};
axs.color.calculateLuminance = function(a) {
  return axs.color.toYCbCr(a).luma;
};
axs.color.luminanceRatio = function(a, b) {
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
};
axs.color.parseColor = function(a) {
  if ("transparent" === a) {
    return new axs.color.Color(0, 0, 0, 0);
  }
  var b = a.match(/^rgb\((\d+), (\d+), (\d+)\)$/);
  if (b) {
    a = parseInt(b[1], 10);
    var c = parseInt(b[2], 10), d = parseInt(b[3], 10);
    return new axs.color.Color(a, c, d, 1);
  }
  return (b = a.match(/^rgba\((\d+), (\d+), (\d+), (\d*(\.\d+)?)\)/)) ? (a = parseInt(b[1], 10), c = parseInt(b[2], 10), d = parseInt(b[3], 10), b = parseFloat(b[4]), new axs.color.Color(a, c, d, b)) : null;
};
axs.color.colorChannelToString = function(a) {
  a = Math.round(a);
  return 15 >= a ? "0" + a.toString(16) : a.toString(16);
};
axs.color.colorToString = function(a) {
  return 1 == a.alpha ? "#" + axs.color.colorChannelToString(a.red) + axs.color.colorChannelToString(a.green) + axs.color.colorChannelToString(a.blue) : "rgba(" + [a.red, a.green, a.blue, a.alpha].join() + ")";
};
axs.color.luminanceFromContrastRatio = function(a, b, c) {
  return c ? (a + .05) * b - .05 : (a + .05) / b - .05;
};
axs.color.translateColor = function(a, b) {
  for (var c = b > a.luma ? axs.color.WHITE_YCC : axs.color.BLACK_YCC, d = c == axs.color.WHITE_YCC ? axs.color.YCC_CUBE_FACES_WHITE : axs.color.YCC_CUBE_FACES_BLACK, e = new axs.color.YCbCr([0, a.Cb, a.Cr]), f = new axs.color.YCbCr([1, a.Cb, a.Cr]), f = {a:e, b:f}, e = null, g = 0;g < d.length && !(e = axs.color.findIntersection(f, d[g]), 0 <= e.z && 1 >= e.z);g++) {
  }
  if (!e) {
    throw "Couldn't find intersection with YCbCr color cube for Cb=" + a.Cb + ", Cr=" + a.Cr + ".";
  }
  if (e.x != a.x || e.y != a.y) {
    throw "Intersection has wrong Cb/Cr values.";
  }
  if (Math.abs(c.luma - e.luma) < Math.abs(c.luma - b)) {
    return c = [b, a.Cb, a.Cr], axs.color.fromYCbCrArray(c);
  }
  c = (b - e.luma) / (c.luma - e.luma);
  c = [b, e.Cb - e.Cb * c, e.Cr - e.Cr * c];
  return axs.color.fromYCbCrArray(c);
};
axs.color.suggestColors = function(a, b, c) {
  var d = {}, e = axs.color.calculateLuminance(a), f = axs.color.calculateLuminance(b), g = f > e, h = axs.color.toYCbCr(b), k = axs.color.toYCbCr(a), m;
  for (m in c) {
    var l = c[m], n = axs.color.luminanceFromContrastRatio(e, l + .02, g);
    if (1 >= n && 0 <= n) {
      var p = axs.color.translateColor(h, n), l = axs.color.calculateContrastRatio(p, a), n = {};
      n.fg = axs.color.colorToString(p);
      n.bg = axs.color.colorToString(a);
      n.contrast = l.toFixed(2);
      d[m] = n;
    } else {
      l = axs.color.luminanceFromContrastRatio(f, l + .02, !g), 1 >= l && 0 <= l && (p = axs.color.translateColor(k, l), l = axs.color.calculateContrastRatio(b, p), n = {}, n.bg = axs.color.colorToString(p), n.fg = axs.color.colorToString(b), n.contrast = l.toFixed(2), d[m] = n);
    }
  }
  return d;
};
axs.color.flattenColors = function(a, b) {
  var c = a.alpha;
  return new axs.color.Color((1 - c) * b.red + c * a.red, (1 - c) * b.green + c * a.green, (1 - c) * b.blue + c * a.blue, a.alpha + b.alpha * (1 - a.alpha));
};
axs.color.multiplyMatrixVector = function(a, b) {
  var c = b[0], d = b[1], e = b[2];
  return [a[0][0] * c + a[0][1] * d + a[0][2] * e, a[1][0] * c + a[1][1] * d + a[1][2] * e, a[2][0] * c + a[2][1] * d + a[2][2] * e];
};
axs.color.toYCbCr = function(a) {
  var b = a.red / 255, c = a.green / 255;
  a = a.blue / 255;
  return new axs.color.YCbCr(axs.color.multiplyMatrixVector(axs.color.YCC_MATRIX, [.03928 >= b ? b / 12.92 : Math.pow((b + .055) / 1.055, 2.4), .03928 >= c ? c / 12.92 : Math.pow((c + .055) / 1.055, 2.4), .03928 >= a ? a / 12.92 : Math.pow((a + .055) / 1.055, 2.4)]));
};
axs.color.fromYCbCr = function(a) {
  return axs.color.fromYCbCrArray([a.luma, a.Cb, a.Cr]);
};
axs.color.fromYCbCrArray = function(a) {
  var b = axs.color.multiplyMatrixVector(axs.color.INVERTED_YCC_MATRIX, a);
  a = b[0];
  var c = b[1], b = b[2];
  return new axs.color.Color(Math.min(Math.max(Math.round(255 * (.00303949 >= a ? 12.92 * a : 1.055 * Math.pow(a, 1 / 2.4) - .055)), 0), 255), Math.min(Math.max(Math.round(255 * (.00303949 >= c ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - .055)), 0), 255), Math.min(Math.max(Math.round(255 * (.00303949 >= b ? 12.92 * b : 1.055 * Math.pow(b, 1 / 2.4) - .055)), 0), 255), 1);
};
axs.color.RGBToYCbCrMatrix = function(a, b) {
  return [[a, 1 - a - b, b], [-a / (2 - 2 * b), (a + b - 1) / (2 - 2 * b), (1 - b) / (2 - 2 * b)], [(1 - a) / (2 - 2 * a), (a + b - 1) / (2 - 2 * a), -b / (2 - 2 * a)]];
};
axs.color.invert3x3Matrix = function(a) {
  var b = a[0][0], c = a[0][1], d = a[0][2], e = a[1][0], f = a[1][1], g = a[1][2], h = a[2][0], k = a[2][1];
  a = a[2][2];
  return axs.color.scalarMultiplyMatrix([[f * a - g * k, d * k - c * a, c * g - d * f], [g * h - e * a, b * a - d * h, d * e - b * g], [e * k - f * h, h * c - b * k, b * f - c * e]], 1 / (b * (f * a - g * k) - c * (a * e - g * h) + d * (e * k - f * h)));
};
axs.color.findIntersection = function(a, b) {
  var c = [a.a.x - b.p0.x, a.a.y - b.p0.y, a.a.z - b.p0.z], d = axs.color.invert3x3Matrix([[a.a.x - a.b.x, b.p1.x - b.p0.x, b.p2.x - b.p0.x], [a.a.y - a.b.y, b.p1.y - b.p0.y, b.p2.y - b.p0.y], [a.a.z - a.b.z, b.p1.z - b.p0.z, b.p2.z - b.p0.z]]), c = axs.color.multiplyMatrixVector(d, c)[0];
  return a.a.add(a.b.subtract(a.a).multiply(c));
};
axs.color.scalarMultiplyMatrix = function(a, b) {
  for (var c = [], d = 0;3 > d;d++) {
    c[d] = axs.color.scalarMultiplyVector(a[d], b);
  }
  return c;
};
axs.color.scalarMultiplyVector = function(a, b) {
  for (var c = [], d = 0;d < a.length;d++) {
    c[d] = a[d] * b;
  }
  return c;
};
axs.color.kR = .2126;
axs.color.kB = .0722;
axs.color.YCC_MATRIX = axs.color.RGBToYCbCrMatrix(axs.color.kR, axs.color.kB);
axs.color.INVERTED_YCC_MATRIX = axs.color.invert3x3Matrix(axs.color.YCC_MATRIX);
axs.color.BLACK = new axs.color.Color(0, 0, 0, 1);
axs.color.BLACK_YCC = axs.color.toYCbCr(axs.color.BLACK);
axs.color.WHITE = new axs.color.Color(255, 255, 255, 1);
axs.color.WHITE_YCC = axs.color.toYCbCr(axs.color.WHITE);
axs.color.RED = new axs.color.Color(255, 0, 0, 1);
axs.color.RED_YCC = axs.color.toYCbCr(axs.color.RED);
axs.color.GREEN = new axs.color.Color(0, 255, 0, 1);
axs.color.GREEN_YCC = axs.color.toYCbCr(axs.color.GREEN);
axs.color.BLUE = new axs.color.Color(0, 0, 255, 1);
axs.color.BLUE_YCC = axs.color.toYCbCr(axs.color.BLUE);
axs.color.CYAN = new axs.color.Color(0, 255, 255, 1);
axs.color.CYAN_YCC = axs.color.toYCbCr(axs.color.CYAN);
axs.color.MAGENTA = new axs.color.Color(255, 0, 255, 1);
axs.color.MAGENTA_YCC = axs.color.toYCbCr(axs.color.MAGENTA);
axs.color.YELLOW = new axs.color.Color(255, 255, 0, 1);
axs.color.YELLOW_YCC = axs.color.toYCbCr(axs.color.YELLOW);
axs.color.YCC_CUBE_FACES_BLACK = [{p0:axs.color.BLACK_YCC, p1:axs.color.RED_YCC, p2:axs.color.GREEN_YCC}, {p0:axs.color.BLACK_YCC, p1:axs.color.GREEN_YCC, p2:axs.color.BLUE_YCC}, {p0:axs.color.BLACK_YCC, p1:axs.color.BLUE_YCC, p2:axs.color.RED_YCC}];
axs.color.YCC_CUBE_FACES_WHITE = [{p0:axs.color.WHITE_YCC, p1:axs.color.CYAN_YCC, p2:axs.color.MAGENTA_YCC}, {p0:axs.color.WHITE_YCC, p1:axs.color.MAGENTA_YCC, p2:axs.color.YELLOW_YCC}, {p0:axs.color.WHITE_YCC, p1:axs.color.YELLOW_YCC, p2:axs.color.CYAN_YCC}];
axs.dom = {};
axs.dom.parentElement = function(a) {
  if (!a) {
    return null;
  }
  a = axs.dom.composedParentNode(a);
  if (!a) {
    return null;
  }
  switch(a.nodeType) {
    case Node.ELEMENT_NODE:
      return a;
    default:
      return axs.dom.parentElement(a);
  }
};
axs.dom.shadowHost = function(a) {
  return "host" in a ? a.host : null;
};
axs.dom.composedParentNode = function(a) {
  if (!a) {
    return null;
  }
  if (a.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
    return axs.dom.shadowHost(a);
  }
  var b = a.parentNode;
  if (!b) {
    return null;
  }
  if (b.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
    return axs.dom.shadowHost(b);
  }
  if (!b.shadowRoot) {
    return b;
  }
  a = a.getDestinationInsertionPoints();
  return 0 < a.length ? axs.dom.composedParentNode(a[a.length - 1]) : null;
};
axs.dom.asElement = function(a) {
  switch(a.nodeType) {
    case Node.COMMENT_NODE:
      break;
    case Node.ELEMENT_NODE:
      if ("script" == a.localName || "template" == a.localName) {
        break;
      }
      return a;
    case Node.DOCUMENT_FRAGMENT_NODE:
      return a.host;
    case Node.TEXT_NODE:
      return axs.dom.parentElement(a);
    default:
      console.warn("Unhandled node type: ", a.nodeType);
  }
  return null;
};
axs.dom.composedTreeSearch = function(a, b, c, d, e) {
  if (a === b) {
    return !0;
  }
  if (a.nodeType == Node.ELEMENT_NODE) {
    var f = a
  }
  var g = !1;
  d = Object.create(d);
  if (f) {
    var h = f.localName;
    d.collectIdRefs && (d.idrefs = axs.utils.getReferencedIds(f));
    if (!d.disabled || "legend" === h && axs.browserUtils.matchSelector(f, "fieldset>legend:first-of-type")) {
      d.disabled = axs.utils.isElementDisabled(f, !0);
    }
    d.hidden || (d.hidden = axs.utils.isElementHidden(f));
    if (c.preorder && !c.preorder(f, d)) {
      return g;
    }
    var k = f.shadowRoot || f.webkitShadowRoot;
    if (k) {
      return d.level++, g = axs.dom.composedTreeSearch(k, b, c, d, k), f && c.postorder && !g && c.postorder(f, d), g;
    }
    if ("content" == h) {
      a = f.getDistributedNodes();
      for (h = 0;h < a.length && !g;h++) {
        g = axs.dom.composedTreeSearch(a[h], b, c, d, e);
      }
      c.postorder && !g && c.postorder.call(null, f, d);
      return g;
    }
  }
  for (a = a.firstChild;null != a && !g;) {
    g = axs.dom.composedTreeSearch(a, b, c, d, e), a = a.nextSibling;
  }
  f && c.postorder && !g && c.postorder.call(null, f, d);
  return g;
};
axs.utils = {};
axs.utils.FOCUSABLE_ELEMENTS_SELECTOR = "input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled]),button:not([disabled]),a[href],iframe,[tabindex]";
axs.utils.LABELABLE_ELEMENTS_SELECTOR = "button,input:not([type=hidden]),keygen,meter,output,progress,select,textarea";
axs.utils.elementIsTransparent = function(a) {
  return "0" == a.style.opacity;
};
axs.utils.elementHasZeroArea = function(a) {
  a = a.getBoundingClientRect();
  var b = a.top - a.bottom;
  return a.right - a.left && b ? !1 : !0;
};
axs.utils.elementIsOutsideScrollArea = function(a) {
  for (var b = axs.dom.parentElement(a), c = a.ownerDocument.defaultView;b != c.document.body;) {
    if (axs.utils.isClippedBy(a, b)) {
      return !0;
    }
    if (axs.utils.canScrollTo(a, b) && !axs.utils.elementIsOutsideScrollArea(b)) {
      return !1;
    }
    b = axs.dom.parentElement(b);
  }
  return !axs.utils.canScrollTo(a, c.document.body);
};
axs.utils.canScrollTo = function(a, b) {
  var c = a.getBoundingClientRect(), d = b.getBoundingClientRect();
  if (b == b.ownerDocument.body) {
    var e = d.top, f = d.left
  } else {
    e = d.top - b.scrollTop, f = d.left - b.scrollLeft;
  }
  var g = e + b.scrollHeight, h = f + b.scrollWidth;
  if (c.right < f || c.bottom < e || c.left > h || c.top > g) {
    return !1;
  }
  e = a.ownerDocument.defaultView;
  f = e.getComputedStyle(b);
  return c.left > d.right || c.top > d.bottom ? "scroll" == f.overflow || "auto" == f.overflow || b instanceof e.HTMLBodyElement : !0;
};
axs.utils.isClippedBy = function(a, b) {
  var c = a.getBoundingClientRect(), d = b.getBoundingClientRect(), e = d.top - b.scrollTop, f = d.left - b.scrollLeft, g = a.ownerDocument.defaultView.getComputedStyle(b);
  return (c.right < d.left || c.bottom < d.top || c.left > d.right || c.top > d.bottom) && "hidden" == g.overflow ? !0 : c.right < f || c.bottom < e ? "visible" != g.overflow : !1;
};
axs.utils.isAncestor = function(a, b) {
  if (null == b) {
    return !1;
  }
  if (b === a) {
    return !0;
  }
  var c = axs.dom.composedParentNode(b);
  return axs.utils.isAncestor(a, c);
};
axs.utils.overlappingElements = function(a) {
  if (axs.utils.elementHasZeroArea(a)) {
    return null;
  }
  for (var b = [], c = a.getClientRects(), d = 0;d < c.length;d++) {
    var e = c[d], e = document.elementFromPoint((e.left + e.right) / 2, (e.top + e.bottom) / 2);
    if (null != e && e != a && !axs.utils.isAncestor(e, a) && !axs.utils.isAncestor(a, e)) {
      var f = window.getComputedStyle(e, null);
      f && (f = axs.utils.getBgColor(f, e)) && 0 < f.alpha && 0 > b.indexOf(e) && b.push(e);
    }
  }
  return b;
};
axs.utils.elementIsHtmlControl = function(a) {
  var b = a.ownerDocument.defaultView;
  return a instanceof b.HTMLButtonElement || a instanceof b.HTMLInputElement || a instanceof b.HTMLSelectElement || a instanceof b.HTMLTextAreaElement ? !0 : !1;
};
axs.utils.elementIsAriaWidget = function(a) {
  return a.hasAttribute("role") && (a = a.getAttribute("role")) && (a = axs.constants.ARIA_ROLES[a]) && "widget" in a.allParentRolesSet ? !0 : !1;
};
axs.utils.elementIsVisible = function(a) {
  return axs.utils.elementIsTransparent(a) || axs.utils.elementHasZeroArea(a) || axs.utils.elementIsOutsideScrollArea(a) || axs.utils.overlappingElements(a).length ? !1 : !0;
};
axs.utils.isLargeFont = function(a) {
  var b = a.fontSize;
  a = "bold" == a.fontWeight;
  var c = b.match(/(\d+)px/);
  if (c) {
    b = parseInt(c[1], 10);
    if (c = window.getComputedStyle(document.body, null).fontSize.match(/(\d+)px/)) {
      var d = parseInt(c[1], 10), c = 1.2 * d, d = 1.5 * d
    } else {
      c = 19.2, d = 24;
    }
    return a && b >= c || b >= d;
  }
  if (c = b.match(/(\d+)em/)) {
    return b = parseInt(c[1], 10), a && 1.2 <= b || 1.5 <= b ? !0 : !1;
  }
  if (c = b.match(/(\d+)%/)) {
    return b = parseInt(c[1], 10), a && 120 <= b || 150 <= b ? !0 : !1;
  }
  if (c = b.match(/(\d+)pt/)) {
    if (b = parseInt(c[1], 10), a && 14 <= b || 18 <= b) {
      return !0;
    }
  }
  return !1;
};
axs.utils.getBgColor = function(a, b) {
  var c = axs.color.parseColor(a.backgroundColor);
  if (!c) {
    return null;
  }
  1 > a.opacity && (c.alpha *= a.opacity);
  if (1 > c.alpha) {
    var d = axs.utils.getParentBgColor(b);
    if (null == d) {
      return null;
    }
    c = axs.color.flattenColors(c, d);
  }
  return c;
};
axs.utils.getParentBgColor = function(a) {
  var b = a;
  a = [];
  for (var c = null;b = axs.dom.parentElement(b);) {
    var d = window.getComputedStyle(b, null);
    if (d) {
      var e = axs.color.parseColor(d.backgroundColor);
      if (e && (1 > d.opacity && (e.alpha *= d.opacity), 0 != e.alpha && (a.push(e), 1 == e.alpha))) {
        c = !0;
        break;
      }
    }
  }
  c || a.push(new axs.color.Color(255, 255, 255, 1));
  for (b = a.pop();a.length;) {
    c = a.pop(), b = axs.color.flattenColors(c, b);
  }
  return b;
};
axs.utils.getFgColor = function(a, b, c) {
  var d = axs.color.parseColor(a.color);
  if (!d) {
    return null;
  }
  1 > d.alpha && (d = axs.color.flattenColors(d, c));
  1 > a.opacity && (b = axs.utils.getParentBgColor(b), d.alpha *= a.opacity, d = axs.color.flattenColors(d, b));
  return d;
};
axs.utils.getContrastRatioForElement = function(a) {
  var b = window.getComputedStyle(a, null);
  return axs.utils.getContrastRatioForElementWithComputedStyle(b, a);
};
axs.utils.getContrastRatioForElementWithComputedStyle = function(a, b) {
  if (axs.utils.isElementHidden(b)) {
    return null;
  }
  var c = axs.utils.getBgColor(a, b);
  if (!c) {
    return null;
  }
  var d = axs.utils.getFgColor(a, b, c);
  return d ? axs.color.calculateContrastRatio(d, c) : null;
};
axs.utils.isNativeTextElement = function(a) {
  var b = a.tagName.toLowerCase();
  a = a.type ? a.type.toLowerCase() : "";
  if ("textarea" == b) {
    return !0;
  }
  if ("input" != b) {
    return !1;
  }
  switch(a) {
    case "email":
    ;
    case "number":
    ;
    case "password":
    ;
    case "search":
    ;
    case "text":
    ;
    case "tel":
    ;
    case "url":
    ;
    case "":
      return !0;
    default:
      return !1;
  }
};
axs.utils.isLowContrast = function(a, b, c) {
  a = Math.round(10 * a) / 10;
  return c ? 4.5 > a || !axs.utils.isLargeFont(b) && 7 > a : 3 > a || !axs.utils.isLargeFont(b) && 4.5 > a;
};
axs.utils.hasLabel = function(a) {
  var b = a.tagName.toLowerCase(), c = a.type ? a.type.toLowerCase() : "";
  if (a.hasAttribute("aria-label") || a.hasAttribute("title") || "img" == b && a.hasAttribute("alt") || "input" == b && "image" == c && a.hasAttribute("alt") || "input" == b && ("submit" == c || "reset" == c) || a.hasAttribute("aria-labelledby") || a.hasAttribute("id") && 0 < document.querySelectorAll('label[for="' + a.id + '"]').length) {
    return !0;
  }
  for (b = axs.dom.parentElement(a);b;) {
    if ("label" == b.tagName.toLowerCase() && b.control == a) {
      return !0;
    }
    b = axs.dom.parentElement(b);
  }
  return !1;
};
axs.utils.isNativelyDisableable = function(a) {
  return a.tagName.toUpperCase() in axs.constants.NATIVELY_DISABLEABLE;
};
axs.utils.isElementDisabled = function(a, b) {
  if (axs.browserUtils.matchSelector(a, b ? "[aria-disabled=true]" : "[aria-disabled=true], [aria-disabled=true] *")) {
    return !0;
  }
  if (!axs.utils.isNativelyDisableable(a) || axs.browserUtils.matchSelector(a, "fieldset>legend:first-of-type *")) {
    return !1;
  }
  for (var c = a;null !== c;c = axs.dom.parentElement(c)) {
    if (c.hasAttribute("disabled")) {
      return !0;
    }
    if (b) {
      break;
    }
  }
  return !1;
};
axs.utils.isElementHidden = function(a) {
  if (!(a instanceof a.ownerDocument.defaultView.HTMLElement)) {
    return !1;
  }
  if (a.hasAttribute("chromevoxignoreariahidden")) {
    var b = !0
  }
  var c = window.getComputedStyle(a, null);
  return "none" == c.display || "hidden" == c.visibility ? !0 : a.hasAttribute("aria-hidden") && "true" == a.getAttribute("aria-hidden").toLowerCase() ? !b : !1;
};
axs.utils.isElementOrAncestorHidden = function(a) {
  return axs.utils.isElementHidden(a) ? !0 : axs.dom.parentElement(a) ? axs.utils.isElementOrAncestorHidden(axs.dom.parentElement(a)) : !1;
};
axs.utils.isInlineElement = function(a) {
  a = a.tagName.toUpperCase();
  return axs.constants.InlineElements[a];
};
axs.utils.getRoles = function(a, b) {
  if (!a || a.nodeType !== Node.ELEMENT_NODE || !a.hasAttribute("role") && !b) {
    return null;
  }
  var c = a.getAttribute("role");
  !c && b && (c = axs.properties.getImplicitRole(a));
  if (!c) {
    return null;
  }
  for (var c = c.split(" "), d = {roles:[], valid:!1}, e = 0;e < c.length;e++) {
    var f = c[e], g = axs.constants.ARIA_ROLES[f], f = {name:f};
    g && !g["abstract"] ? (f.details = g, d.applied || (d.applied = f), f.valid = d.valid = !0) : f.valid = !1;
    d.roles.push(f);
  }
  return d;
};
axs.utils.getAriaPropertyValue = function(a, b, c) {
  var d = a.replace(/^aria-/, ""), e = axs.constants.ARIA_PROPERTIES[d], d = {name:a, rawValue:b};
  if (!e) {
    return d.valid = !1, d.reason = '"' + a + '" is not a valid ARIA property', d;
  }
  e = e.valueType;
  if (!e) {
    return d.valid = !1, d.reason = '"' + a + '" is not a valid ARIA property', d;
  }
  switch(e) {
    case "idref":
      a = axs.utils.isValidIDRefValue(b, c), d.valid = a.valid, d.reason = a.reason, d.idref = a.idref;
    case "idref_list":
      a = b.split(/\s+/);
      d.valid = !0;
      for (b = 0;b < a.length;b++) {
        e = axs.utils.isValidIDRefValue(a[b], c), e.valid || (d.valid = !1), d.values ? d.values.push(e) : d.values = [e];
      }
      return d;
    case "integer":
      c = axs.utils.isValidNumber(b);
      if (!c.valid) {
        return d.valid = !1, d.reason = c.reason, d;
      }
      Math.floor(c.value) !== c.value ? (d.valid = !1, d.reason = "" + b + " is not a whole integer") : (d.valid = !0, d.value = c.value);
      return d;
    case "decimal":
    ;
    case "number":
      c = axs.utils.isValidNumber(b);
      d.valid = c.valid;
      if (!c.valid) {
        return d.reason = c.reason, d;
      }
      d.value = c.value;
      return d;
    case "string":
      return d.valid = !0, d.value = b, d;
    case "token":
      return c = axs.utils.isValidTokenValue(a, b.toLowerCase()), c.valid ? (d.valid = !0, d.value = c.value) : (d.valid = !1, d.value = b, d.reason = c.reason), d;
    case "token_list":
      e = b.split(/\s+/);
      d.valid = !0;
      for (b = 0;b < e.length;b++) {
        c = axs.utils.isValidTokenValue(a, e[b].toLowerCase()), c.valid || (d.valid = !1, d.reason ? (d.reason = [d.reason], d.reason.push(c.reason)) : (d.reason = c.reason, d.possibleValues = c.possibleValues)), d.values ? d.values.push(c.value) : d.values = [c.value];
      }
      return d;
    case "tristate":
      return c = axs.utils.isPossibleValue(b.toLowerCase(), axs.constants.MIXED_VALUES, a), c.valid ? (d.valid = !0, d.value = c.value) : (d.valid = !1, d.value = b, d.reason = c.reason), d;
    case "boolean":
      return c = axs.utils.isValidBoolean(b), c.valid ? (d.valid = !0, d.value = c.value) : (d.valid = !1, d.value = b, d.reason = c.reason), d;
  }
  d.valid = !1;
  d.reason = "Not a valid ARIA property";
  return d;
};
axs.utils.isValidTokenValue = function(a, b) {
  var c = a.replace(/^aria-/, "");
  return axs.utils.isPossibleValue(b, axs.constants.ARIA_PROPERTIES[c].valuesSet, a);
};
axs.utils.isPossibleValue = function(a, b, c) {
  return b[a] ? {valid:!0, value:a} : {valid:!1, value:a, reason:'"' + a + '" is not a valid value for ' + c, possibleValues:Object.keys(b)};
};
axs.utils.isValidBoolean = function(a) {
  try {
    var b = JSON.parse(a);
  } catch (c) {
    b = "";
  }
  return "boolean" != typeof b ? {valid:!1, value:a, reason:'"' + a + '" is not a true/false value'} : {valid:!0, value:b};
};
axs.utils.isValidIDRefValue = function(a, b) {
  return 0 == a.length ? {valid:!0, idref:a} : b.ownerDocument.getElementById(a) ? {valid:!0, idref:a} : {valid:!1, idref:a, reason:'No element with ID "' + a + '"'};
};
axs.utils.isValidNumber = function(a) {
  var b = {valid:!1, value:a, reason:'"' + a + '" is not a number'};
  if (!a) {
    return b;
  }
  if (/^0x/i.test(a)) {
    return b.reason = '"' + a + '" is not a decimal number', b;
  }
  a *= 1;
  return isFinite(a) ? {valid:!0, value:a} : b;
};
axs.utils.isElementImplicitlyFocusable = function(a) {
  var b = a.ownerDocument.defaultView;
  return a instanceof b.HTMLAnchorElement || a instanceof b.HTMLAreaElement ? a.hasAttribute("href") : a instanceof b.HTMLInputElement || a instanceof b.HTMLSelectElement || a instanceof b.HTMLTextAreaElement || a instanceof b.HTMLButtonElement || a instanceof b.HTMLIFrameElement ? !a.disabled : !1;
};
axs.utils.values = function(a) {
  var b = [], c;
  for (c in a) {
    a.hasOwnProperty(c) && "function" != typeof a[c] && b.push(a[c]);
  }
  return b;
};
axs.utils.namedValues = function(a) {
  var b = {}, c;
  for (c in a) {
    a.hasOwnProperty(c) && "function" != typeof a[c] && (b[c] = a[c]);
  }
  return b;
};
function escapeId(a) {
  return a.replace(/[^a-zA-Z0-9_-]/g, function(a) {
    return "\\" + a;
  });
}
axs.utils.getQuerySelectorText = function(a) {
  if (null == a || "HTML" == a.tagName) {
    return "html";
  }
  if ("BODY" == a.tagName) {
    return "body";
  }
  if (a.hasAttribute) {
    if (a.id) {
      return "#" + escapeId(a.id);
    }
    if (a.className) {
      for (var b = "", c = 0;c < a.classList.length;c++) {
        b += "." + a.classList[c];
      }
      var d = 0;
      if (a.parentNode) {
        for (c = 0;c < a.parentNode.children.length;c++) {
          var e = a.parentNode.children[c];
          axs.browserUtils.matchSelector(e, b) && d++;
          if (e === a) {
            break;
          }
        }
      } else {
        d = 1;
      }
      if (1 == d) {
        return axs.utils.getQuerySelectorText(a.parentNode) + " > " + b;
      }
    }
    if (a.parentNode) {
      b = a.parentNode.children;
      d = 1;
      for (c = 0;b[c] !== a;) {
        b[c].tagName == a.tagName && d++, c++;
      }
      c = "";
      "BODY" != a.parentNode.tagName && (c = axs.utils.getQuerySelectorText(a.parentNode) + " > ");
      return 1 == d ? c + a.tagName : c + a.tagName + ":nth-of-type(" + d + ")";
    }
  } else {
    if (a.selectorText) {
      return a.selectorText;
    }
  }
  return "";
};
axs.utils.getAriaIdReferrers = function(a, b) {
  var c = function(a) {
    var b = axs.constants.ARIA_PROPERTIES[a];
    if (b) {
      if ("idref" === b.valueType) {
        return "[aria-" + a + "='" + d + "']";
      }
      if ("idref_list" === b.valueType) {
        return "[aria-" + a + "~='" + d + "']";
      }
    }
    return "";
  };
  if (!a) {
    return null;
  }
  var d = a.id;
  if (!d) {
    return null;
  }
  d = d.replace(/'/g, "\\'");
  if (b) {
    var e = b.replace(/^aria-/, ""), f = c(e);
    if (f) {
      return a.ownerDocument.querySelectorAll(f);
    }
  } else {
    var g = [];
    for (e in axs.constants.ARIA_PROPERTIES) {
      (f = c(e)) && g.push(f);
    }
    return a.ownerDocument.querySelectorAll(g.join(","));
  }
  return null;
};
axs.utils.getHtmlIdReferrers = function(a) {
  if (!a) {
    return null;
  }
  var b = a.id;
  if (!b) {
    return null;
  }
  var b = b.replace(/'/g, "\\'"), c = "[contextmenu='{id}'] [itemref~='{id}'] button[form='{id}'] button[menu='{id}'] fieldset[form='{id}'] input[form='{id}'] input[list='{id}'] keygen[form='{id}'] label[for='{id}'] label[form='{id}'] menuitem[command='{id}'] object[form='{id}'] output[for~='{id}'] output[form='{id}'] select[form='{id}'] td[headers~='{id}'] textarea[form='{id}'] tr[headers~='{id}']".split(" ").map(function(a) {
    return a.replace("{id}", b);
  });
  return a.ownerDocument.querySelectorAll(c.join(","));
};
axs.utils.getReferencedIds = function(a) {
  for (var b = [], c = function(a) {
    a && (0 < a.indexOf(" ") ? b = b.concat(f.value.split(" ")) : b.push(a));
  }, d = 0;d < a.attributes.length;d++) {
    var e = a.tagName.toLowerCase(), f = a.attributes[d];
    if (f.specified) {
      var g = f.name, h = g.match(/aria-(.+)/);
      if (h) {
        e = axs.constants.ARIA_PROPERTIES[h[1]], !e || "idref" !== e.valueType && "idref_list" !== e.valueType || c(f.value);
      } else {
        switch(g) {
          case "contextmenu":
          ;
          case "itemref":
            c(f.value);
            break;
          case "form":
            "button" != e && "fieldset" != e && "input" != e && "keygen" != e && "label" != e && "object" != e && "output" != e && "select" != e && "textarea" != e || c(f.value);
            break;
          case "for":
            "label" != e && "output" != e || c(f.value);
            break;
          case "menu":
            "button" == e && c(f.value);
            break;
          case "list":
            "input" == e && c(f.value);
            break;
          case "command":
            "menuitem" == e && c(f.value);
            break;
          case "headers":
            "td" != e && "tr" != e || c(f.value);
        }
      }
    }
  }
  return b;
};
axs.utils.getIdReferrers = function(a) {
  var b = [], c = axs.utils.getHtmlIdReferrers(a);
  c && (b = b.concat(Array.prototype.slice.call(c)));
  (c = axs.utils.getAriaIdReferrers(a)) && (b = b.concat(Array.prototype.slice.call(c)));
  return b;
};
axs.utils.getIdReferents = function(a, b) {
  var c = [], d = a.replace(/^aria-/, ""), d = axs.constants.ARIA_PROPERTIES[d];
  if (!d || !b.hasAttribute(a)) {
    return c;
  }
  d = d.valueType;
  if ("idref_list" === d || "idref" === d) {
    for (var d = b.ownerDocument, e = b.getAttribute(a), e = e.split(/\s+/), f = 0, g = e.length;f < g;f++) {
      var h = d.getElementById(e[f]);
      h && (c[c.length] = h);
    }
  }
  return c;
};
axs.utils.getAriaPropertiesByValueType = function(a) {
  var b = {}, c;
  for (c in axs.constants.ARIA_PROPERTIES) {
    var d = axs.constants.ARIA_PROPERTIES[c];
    d && 0 <= a.indexOf(d.valueType) && (b[c] = d);
  }
  return b;
};
axs.utils.getSelectorForAriaProperties = function(a) {
  a = Object.keys(a).map(function(a) {
    return "[aria-" + a + "]";
  });
  a.sort();
  return a.join(",");
};
axs.utils.findDescendantsWithRole = function(a, b) {
  if (!a || !b) {
    return [];
  }
  var c = axs.properties.getSelectorForRole(b);
  if (c && (c = a.querySelectorAll(c))) {
    c = Array.prototype.map.call(c, function(a) {
      return a;
    });
  } else {
    return [];
  }
  return c;
};
axs.properties = {};
axs.properties.TEXT_CONTENT_XPATH = './/text()[normalize-space(.)!=""]/parent::*[name()!="script"]';
axs.properties.getFocusProperties = function(a) {
  var b = {}, c = a.getAttribute("tabindex");
  void 0 != c ? b.tabindex = {value:c, valid:!0} : axs.utils.isElementImplicitlyFocusable(a) && (b.implicitlyFocusable = {value:!0, valid:!0});
  if (0 == Object.keys(b).length) {
    return null;
  }
  var d = axs.utils.elementIsTransparent(a), e = axs.utils.elementHasZeroArea(a), f = axs.utils.elementIsOutsideScrollArea(a), g = axs.utils.overlappingElements(a);
  if (d || e || f || 0 < g.length) {
    var c = axs.utils.isElementOrAncestorHidden(a), h = {value:!1, valid:c};
    d && (h.transparent = !0);
    e && (h.zeroArea = !0);
    f && (h.outsideScrollArea = !0);
    g && 0 < g.length && (h.overlappingElements = g);
    d = {value:c, valid:c};
    c && (d.reason = axs.properties.getHiddenReason(a));
    h.hidden = d;
    b.visible = h;
  } else {
    b.visible = {value:!0, valid:!0};
  }
  return b;
};
axs.properties.getHiddenReason = function(a) {
  if (!(a && a instanceof a.ownerDocument.defaultView.HTMLElement)) {
    return null;
  }
  if (a.hasAttribute("chromevoxignoreariahidden")) {
    var b = !0
  }
  var c = window.getComputedStyle(a, null);
  return "none" == c.display ? {property:"display: none", on:a} : "hidden" == c.visibility ? {property:"visibility: hidden", on:a} : a.hasAttribute("aria-hidden") && "true" == a.getAttribute("aria-hidden").toLowerCase() && !b ? {property:"aria-hidden", on:a} : axs.properties.getHiddenReason(axs.dom.parentElement(a));
};
axs.properties.getColorProperties = function(a) {
  var b = {};
  (a = axs.properties.getContrastRatioProperties(a)) && (b.contrastRatio = a);
  return 0 == Object.keys(b).length ? null : b;
};
axs.properties.hasDirectTextDescendant = function(a) {
  function b() {
    for (var b = c.evaluate(axs.properties.TEXT_CONTENT_XPATH, a, null, XPathResult.ANY_TYPE, null), e = b.iterateNext();null != e;e = b.iterateNext()) {
      if (e === a) {
        return !0;
      }
    }
    return !1;
  }
  var c;
  c = a.nodeType == Node.DOCUMENT_NODE ? a : a.ownerDocument;
  return c.evaluate ? b() : function() {
    for (var b = c.createTreeWalker(a, NodeFilter.SHOW_TEXT, null, !1);b.nextNode();) {
      var e = b.currentNode, f = e.parentNode.tagName.toLowerCase();
      if (e.nodeValue.trim() && "script" !== f && a !== e) {
        return !0;
      }
    }
    return !1;
  }();
};
axs.properties.getContrastRatioProperties = function(a) {
  if (!axs.properties.hasDirectTextDescendant(a)) {
    return null;
  }
  var b = {}, c = window.getComputedStyle(a, null), d = axs.utils.getBgColor(c, a);
  if (!d) {
    return null;
  }
  b.backgroundColor = axs.color.colorToString(d);
  var e = axs.utils.getFgColor(c, a, d);
  b.foregroundColor = axs.color.colorToString(e);
  a = axs.utils.getContrastRatioForElementWithComputedStyle(c, a);
  if (!a) {
    return null;
  }
  b.value = a.toFixed(2);
  axs.utils.isLowContrast(a, c) && (b.alert = !0);
  var f = axs.utils.isLargeFont(c) ? 3 : 4.5, c = axs.utils.isLargeFont(c) ? 4.5 : 7, g = {};
  f > a && (g.AA = f);
  c > a && (g.AAA = c);
  if (!Object.keys(g).length) {
    return b;
  }
  (d = axs.color.suggestColors(d, e, g)) && Object.keys(d).length && (b.suggestedColors = d);
  return b;
};
axs.properties.findTextAlternatives = function(a, b, c, d) {
  var e = c || !1;
  c = axs.dom.asElement(a);
  if (!c || !d && axs.utils.isElementOrAncestorHidden(c)) {
    return null;
  }
  if (a.nodeType == Node.TEXT_NODE) {
    return c = {type:"text"}, c.text = a.textContent, c.lastWord = axs.properties.getLastWord(c.text), b.content = c, a.textContent;
  }
  a = null;
  e || (a = axs.properties.getTextFromAriaLabelledby(c, b));
  if (c.hasAttribute("aria-label")) {
    var f = {type:"text"};
    f.text = c.getAttribute("aria-label");
    f.lastWord = axs.properties.getLastWord(f.text);
    a ? f.unused = !0 : e && axs.utils.elementIsHtmlControl(c) || (a = f.text);
    b.ariaLabel = f;
  }
  c.hasAttribute("role") && "presentation" == c.getAttribute("role") || (a = axs.properties.getTextFromHostLanguageAttributes(c, b, a, e));
  e && axs.utils.elementIsHtmlControl(c) && (f = c.ownerDocument.defaultView, c instanceof f.HTMLInputElement && ("text" == c.type && c.value && 0 < c.value.length && (b.controlValue = {text:c.value}), "range" == c.type && (b.controlValue = {text:c.value})), c instanceof f.HTMLSelectElement && (b.controlValue = {text:c.value}), b.controlValue && (f = b.controlValue, a ? f.unused = !0 : a = f.text));
  if (e && axs.utils.elementIsAriaWidget(c)) {
    e = c.getAttribute("role");
    "textbox" == e && c.textContent && 0 < c.textContent.length && (b.controlValue = {text:c.textContent});
    if ("slider" == e || "spinbutton" == e) {
      c.hasAttribute("aria-valuetext") ? b.controlValue = {text:c.getAttribute("aria-valuetext")} : c.hasAttribute("aria-valuenow") && (b.controlValue = {value:c.getAttribute("aria-valuenow"), text:"" + c.getAttribute("aria-valuenow")});
    }
    if ("menu" == e) {
      for (var g = c.querySelectorAll("[role=menuitemcheckbox], [role=menuitemradio]"), f = [], h = 0;h < g.length;h++) {
        "true" == g[h].getAttribute("aria-checked") && f.push(g[h]);
      }
      if (0 < f.length) {
        g = "";
        for (h = 0;h < f.length;h++) {
          g += axs.properties.findTextAlternatives(f[h], {}, !0), h < f.length - 1 && (g += ", ");
        }
        b.controlValue = {text:g};
      }
    }
    if ("combobox" == e || "select" == e) {
      b.controlValue = {text:"TODO"};
    }
    b.controlValue && (f = b.controlValue, a ? f.unused = !0 : a = f.text);
  }
  f = !0;
  c.hasAttribute("role") && (e = c.getAttribute("role"), (e = axs.constants.ARIA_ROLES[e]) && (!e.namefrom || 0 > e.namefrom.indexOf("contents")) && (f = !1));
  (d = axs.properties.getTextFromDescendantContent(c, d)) && f && (e = {type:"text"}, e.text = d, e.lastWord = axs.properties.getLastWord(e.text), a ? e.unused = !0 : a = d, b.content = e);
  c.hasAttribute("title") && (d = {type:"string", valid:!0}, d.text = c.getAttribute("title"), d.lastWord = axs.properties.getLastWord(d.lastWord), a ? d.unused = !0 : a = d.text, b.title = d);
  return 0 == Object.keys(b).length && null == a ? null : a;
};
axs.properties.getTextFromDescendantContent = function(a, b) {
  for (var c = a.childNodes, d = [], e = 0;e < c.length;e++) {
    var f = axs.properties.findTextAlternatives(c[e], {}, !0, b);
    f && d.push(f.trim());
  }
  if (d.length) {
    c = "";
    for (e = 0;e < d.length;e++) {
      c = [c, d[e]].join(" ").trim();
    }
    return c;
  }
  return null;
};
axs.properties.getTextFromAriaLabelledby = function(a, b) {
  var c = null;
  if (!a.hasAttribute("aria-labelledby")) {
    return c;
  }
  for (var d = a.getAttribute("aria-labelledby").split(/\s+/), e = {valid:!0}, f = [], g = [], h = 0;h < d.length;h++) {
    var k = {type:"element"}, m = d[h];
    k.value = m;
    var l = document.getElementById(m);
    l ? (k.valid = !0, k.text = axs.properties.findTextAlternatives(l, {}, !0, !0), k.lastWord = axs.properties.getLastWord(k.text), f.push(k.text), k.element = l) : (k.valid = !1, e.valid = !1, k.errorMessage = {messageKey:"noElementWithId", args:[m]});
    g.push(k);
  }
  0 < g.length && (g[g.length - 1].last = !0, e.values = g, e.text = f.join(" "), e.lastWord = axs.properties.getLastWord(e.text), c = e.text, b.ariaLabelledby = e);
  return c;
};
axs.properties.getTextFromHostLanguageAttributes = function(a, b, c, d) {
  if (axs.browserUtils.matchSelector(a, "img") && a.hasAttribute("alt")) {
    var e = {type:"string", valid:!0};
    e.text = a.getAttribute("alt");
    c ? e.unused = !0 : c = e.text;
    b.alt = e;
  }
  if (axs.browserUtils.matchSelector(a, 'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), video:not([disabled])') && !d) {
    if (a.hasAttribute("id")) {
      d = document.querySelectorAll('label[for="' + a.id + '"]');
      for (var e = {}, f = [], g = [], h = 0;h < d.length;h++) {
        var k = {type:"element"}, m = d[h], l = axs.properties.findTextAlternatives(m, {}, !0);
        l && 0 < l.trim().length && (k.text = l.trim(), g.push(l.trim()));
        k.element = m;
        f.push(k);
      }
      0 < f.length && (f[f.length - 1].last = !0, e.values = f, e.text = g.join(" "), e.lastWord = axs.properties.getLastWord(e.text), c ? e.unused = !0 : c = e.text, b.labelFor = e);
    }
    d = axs.dom.parentElement(a);
    for (e = {};d;) {
      if ("label" == d.tagName.toLowerCase() && (f = d, f.control == a)) {
        e.type = "element";
        e.text = axs.properties.findTextAlternatives(f, {}, !0);
        e.lastWord = axs.properties.getLastWord(e.text);
        e.element = f;
        break;
      }
      d = axs.dom.parentElement(d);
    }
    e.text && (c ? e.unused = !0 : c = e.text, b.labelWrapped = e);
    axs.browserUtils.matchSelector(a, 'input[type="image"]') && a.hasAttribute("alt") && (e = {type:"string", valid:!0}, e.text = a.getAttribute("alt"), c ? e.unused = !0 : c = e.text, b.alt = e);
    Object.keys(b).length || (b.noLabel = !0);
  }
  return c;
};
axs.properties.getLastWord = function(a) {
  if (!a) {
    return null;
  }
  var b = a.lastIndexOf(" ") + 1, c = a.length - 10;
  return a.substring(b > c ? b : c);
};
axs.properties.getTextProperties = function(a) {
  var b = {}, c = axs.properties.findTextAlternatives(a, b, !1, !0);
  if (0 == Object.keys(b).length && ((a = axs.dom.asElement(a)) && axs.browserUtils.matchSelector(a, "img") && (b.alt = {valid:!1, errorMessage:"No alt value provided"}, a = a.src, "string" == typeof a && (c = a.split("/").pop(), b.filename = {text:c})), !c)) {
    return null;
  }
  b.hasProperties = !!Object.keys(b).length;
  b.computedText = c;
  b.lastWord = axs.properties.getLastWord(c);
  return b;
};
axs.properties.getAriaProperties = function(a) {
  var b = {}, c = axs.properties.getGlobalAriaProperties(a), d;
  for (d in axs.constants.ARIA_PROPERTIES) {
    var e = "aria-" + d;
    if (a.hasAttribute(e)) {
      var f = a.getAttribute(e);
      c[e] = axs.utils.getAriaPropertyValue(e, f, a);
    }
  }
  0 < Object.keys(c).length && (b.properties = axs.utils.values(c));
  f = axs.utils.getRoles(a);
  if (!f) {
    return Object.keys(b).length ? b : null;
  }
  b.roles = f;
  if (!f.valid || !f.roles) {
    return b;
  }
  for (var e = f.roles, g = 0;g < e.length;g++) {
    var h = e[g];
    if (h.details && h.details.propertiesSet) {
      for (d in h.details.propertiesSet) {
        d in c || (a.hasAttribute(d) ? (f = a.getAttribute(d), c[d] = axs.utils.getAriaPropertyValue(d, f, a), "values" in c[d] && (f = c[d].values, f[f.length - 1].isLast = !0)) : h.details.requiredPropertiesSet[d] && (c[d] = {name:d, valid:!1, reason:"Required property not set"}));
      }
    }
  }
  0 < Object.keys(c).length && (b.properties = axs.utils.values(c));
  return 0 < Object.keys(b).length ? b : null;
};
axs.properties.getGlobalAriaProperties = function(a) {
  var b = {}, c;
  for (c in axs.constants.GLOBAL_PROPERTIES) {
    if (a.hasAttribute(c)) {
      var d = a.getAttribute(c);
      b[c] = axs.utils.getAriaPropertyValue(c, d, a);
    }
  }
  return b;
};
axs.properties.getVideoProperties = function(a) {
  if (!axs.browserUtils.matchSelector(a, "video")) {
    return null;
  }
  var b = {};
  b.captionTracks = axs.properties.getTrackElements(a, "captions");
  b.descriptionTracks = axs.properties.getTrackElements(a, "descriptions");
  b.chapterTracks = axs.properties.getTrackElements(a, "chapters");
  return b;
};
axs.properties.getTrackElements = function(a, b) {
  var c = a.querySelectorAll("track[kind=" + b + "]"), d = {};
  if (!c.length) {
    return d.valid = !1, d.reason = {messageKey:"noTracksProvided", args:[[b]]}, d;
  }
  d.valid = !0;
  for (var e = [], f = 0;f < c.length;f++) {
    var g = {}, h = c[f].getAttribute("src"), k = c[f].getAttribute("srcLang"), m = c[f].getAttribute("label");
    h ? (g.valid = !0, g.src = h) : (g.valid = !1, g.reason = {messageKey:"noSrcProvided"});
    h = "";
    m && (h += m, k && (h += " "));
    k && (h += "(" + k + ")");
    "" == h && (h = "[[object Object]]");
    g.name = h;
    e.push(g);
  }
  d.values = e;
  return d;
};
axs.properties.getAllProperties = function(a) {
  var b = axs.dom.asElement(a);
  if (!b) {
    return {};
  }
  var c = {};
  c.ariaProperties = axs.properties.getAriaProperties(b);
  c.colorProperties = axs.properties.getColorProperties(b);
  c.focusProperties = axs.properties.getFocusProperties(b);
  c.textProperties = axs.properties.getTextProperties(a);
  c.videoProperties = axs.properties.getVideoProperties(b);
  return c;
};
(function() {
  function a(a) {
    if (!a) {
      return null;
    }
    var c = a.tagName;
    if (!c) {
      return null;
    }
    c = c.toUpperCase();
    c = axs.constants.TAG_TO_IMPLICIT_SEMANTIC_INFO[c];
    if (!c || !c.length) {
      return null;
    }
    for (var d = null, e = 0, f = c.length;e < f;e++) {
      var g = c[e];
      if (g.selector) {
        if (axs.browserUtils.matchSelector(a, g.selector)) {
          return g;
        }
      } else {
        d = g;
      }
    }
    return d;
  }
  axs.properties.getImplicitRole = function(b) {
    return (b = a(b)) ? b.role : "";
  };
  axs.properties.canTakeAriaAttributes = function(b) {
    return (b = a(b)) ? !b.reserved : !0;
  };
})();
axs.properties.getNativelySupportedAttributes = function(a) {
  var b = [];
  if (!a) {
    return b;
  }
  a = a.cloneNode(!1);
  for (var c = Object.keys(axs.constants.ARIA_TO_HTML_ATTRIBUTE), d = 0;d < c.length;d++) {
    var e = c[d];
    axs.constants.ARIA_TO_HTML_ATTRIBUTE[e] in a && (b[b.length] = e);
  }
  return b;
};
(function() {
  var a = {};
  axs.properties.getSelectorForRole = function(b) {
    if (!b) {
      return "";
    }
    if (a[b] && a.hasOwnProperty(b)) {
      return a[b];
    }
    var c = ['[role="' + b + '"]'];
    Object.keys(axs.constants.TAG_TO_IMPLICIT_SEMANTIC_INFO).forEach(function(a) {
      var e = axs.constants.TAG_TO_IMPLICIT_SEMANTIC_INFO[a];
      if (e && e.length) {
        for (var f = 0;f < e.length;f++) {
          var g = e[f];
          if (g.role === b) {
            if (g.selector) {
              c[c.length] = g.selector;
            } else {
              c[c.length] = a;
              break;
            }
          }
        }
      }
    });
    return a[b] = c.join(",");
  };
})();
axs.AuditRule = function(a) {
  for (var b = a.opt_requires || {}, c = !0, d = [], e = 0;e < axs.AuditRule.requiredFields.length;e++) {
    var f = axs.AuditRule.requiredFields[e];
    f in a || (c = !1, d.push(f));
  }
  if (!c) {
    throw "Invalid spec; the following fields were not specified: " + d.join(", ") + "\n" + JSON.stringify(a);
  }
  this.name = a.name;
  this.severity = a.severity;
  this.relevantElementMatcher_ = a.relevantElementMatcher;
  this.isRelevant_ = a.isRelevant || function(a, b) {
    return !0;
  };
  this.test_ = a.test;
  this.code = a.code;
  this.heading = a.heading || "";
  this.url = a.url || "";
  this.requiresConsoleAPI = !!b.consoleAPI;
  this.relevantElements = [];
  this.relatedElements = [];
  this.collectIdRefs = b.idRefs || !1;
};
axs.AuditRule.requiredFields = "name severity relevantElementMatcher test code heading".split(" ");
axs.AuditRule.NOT_APPLICABLE = {result:axs.constants.AuditResult.NA};
axs.AuditRule.prototype.addElement = function(a, b) {
  a.push(b);
};
axs.AuditRule.prototype.collectMatchingElement = function(a, b) {
  return this.relevantElementMatcher_(a, b) && b.inScope ? (this.relevantElements.push({element:a, flags:b}), !0) : !1;
};
axs.AuditRule.prototype.canRun = function(a) {
  return this.disabled || !a.withConsoleApi && this.requiresConsoleAPI ? !1 : !0;
};
axs.AuditRule.Result = function(a, b) {
  var c = axs.utils.namedValues(b);
  c.severity = a.getSeverity(b.name) || c.severity;
  this.rule = c;
  this.maxResults = a.maxResults;
  this.update(axs.constants.AuditResult.NA);
};
axs.AuditRule.Result.prototype.update = function(a, b) {
  if (a === axs.constants.AuditResult.FAIL) {
    var c = this.elements || (this.elements = []);
    this.result = a;
    this.maxResults && this.elements.length >= this.maxResults ? this.resultsTruncated = !0 : b && c.push(b);
  } else {
    a === axs.constants.AuditResult.PASS ? (this.elements || (this.elements = []), this.result !== axs.constants.AuditResult.FAIL && (this.result = a)) : this.result || (this.result = a);
  }
};
axs.AuditRule.prototype.run = function(a) {
  try {
    for (var b = this._options || {}, c = new axs.AuditRule.Result(a, this), d;d = this.relevantElements.shift();) {
      var e = d.element, f = d.flags;
      this.isRelevant_(e, f) && (this.test_(e, f, b.config) ? c.update(axs.constants.AuditResult.FAIL, e) : c.update(axs.constants.AuditResult.PASS, e));
    }
    return c;
  } finally {
    this.relatedElements.length = 0;
  }
};
axs.AuditRules = {};
(function() {
  var a = {}, b = {};
  axs.AuditRules.specs = {};
  axs.AuditRules.addRule = function(c) {
    var d = new axs.AuditRule(c);
    if (d.code in b) {
      throw Error('Can not add audit rule with same code: "' + d.code + '"');
    }
    if (d.name in a) {
      throw Error('Can not add audit rule with same name: "' + d.name + '"');
    }
    a[d.name] = b[d.code] = d;
    axs.AuditRules.specs[c.name] = c;
  };
  axs.AuditRules.getRule = function(c) {
    return a[c] || b[c] || null;
  };
  axs.AuditRules.getRules = function(b) {
    var d = Object.keys(a);
    return b ? d : d.map(function(a) {
      return this.getRule(a);
    }, axs.AuditRules);
  };
  axs.AuditRules.getActiveRules = function(a) {
    var b;
    b = a.auditRulesToRun && 0 < a.auditRulesToRun.length ? a.auditRulesToRun : axs.AuditRules.getRules(!0);
    if (a.auditRulesToIgnore) {
      for (var e = 0;e < a.auditRulesToIgnore.length;e++) {
        var f = a.auditRulesToIgnore[e];
        0 > b.indexOf(f) || b.splice(b.indexOf(f), 1);
      }
    }
    return b.map(axs.AuditRules.getRule);
  };
})();
axs.AuditResults = function() {
  this.errors_ = [];
  this.warnings_ = [];
};
goog.exportSymbol("axs.AuditResults", axs.AuditResults);
axs.AuditResults.prototype.addError = function(a) {
  "" != a && this.errors_.push(a);
};
goog.exportProperty(axs.AuditResults.prototype, "addError", axs.AuditResults.prototype.addError);
axs.AuditResults.prototype.addWarning = function(a) {
  "" != a && this.warnings_.push(a);
};
goog.exportProperty(axs.AuditResults.prototype, "addWarning", axs.AuditResults.prototype.addWarning);
axs.AuditResults.prototype.numErrors = function() {
  return this.errors_.length;
};
goog.exportProperty(axs.AuditResults.prototype, "numErrors", axs.AuditResults.prototype.numErrors);
axs.AuditResults.prototype.numWarnings = function() {
  return this.warnings_.length;
};
goog.exportProperty(axs.AuditResults.prototype, "numWarnings", axs.AuditResults.prototype.numWarnings);
axs.AuditResults.prototype.getErrors = function() {
  return this.errors_;
};
goog.exportProperty(axs.AuditResults.prototype, "getErrors", axs.AuditResults.prototype.getErrors);
axs.AuditResults.prototype.getWarnings = function() {
  return this.warnings_;
};
goog.exportProperty(axs.AuditResults.prototype, "getWarnings", axs.AuditResults.prototype.getWarnings);
axs.AuditResults.prototype.toString = function() {
  for (var a = "", b = 0;b < this.errors_.length;b++) {
    0 == b && (a += "\nErrors:\n");
    var c = this.errors_[b], a = a + (c + "\n\n");
  }
  for (b = 0;b < this.warnings_.length;b++) {
    0 == b && (a += "\nWarnings:\n"), c = this.warnings_[b], a += c + "\n\n";
  }
  return a;
};
goog.exportProperty(axs.AuditResults.prototype, "toString", axs.AuditResults.prototype.toString);
axs.Audit = {};
axs.AuditConfiguration = function(a) {
  null == a && (a = {});
  this.rules_ = {};
  this.maxResults = this.auditRulesToIgnore = this.auditRulesToRun = this.scope = null;
  this.withConsoleApi = !1;
  this.showUnsupportedRulesWarning = this.walkDom = !0;
  for (var b in this) {
    this.hasOwnProperty(b) && b in a && (this[b] = a[b]);
  }
  goog.exportProperty(this, "scope", this.scope);
  goog.exportProperty(this, "auditRulesToRun", this.auditRulesToRun);
  goog.exportProperty(this, "auditRulesToIgnore", this.auditRulesToIgnore);
  goog.exportProperty(this, "withConsoleApi", this.withConsoleApi);
  goog.exportProperty(this, "walkDom", this.walkDom);
  goog.exportProperty(this, "showUnsupportedRulesWarning", this.showUnsupportedRulesWarning);
};
goog.exportSymbol("axs.AuditConfiguration", axs.AuditConfiguration);
axs.AuditConfiguration.prototype = {ignoreSelectors:function(a, b) {
  a in this.rules_ || (this.rules_[a] = {});
  "ignore" in this.rules_[a] || (this.rules_[a].ignore = []);
  Array.prototype.push.call(this.rules_[a].ignore, b);
}, getIgnoreSelectors:function(a) {
  return a in this.rules_ && "ignore" in this.rules_[a] ? this.rules_[a].ignore : [];
}, setSeverity:function(a, b) {
  a in this.rules_ || (this.rules_[a] = {});
  this.rules_[a].severity = b;
}, getSeverity:function(a) {
  return a in this.rules_ && "severity" in this.rules_[a] ? this.rules_[a].severity : null;
}, setRuleConfig:function(a, b) {
  a in this.rules_ || (this.rules_[a] = {});
  this.rules_[a].config = b;
}, getRuleConfig:function(a) {
  return a in this.rules_ && "config" in this.rules_[a] ? this.rules_[a].config : null;
}};
goog.exportProperty(axs.AuditConfiguration.prototype, "ignoreSelectors", axs.AuditConfiguration.prototype.ignoreSelectors);
goog.exportProperty(axs.AuditConfiguration.prototype, "getIgnoreSelectors", axs.AuditConfiguration.prototype.getIgnoreSelectors);
axs.Audit.unsupportedRulesWarningShown = !1;
axs.Audit.getRulesCannotRun = function(a) {
  return a.withConsoleApi ? [] : axs.AuditRules.getRules().filter(function(a) {
    return a.requiresConsoleAPI;
  }).map(function(a) {
    return a.code;
  });
};
axs.Audit.run = function(a) {
  a = a || new axs.AuditConfiguration;
  if (!axs.Audit.unsupportedRulesWarningShown && a.showUnsupportedRulesWarning) {
    var b = axs.Audit.getRulesCannotRun(a);
    0 < b.length && (console.warn("Some rules cannot be checked using the axs.Audit.run() method call. Use the Chrome plugin to check these rules: " + b.join(", ")), console.warn("To remove this message, pass an AuditConfiguration object to axs.Audit.run() and set configuration.showUnsupportedRulesWarning = false."));
    axs.Audit.unsupportedRulesWarningShown = !0;
  }
  b = axs.AuditRules.getActiveRules(a);
  a.collectIdRefs = b.some(function(a) {
    return a.collectIdRefs;
  });
  a.scope || (a.scope = document.documentElement);
  axs.Audit.collectMatchingElements(a, b);
  for (var c = [], d = 0;d < b.length;d++) {
    var e = b[d];
    e.canRun(a) && c.push(e.run(a));
  }
  return c;
};
goog.exportSymbol("axs.Audit.run", axs.Audit.run);
(function() {
  function a(a, c) {
    var d = a.getIgnoreSelectors(c.name);
    if (0 < d.length || a.scope) {
      this.ignoreSelectors = d;
    }
    if (d = a.getRuleConfig(c.name)) {
      this.config = d;
    }
  }
  axs.Audit.collectMatchingElements = function(b, c) {
    axs.dom.composedTreeSearch(b.walkDom ? document.documentElement : b.scope, null, {preorder:function(d, e) {
      e.inScope || (e.inScope = d === b.scope);
      for (var f = 0;f < c.length;f++) {
        var g = c[f];
        g.canRun(b) && (g._options = new a(b, g), e.ignoring[g.name] || (e.ignoring[g.name] = g._options.shouldIgnore(d)) || g.collectMatchingElement(d, e));
      }
      return !0;
    }}, {walkDom:b.walkDom, collectIdRefs:b.collectIdRefs, level:0, ignoring:{}, disabled:!1, hidden:!1});
  };
  a.prototype.shouldIgnore = function(a) {
    var c = this.ignoreSelectors;
    if (c) {
      for (var d = 0;d < c.length;d++) {
        if (axs.browserUtils.matchSelector(a, c[d])) {
          return !0;
        }
      }
    }
    return !1;
  };
})();
axs.Audit.auditResults = function(a) {
  for (var b = new axs.AuditResults, c = 0;c < a.length;c++) {
    var d = a[c];
    d.result == axs.constants.AuditResult.FAIL && (d.rule.severity == axs.constants.Severity.SEVERE ? b.addError(axs.Audit.accessibilityErrorMessage(d)) : b.addWarning(axs.Audit.accessibilityErrorMessage(d)));
  }
  return b;
};
goog.exportSymbol("axs.Audit.auditResults", axs.Audit.auditResults);
axs.Audit.createReport = function(a, b) {
  var c;
  c = "*** Begin accessibility audit results ***\nAn accessibility audit found " + axs.Audit.auditResults(a).toString();
  b && (c = c + "\nFor more information, please see " + b);
  return c + "\n*** End accessibility audit results ***";
};
goog.exportSymbol("axs.Audit.createReport", axs.Audit.createReport);
axs.Audit.accessibilityErrorMessage = function(a) {
  for (var b = a.rule.severity == axs.constants.Severity.SEVERE ? "Error: " : "Warning: ", b = b + (a.rule.code + " (" + a.rule.heading + ") failed on the following " + (1 == a.elements.length ? "element" : "elements")), b = 1 == a.elements.length ? b + ":" : b + (" (1 - " + Math.min(5, a.elements.length) + " of " + a.elements.length + "):"), c = Math.min(a.elements.length, 5), d = 0;d < c;d++) {
    var e = a.elements[d], b = b + "\n";
    try {
      b += axs.utils.getQuerySelectorText(e);
    } catch (f) {
      b += " tagName:" + e.tagName, b += " id:" + e.id;
    }
  }
  "" != a.rule.url && (b += "\nSee " + a.rule.url + " for more information.");
  return b;
};
goog.exportSymbol("axs.Audit.accessibilityErrorMessage", axs.Audit.accessibilityErrorMessage);
axs.AuditRules.addRule({name:"ariaOnReservedElement", heading:"This element does not support ARIA roles, states and properties", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_12", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return !axs.properties.canTakeAriaAttributes(a);
}, test:function(a) {
  return null !== axs.properties.getAriaProperties(a);
}, code:"AX_ARIA_12"});
axs.AuditRules.addRule({name:"ariaOwnsDescendant", heading:"aria-owns should not be used if ownership is implicit in the DOM", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_06", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "[aria-owns]");
}, test:function(a) {
  return axs.utils.getIdReferents("aria-owns", a).some(function(b) {
    return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_CONTAINED_BY;
  });
}, code:"AX_ARIA_06"});
axs.AuditRules.addRule({name:"ariaRoleNotScoped", heading:"Elements with ARIA roles must be in the correct scope", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_09", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "[role]");
}, test:function(a) {
  var b = axs.utils.getRoles(a);
  if (!b || !b.applied) {
    return !1;
  }
  b = b.applied.details.scope;
  if (!b || 0 === b.length) {
    return !1;
  }
  for (var c = a;c = axs.dom.parentElement(c);) {
    var d = axs.utils.getRoles(c, !0);
    if (d && d.applied && 0 <= b.indexOf(d.applied.name)) {
      return !1;
    }
  }
  if (a = axs.utils.getAriaIdReferrers(a, "aria-owns")) {
    for (c = 0;c < a.length;c++) {
      if ((d = axs.utils.getRoles(a[c], !0)) && d.applied && 0 <= b.indexOf(d.applied.name)) {
        return !1;
      }
    }
  }
  return !0;
}, code:"AX_ARIA_09"});
axs.AuditRules.addRule({name:"audioWithoutControls", heading:"Audio elements should have controls", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_audio_01", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "audio[autoplay]");
}, test:function(a) {
  return !a.querySelectorAll("[controls]").length && 3 < a.duration;
}, code:"AX_AUDIO_01"});
(function() {
  var a = /^aria\-/;
  axs.AuditRules.addRule({name:"badAriaAttribute", heading:"This element has an invalid ARIA attribute", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_11", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(b) {
    b = b.attributes;
    for (var c = 0, d = b.length;c < d;c++) {
      if (a.test(b[c].name)) {
        return !0;
      }
    }
    return !1;
  }, test:function(b) {
    b = b.attributes;
    for (var c = 0, d = b.length;c < d;c++) {
      var e = b[c].name;
      if (a.test(e) && (e = e.replace(a, ""), !axs.constants.ARIA_PROPERTIES.hasOwnProperty(e))) {
        return !0;
      }
    }
    return !1;
  }, code:"AX_ARIA_11"});
})();
axs.AuditRules.addRule({name:"badAriaAttributeValue", heading:"ARIA state and property values must be valid", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_04", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(a) {
  var b = axs.utils.getSelectorForAriaProperties(axs.constants.ARIA_PROPERTIES);
  return axs.browserUtils.matchSelector(a, b);
}, test:function(a) {
  for (var b in axs.constants.ARIA_PROPERTIES) {
    var c = "aria-" + b;
    if (a.hasAttribute(c)) {
      var d = a.getAttribute(c);
      if (!axs.utils.getAriaPropertyValue(c, d, a).valid) {
        return !0;
      }
    }
  }
  return !1;
}, code:"AX_ARIA_04"});
axs.AuditRules.addRule({name:"badAriaRole", heading:"Elements with ARIA roles must use a valid, non-abstract ARIA role", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_01", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "[role]");
}, test:function(a) {
  return !axs.utils.getRoles(a).valid;
}, code:"AX_ARIA_01"});
axs.AuditRules.addRule({name:"controlsWithoutLabel", heading:"Controls and media elements should have labels", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_text_01", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(a) {
  if (!axs.browserUtils.matchSelector(a, 'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), video:not([disabled])') || "presentation" == a.getAttribute("role")) {
    return !1;
  }
  if (0 <= a.tabIndex) {
    return !0;
  }
  for (a = axs.dom.parentElement(a);null != a;a = axs.dom.parentElement(a)) {
    if (axs.utils.elementIsAriaWidget(a)) {
      return !1;
    }
  }
  return !0;
}, test:function(a, b) {
  if (b.hidden || "input" == a.tagName.toLowerCase() && "button" == a.type && a.value.length || "button" == a.tagName.toLowerCase() && a.textContent.replace(/^\s+|\s+$/g, "").length || axs.utils.hasLabel(a)) {
    return !1;
  }
  var c = axs.properties.findTextAlternatives(a, {});
  return null === c || "" === c.trim() ? !0 : !1;
}, code:"AX_TEXT_01", ruleName:"Controls and media elements should have labels"});
axs.AuditRules.addRule({name:"duplicateId", heading:"Any ID referred to via an IDREF must be unique in the DOM", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_html_02", severity:axs.constants.Severity.SEVERE, opt_requires:{idRefs:!0}, relevantElementMatcher:function(a, b) {
  b.idrefs.length && !b.hidden && this.relatedElements.push({element:a, flags:b});
  return a.hasAttribute("id") ? !0 : !1;
}, isRelevant:function(a, b) {
  var c = a.id, d = b.level;
  return this.relatedElements.some(function(a) {
    var b = a.flags.idrefs;
    return a.flags.level === d && 0 <= b.indexOf(c);
  });
}, test:function(a) {
  var b = "[id='" + a.id.replace(/'/g, "\\'") + "']";
  return 1 < a.ownerDocument.querySelectorAll(b).length;
}, code:"AX_HTML_02"});
axs.AuditRules.addRule({name:"focusableElementNotVisibleAndNotAriaHidden", heading:"These elements are focusable but either invisible or obscured by another element", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_focus_01", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  if (!axs.browserUtils.matchSelector(a, axs.utils.FOCUSABLE_ELEMENTS_SELECTOR)) {
    return !1;
  }
  if (0 <= a.tabIndex) {
    return !0;
  }
  for (var b = axs.dom.parentElement(a);null != b;b = axs.dom.parentElement(b)) {
    if (axs.utils.elementIsAriaWidget(b)) {
      return !1;
    }
  }
  a = axs.properties.findTextAlternatives(a, {});
  return null === a || "" === a.trim() ? !1 : !0;
}, test:function(a, b) {
  if (b.hidden) {
    return !1;
  }
  a.focus();
  return !axs.utils.elementIsVisible(a);
}, code:"AX_FOCUS_01"});
axs.AuditRules.addRule({name:"humanLangMissing", heading:"The web page should have the content's human language indicated in the markup", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_html_01", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return a instanceof a.ownerDocument.defaultView.HTMLHtmlElement;
}, test:function(a) {
  return a.lang ? !1 : !0;
}, code:"AX_HTML_01"});
axs.AuditRules.addRule({name:"imagesWithoutAltText", heading:"Images should have a text alternative or presentational role", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_text_02", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a, b) {
  return axs.browserUtils.matchSelector(a, "img") && !b.hidden;
}, test:function(a) {
  if (a.hasAttribute("alt") && "" == a.alt || "presentation" == a.getAttribute("role")) {
    return !1;
  }
  var b = {};
  axs.properties.findTextAlternatives(a, b);
  return 0 == Object.keys(b).length ? !0 : !1;
}, code:"AX_TEXT_02"});
axs.AuditRules.addRule({name:"linkWithUnclearPurpose", heading:"The purpose of each link should be clear from the link text", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_text_04", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a, b) {
  return axs.browserUtils.matchSelector(a, "a[href]") && !b.hidden;
}, test:function(a, b, c) {
  c = c || {};
  var d = c.blacklistPhrases || [], e = /\s+/;
  for (b = 0;b < d.length;b++) {
    var f = "^\\s*" + d[b].trim().replace(e, "\\s*") + "s*[^a-z]$";
    if ((new RegExp(f, "i")).test(a.textContent)) {
      return !0;
    }
  }
  c = c.stopwords || "click tap go here learn more this page link about".split(" ");
  a = axs.properties.findTextAlternatives(a, {});
  if (null === a || "" === a.trim()) {
    return !0;
  }
  a = a.replace(/[^a-zA-Z ]/g, "");
  for (b = 0;b < c.length;b++) {
    if (a = a.replace(new RegExp("\\b" + c[b] + "\\b", "ig"), ""), "" == a.trim()) {
      return !0;
    }
  }
  return !1;
}, code:"AX_TEXT_04"});
axs.AuditRules.addRule({name:"lowContrastElements", heading:"Text elements should have a reasonable contrast ratio", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_color_01", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a, b) {
  return !b.disabled && axs.properties.hasDirectTextDescendant(a);
}, test:function(a) {
  var b = window.getComputedStyle(a, null);
  return (a = axs.utils.getContrastRatioForElementWithComputedStyle(b, a)) && axs.utils.isLowContrast(a, b);
}, code:"AX_COLOR_01"});
axs.AuditRules.addRule({name:"mainRoleOnInappropriateElement", heading:"role=main should only appear on significant elements", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_05", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "[role~=main]");
}, test:function(a) {
  if (axs.utils.isInlineElement(a)) {
    return !0;
  }
  a = axs.properties.getTextFromDescendantContent(a);
  return !a || 50 > a.length ? !0 : !1;
}, code:"AX_ARIA_05"});
axs.AuditRules.addRule({name:"elementsWithMeaningfulBackgroundImage", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a, b) {
  return !b.hidden;
}, heading:"Meaningful images should not be used in element backgrounds", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_image_01", test:function(a) {
  if (a.textContent && 0 < a.textContent.length) {
    return !1;
  }
  a = window.getComputedStyle(a, null);
  var b = a.backgroundImage;
  if (!b || "undefined" === b || "none" === b || 0 != b.indexOf("url")) {
    return !1;
  }
  b = parseInt(a.width, 10);
  a = parseInt(a.height, 10);
  return 150 > b && 150 > a;
}, code:"AX_IMAGE_01"});
axs.AuditRules.addRule({name:"multipleAriaOwners", heading:"An element's ID must not be present in more that one aria-owns attribute at any time", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_07", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "[aria-owns]");
}, test:function(a) {
  return axs.utils.getIdReferents("aria-owns", a).some(function(a) {
    return 1 < axs.utils.getAriaIdReferrers(a, "aria-owns").length;
  });
}, code:"AX_ARIA_07"});
axs.AuditRules.addRule({name:"multipleLabelableElementsPerLabel", heading:"A label element may not have labelable descendants other than its labeled control.", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#-ax_text_03--labels-should-only-contain-one-labelable-element", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "label");
}, test:function(a) {
  if (1 < a.querySelectorAll(axs.utils.LABELABLE_ELEMENTS_SELECTOR).length) {
    return !0;
  }
}, code:"AX_TEXT_03"});
axs.AuditRules.addRule({name:"nonExistentRelatedElement", heading:"Attributes which refer to other elements by ID should refer to elements which exist in the DOM", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_html_03", severity:axs.constants.Severity.SEVERE, opt_requires:{idRefs:!0}, relevantElementMatcher:function(a, b) {
  return 0 < b.idrefs.length;
}, test:function(a, b) {
  return b.idrefs.some(function(a) {
    return !document.getElementById(a);
  });
}, code:"AX_HTML_03"});
axs.AuditRules.addRule({name:"pageWithoutTitle", heading:"The web page should have a title that describes topic or purpose", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_title_01", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return "html" == a.tagName.toLowerCase();
}, test:function(a) {
  a = a.querySelector("head");
  return a ? (a = a.querySelector("title")) ? !a.textContent : !0 : !0;
}, code:"AX_TITLE_01"});
axs.AuditRules.addRule({name:"requiredAriaAttributeMissing", heading:"Elements with ARIA roles must have all required attributes for that role", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_03", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "[role]");
}, test:function(a) {
  var b = axs.utils.getRoles(a);
  if (!b.valid) {
    return !1;
  }
  for (var c = 0;c < b.roles.length;c++) {
    var d = b.roles[c].details.requiredPropertiesSet, e;
    for (e in d) {
      if (d = e.replace(/^aria-/, ""), !("defaultValue" in axs.constants.ARIA_PROPERTIES[d] || a.hasAttribute(e)) && 0 > axs.properties.getNativelySupportedAttributes(a).indexOf(e)) {
        return !0;
      }
    }
  }
}, code:"AX_ARIA_03"});
(function() {
  function a(a) {
    a = axs.utils.getRoles(a);
    if (!a || !a.applied) {
      return [];
    }
    a = a.applied;
    return a.valid ? a.details.mustcontain || [] : [];
  }
  axs.AuditRules.addRule({name:"requiredOwnedAriaRoleMissing", heading:"Elements with ARIA roles must ensure required owned elements are present", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_08", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(b) {
    return axs.browserUtils.matchSelector(b, "[role]") ? 0 < a(b).length : !1;
  }, test:function(b) {
    if ("true" === b.getAttribute("aria-busy")) {
      return !1;
    }
    for (var c = a(b), d = c.length - 1;0 <= d;d--) {
      var e = axs.utils.findDescendantsWithRole(b, c[d]);
      if (e && e.length) {
        return !1;
      }
    }
    b = axs.utils.getIdReferents("aria-owns", b);
    for (d = b.length - 1;0 <= d;d--) {
      if ((e = axs.utils.getRoles(b[d], !0)) && e.applied) {
        for (var e = e.applied, f = c.length - 1;0 <= f;f--) {
          if (e.name === c[f]) {
            return !1;
          }
        }
      }
    }
    return !0;
  }, code:"AX_ARIA_08"});
})();
axs.AuditRules.addRule({name:"roleTooltipRequiresDescribedby", heading:"Elements with role=tooltip should have a corresponding element with aria-describedby", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_02", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(a, b) {
  return axs.browserUtils.matchSelector(a, "[role=tooltip]") && !b.hidden;
}, test:function(a) {
  a = axs.utils.getAriaIdReferrers(a, "aria-describedby");
  return !a || 0 === a.length;
}, code:"AX_TOOLTIP_01"});
axs.AuditRules.addRule({name:"tabIndexGreaterThanZero", heading:"Avoid positive integer values for tabIndex", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_focus_03", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "[tabindex]");
}, test:function(a) {
  if (0 < a.tabIndex) {
    return !0;
  }
}, code:"AX_FOCUS_03"});
(function() {
  function a(a) {
    if (0 == a.childElementCount) {
      return !0;
    }
    if (a.hasAttribute("role") && "presentation" != a.getAttribute("role")) {
      return !1;
    }
    if ("presentation" == a.getAttribute("role")) {
      a = a.querySelectorAll("*");
      for (var c = 0;c < a.length;c++) {
        if ("TR" != a[c].tagName && "TD" != a[c].tagName) {
          return !1;
        }
      }
      return !0;
    }
    return !1;
  }
  axs.AuditRules.addRule({name:"tableHasAppropriateHeaders", heading:"Tables should have appropriate headers", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_table_01", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(b) {
    return axs.browserUtils.matchSelector(b, "table") && !a(b) && 0 < b.querySelectorAll("tr").length;
  }, test:function(a) {
    a = a.querySelectorAll("tr");
    var c;
    a: {
      c = a[0].children;
      for (var d = 0;d < c.length;d++) {
        if ("TH" != c[d].tagName) {
          c = !0;
          break a;
        }
      }
      c = !1;
    }
    if (c) {
      a: {
        for (c = 0;c < a.length;c++) {
          if ("TH" != a[c].children[0].tagName) {
            c = !0;
            break a;
          }
        }
        c = !1;
      }
    }
    if (c) {
      a: {
        c = a[0].children;
        for (d = 1;d < c.length;d++) {
          if ("TH" != c[d].tagName) {
            c = !0;
            break a;
          }
        }
        for (d = 1;d < a.length;d++) {
          if ("TH" != a[d].children[0].tagName) {
            c = !0;
            break a;
          }
        }
        c = !1;
      }
    }
    return c;
  }, code:"AX_TABLE_01"});
})();
(function() {
  axs.AuditRules.addRule({name:"uncontrolledTabpanel", heading:"A tabpanel should be related to a tab via aria-controls or aria-labelledby", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_13", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
    return axs.browserUtils.matchSelector(a, '[role="tabpanel"]');
  }, test:function(a) {
    var b;
    b = document.querySelectorAll('[role="tab"][aria-controls="' + a.id + '"]');
    (b = a.id && 1 === b.length) || (a.hasAttribute("aria-labelledby") ? (a = document.querySelectorAll("#" + a.getAttribute("aria-labelledby")), b = 1 === a.length && "tab" === a[0].getAttribute("role")) : b = !1);
    return !b;
  }, code:"AX_ARIA_13"});
})();
axs.AuditRules.addRule({name:"unfocusableElementsWithOnClick", heading:"Elements with onclick handlers must be focusable", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_focus_02", severity:axs.constants.Severity.WARNING, opt_requires:{consoleAPI:!0}, relevantElementMatcher:function(a, b) {
  return a instanceof a.ownerDocument.defaultView.HTMLBodyElement || b.hidden ? !1 : "click" in getEventListeners(a) ? !0 : !1;
}, test:function(a) {
  return !a.hasAttribute("tabindex") && !axs.utils.isElementImplicitlyFocusable(a) && !a.disabled;
}, code:"AX_FOCUS_02"});
(function() {
  var a = /^aria\-/, b = axs.utils.getSelectorForAriaProperties(axs.constants.ARIA_PROPERTIES);
  axs.AuditRules.addRule({name:"unsupportedAriaAttribute", heading:"This element has an unsupported ARIA attribute", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_aria_10", severity:axs.constants.Severity.SEVERE, relevantElementMatcher:function(a) {
    return axs.browserUtils.matchSelector(a, b);
  }, test:function(b) {
    var d = axs.utils.getRoles(b, !0), d = d && d.applied ? d.applied.details.propertiesSet : axs.constants.GLOBAL_PROPERTIES;
    b = b.attributes;
    for (var e = 0, f = b.length;e < f;e++) {
      var g = b[e].name;
      if (a.test(g)) {
        var h = g.replace(a, "");
        if (axs.constants.ARIA_PROPERTIES.hasOwnProperty(h) && !(g in d)) {
          return !0;
        }
      }
    }
    return !1;
  }, code:"AX_ARIA_10"});
})();
axs.AuditRules.addRule({name:"videoWithoutCaptions", heading:"Video elements should use <track> elements to provide captions", url:"https://github.com/GoogleChrome/accessibility-developer-tools/wiki/Audit-Rules#ax_video_01", severity:axs.constants.Severity.WARNING, relevantElementMatcher:function(a) {
  return axs.browserUtils.matchSelector(a, "video");
}, test:function(a) {
  return !a.querySelectorAll("track[kind=captions]").length;
}, code:"AX_VIDEO_01"});

  return axs;
});

// Define AMD module if possible, export globals otherwise.
if (typeof define !== 'undefined' && define.amd) {
  define([], fn);
} else {
  var axs = fn.call(this);
}

