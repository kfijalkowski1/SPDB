# SPDB

Repository for project being made for SPDB (in WUT uni) course

## Running the service

### Prerequisites

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

### Run the service

Run with auto reload:

```shell
docker compose up --build -d && docker compose logs --follow
```

Note that the `importer` service will in `Waiting` state until it finishes importing data. Depending on you machine and import size this may take a few hours (importing the entire Poland), but it usually finishes much earlier if you're only importing a single voivodeship. To view current progress, simply:

```shell
docker compose logs --follow importer
```

Run locally with debugger:

```shell
debugpy --listen 5678 -m streamlit run src/visualizer.py --server.port 2000
```

If you're using VS Code, check `.vscode/launch.json` to attach the debugger

### Note on importing routes

This is both a compute-heavy and memory-heavy operation. Ensure you have plenty of RAM (32 is the minimum) and time. On an i7 8700 with 32GB of RAM importing the entire Poland takes roughly 1h 45min and requires swapping (at least that's what I saw - even though the actual RAM usage was not that high, all RAM was used by buffered pages which OS refused to clean up, hence swapping was needed). **If you only need a single voivodeship, limit the number of files loaded in [import_osm.sh](db/osm_imports/import_osm.sh)**. 

Loading the entire topology is likely a good idea when testing performance-related changes, as fully populated tables contain approximately 11.7mln edges and 9mln vertices and PostgreSQL will sometimes perform sequential scans over both of these tables (try finding a route from Rzeszów to Szczecin without doing a sequential scan!).

### Accessing the service

- The app is running at `localhost:8501`
- PgAdmin4 is running at `localhost:8888` (username root@root.com, password toor)


## Development

### Useful commands

- `uv run streamlit run code/visualizer.py` - run front locally
- `uv sync` - sync packages
- `uv add <name>` - add new package
- `uv remove <name>` - remove package
- `docker compose up --build --env-file .env` - build and run docker containers -- parsing xml to db for the first time might take a while
- `apt install osmctools` -- needed for parsing osm.pbf to osm

### Notes

~~Don't try to import whole poland - it's too big and there is mem overflow in osm2pgrouting~~

Count disconnected edges in the graph (should be exactly 0):

```sql
SELECT pgr_analyzeGraph('ways', 0.000001, the_geom := 'the_geom', id := 'gid');
```
