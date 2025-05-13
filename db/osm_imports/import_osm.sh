#!/bin/bash
set -e

PGHOST=${PG_HOST:-localhost}
PGUSER=${PG_USER:-postgres}
PGPASSWORD=${PG_PASSWORD:-bikepass}
export PGPASSWORD

DB_NAME="routing"
#OSM_FILES=("/data/germany-latest.osm" "/data/poland-latest.osm")
OSM_FILES=("/data/poland_zach_pom.osm")

# Wait for PostgreSQL to start
until pg_isready -h "$PGHOST" -U "$PGUSER"; do
  echo "Waiting for PostgreSQL at $PGHOST..."
  sleep 2
done

# if no osm files are found convert pbf to osm



# Check if the database exists
if psql -U "$PGUSER" -h "$PGHOST" -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  echo "Database '${DB_NAME}' already exists. Skipping import."
else
  echo "Database '${DB_NAME}' does not exist. Creating and importing..."

  # Create the database
  createdb -U "$PGUSER" -h "$PGHOST" "${DB_NAME}"
  psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "CREATE EXTENSION postgis;"
  psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "CREATE EXTENSION pgrouting;"

  # Import OSM files using osm2pgrouting
  for file in "${OSM_FILES[@]}"; do
    echo "Importing $file..."
    osm2pgrouting -f "$file" \
      -d "${DB_NAME}" \
      -U "$PGUSER" \
      -h "$PGHOST" \
      -W "$PGPASSWORD"
  done

  echo "Import completed."
fi

sleep infinity # workaround for no init containers in docker compose :(
