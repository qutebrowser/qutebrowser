#!/bin/bash
# initial idea: Florian Bruhin (The-Compiler)
# author: Thore Bödecker (foxxx0)

_url="$1"
_qb_version='0.10.1'
_proto_version=1
_ipc_socket="${XDG_RUNTIME_DIR}/qutebrowser/ipc-$(echo -n "$USER" | md5sum | cut -d' ' -f1)"
_qute_bin="/usr/bin/qutebrowser"

exec printf '{"args": ["%s"], "target_arg": null, "version": "%s", "protocol_version": %d, "cwd": "%s"}\n' \
            "${_url}" \
            "${_qb_version}" \
            "${_proto_version}" \
            "${PWD}" | socat - UNIX-CONNECT:"${_ipc_socket}" 2>/dev/null || $_qute_bin --backend webengine "$@" &
