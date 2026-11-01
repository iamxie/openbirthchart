# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Test instrumentation, not an OS security sandbox.

Blocks Python-level network, subprocesses, Swiss imports/files before engine import.
An OS-isolated audit would be additional evidence, not claimed here.
"""
import importlib.abc
import os
import sys

class ForbiddenDependency(RuntimeError): pass

class RuntimeGuard(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.events = []
        self.data_reads = set()
        self.phase = 'calculation'

    def block(self, kind, detail):
        self.events.append({'phase': self.phase, 'kind': kind, 'detail': str(detail)})
        raise ForbiddenDependency(f'{kind}: {detail}')

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('swisseph', 'pyswisseph', 'pysweph'):
            self.block('swiss_import', fullname)
        return None

    def audit(self, event, args):
        if event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.sendto'):
            self.block('network', event)
        if event in ('subprocess.Popen', 'os.system'):
            self.block('subprocess', event)
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = os.fsdecode(args[0]).replace('\\', '/').lower()
            if '/data/reference/' in path or '/.venv-reference/' in path or path.endswith('.se1') or 'swisseph' in path:
                self.block('swiss_file', path)
            if path.endswith(('.bsp', '.leb', '.leb2', '.npz', '.npy', '.se1', '.dat', '.csv')):
                self.data_reads.add(os.path.abspath(os.fsdecode(args[0])))

    def install(self):
        sys.meta_path.insert(0, self)
        sys.addaudithook(self.audit)

    def self_test(self):
        import importlib
        import socket
        self.phase = 'self_test'
        checks = {}
        for name, callback in [('import', lambda: importlib.import_module('swisseph')),
                               ('network', lambda: socket.getaddrinfo('example.invalid', 443)),
                               ('file', lambda: open('forbidden.se1', 'rb'))]:
            try:
                callback()
            except ForbiddenDependency:
                checks[name] = True
            else:
                checks[name] = False
        self.phase = 'calculation'
        if not all(checks.values()):
            raise AssertionError(checks)
        return checks
