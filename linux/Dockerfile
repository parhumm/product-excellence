FROM mcr.microsoft.com/playwright:v1.62.0-noble
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 && rm -rf /var/lib/apt/lists/*
WORKDIR /service
COPY package*.json ./
RUN npm install --omit=dev
COPY server.mjs ./
EXPOSE 8752 8753
CMD ["node", "server.mjs"]
