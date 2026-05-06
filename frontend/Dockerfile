# ── Stage 1: Build Environment ────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies using clean install for deterministic builds
COPY package*.json ./
RUN npm ci

# Copy full frontend codebase
COPY . .

# Compile optimized production assets
RUN npm run build

# ── Stage 2: Serve Environment ────────────────────────────────
FROM nginx:1.25-alpine

# Copy built HTML/JS/CSS assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy optimized custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
