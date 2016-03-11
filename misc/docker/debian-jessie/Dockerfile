FROM debian:jessie
MAINTAINER Florian Bruhin <me@the-compiler.org>

RUN apt-get -y update && \
    apt-get -y install python3-pyqt5 python3-pyqt5.qtwebkit python-tox \
                       python3-sip python3-dev xvfb git dbus \
                       python3-setuptools wget xinit build-essential \
                       xserver-xorg-core xserver-xorg-video-dummy herbstluftwm
RUN dbus-uuidgen --ensure
RUN wget http://www.karlrunge.com/x11vnc/Xdummy -O /usr/local/bin/Xdummy && \
    chmod +x /usr/local/bin/Xdummy
RUN Xdummy -install
# Keep image small after Xdummy is installed
RUN apt-get -y purge build-essential && apt-get -y autoremove

RUN useradd user && mkdir /home/user && chown -R user:users /home/user
USER user
WORKDIR /home/user

RUN echo 'exec herbstluftwm' > /home/user/.xinitrc

ENV DISPLAY=:0

CMD startx -- /usr/local/bin/Xdummy :0 & \
    git clone /outside qutebrowser.git && \
    cd qutebrowser.git && \
    tox -e py34
