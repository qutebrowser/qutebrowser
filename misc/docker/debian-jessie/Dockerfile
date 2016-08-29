FROM debian:jessie
MAINTAINER Florian Bruhin <me@the-compiler.org>

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && \
    apt-get -y dist-upgrade && \
    apt-get -y install --no-install-recommends \
            python3-pyqt5 \
            python3-pyqt5.qtquick \
            python3-pyqt5.qtwebkit \
            python-tox \
            python3-sip \
            xvfb \
            xauth \
            git \
            python3-setuptools \
            wget \
            locales \
            libjs-pdf
RUN echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen && locale-gen

RUN useradd user && mkdir /home/user && chown -R user:users /home/user
USER user
WORKDIR /home/user

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8

CMD git clone /outside qutebrowser.git && \
    cd qutebrowser.git && \
    tox -e py34
