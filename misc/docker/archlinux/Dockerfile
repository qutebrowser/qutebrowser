FROM base/archlinux
MAINTAINER Florian Bruhin <me@the-compiler.org>

RUN echo 'Server = http://mirror.de.leaseweb.net/archlinux/$repo/os/$arch' > /etc/pacman.d/mirrorlist
RUN pacman-key --init && pacman-key --populate archlinux && pacman -Sy --noconfirm archlinux-keyring
RUN pacman -S --noconfirm pacman && pacman-db-upgrade

RUN pacman -Suyy --noconfirm \
    git \
    python-tox \
    qt5-base \
    qt5-webkit \
    python-pyqt5 \
    xorg-xinit \
    xorg-server-xvfb

RUN echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen && locale-gen

RUN useradd user && mkdir /home/user && chown -R user:users /home/user
USER user
WORKDIR /home/user

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8

CMD git clone /outside qutebrowser.git && \
    cd qutebrowser.git && \
    tox -e py35
