#!/usr/bin/env just --justfile
export PATH := join(justfile_directory(), ".env", "bin") + ":" + env_var('PATH')

setup:
    uv sync
    mkdir -p data
    cp .env.sample .env

download-data:
    mkdir -p data
    curl -o data/poland-latest.osm.pbf https://download.geofabrik.de/europe/poland-latest.osm.pbf
    curl -o data/poland-zach-pom.osm.pbf https://download.geofabrik.de/europe/poland/zachodniopomorskie-latest.osm.pbf
    curl -o data/poland-maz.osm.pbf https://download.geofabrik.de/europe/poland/mazowieckie-latest.osm.pbf
    osmconvert data/poland-latest.osm.pbf --drop-author --drop-version --out-osm -o=data/poland.osm
    osmconvert data/poland-zach-pom.osm.pbf --drop-author --drop-version --out-osm -o=data/poland-zach-pom.osm
    osmconvert data/poland-maz.osm.pbf --drop-author --drop-version --out-osm -o=data/poland-maz.osm


upgrade:
  uv lock --upgrade
