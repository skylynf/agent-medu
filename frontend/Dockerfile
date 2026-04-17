FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/templates/default.conf.template /etc/nginx/templates/default.conf.template

# Railway：在前端服务环境变量中设置 BACKEND_HOST=<后端服务名>.railway.internal:8000（需开启私有网络）
# 本地 Docker Compose 服务名一般为 backend
ENV BACKEND_HOST=backend:8000

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
