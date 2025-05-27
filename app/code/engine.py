import concurrent.futures
import itertools
import math
from enum import Enum
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from db_utils import session


class Point(NamedTuple):
    lat: float
    lon: float
    short_desc: str = "Default Point"
    type: str = None
    
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
    # osm_id: int
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
    SELECT id, lat, lon, the_geom
    FROM ways_vertices_pgr "vert"
    ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geometry ASC
    LIMIT :n
    """

    with session() as db_session:
        result = db_session.execute(
            text(stmt),
            {
                "lat": reference_point.lat,
                "lon": reference_point.lon,
                "n": n
            }
        )
    return [
        DbPoint(
            id=row[0],
            # osm_id=row[1],
            lat=row[1],
            lon=row[2],
            geom=row[3]
        )
        for row in result
    ]


def get_closest_point(reference_point: Point) -> DbPoint:
    return get_closest_points(reference_point, 1)[0]


def _find_path_astar(
    start_point: Point,
    end_point: Point,
    road_type_weights: dict[RoadType, float] | None = None,
) -> list[Line]:

    x_a, y_a = start_point.lon, start_point.lat
    x_b, y_b = end_point.lon, end_point.lat
    print(x_a, y_a)
    print(x_b, y_b)
    factor_a = y_b - y_a
    factor_b = x_a - x_b
    factor_c = x_b * y_a - x_a * y_b
    factor_bott = math.sqrt(factor_a ** 2 + factor_b ** 2)
    
    lon_lower_bound = min(start_point.lon, end_point.lon)
    lon_upper_bound = max(start_point.lon, end_point.lon)
    lat_lower_bound = min(start_point.lat, end_point.lat)
    lat_upper_bound = max(start_point.lat, end_point.lat)
    
    ab_dist = math.sqrt((x_a - x_b) ** 2 + (y_a - y_b) ** 2)

    # gradually decrease from ~3.1 over very short distances to ~0.3 over long distances
    dist_filter_relative = 4.3 - 4 / (1 + math.exp(-3.5 * ab_dist + 1))
    # minimum value has to be introduced since grid has limited resolution and would otherwise return no points when querying
    # over very short distances
    
    MIN_DIST_FILTER_DEG = 0.5
    MAX_DIST_FILTER_DEG = 3.0
    
    dist_filter_deg = min(max(ab_dist * dist_filter_relative, MIN_DIST_FILTER_DEG), MAX_DIST_FILTER_DEG)
    
    GRID_SCALE = 100
    
    # Alright, why does this even work
    # We employ two filters to reduce the number of ways returned by the inner query without sacrificing performance
    # We intentionally refer to grid_lon and grid_lat: plain integer values, essentially (lat|lon) * 100 rounded to the nearest integer
    # The first filter is a bounding box filter, which only selects ways that are within a bounding box defined by the start and end points + some margin
    # The second filter selects ways that are within a certain distance from the line defined by the start and end points
    # Instead of using ST_DWithin which is very compute-heavy, we use a linear equation to filter the ways:
    #  - First, we compute the line equation of the line defined by the start and end points (referred to as "a" and "b"):
    #     y = (y_b - y_a) / (x_b - x_a) * x + (y_b - y_a) / (x_b - x_a) * x_a * y_a
    #  - Or in other words:
    #     lat = (lat_b - lat_a) / (lon_b - lon_a) * lon + (lat_b - lat_a) / (lon_b - lon_a) * lon_a * lat_a
    #  - After some transformations we get:
    #     (lat_b - lat_a) * lon + (lon_a - lon_b) * lat + lon_b * lat_a - lon_a * lat_b = 0
    #  - Notice that:
    #     factor_a = (lat_b - lat_a)
    #     factor_b = (lon_a - lon_b)
    #     factor_c = (lon_b * lat_a - lon_a * lat_b)
    #  - Now we can compute the distance of a point (grid_lon, grid_lat) to the line defined by the start and end points:
    #     dist = abs(factor_a * grid_lon + factor_b * grid_lat + factor_c) / sqrt(factor_a ** 2 + factor_b ** 2)
    #  - The rest is just transformations to reduce tha number of computations that postgres has to make when filtering the ways


    stmt = f"""
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

        SELECT y1 "lat1", x1 "lon1", y2 "lat2", x2 "lon2" FROM pgr_bdastar(
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
                WHERE 
                    (grid_lon BETWEEN (:lon_lower_bound - :dist_filter_deg) * {GRID_SCALE} AND (:lon_upper_bound + :dist_filter_deg) * {GRID_SCALE})
                    AND (grid_lat BETWEEN (:lat_lower_bound - :dist_filter_deg) * {GRID_SCALE} AND (:lat_upper_bound + :dist_filter_deg) * {GRID_SCALE})
                    AND (:dist_filter_deg * :factor_bott - (:factor_c)) * {GRID_SCALE} > :factor_a * grid_lon + :factor_b * grid_lat
                    AND (- (:dist_filter_deg * :factor_bott) - (:factor_c)) * {GRID_SCALE} < :factor_a * grid_lon + :factor_b * grid_lat
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
            "start_lat": float(start_point.lat),
            "start_lon": float(start_point.lon),
            "end_lat": float(end_point.lat),
            "end_lon": float(end_point.lon),
            "paved_weight": float(road_type_weights.get(RoadType.paved, 1.0)),
            "unpaved_weight": float(road_type_weights.get(RoadType.unpaved, 1.5)),
            "unknown_surface_weight": float(road_type_weights.get(RoadType.unknown_surface, 2.0)),
            "primary_weight": float(road_type_weights.get(RoadType.primary, 1.0)),
            "secondary_weight": float(road_type_weights.get(RoadType.secondary, 1.5)),
            "cycleway_weight": float(road_type_weights.get(RoadType.cycleway, 0.5)),
            "dist_filter_deg": float(dist_filter_deg),
            "factor_bott": float(factor_bott),
            "factor_a": float(factor_a),
            "factor_b": float(factor_b),
            "factor_c": float(factor_c),
            "lon_lower_bound": float(lon_lower_bound),
            "lon_upper_bound": float(lon_upper_bound),
            "lat_lower_bound": float(lat_lower_bound),
            "lat_upper_bound": float(lat_upper_bound)
        }
        
        compiled = text(stmt).bindparams(**params).compile(dialect=postgresql.dialect(),compile_kwargs={"literal_binds": True})
        print(compiled, flush=True)
        
        result = db_session.execute(
            text(stmt),
            params
        ).fetchall()
    
    rows = [
        Line(
            lat1=row[0],
            lon1=row[1],
            lat2=row[2],
            lon2=row[3]
        )
        for row in result
    ]
    
    if len(rows) == 0:
        raise NoRouteError(f"No route found between {start_point} and {end_point}")
        
    return rows


def build_route(points: list[Point], bike_type: str) -> list[Line]:
    # todo compute based on bike type
    # lower weight <=> higher preference
    WEIGHTS = {
        RoadType.primary: 3,
        RoadType.secondary: 1.5,
        RoadType.paved: 1,
        RoadType.unpaved: 2,
        RoadType.unknown_surface: 2,
        RoadType.cycleway: 0.5
    }

    assert len(points) >= 2, f"build_route requires at least 2 points, got {len(points)}"
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        segments_to_future = {
            (s_start, s_end): executor.submit(
                _find_path_astar,
                start_point=s_start,
                end_point=s_end,
                road_type_weights=WEIGHTS
            )
            for s_start, s_end in itertools.pairwise(points)
        }
    
    route = []
    for i, ((s_start, s_end), future) in enumerate(segments_to_future.items(), start=1):
        try:
            segment = future.result()
            route.extend(segment)
        except NoRouteError as e:
            print(f"Error finding route between points {i} -> {i+1} {s_start} and {s_end}: {e}")
            raise e
    return route
