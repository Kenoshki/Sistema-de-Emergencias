# Frontend estático (Vite) servido con nginx. Pensado para Railway.
# VITE_* se incrustan al compilar: defínalas como variables del servicio en Railway.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ARG VITE_OSRM_URL
ARG VITE_TILE_URL
RUN npm run build

FROM nginx:1.27-alpine
# nginx sustituye ${PORT} en la plantilla al arrancar (Railway asigna el puerto).
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
