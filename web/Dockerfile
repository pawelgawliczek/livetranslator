FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm i
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
# keep public path under / for Caddy reverse_proxy web:80
EXPOSE 80
