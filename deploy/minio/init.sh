#!/bin/sh
# MinIO one-shot bootstrap: bucket, scoped application user, write-only
# policy. Runs inside the minio-init container; fails loudly so compose marks
# the init as unhealthy instead of silently leaving a misconfigured server.
#
# Credentials come from environment variables shared with the backend:
#   MINIO_ROOT_USER / MINIO_ROOT_PASSWORD  (root login)
#   MINIO_ACCESS_KEY / MINIO_SECRET_KEY    (application user to create)
#   MINIO_BUCKET                           (bucket name)
set -eu

echo "==> waiting for MinIO at minio:9000"
i=0
until mc alias set kudos http://minio:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "MinIO did not become ready in time" >&2
    exit 1
  fi
  sleep 2
done
echo "==> MinIO is up"

echo "==> creating bucket '${MINIO_BUCKET:-kudos}'"
mc mb --ignore-existing "kudos/${MINIO_BUCKET:-kudos}"

echo "==> enabling bucket versioning"
mc version enable "kudos/${MINIO_BUCKET:-kudos}"

echo "==> creating scoped application user ${MINIO_ACCESS_KEY}"
mc admin user add kudos "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" >/dev/null 2>&1 || \
  echo "user already exists (or password update needed)"

echo "==> applying application policy"
mc admin policy create kudos kudos-app /policies/app-policy.json >/dev/null 2>&1 || true
mc admin policy attach kudos kudos-app --user "${MINIO_ACCESS_KEY}" >/dev/null

echo "==> storage bootstrap complete"
