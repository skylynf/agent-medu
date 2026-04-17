#!/bin/sh
# 替换 nginx 配置模板中的 BACKEND_HOST 和 NGINX_LOCAL_RESOLVERS。
# 只替换这两个变量，$uri / $host / $backend 等 nginx 内置变量原样保留。
set -e

# NGINX_LOCAL_RESOLVERS 由 15-local-resolvers.envsh 注入；
# 若不可用（子进程环境隔离），则直接从 /etc/resolv.conf 读取 nameserver。
if [ -z "${NGINX_LOCAL_RESOLVERS}" ]; then
    NGINX_LOCAL_RESOLVERS=$(awk 'BEGIN{ORS=" "} /^nameserver/{print $2}' /etc/resolv.conf | sed 's/ *$//')
fi
# 最终兜底：Docker 内置 DNS
: "${NGINX_LOCAL_RESOLVERS:=127.0.0.11}"

export NGINX_LOCAL_RESOLVERS

envsubst '$BACKEND_HOST $NGINX_LOCAL_RESOLVERS' \
    < /etc/nginx/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "40-backend-config.sh: nginx config generated"
echo "  BACKEND_HOST          = ${BACKEND_HOST}"
echo "  NGINX_LOCAL_RESOLVERS = ${NGINX_LOCAL_RESOLVERS}"
