FROM ubuntu:xenial
MAINTAINER Florian Bruhin <me@the-compiler.org>

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && \
    apt-get -y dist-upgrade && \
    apt-get -y install --no-install-recommends \
            python3-pyqt5 \
            python3-pyqt5.qtwebkit \
            python-tox \
            python3-sip \
            xvfb \
            git \
            python3-setuptools \
            wget \
            herbstluftwm \
            language-pack-en \
            libjs-pdf \
            dbus

RUN dbus-uuidgen --ensure

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
    tox -e py34
