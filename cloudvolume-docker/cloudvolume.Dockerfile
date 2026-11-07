FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e

COPY nginx.conf /etc/nginx/nginx.conf
COPY --chmod=755 check-volume.sh /docker-entrypoint.d/05-check-volume.sh

VOLUME ["/mnt/data"]
EXPOSE 1337

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -q --spider http://127.0.0.1:1337/info || exit 1
