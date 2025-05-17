#!/bin/bash
set -euo pipefail

set -x

PGHOST=${PG_HOST:-localhost}
PGUSER=${PG_USER:-postgres}
PGPASSWORD=${PG_PASSWORD:-bikepass}
export PGPASSWORD

DB_NAME="routing"
#OSM_FILES=("/data/germany-latest.osm" "/data/poland-latest.osm")
OSM_FILES=("/data/poland-zach-pom.osm")

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
  psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "CREATE EXTENSION hstore;"
  psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "CREATE TYPE road_type_enum AS ENUM ('roads_primary', 'roads_secondary', 'roads_paved', 'roads_unpaved', 'roads_unknown_surface', 'cycleways');"

  # Import OSM files using osm2pgrouting
  for source_file in "${OSM_FILES[@]}"; do
    echo "Processing $source_file..."
    
    for filter in "roads_primary" "roads_secondary" "roads_paved" "roads_unpaved" "roads_unknown_surface" "cycleways"; do
      PARAMS_FILE="/osmfilter/$filter.txt"
      FILTERED_OSM_FILE="${filter}_filtered.osm"

      echo "Importing $filter from $source_file..."
      osmfilter $source_file "--parameter-file=$PARAMS_FILE" > "$FILTERED_OSM_FILE"

      osm2pgrouting -f "$FILTERED_OSM_FILE" \
        -d "${DB_NAME}" \
        -U "$PGUSER" \
        -h "$PGHOST" \
        -W "$PGPASSWORD" \
        -c "/mapconfig_bikes.xml" \
        --tags \
        --attributes \

      psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "ALTER TABLE ways ADD IF NOT EXISTS road_type road_type_enum DEFAULT NULL;"
      psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "UPDATE ways SET road_type = '$filter' WHERE road_type IS NULL;"
    done
  done
  psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "ALTER TABLE ways ALTER COLUMN road_type SET NOT NULL;"

  echo "Import completed."
fi

sleep infinity # workaround for no init containers in docker compose :(
