# SPDB

Repository for project being made for SPDB (in WUT uni) course

## Prerequisites

In this project we use UV !!

- uv
- just
- python3
- docker-compose

Setup the project and fetch data:

```shell
just setup
just download-data
```

## Useful commands

- `uv run streamlit run code/visualizer.py` - run front locally
- `uv sync` - sync packages
- `uv add <name>` - add new package
- `uv remove <name>` - remove package
- `docker compose up --build --env-file .env` - build and run docker containers -- parsing xml to db for the first time might take a while
- `apt install osmctools` -- needed for parsing osm.pbf to osm

## Notes

Don't try to import whole poland - it's too big and there is mem overflow in osm2pgrouting
