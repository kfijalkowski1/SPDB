#!/bin/bash
set -euo pipefail

set -x

PGHOST=${PG_HOST:-localhost}
PGUSER=${PG_USER:-postgres}
PGPASSWORD=${PG_PASSWORD:-bikepass}
export PGPASSWORD

DB_NAME="routing"
# OSM_FILES=("/data/poland.osm")
# OSM_FILES=("/data/poland-zachodniopomorskie.osm")
# OSM_FILES=("/data/poland-mazowieckie.osm")

OSM_FILES=(
  "/data/poland-dolnoslaskie.osm"
  "/data/poland-kujawsko-pomorskie.osm"
  "/data/poland-lubelskie.osm"
  "/data/poland-lubuskie.osm"
  "/data/poland-lodzkie.osm"
  "/data/poland-malopolskie.osm"
  "/data/poland-mazowieckie.osm"
  "/data/poland-opolskie.osm"
  "/data/poland-podkarpackie.osm"
  "/data/poland-podlaskie.osm"
  "/data/poland-pomorskie.osm"
  "/data/poland-slaskie.osm"
  "/data/poland-swietokrzyskie.osm"
  "/data/poland-warminsko-mazurskie.osm"
  "/data/poland-wielkopolskie.osm"
  "/data/poland-zachodniopomorskie.osm"
)

# Wait for PostgreSQL to start
until pg_isready -h "$PGHOST" -U "$PGUSER"; do
  echo "Waiting for PostgreSQL at $PGHOST..."
  sleep 2
done

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


  for source_file in "${OSM_FILES[@]}"; do
    echo "Processing $source_file..."

    # Load all acceptable road types (mapconfig_bikes.xml) and create routing topology 
    # TODO add osmfilter to select only roads with tags that are relevant for routing to avoid loading 700.000.000 ways into ram
    osmfilter $source_file "--parameter-file=/osmfilter/all.txt" > "all_filtered.osm"
    osm2pgrouting -f "all_filtered.osm" \
      -d "${DB_NAME}" \
      -U "$PGUSER" \
      -h "$PGHOST" \
      -W "$PGPASSWORD" \
      -c "/mapconfig_bikes.xml" \
      --tags \
      --attributes \
      --no-index \
      --chunk 100000

    # Add road type
    psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "ALTER TABLE ways ADD COLUMN IF NOT EXISTS road_type road_type_enum DEFAULT NULL;"

    for filter in "roads_primary" "roads_secondary" "roads_paved" "roads_unpaved" "cycleways"; do
      # for every filter file: get matching OSM roads, import to DB and set road_type on the ways table based on osm_id
      PARAMS_FILE="/osmfilter/$filter.txt"
      FILTERED_OSM_FILE="${filter}_filtered.osm"

      echo "Importing $filter from $source_file..."
      osmfilter all_filtered.osm "--parameter-file=$PARAMS_FILE" > "$FILTERED_OSM_FILE"

      osm2pgsql -U "$PGUSER"  -H "$PGHOST" --create -d "${DB_NAME}" --latlong --cache 12000 --cache-strategy sparse "$FILTERED_OSM_FILE"

      psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "ALTER TABLE planet_osm_line ADD IF NOT EXISTS road_type road_type_enum DEFAULT NULL;"
      psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "UPDATE planet_osm_line SET road_type = '$filter' WHERE road_type IS NULL;"
      psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "UPDATE ways SET road_type = planet_osm_line.road_type FROM planet_osm_line WHERE ways.osm_id = planet_osm_line.osm_id AND ways.road_type IS NULL;"

    done

    # Assume all roads which were selected by filters are of unknown surface
    psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -c "UPDATE ways SET road_type = 'roads_unknown_surface' WHERE ways.road_type IS NULL;"
  done

  cat <<EOF > post_import.sql
-- this is what osm2pgrouting does unless --no-index is specified
ALTER TABLE ways ADD PRIMARY KEY (gid);
ALTER TABLE ways_vertices_pgr ADD PRIMARY KEY (id);
ALTER TABLE configuration ADD PRIMARY KEY (id);
ALTER TABLE pointsofinterest ADD PRIMARY KEY (pid);
CREATE INDEX ON ways USING gist (the_geom);
CREATE INDEX ON ways_vertices_pgr USING gist (the_geom);
CREATE INDEX ON pointsofinterest USING gist (the_geom);

ALTER TABLE ways ALTER COLUMN road_type SET NOT NULL;

-- find isolated vertices and edges
ALTER TABLE ways ADD COLUMN component BIGINT;
ALTER TABLE ways_vertices_pgr ADD COLUMN component BIGINT;

UPDATE ways_vertices_pgr SET component = c.component
FROM (
  SELECT * FROM pgr_connectedComponents(
  'SELECT gid as id, source, target, cost, reverse_cost FROM ways')
) AS c
WHERE id = node;

UPDATE ways SET component = v.component
FROM (SELECT id, component FROM ways_vertices_pgr) AS v
WHERE source = v.id;

-- creating indices speeds up deletion of isolated components
CREATE INDEX ON ways (source);
CREATE INDEX ON ways (target);
CREATE INDEX ON ways (source_osm);
CREATE INDEX ON ways (target_osm);

-- delete isolated edges
WITH max_component AS (
	WITH
	all_components AS (SELECT component, count(*) FROM ways GROUP BY component),
	max_component AS (SELECT max(count) from all_components)
	SELECT component FROM all_components WHERE count = (SELECT max FROM max_component)
) DELETE FROM ways WHERE component != (SELECT component FROM max_component);

-- delete isolated vertices
WITH 
	all_components AS (SELECT component, count(*) FROM ways_vertices_pgr GROUP BY component),
	max_component AS (SELECT max(count) from all_components)
DELETE FROM ways_vertices_pgr WHERE component != (SELECT max FROM max_component) AND NOT EXISTS (
   SELECT FROM ways
   WHERE
   	   ways.source = ways_vertices_pgr.id
	   or ways.target = ways_vertices_pgr.id
   	   or ways.source_osm = ways_vertices_pgr.osm_id
	   or ways.target_osm = ways_vertices_pgr.osm_id
);

-- build GIST indices for faster queries
CREATE INDEX ON ways (gid, road_type);
CREATE INDEX ON ways USING gist( (the_geom::geography) );
CREATE INDEX ON ways_vertices_pgr USING gist( (the_geom::geography) );
CREATE INDEX ON pointsofinterest USING gist( (the_geom::geography) );

-- build grid for faster filtering
ALTER TABLE ways ADD IF NOT EXISTS grid_lat numeric DEFAULT NULL;
ALTER TABLE ways ADD IF NOT EXISTS grid_lon numeric DEFAULT NULL;
UPDATE ways SET grid_lat=round(ST_Y(ST_SnapToGrid(ST_Centroid(the_geom), 0.2, 0.16)) * 100)::numeric;
UPDATE ways SET grid_lon=round(ST_X(ST_SnapToGrid(ST_Centroid(the_geom), 0.2, 0.16)) * 100)::numeric;
ALTER TABLE ways ALTER COLUMN grid_lon SET NOT NULL;
ALTER TABLE ways ALTER COLUMN grid_lat SET NOT NULL;
CREATE INDEX ON ways (grid_lon);
CREATE INDEX ON ways (grid_lat);

-- update optimizer stats
VACUUM ANALYZE ways;
VACUUM ANALYZE ways_vertices_pgr;
VACUUM ANALYZE pointsofinterest;
EOF

  psql -U "$PGUSER" -h "$PGHOST" -d "${DB_NAME}" -f post_import.sql

  echo "Import completed."
fi

# We should now have a routing topology with no disconnected edges or vertices and all roads classified by type.
