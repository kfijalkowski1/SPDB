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

## Run the service

Run with auto reload:

```shell
docker compose up --build -d && docker compose logs --follow
```

Note that the `importer` service will in `Waiting` state until it finishes importing data. Depending on you machine and import size this may take a few hours (importing the entire Poland), but it usually finishes much earlier if you're only importing a single voivodeship. To view current progress, simply:

```shell
docker compose logs --follow importer
```

## Accessing the service

- The app is running at `localhost:8501`
- PgAdmin4 is running at `localhost:8888` (username root@root.com, password toor)

## Useful commands

- `uv run streamlit run code/visualizer.py` - run front locally
- `uv sync` - sync packages
- `uv add <name>` - add new package
- `uv remove <name>` - remove package
- `docker compose up --build --env-file .env` - build and run docker containers -- parsing xml to db for the first time might take a while
- `apt install osmctools` -- needed for parsing osm.pbf to osm

## Notes

~~Don't try to import whole poland - it's too big and there is mem overflow in osm2pgrouting~~

Count disconnected edges in the graph (should be exactly 0):

```sql
SELECT pgr_analyzeGraph('ways', 0.000001, the_geom := 'the_geom', id := 'gid');
```
