# ── Build stage ───────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .

ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# ── Production stage — unprivileged nginx (runs as uid 101, not root) ─────────
FROM nginxinc/nginx-unprivileged:1.25-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Port 8080 — required by nginx-unprivileged (cannot bind <1024 without root)
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
