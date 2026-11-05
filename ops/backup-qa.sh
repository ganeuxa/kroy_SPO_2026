#!/bin/sh
# Explicitly scoped to Varvara's local QA project. Never selects production.
set -eu
cd "$(dirname "$0")/.."
compose() { docker compose -f docker-compose.test.yml -f docker-compose.backup.yml --env-file .env.qa -p kroy-varvara-nginx-qa "$@"; }
restore_services() { compose start storage backend; }
trap restore_services EXIT
compose stop backend storage
RELEASE_REVISION=$(git rev-parse HEAD)
export RELEASE_REVISION
compose run --rm --no-deps backup
