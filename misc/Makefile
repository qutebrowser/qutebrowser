PYTHON = python3
PREFIX ?= /usr/local
ICONSIZES = 16 24 32 48 64 128 256 512
DATAROOTDIR = $(PREFIX)/share
DATADIR ?= $(DATAROOTDIR)
MANDIR ?= $(DATAROOTDIR)/man

ifdef DESTDIR
SETUPTOOLSOPTS = --root="$(DESTDIR)"
endif

all: man
	$(PYTHON) setup.py build

man: doc/qutebrowser.1
doc/qutebrowser.1: doc/qutebrowser.1.asciidoc
	a2x -f manpage $<

install: man
	$(PYTHON) setup.py install --prefix="$(PREFIX)" --optimize=1 $(SETUPTOOLSOPTS)
	install -Dm644 misc/org.qutebrowser.qutebrowser.appdata.xml \
		"$(DESTDIR)$(DATADIR)/metainfo/org.qutebrowser.qutebrowser.appdata.xml"
	install -Dm644 doc/qutebrowser.1 \
		"$(DESTDIR)$(MANDIR)/man1/qutebrowser.1"
	install -Dm644 misc/org.qutebrowser.qutebrowser.desktop \
		"$(DESTDIR)$(DATADIR)/applications/org.qutebrowser.qutebrowser.desktop"
	$(foreach i,$(ICONSIZES),install -Dm644 "icons/qutebrowser-$(i)x$(i).png" \
			"$(DESTDIR)$(DATADIR)/icons/hicolor/$(i)x$(i)/apps/qutebrowser.png";)
	install -Dm644 icons/qutebrowser.svg \
		"$(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps/qutebrowser.svg"
	install -Dm755 -t "$(DESTDIR)$(DATADIR)/qutebrowser/userscripts/" \
		$(wildcard misc/userscripts/*)
	install -Dm755 -t "$(DESTDIR)$(DATADIR)/qutebrowser/scripts/" \
		$(filter-out scripts/__init__.py scripts/__pycache__ scripts/dev \
		  scripts/testbrowser scripts/asciidoc2html.py scripts/setupcommon.py \
			scripts/link_pyqt.py,$(wildcard scripts/*))

.PHONY: all man install
