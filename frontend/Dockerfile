# TransformerAI — arayüz (Zayıf yanlar 4/4)
#
# 1. node  — üretim derlemesi (frontend/dist)
# 2. nginx — derlenmiş dosyaları sunar ve /api, /maint isteklerini servislere
#            yönlendirir. Geliştirmede bu işi Vite vekili yapıyordu
#            (vite.config.js); üretimde ters vekil nginx.

FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-app.conf nginx-tls.conf /etc/nginx/
COPY --from=build /src/dist /usr/share/nginx/html
COPY docker-entrypoint.sh /docker-entrypoint-tls.sh
RUN chmod +x /docker-entrypoint-tls.sh
EXPOSE 80 443
ENTRYPOINT ["/docker-entrypoint-tls.sh"]
