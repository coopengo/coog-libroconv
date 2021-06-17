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
WORKDIR /app
COPY ./requirements.txt /tmp/requirements.txt
COPY ./convert_app.py /app/convert_app.py

RUN set -eux \
    && adduser --uid 1003 coog --disabled-login \
    && chown coog:coog /app -R \
    && chmod -R 771 /app -R \
    && ln -s /usr/bin/python3 /usr/bin/python


RUN pip3 install -r /tmp/requirements.txt

USER coog

EXPOSE 5000

# Startup
ENTRYPOINT uwsgi --plugins http,python3 --http 0.0.0.0:5000 --master --wsgi-file convert_app.py --callable app --processes 8 --post-buffering 50000 --http-timeout 120
#ENTRYPOINT uwsgi --version
#ENTRYPOINT python --version
