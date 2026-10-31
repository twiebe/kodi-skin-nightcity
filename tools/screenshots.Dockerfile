# The image `make screenshots` runs tools/screenshots.py in: Python with Pillow, ffmpeg for the
# showcase clips, the Docker CLI with compose and git for kdev. No keys or checkouts go in here, the
# Makefile mounts the checkouts and passes the keys from the environment at run time.
FROM python:3.12-slim
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:27-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*' \
    && pip install --no-cache-dir pillow==11.3.0
# the run's user has no home of its own; the Docker CLI keeps its config there
ENV HOME=/tmp
