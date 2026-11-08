# Fake Matter devices for the iot_devices end-to-end tests.
FROM node:22-slim

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY fake_devices.mjs ./

# One process runs one device of each kind.  Their state JSON files are
# written under /data, which the test bind mounts.
ENV FAKE_DEVICE_DATA_PATH=/data

ENTRYPOINT ["node", "fake_devices.mjs"]
# Pass --commissionable to open the commissioning windows on start.
