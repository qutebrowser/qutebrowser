This directory contains various `requirements` files which are used by `tox` to
have reproducable tests with pinned versions.

The files are generated based on unpinned requirements in `*.txt-raw` files.

Those files can also contain some special commands:

- Add an additional comment to a line: `#@ comment: <package> <comment here>`
- Filter a line for requirements.io: `#@ filter: <package> <filter>`
- Don't include a package in the output: `#@ ignore: <package>` (or multiple packages)
- Replace a part of a frozen package specification with another: `#@ replace <regex> <replacement>`

Some examples:

```
#@ comment: mypkg blah blub
#@ filter: mypkg != 1.0.0
#@ ignore: mypkg, otherpkg
#@ replace: foo bar
```
