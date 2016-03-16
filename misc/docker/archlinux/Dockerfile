FROM base/archlinux
MAINTAINER Florian Bruhin <me@the-compiler.org>

RUN echo 'Server = http://mirror.de.leaseweb.net/archlinux/$repo/os/$arch' > /etc/pacman.d/mirrorlist
RUN pacman-key --init && pacman-key --populate archlinux && pacman -Sy --noconfirm archlinux-keyring

RUN pacman-key -r 0xD6A1C70FE80A0C82 && \
    pacman-key --lsign-key 0xD6A1C70FE80A0C82 && \
    echo -e '[qt-debug]\nServer = http://qutebrowser.org/qt-debug/$arch' >> /etc/pacman.conf

RUN pacman -Suyy --noconfirm
RUN pacman-db-upgrade

RUN pacman -S --noconfirm \
    git \
    python-tox \
    qt5-base-debug \
    qt5-webkit-debug \
    python-pyqt5-debug \
    xorg-xinit \
    herbstluftwm \
    xorg-server-xvfb

RUN echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen && locale-gen

RUN useradd user && mkdir /home/user && chown -R user:users /home/user
USER user
WORKDIR /home/user

ENV DISPLAY=:0
ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8

CMD Xvfb -screen 0 800x600x24 :0 & \
    sleep 2 && \
    herbstluftwm & \
    git clone /outside qutebrowser.git && \
    cd qutebrowser.git && \
    tox -e py35
