#!/usr/bin/env bash

set -euo pipefail

mkdir -p data
for voi in "dolnoslaskie" "kujawsko-pomorskie" "lubelskie" "lubuskie" "lodzkie" "malopolskie" "mazowieckie" "opolskie" "podkarpackie" "podlaskie" "pomorskie" "slaskie" "swietokrzyskie" "warminsko-mazurskie" "wielkopolskie" "zachodniopomorskie"; do
    curl -o data/poland-$voi.osm.pbf https://download.geofabrik.de/europe/poland/$voi-latest.osm.pbf
    osmconvert data/poland-$voi.osm.pbf --drop-author --drop-version --out-osm -o=data/poland-$voi.osm
done