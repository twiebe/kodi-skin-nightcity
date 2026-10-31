# Take the screenshots in resources/screenshots/ with tools/screenshots.py in a container, so
# no local venv is needed. The script starts a kodi-dev instance with kdev from KODI_DEV
# (see README.md, Development); SHOTS picks some of them (e.g. SHOTS="info player"),
# SCREENSHOTS_ARGS passes options (e.g. --keep). MDBLIST_API_KEY and OMDB_API_KEY go
# through from the environment when they are set.

KODI_DEV ?= ../kodi-dev
SHOTS ?=
SCREENSHOTS_ARGS ?=
SCREENSHOTS_IMAGE ?= nightcity-screenshots
export MDBLIST_API_KEY OMDB_API_KEY

KODI_DEV_PATH := $(abspath $(KODI_DEV))
DOCKER_SOCK := /var/run/docker.sock

.PHONY: screenshots screenshots-image

screenshots-image:
	docker build -q -t $(SCREENSHOTS_IMAGE) -f tools/screenshots.Dockerfile tools

# Both checkouts keep their paths in the container: kdev hands them to the same Docker daemon as
# bind mounts of the instance. Host network: kdev publishes the instance's ports on 127.0.0.1.
# The run takes the user's ids, so its files are the user's, and the group of the Docker socket.
# The keys go by name only (-e NAME), so their values stay out of the command line and the image.
screenshots: screenshots-image
	docker run --rm --network host \
		--user $$(id -u):$$(id -g) \
		--group-add $$(docker run --rm -v $(DOCKER_SOCK):$(DOCKER_SOCK) --entrypoint stat $(SCREENSHOTS_IMAGE) -c %g $(DOCKER_SOCK)) \
		-v $(DOCKER_SOCK):$(DOCKER_SOCK) \
		-v $(CURDIR):$(CURDIR) -v $(KODI_DEV_PATH):$(KODI_DEV_PATH) -w $(CURDIR) \
		-e KODI_DEV=$(KODI_DEV_PATH) -e MDBLIST_API_KEY -e OMDB_API_KEY \
		$(SCREENSHOTS_IMAGE) python tools/screenshots.py $(SCREENSHOTS_ARGS) $(SHOTS)
