FROM ubuntu:22.04
COPY payload/ /opt/
ENV PATH=/opt/python/bin:/opt/mysql/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONHOME=/opt/python LD_LIBRARY_PATH=/opt/native \
    SSL_CERT_FILE=/opt/certs/ca-certificates.crt LANG=C.UTF-8
WORKDIR /opt/app
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=20s --timeout=5s --start-period=180s CMD /opt/python/bin/python3.13 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz',timeout=3)" || exit 1
ENTRYPOINT ["/opt/python/bin/python3.13", "/opt/app/deployment/entry.py"]
