FROM node:22-alpine AS builder
ARG NEXT_PUBLIC_API_URL
WORKDIR /app
COPY . .
RUN npm ci && npm run build
