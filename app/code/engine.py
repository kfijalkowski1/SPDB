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
    dist_filter_deg: float | None = None,
) -> list[Line]:
    dist_filter_deg = dist_filter_deg or 1
    
    if dist_filter_deg is None:
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
                ) AS sq
                ',
                (SELECT id FROM start_point),
                (SELECT id FROM end_point),
                directed => true, heuristic => 4
            ) as waypoints
            INNER JOIN ways rd ON waypoints.edge = rd.gid;
        """
    else:
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
        
        GRID_SCALE = 100
        
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
                        AND ST_Distance(ST_MakePoint(:start_lon, :start_lat), ST_MakePoint(:end_lon, :end_lat)) * 0.3   > abs(:factor_a * grid_lon / {GRID_SCALE} + :factor_b * grid_lat / {GRID_SCALE} + (:factor_c)) / :factor_bott
                        
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
            "cycleway_weight": float(road_type_weights.get(RoadType.cycleway, 0.5))
        }
        if dist_filter_deg is not None:
            params["dist_filter_deg"] = float(dist_filter_deg)
            params["factor_bott"] = float(factor_bott)
            params["factor_a"] = float(factor_a)
            params["factor_b"] = float(factor_b)
            params["factor_c"] = float(factor_c)
            params["lon_lower_bound"] = float(lon_lower_bound)
            params["lon_upper_bound"] = float(lon_upper_bound)
            params["lat_lower_bound"] = float(lat_lower_bound)
            params["lat_upper_bound"] = float(lat_upper_bound)
        
        compiled = text(stmt).bindparams(**params).compile(dialect=postgresql.dialect(),compile_kwargs={"literal_binds": True})
        print(compiled, flush=True)
        
        result = db_session.execute(
            text(stmt),
            params
        )
    
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
