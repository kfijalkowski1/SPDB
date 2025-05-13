FROM postgis/postgis:latest

# Install required tools
RUN apt-get update && apt-get install -y \
    osm2pgrouting \
    wget \
    postgresql-client \
    osmctools \
    && apt-get clean

# Copy entrypoint script
COPY import_osm.sh /import_osm.sh
ENTRYPOINT ["bash", "import_osm.sh"]
