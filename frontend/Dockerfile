# Build static assets; browser calls API on host port 8000 by default.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci can fail if lockfile optional deps differ from container npm; install is OK for images.
RUN npm install
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
