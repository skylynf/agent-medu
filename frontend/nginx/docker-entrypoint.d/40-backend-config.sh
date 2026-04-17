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

# nginx resolver 指令要求 IPv6 地址用方括号包裹（如 [fd12::10]），
# 而 /etc/resolv.conf 里的 IPv6 地址没有括号，需要在这里补上。
bracket_ipv6() {
    echo "$1" | awk '{
        n = split($0, parts, " ")
        for (i = 1; i <= n; i++) {
            addr = parts[i]
            # 含冒号说明是 IPv6，且尚未被括号包裹
            if (addr ~ /:/ && addr !~ /^\[/) {
                addr = "[" addr "]"
            }
            printf "%s", addr
            if (i < n) printf " "
        }
        print ""
    }'
}

NGINX_LOCAL_RESOLVERS=$(bracket_ipv6 "${NGINX_LOCAL_RESOLVERS}")
export NGINX_LOCAL_RESOLVERS

envsubst '$BACKEND_HOST $NGINX_LOCAL_RESOLVERS' \
    < /etc/nginx/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "40-backend-config.sh: nginx config generated"
echo "  BACKEND_HOST          = ${BACKEND_HOST}"
echo "  NGINX_LOCAL_RESOLVERS = ${NGINX_LOCAL_RESOLVERS}"
