FROM node:20-alpine

WORKDIR /app

# Copy manifests first so layer caching survives source changes.
COPY package.json ./
RUN npm install --no-audit --no-fund --no-progress

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
