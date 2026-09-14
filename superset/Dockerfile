FROM apache/superset:4.1.1

USER root
RUN apt-get update \
    && apt-get install -y gcc g++ python3-dev build-essential chromium-driver chromium-l10n \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER superset
RUN pip install --upgrade pip
RUN pip --no-cache-dir install \
    'cryptography>=42.0.4,<43.0.0' \
    Authlib==1.2.1 \
    python-keycloak==3.12.0 \
    python-jose==3.3.0 \
    pydruid \
    psycopg2-binary \
    Pillow \
    openpyxl \
    xlrd

USER root
COPY repan-superset-startup.sh /usr/bin/repan-superset-startup.sh
RUN chmod +x /usr/bin/repan-superset-startup.sh

USER superset

VOLUME ["/app/import"]
CMD ["/usr/bin/repan-superset-startup.sh"]
