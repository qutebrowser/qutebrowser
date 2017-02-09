#compdef qutebrowser

local ret=1

_arguments -s : \
  '(- *)'{-h,--help}'[show the help message]' \
  '(- *)'{-V,--version}'[show version information]' \
  '(-h --help -V --version --basedir)--basedir[base directory for all storage.]:storage base directory:_directories' \
  '(-h --help -V --version)'-{s,-set}'[set a temporary setting for this session]:option:' \
  '(-h --help -V --version -r --restore)'-{r,-restore}'[restore a named session]:session name:' \
  '(-h --help -V --version -R --override-restore)'-{R,-override-restore}'[do not restore a session]' \
  '(-h --help -V --version --target)--target[how to open URLs in running instance]:open URLs in:(auto tab tab-bg tab-silent tab-bg-silent window)' \
  '(-h --help -V --version --backend)--backend[which backend to use]:backend:(webkit webengine)' \
  '(-h --help -V --version --enable-webengine-inspector)--enable-webengine-inspector[enable web inspector for QtWebEngine]' \
  '(-h --help -V --version -l --loglevel)'-{l,-loglevel}'[set loglevel]:log level:(critical error warning info debug vdebug)' \
  '(-h --help -V --version --logfilter)--logfilter[what to log to stdout]:log items:' \
  '(-h --help -V --version --loglines)--loglines[log lines to keep in RAM]:lines:_integer' \
  '(-h --help -V --version --debug)--debug[turn on debugging options]' \
  '(-h --help -V --version --json-logging)--json-logging[output log in json]' \
  '(-h --help -V --version --nocolor)--nocolor[turn off coled logging]' \
  '(-h --help -V --version --force-color)--force-color[force coled logging]' \
  '(-h --help -V --version --harfbuzz)--harfbuzz[harfbuzz version to use]:harfbuzz engine:(old new system auto)' \
  '(-h --help -V --version --relaxed-config)--relaxed-config[silently remove unknown config options]' \
  '(-h --help -V --version --nowindow)--nowindow[do not show main window]' \
  '(-h --help -V --version --debug-exit)--debug-exit[turn on debugging of late exit]' \
  '(-h --help -V --version --pdb-postmortem)--pdb-postmortem[Drop into pdb on exceptions]' \
  '(-h --help -V --version --temp-basedir)--temp-basedir[Use a temporary basedir]' \
  '(-h --help -V --version --no-err-windows)--no-err-windows[Don'\''t show any error windows]' \
  '(-h --help -V --version)--qt-arg[pass an argument with a value to Qt]:option and argument:' \
  '(-h --help -V --version)--qt-flag[pass an argument to Qt as flag]:flag:' \
  ':URL:_urls' \
  && ret=0

# TODO: complete internal commands
