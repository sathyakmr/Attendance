# ---- Build stage ----
FROM node:20-slim AS builder

WORKDIR /build
COPY package.json ./
RUN npm install

COPY . .

# Vite inlines import.meta.env.VITE_* at BUILD time, not container runtime —
# these must be passed as Docker build args (see docker-compose.yml's
# `build.args` for this service), not as a runtime `environment:` block,
# or they'll silently have no effect on the compiled bundle.
ARG VITE_IDENTITY_URL=http://localhost:8001
ARG VITE_ATTENDANCE_URL=http://localhost:8000
ARG VITE_REGULARIZATION_URL=http://localhost:8002
ARG VITE_AGENT_URL=http://localhost:8003
ARG VITE_REPORTING_URL=http://localhost:8004
ENV VITE_IDENTITY_URL=$VITE_IDENTITY_URL \
    VITE_ATTENDANCE_URL=$VITE_ATTENDANCE_URL \
    VITE_REGULARIZATION_URL=$VITE_REGULARIZATION_URL \
    VITE_AGENT_URL=$VITE_AGENT_URL \
    VITE_REPORTING_URL=$VITE_REPORTING_URL

RUN npm run build

# ---- Runtime stage: static files served by nginx ----
FROM nginx:1.27-alpine AS runtime

COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O- http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
