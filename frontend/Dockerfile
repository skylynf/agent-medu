FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# 模板放在 /etc/nginx/（不放 /etc/nginx/templates/），
# 避免 nginx 镜像自带的 20-envsubst-on-templates.sh 用全量 env 替换，
# 导致 nginx 内置变量（$uri / $host 等）被错误清空。
COPY nginx/templates/default.conf.template /etc/nginx/default.conf.template

# 自定义启动脚本：只替换 BACKEND_HOST，其余 nginx 变量原样保留
COPY nginx/docker-entrypoint.d/40-backend-config.sh /docker-entrypoint.d/40-backend-config.sh
RUN chmod +x /docker-entrypoint.d/40-backend-config.sh

# Railway：在前端服务环境变量中设置 BACKEND_HOST=<后端内网主机>:<端口>
# 例如 backend.railway.internal:8000（需在 Railway 开启私有网络）
# 本地 Docker Compose 默认服务名为 backend
ENV BACKEND_HOST=backend:8000

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
