# The official quay.io/minio/mc image (UBI9) requires an x86-64-v2 CPU.
# This host is a KVM guest exposing a generic x86-64 CPU, so we copy the (static) mc binary
# onto a Debian base instead. MinIO no longer serves mc binaries from dl.min.io, hence the
# copy from the official image, pinned by digest (mc RELEASE.2025-08-13T08-35-41Z).
FROM quay.io/minio/mc@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727 AS mc

FROM debian:bookworm-slim
COPY --from=mc /usr/bin/mc /usr/bin/mc
ENTRYPOINT ["mc"]
