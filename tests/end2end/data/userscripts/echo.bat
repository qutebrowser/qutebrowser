@echo off
rem This is needed because echo does not exist as an external program on
rem Windows, so we can't call echo(.exe) from qutebrowser, but it's useful for
rem tests. This little file is callable via :spawn and mimics (in a very naive
rem way) the echo command line utility.
echo %*
