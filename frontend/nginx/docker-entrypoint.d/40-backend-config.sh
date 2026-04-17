#!/bin/sh
# 只替换 BACKEND_HOST，让 $uri / $host 等 nginx 内置变量原样保留
set -e
envsubst '$BACKEND_HOST' \
    < /etc/nginx/default.conf.template \
    > /etc/nginx/conf.d/default.conf
echo "40-backend-config.sh: generated /etc/nginx/conf.d/default.conf (BACKEND_HOST=${BACKEND_HOST})"
