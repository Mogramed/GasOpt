FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend/ ./
RUN npm run build
FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=4 \
 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
