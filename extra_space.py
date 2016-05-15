# !/usr/bin/env python
'''
This module automatically checks for trailing spaces.
It scans the complete folder, searches for python files
(ignoring the virtual environment python files) and automatially
removes the trailing spaces.
'''

import os
import sys


BASE_DIR = os.path.abspath(__file__)


def fix_file(path):
    '''
    The function, using 'for' loop scans all the directories as well
    as sub-directories of the folder for python file and checks
    for trailing white space.
    '''
    p = ""
    for dirpath, _, filenames in os.walk(path):
        if(os.path.exists(os.path.join(dirpath, 'bin/activate'))):
            p = dirpath
        for f in filenames:
            if f.endswith('.py'):
                filename = os.path.abspath(os.path.join(dirpath, f))
                if (not bool(p)):
                    if os.access(filename, os.W_OK):
                        try:
                            file1 = open(filename, 'r')
                            lines = file1.readlines()
                            for index, line in enumerate(lines):
                                if line.endswith(" \n"):
                                    lines[index] = line.rstrip() + "\n"
                                if line.endswith("\r\n"):
                                    lines[index] = line.rstrip() + "\n"
                                with open(filename, "wb") as file2:
                                        file2.writelines(lines)
                        except:
                            print(filename)
                            print(sys.exc_info()[0])


if __name__ == "__main__":
    path_of_dir = [
        os.path.dirname(BASE_DIR),
    ]
    for x in path_of_dir:
        fix_file(x)
