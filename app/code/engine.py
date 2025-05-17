from enum import Enum
from typing import NamedTuple

from sqlalchemy import text

from db_utils import session


class Point(NamedTuple):
    lat: float
    lon: float
    
    def __str__(self):
        return f"({self.lat}, {self.lon})"


class Line(NamedTuple):
    lat1: float
    lon1: float
    lat2: float
    lon2: float
    
    def __str__(self):
        return f"({self.lat1}, {self.lon1}) -> ({self.lat2}, {self.lon2})"


class DbPoint(NamedTuple):
    id: int
    osm_id: int
    lat: float
    lon: float
    geom: str

    def __str__(self):
        return f"id={self.id} ({self.lat}, {self.lon})"
    
    @property
    def point(self):
        return Point(self.lat, self.lon)


class RoadType(Enum):
    primary = "roads_primary"
    secondary = "roads_secondary"
    paved = "roads_paved"
    unpaved = "roads_unpaved"
    unknown_surface = "roads_unknown_surface"
    cycleway = "cycleways"


class NoRouteError(ValueError):
    """Raised when no route is found"""
    pass


def generate_path(start_point: Point, end_point: Point, bike_type, num_points=50):
    """Mock path generator, returns straight line between points"""
    print(f"Generating path from {start_point} to {end_point} for {bike_type}")
    lat1, lon1 = start_point
    lat2, lon2 = end_point

    path = [
        (
            lat1 + (lat2 - lat1) * i / (num_points - 1),
            lon1 + (lon2 - lon1) * i / (num_points - 1)
        )
        for i in range(num_points)
    ]
    print(path)
    return path


def get_closest_points(reference_point: Point, n: int) -> list[DbPoint]:
    
    # note lat and lon are swapped!
    stmt = """
    SELECT id, osm_id, lat, lon, the_geom
    FROM ways_vertices_pgr "vert"
    ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), :srid)::geometry ASC
    LIMIT :n
    """

    with session() as db_session:
        result = db_session.execute(
            text(stmt),
            {
                "lat": reference_point.lat,
                "lon": reference_point.lon,
                "srid": SRID,
                "n": n
            }
        )
    return [
        DbPoint(
            id=row[0],
            osm_id=row[1],
            lat=row[2],
            lon=row[3],
            geom=row[4]
        )
        for row in result
    ]


def get_closest_point(reference_point: Point) -> DbPoint:
    return get_closest_points(reference_point, 1)[0]


def _find_path_astar(
    start_point: Point,
    end_point: Point,
    road_type_weights: dict[RoadType, float] | None = None,
    # note: this will (likely) drastically impact performance
    dist_filter_meters: float | None = None,
) -> list[Line]:
    if dist_filter_meters is None:
        stmt="""
            WITH start_point AS (
                SELECT id
                FROM ways_vertices_pgr "vert"
                ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(:start_lon, :start_lat), 4326)::geometry ASC
                LIMIT 1
            ), end_point AS (
                SELECT id
                FROM ways_vertices_pgr "vert"
                ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(:end_lon, :end_lat), 4326)::geometry ASC
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
                            WHEN road_type = ''roads_paved'' THEN :paved_weight * length
                            WHEN road_type = ''roads_unpaved'' THEN :unpaved_weight * length
                            WHEN road_type = ''roads_unknown_surface'' THEN :unknown_surface_weight * length
                            WHEN road_type = ''roads_primary'' THEN :primary_weight * length
                            WHEN road_type = ''roads_secondary'' THEN :secondary_weight * length
                            WHEN road_type = ''cycleways'' THEN :cycleway_weight * length
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
        """
    else:
        stmt = """
            WITH start_point AS (
                SELECT id
                FROM ways_vertices_pgr "vert"
                ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(:start_lon, :start_lat), 4326)::geometry ASC
                LIMIT 1
            ), end_point AS (
                SELECT id
                FROM ways_vertices_pgr "vert"
                ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(:end_lon, :end_lat), 4326)::geometry ASC
                LIMIT 1
            )

            SELECT y1 "lat1", x1 "lon1", y2 "lat2", x2 "lon2", the_geom FROM pgr_bdastar(
                '
                WITH line_ab AS (
                    SELECT ST_MakeLine(
                        ST_SetSRID(ST_MakePoint(:start_lon, :start_lat), 4326),
                        ST_SetSRID(ST_MakePoint(:end_lon, :end_lat), 4326)
                    )::geography AS geom
                )
                SELECT sq.id, sq.source, sq.target, sq.cost, sq.sgn * sq.cost "reverse_cost", sq.x1, sq.y1, sq.x2, sq.y2
                FROM (
                    SELECT 
                        gid "id",
                        source,
                        target,
                        CASE
                            WHEN road_type = ''roads_paved'' THEN :paved_weight * length
                            WHEN road_type = ''roads_unpaved'' THEN :unpaved_weight * length
                            WHEN road_type = ''roads_unknown_surface'' THEN :unknown_surface_weight * length
                            WHEN road_type = ''roads_primary'' THEN :primary_weight * length
                            WHEN road_type = ''roads_secondary'' THEN :secondary_weight * length
                            WHEN road_type = ''cycleways'' THEN :cycleway_weight * length
                        END AS "cost",
                        SIGN(reverse_cost) AS sgn,
                        x1, y1, x2, y2
                    FROM ways, line_ab
                    WHERE ST_DWithin(
                        ways.the_geom::geography,
                        line_ab.geom,
                        :dist_filter_meters
                    )
                ) AS sq
                ',
                (SELECT id FROM start_point),
                (SELECT id FROM end_point),
                directed => true, heuristic => 4
            ) as waypoints
            INNER JOIN ways rd ON waypoints.edge = rd.gid;
        """
    
    with session() as db_session:
        params = {
            "start_lat": start_point.lat,
            "start_lon": start_point.lon,
            "end_lat": end_point.lat,
            "end_lon": end_point.lon,
            "paved_weight": road_type_weights.get(RoadType.paved, 1.0),
            "unpaved_weight": road_type_weights.get(RoadType.unpaved, 1.5),
            "unknown_surface_weight": road_type_weights.get(RoadType.unknown_surface, 2.0),
            "primary_weight": road_type_weights.get(RoadType.primary, 1.0),
            "secondary_weight": road_type_weights.get(RoadType.secondary, 1.5),
            "cycleway_weight": road_type_weights.get(RoadType.cycleway, 0.5)
        }
        if dist_filter_meters is not None:
            params["dist_filter_meters"] = dist_filter_meters
        
        result = db_session.execute(
            text(stmt),
            params
        )
    
    if len(result) == 0:
        raise NoRouteError(f"No route found between {start_point} and {end_point}")
        
    return [
        Line(
            lat1=row[0],
            lon1=row[1],
            lat2=row[2],
            lon2=row[3]
        )
        for row in result
    ]


def build_route(start_point: Point, end_point: Point, bike_type: str) -> list[Line]:
    WEIGHTS = {
        RoadType.primary: 100,
        RoadType.secondary: 20,
        RoadType.paved: 1,
        RoadType.unpaved: 5,
        RoadType.unknown_surface: 5,
        RoadType.cycleway: 0.5
    }
    
    # TODO closest points can be searched directly in the a* query
    route = _find_path_astar(
        start_point=start_point,
        end_point=end_point,
        road_type_weights=WEIGHTS
    )
    return route
