# Dockerfile de desenvolvimento: roda o Vite dev server com hot-reload.
FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

# --host expõe fora do container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
