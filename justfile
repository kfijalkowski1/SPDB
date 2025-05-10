#!/usr/bin/env just --justfile
export PATH := join(justfile_directory(), ".env", "bin") + ":" + env_var('PATH')

download-data:
    mkdir -p data
    curl -o data/poland-latest.osm.pbf https://download.geofabrik.de/europe/poland-latest.osm.pbf
    curl -o data/germany-latest.osm.pbf https://download.geofabrik.de/europe/germany-latest.osm.pbf


upgrade:
  uv lock --upgrade