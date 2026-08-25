# Multi-stage: build the Vite bundle, then serve static files from nginx.
# Not built/run in this sandbox — see backend/Dockerfile's header for why.
#
# Vite bakes VITE_API_BASE_URL in at BUILD time (it's a static-site bundle,
# not a server that reads env vars at request time) — pass it as a build
# arg per environment:
#   docker build --build-arg VITE_API_BASE_URL=https://api.example.com .

FROM node:20-slim AS builder

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

RUN addgroup -g 1000 tprm && adduser -D -u 1000 -G tprm tprm \
    && chown -R tprm:tprm /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid && chown tprm:tprm /var/run/nginx.pid
USER tprm

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O- http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
