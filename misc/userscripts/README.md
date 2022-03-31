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
- [qute-keepassxc](./qute-keepassxc): Insert credentials from open KeepassXC database
  using keepassxc-browser protocol.
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
- [qr](./qr): Show a QR code for the current webpage via
  [qrencode](https://fukuchi.org/works/qrencode/).
- [kodi](./kodi): Play videos in Kodi.
- [add-nextcloud-bookmarks](./add-nextcloud-bookmarks): Create bookmarks in Nextcloud's Bookmarks app.
- [add-nextcloud-cookbook](./add-nextcloud-cookbook): Add recipes to Nextcloud's Cookbook app.

[castnow]: https://github.com/xat/castnow
[youtube-dl]: https://rg3.github.io/youtube-dl/

## Others

The following userscripts can be found on their own repositories.

- [qurlshare](https://github.com/sim590/qurlshare): *secure* sharing of a URL between qutebrowser
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
- [Qute-Translate](https://github.com/AckslD/Qute-Translate): Translate URLs or
  selections via Google Translate.
- [qute-snippets](https://github.com/Aledosim/qute-snippets): Bind text snippets to a keyword
   and retrieve they when you want.
- [doi](https://github.com/cadadr/configuration/blob/master/qutebrowser/userscripts/doi):
  Opens DOIs on Sci-Hub.
- [1password](https://github.com/tomoakley/dotfiles/blob/master/qutebrowser/userscripts/1password):
  Integration with 1password on macOS.
- [localhost](https://github.com/SidharthArya/.qutebrowser/blob/master/userscripts/localhost):
  Quickly navigate to localhost:port. For reference: [A quicker way to reach localhost with qutebrowser](https://sidhartharya.me/a-quicker-way-to-reach-localhost-with-qutebrowser/)
- [untrack-url](https://github.com/qutebrowser/qutebrowser/discussions/6555),
  convert various URLs (YouTube/Reddit/Twitter/Instagram/Google Maps) to other
  services (Invidious, Teddit, Nitter, Bibliogram, OpenStreetMap).
- [CIAvash/qutebrowser-userscripts](https://github.com/CIAvash/qutebrowser-userscripts),
  various small userscripts written in Raku.
- [bitwarden-rofi](https://github.com/haztecaso/bitwarden-rofi), rofi wrapper for bitwarden cli
  interface using gpg instead of keyctl.
- [yomichad](https://github.com/potamides/yomichad): Japanese pop-up dictionary
  for looking up readings and definitions of currently selected words, kanji
  and names
- [~palb91/qutescripts](https://git.sr.ht/~palb91/qutescripts): A list of
  personal userscripts for qutebrowser (`domcycle`:settings per domain,
  `gitclone`, `jsdownload`: smart download, and `substiqute`: bash-like url
  substitution)
  
[Zotero]: https://www.zotero.org/
[Pocket]: https://getpocket.com/
[Instapaper]: https://www.instapaper.com/
[Pinboard]: https://pinboard.in/
