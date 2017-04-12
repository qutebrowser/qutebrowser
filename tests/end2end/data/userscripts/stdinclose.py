#!/usr/bin/python3

import sys
import os
sys.stdin.read()
with open(os.environ['QUTE_FIFO'], 'wb') as fifo:
    fifo.write(b':message-info "stdin closed"\n')
