- Import osm using a pre-defined xml config (https://github.com/pgRouting/osm2pgrouting/blob/main/mapconfig_for_bicycles.xml)
  - This allows to whitelist desired road types
  - Sample config needs to be reviewed
  - earlier, in osmconvert - `--complete-ways` allegedly handles region crossing
- Adding `--tags` and `--attributes` to osm2pgrouting preserves road type information - this is what we need
  - stored in a separate table, pre-join?
- osm2pgrouting precomputes cost as distance / max_speed, this is essentially garbage info
  - NOTE: max speed in `ways` is different than in `configuration`
  - negative cost - forbidden, eg route is one-way
    - one_way column, (UNKNOWN || NO) => two-way, yes => one-way
- we need to compute the cost at runtime 
  - or can it be precomputed? Does this make much of a difference?
  - what needs to be included:
    - road length (duh)
    - cruise speed derived from:
      - bike type (constant for all roads)
      - physical form (do we need to take this into account? we can assume all costs are scaled the same and physical form only affects daily range)
      - surface type (road tag)
      - effectively, bike type and form are constant between roads, therefore we only need a mapping from surface type to cruise speed (mapping is derived from bike type + potentially physical form)
    - penalty for each road type derived from:
      - bike type (constant)
      - road tag
      - same case - we only need to map the penalty from road type
    - so effectively, we can create derive a mapping `road tag -> cruise speed * penalty` from bike type and physical form before executing the query and apply the mapping at compute time to get actual edge costs
  - in extremely rare cases a way can be missing `length_m` (`length` is always present, we can compute `length_m`)
  - unpaved roads can be excluded in case of road bikes
  - or maybe we can include the `priority` property from the xml? It is present in the table
- optimization: ST_BUFFER around straight line between two points (range proportional to line length, or should it increase / decrease? I guess it should decrease, as it's harder to find an approximately straight route over small distances)
- bidirectional a* >= unidirectional a*
- idea: if the user picks PoIs beforehand (I think this is what the project assumes), we can parallelize the query by computing paths between N-1 subsequent PoI pairs simultaneously. The more PoI, the better the parallelization. Note that this may speed up the query even further, as with smaller distances we don't need to select such a large ST_BUFFER
  - but what about the order in which PoIs should be visited? Either the user should input it explicitly (easier approach xd) or we should suggest which PoIs can be visited in different order
    - the latter option could rely on computing all possible paths from A->B over all PoI, assuming paths between PoIs are straight lines - 
      - (n factorial paths! but does this even matter? this is essentially a Hamilton path with explicitly given start and end points. Maybe we can restrict the max route length to reduce the complexity? and / or use floyd-warshall to compute paths?)
    - - and suggesting N shortest paths. In this case, we probably only need to compute a few extra paths between PoI, since the shortest paths are likely to be similar. And again, this can be easily parallelized
- note for future me: inspect waits in the query! maybe it is not cpu-bound and there are some easy performance gains achievable by tuning postgres
- what about elevation? do we want to minimise the elevation gain? 




---


#######################################################################

Without distance filter:

```sql
WITH start_point AS (
    SELECT id
    FROM ways_vertices_pgr "vert"
    ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(16.18229464051224, 54.190044572153056), 4326)::geometry ASC
    LIMIT 1
), end_point AS (
    SELECT id
    FROM ways_vertices_pgr "vert"
    ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(15.045312226622825, 53.33702543121671), 4326)::geometry ASC
    LIMIT 1
)

SELECT y1 "lat1", x1 "lon1", y2 "lat2", x2 "lon2", the_geom FROM pgr_bdastar(
	'
	SELECT sq.id, sq.source, sq.target, sq.cost, sq.sgn * sq.cost "reverse_cost", sq.x1, sq.y1, sq.x2, sq.y2
	FROM (
		SELECT 
			gid "id",
			source,
			target,
			CASE
				WHEN road_type = ''roads_paved'' THEN 1 * length
				WHEN road_type = ''roads_unpaved'' THEN 5 * length
				WHEN road_type = ''roads_unknown_surface'' THEN 5 * length
				WHEN road_type = ''roads_primary'' THEN 100 * length
				WHEN road_type = ''roads_secondary'' THEN 20 * length
				WHEN road_type = ''cycleways'' THEN 0.5 * length
			END AS "cost",
			SIGN(reverse_cost) AS sgn,
			x1, y1, x2, y2
		FROM ways
	) AS sq
	',
	(SELECT id FROM start_point),
	(SELECT id FROM end_point),
	directed => true, heuristic => 4
) as waypoints
INNER JOIN ways rd ON waypoints.edge = rd.gid;
```

#############################################################################


With distance filter:

```sql
WITH start_point AS (
    SELECT id
    FROM ways_vertices_pgr "vert"
    ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(16.18229464051224, 54.190044572153056), 4326)::geometry ASC
    LIMIT 1
), end_point AS (
    SELECT id
    FROM ways_vertices_pgr "vert"
    ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(15.045312226622825, 53.33702543121671), 4326)::geometry ASC
    LIMIT 1
)

SELECT y1 "lat1", x1 "lon1", y2 "lat2", x2 "lon2", the_geom FROM pgr_bdastar(
	'
	WITH line_ab AS (
	  SELECT ST_MakeLine(
	    ST_SetSRID(ST_MakePoint(15.045312226622825, 53.33702543121671), 4326),
	    ST_SetSRID(ST_MakePoint(16.18229464051224, 54.190044572153056), 4326)
	  )::geography AS geom
	)
	SELECT sq.id, sq.source, sq.target, sq.cost, sq.sgn * sq.cost "reverse_cost", sq.x1, sq.y1, sq.x2, sq.y2
	FROM (
		SELECT 
			gid "id",
			source,
			target,
			CASE
				WHEN road_type = ''roads_paved'' THEN 1 * length
				WHEN road_type = ''roads_unpaved'' THEN 5 * length
				WHEN road_type = ''roads_unknown_surface'' THEN 5 * length
				WHEN road_type = ''roads_primary'' THEN 100 * length
				WHEN road_type = ''roads_secondary'' THEN 20 * length
				WHEN road_type = ''cycleways'' THEN 0.5 * length
			END AS "cost",
			SIGN(reverse_cost) AS sgn,
			x1, y1, x2, y2
		FROM ways, line_ab
		WHERE ST_DWithin(
		  ways.the_geom::geography,
		  line_ab.geom,
		  30000
		)
	) AS sq
	',
	(SELECT id FROM start_point),
	(SELECT id FROM end_point),
	directed => true, heuristic => 4
) as waypoints
INNER JOIN ways rd ON waypoints.edge = rd.gid;
```
