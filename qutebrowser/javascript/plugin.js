"use strict";


window.Qute = {
    channel: new QWebChannel(qt.webChannelTransport, function(channel) {
        window.addEventListener('qute', function (e) {
            const { detail } = e
            if (detail.type == 'command') {
                channel.objects.handler.run_command(
                    e.detail.command,
                    e.detail.count || 1
                )
            }
        })
    }),
    // run command with options
    run(command, options) {
        options = Object.assign({node: window, count: 1}, options)
        options.node.dispatchEvent(new CustomEvent('qute', {
            bubbles: true,
            detail: { type: 'command', command, count: options.count}
        }))
    }
}
