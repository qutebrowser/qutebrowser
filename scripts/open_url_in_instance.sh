#!/bin/bash
# initial idea: Florian Bruhin (The-Compiler)
# author: Thore Bödecker (foxxx0)

_url="$1"
_qb_version='0.10.1'
_proto_version=1
_ipc_socket="${XDG_RUNTIME_DIR}/qutebrowser/ipc-$(echo -n "$USER" | md5sum | cut -d' ' -f1)"

if [[ -e "${_ipc_socket}" ]]; then
	exec printf '{"args": ["%s"], "target_arg": null, "version": "%s", "protocol_version": %d, "cwd": "%s"}\n' \
				"${_url}" \
				"${_qb_version}" \
				"${_proto_version}" \
				"${PWD}" | socat - UNIX-CONNECT:"${_ipc_socket}"
else
    exec /usr/bin/qutebrowser --backend webengine "$@"
fi
