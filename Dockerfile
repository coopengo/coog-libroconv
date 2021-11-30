from debian:stable-slim

RUN apt-get update && apt upgrade -y \
    python3 \
    python3-pip \
    uwsgi-plugin-python3 \
    libreoffice-common \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress

RUN mkdir /app
RUN mkdir /app/tests
RUN mkdir /home/coog/
RUN mkdir /home/coog_saas/
WORKDIR /app
COPY ./requirements.txt /tmp/requirements.txt
COPY ./convert_app.py /app/convert_app.py
COPY ./tests/test_liveness.odt /app/tests/test_liveness.odt
COPY ep.sh /usr/bin/

RUN set -eux; \
    groupadd -g 1003 coog; \
    groupadd -g 1000 coog_saas; \
    useradd -u 1003 -g coog -G coog,coog_saas coog; \
    useradd -u 1000 -g coog_saas -G coog,coog_saas coog_saas; \
    chown coog:coog /app -R; \
    chown coog:coog /home/coog -R; \
    chown coog:coog /home/coog_saas -R; \
    chmod -R 771 /app;  \
    chmod -R 2771 /home/coog;  \
    chmod -R 2771 /home/coog_saas;  \
    ln -s /usr/bin/python3 /usr/bin/python;


RUN pip3 install -r /tmp/requirements.txt

USER coog

EXPOSE 5000

# Startup
ENTRYPOINT ep.sh
