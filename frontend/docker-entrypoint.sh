#!/bin/sh
# Sertifika bağlanmışsa HTTPS'i aç, yoksa düz HTTP ile devam et.
set -e

CERT=/etc/nginx/certs/dev-cert.pem
KEY=/etc/nginx/certs/dev-key.pem

if [ -f "$CERT" ] && [ -f "$KEY" ]; then
    cp /etc/nginx/nginx-tls.conf /etc/nginx/conf.d/tls.conf
    # HTTP bloğu artık yalnızca yönlendirir.
    cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
EOF
    echo "[nginx] TLS acik — https://localhost:8443"
else
    echo "[nginx] sertifika yok (certs/), duz HTTP ile calisiyor."
fi

exec nginx -g 'daemon off;'
