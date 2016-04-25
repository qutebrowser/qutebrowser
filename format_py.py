#!/usr/bin/env python

import os
import autopep8


BASE_DIR = os.path.abspath(__file__)


def fix_file(path):
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            if f.endswith('.py'):
                filename = os.path.abspath(os.path.join(dirpath, f))
                afile = open(filename, 'rw+')
                source_code = afile.read()
                afile.seek(0)
                afile.truncate()
                afile.write(autopep8.fix_code(source_code))
                afile.close()


if __name__ == "__main__":
    path_of_dir = [
        os.path.dirname(BASE_DIR),
    ]
    for x in path_of_dir:
        fix_file(x)
