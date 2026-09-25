# The official quay.io/keycloak/keycloak images (UBI9) require an x86-64-v2 CPU.
# This host is a KVM guest exposing a generic x86-64 CPU, so we run the official
# Keycloak distribution on a Temurin (Ubuntu) JRE instead.
FROM eclipse-temurin:21-jre-jammy

ARG KEYCLOAK_VERSION=26.7.4
ARG KEYCLOAK_SHA256=04823c336b797a7e18889a44262a7a64e6bf624cbbcc518c85e2622176ff2eee

RUN curl -fsSL -o /tmp/keycloak.tar.gz \
        https://github.com/keycloak/keycloak/releases/download/${KEYCLOAK_VERSION}/keycloak-${KEYCLOAK_VERSION}.tar.gz \
    && echo "${KEYCLOAK_SHA256}  /tmp/keycloak.tar.gz" | sha256sum -c - \
    && mkdir -p /opt/keycloak \
    && tar -xzf /tmp/keycloak.tar.gz -C /opt/keycloak --strip-components=1 \
    && rm /tmp/keycloak.tar.gz \
    && useradd -r -u 1000 -g 0 -d /opt/keycloak keycloak \
    && chown -R 1000:0 /opt/keycloak \
    && chmod -R g+rwX /opt/keycloak

USER 1000
WORKDIR /opt/keycloak
EXPOSE 8080 9000
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
