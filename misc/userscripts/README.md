# Userscripts

The following userscripts are included in the current directory.

- [cast](./cast): Cast content on your Chromecast using [castnow][]. Only
  [youtube-dl][] downloadable content.
- [dmenu_qutebrowser](./dmenu_qutebrowser): Pipes history, quickmarks, and URL into dmenu.
- [format_json](./format_json): Pretty prints current page's JSON code in other
  tab.
- [getbib](./getbib): Scraping the current web page for DOIs and downloading
  corresponding bibtex information.
- [open_download](./open_download): Opens a rofi menu with
  all files from the download directory and opens the selected file.
- [openfeeds](./openfeeds): Opens all links to feeds defined in the head of a site.
- [password_fill](./password_fill): Find a username/password entry and fill it
  with credentials given by the configured backend (currently only pass) for the
  current website.
- [qute-keepass](./qute-keepass): Insertion of usernames and passwords from keepass
  databases using pykeepass.
- [qute-pass](./qute-pass): Insert login information using pass and a
  dmenu-compatible application (e.g. dmenu, rofi -dmenu, ...).
- [qute-lastpass](./qute-lastpass): Similar to qute-pass, for Lastpass.
- [qute-bitwarden](./qute-bitwarden): Similar to qute-pass, for Bitwarden.
- [qutedmenu](./qutedmenu): Handle open -s && open -t with bemenu.
- [readability](./readability): Executes python-readability on current page and
  opens the summary as new tab.
- [readability-js](./readability-js): Processes the current page with the readability 
  library used in Firefox Reader View and opens the summary as new tab.
- [ripbang](./ripbang): Adds DuckDuckGo bang as searchengine.
- [rss](./rss): Keeps track of URLs in RSS feeds and opens new ones.
- [taskadd](./taskadd): Adds a task to taskwarrior.
- [tor_identity](./tor_identity): Change your tor identity.
- [view_in_mpv](./view_in_mpv): Views the current web page in mpv using
  sensible mpv-flags.

[castnow]: https://github.com/xat/castnow
[youtube-dl]: https://rg3.github.io/youtube-dl/

## Others

The following userscripts can be found on their own repositories.

- [qurlshare](https://github.com/sim590/qurlshare): *secure* sharing of an URL between qutebrowser
  instances using a distributed hash table.
- [qutebrowser-userscripts](https://github.com/cryzed/qutebrowser-userscripts):
  a small pack of userscripts.
- [qutebrowser-zotero](https://github.com/parchd-1/qutebrowser-zotero): connects
  qutebrowser to [Zotero][] standalone.
- [qute.match](https://github.com/bziur/qute.match): execute script based on
  visited url.
- [qutepocket](https://github.com/kepi/qutepocket): Add URL to your [Pocket][]
  bookmark manager.
- [qb-scripts](https://github.com/peterjschroeder/qb-scripts): a small pack of
  userscripts.
- [instapaper.zsh](https://github.com/dmcgrady/instapaper.zsh): Add URL to
  your [Instapaper][] bookmark manager.
- [qtb.us](https://github.com/Chinggis6/qtb.us): small pack of userscripts.
- [pinboard.zsh](https://github.com/dmix/pinboard.zsh): Add URL to your
  [Pinboard][] bookmark manager.
- [qute-capture](https://github.com/alcah/qute-capture): Capture links with
  Emacs's org-mode to a read-later file.
- [qute-code-hint](https://github.com/LaurenceWarne/qute-code-hint): Copy code
  snippets on web pages to the clipboard via hints.

[Zotero]: https://www.zotero.org/
[Pocket]: https://getpocket.com/
[Instapaper]: https://www.instapaper.com/
[Pinboard]: https://pinboard.in/
