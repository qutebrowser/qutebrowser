"use strict";


window._qutebrowser.plugin = (function(){
    const plugin = {}
    var channel = new QWebChannel(qt.webChannelTransport, function(channel) {
        plugin.run = function(command, count) {
            return channel.objects.handler.run_command(command, count)
        }
    })
    // run command with options
    return plugin
})()
