#!/usr/bin/python

from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages
import qutebrowser

def read_file(name):
    with open(name) as f:
        return f.read()

setup(
    name='qutebrowser',
    version=qutebrowser.__version__,
    description="A keyboard-driven, vim-like browser based on PyQt5 and "
                "QtWebKit.",
    long_description=read_file('README'),
    url='http://www.qutebrowser.org/',
    author="Florian Bruhin",
    author_email='me@qutebrowser.org',
    license='GPL',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 or later '
            '(GPLv3+)',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: Microsoft :: Windows :: Windows XP',
        'Operating System :: Microsoft :: Windows :: Windows 7',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Browsers',
    ],
    keywords='pyqt browser web qt webkit',
    packages=find_packages(exclude=['qutebrowser.test']),
    include_package_data=True,
    package_data={'qutebrowser': ['html/*']},
    entry_points={'gui_scripts': ['qutebrowser = qutebrowser.__main__:main']},
    test_suite='qutebrowser.test',
    zip_safe=True,
)
