#!/usr/bin/env just --justfile
export PATH := join(justfile_directory(), ".env", "bin") + ":" + env_var('PATH')

download-data:
    mkdir -p data
    curl -o data/poland-latest.osm.pbf https://download.geofabrik.de/europe/poland-latest.osm.pbf
    curl -o data/poland-zach-pom.osm.pbf https://download.geofabrik.de/europe/poland/zachodniopomorskie-latest.osm.pbf
    apt install osmconvert
    osmconvert poland-latest.osm.pbf --drop-author --drop-version --out-osm -o=poland.osm


upgrade:
  uv lock --upgrade