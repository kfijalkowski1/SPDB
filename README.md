# SPDB
Repository for project being made for SPDB (in WUT uni) course

## Prerequisites
In this project we use UV !!
- uv
- just
- python3
- docker-compose

## useful commands
- `streamlit run .\visualizer.py` - run front locally
- `uv sync` - sync packages
- `uv add <name>` - add new package
- `uv remove <name>` - remove package
- `docker compose up --build --env-file .env` - build and run docker containers -- parsing xml to db for the first time might take a while
- `apt install osmconvert` -- needed for parsing osm.pbf to osm

## notes
Don't try to import whole poland - it's too big and there is mem overflow in osm2pgrouting