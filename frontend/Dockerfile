# Multi-stage build for PraktiKit frontend
# Stage 1: Builder - install dependencies and build
FROM node:20-alpine AS builder

WORKDIR /app

# API URL baked at build time.
# Default: empty string → same-origin relative paths, nginx proxies /api → backend.
# Override for split-domain deployment: --build-arg NEXT_PUBLIC_API_URL=https://api.example.com
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the Next.js application (static export → out/)
RUN npm run build

# Stage 2: Production - serve static files with nginx
FROM nginx:alpine

# Copy built static files from builder stage
COPY --from=builder /app/out /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80 || exit 1

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
