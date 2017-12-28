PYTHON = python3
DESTDIR = /
ICONSIZES = 16 24 32 48 64 128 256 512

.PHONY: install

doc/qutebrowser.1.html:
	a2x -f manpage doc/qutebrowser.1.asciidoc

install: doc/qutebrowser.1.html
	$(PYTHON) setup.py install --root="$(DESTDIR)" --optimize=1
	install -Dm644 doc/qutebrowser.1 \
		"$(DESTDIR)/usr/share/man/man1/qutebrowser.1"
	install -Dm644 misc/qutebrowser.desktop \
		"$(DESTDIR)/usr/share/applications/qutebrowser.desktop"
	$(foreach i,$(ICONSIZES),install -Dm644 "icons/qutebrowser-$(i)x$(i).png" \
			"$(DESTDIR)/usr/share/icons/hicolor/$(i)x$(i)/apps/qutebrowser.png";)
	install -Dm644 icons/qutebrowser.svg \
		"$(DESTDIR)/usr/share/icons/hicolor/scalable/apps/qutebrowser.svg"
	install -Dm755 -t "$(DESTDIR)/usr/share/qutebrowser/userscripts/" \
		$(wildcard misc/userscripts/*)
	install -Dm755 -t "$(DESTDIR)/usr/share/qutebrowser/scripts/" \
		$(filter-out scripts/__init__.py scripts/__pycache__ scripts/dev \
		  scripts/testbrowser_cpp scripts/asciidoc2html.py scripts/setupcommon.py \
			scripts/link_pyqt.py,$(wildcard scripts/*))
