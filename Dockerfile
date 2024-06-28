LABEL org.opencontainers.image.authors="Peter Ortiz (https://github.com/pjortiz)"

# MONGO_VERSION cannot be Latest
ARG MONGO_VERSION
FROM docker.io/mongo:${MONGO_VERSION}

# Copy all scripts and give then execution permistions
COPY --chmod=755 ./scripts /scripts

# Make the directory incase it doesn't exist
RUN mkdir -p /docker-entrypoint-initdb.d

# Dynamicaly choose script(s) based on provided MONGO_VERSION
RUN if [ -d "/scripts/${MONGO_VERSION}" ] && [ "$(ls -A /scripts/${MONGO_VERSION})" ]; then \
        echo "Setting init script(s) from '/scripts/${MONGO_VERSION}'..."
        cp -r /scripts/${MONGO_VERSION}/* /docker-entrypoint-initdb.d/; \
    elif [ "${MONGO_VERSION%%.*}" -le 4 ] && [ -d "/scripts/3-4" ]; then \
        echo "Setting init script(s) from '/scripts/3-4'..."
        cp -r /scripts/3-4/* /docker-entrypoint-initdb.d/; \
    elif [ "${MONGO_VERSION%%.*}" -eq 5 ] && [ -d "/scripts/5" ]; then \
        echo "Setting init script(s) from '/scripts/5'..."
        cp -r /scripts/5/* /docker-entrypoint-initdb.d/; \
    elif [ "${MONGO_VERSION%%.*}" -ge 6 ] && [ -d "/scripts/6+" ]; then \
        echo "Setting init script(s) from '/scripts/6+'..."
        cp -r /scripts/6+/* /docker-entrypoint-initdb.d/; \
    fi \
    ls -ls

# Clean up
RUN rm -rf /scripts

# Need MONGO_VERSION during runtime for healthchecks because 'mongo' command deprication in later version
ENV MONGO_VERSION=${MONGO_VERSION}

# Define the health check command
HEALTHCHECK --interval=10s --timeout=10s --retries=5 --start-period=20s \
    CMD if [ "${MONGO_VERSION%%.*}" -ge 6 ]; then \
            echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet; \
        else \
            echo 'db.runCommand("ping").ok' | mongo localhost:27017/test --quiet; \
        fi