#!/bin/sh
set -eu

test_database="${POSTGRES_DB}_test"

# Database names are constructed locally, but validate them before
# interpolating the value into the PostgreSQL query.
case "$test_database" in
  ""|*[!A-Za-z0-9_]*)
    echo "Invalid test database name: $test_database" >&2
    exit 1
    ;;
esac

database_exists="$(
  psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --tuples-only \
    --no-align \
    --command="
      SELECT 1
      FROM pg_database
      WHERE datname = '$test_database';
    "
)"

if [ "$database_exists" = "1" ]; then
  echo "Test database already exists: $test_database"
else
  createdb \
    --username "$POSTGRES_USER" \
    --owner "$POSTGRES_USER" \
    "$test_database"

  echo "Created test database: $test_database"
fi
