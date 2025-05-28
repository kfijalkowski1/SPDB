from __future__ import annotations

import concurrent.futures
import itertools
import math
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from db_utils import session
from enums import BikeType, RoadType
from weights import BIKE_TYPE_WEIGHTS
from db_utils import session
from enums import BikeType, RoadType
from weights import BIKE_TYPE_WEIGHTS
from enum import Enum

class PointTypes(Enum):
    SLEEPING = "sleeping"
    POI = "poi"


class Point(NamedTuple):
    lat: float
    lon: float
    short_desc: str = "Default Point"
    type: PointTypes | None = None


class Line(NamedTuple):
    lat1: float
    lon1: float
    lat2: float
    lon2: float
    length_m: float
    geojson: str


class Route(NamedTuple):
    start: Point
    end: Point
    geojson: str
    geom: str
    length_m: float
    length_m_road_types: dict[RoadType, float]


class DbPoint(NamedTuple):
    id: int
    lat: float
    lon: float
    geom: str

    @property
    def point(self) -> Point:
        return Point(self.lat, self.lon)


class NoRouteError(ValueError):
    pass


def get_closest_points(reference_point: Point, n: int) -> list[DbPoint]:
    # note lat and lon are swapped!
    stmt = """
    SELECT id, lat, lon, the_geom
    FROM ways_vertices_pgr "vert"
    ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geometry ASC
    LIMIT :n
    """

    with session() as db_session:
        result = db_session.execute(text(stmt), {"lat": reference_point.lat, "lon": reference_point.lon, "n": n})
    return [DbPoint(id=row[0], lat=row[1], lon=row[2], geom=row[3]) for row in result]


def get_closest_point(reference_point: Point) -> DbPoint:
    return get_closest_points(reference_point, 1)[0]


def _find_path_astar(
    start_point: Point,
    end_point: Point,
    road_type_weights: dict[RoadType, float],
) -> Route:
    x_a, y_a = float(start_point.lon), float(start_point.lat)
    x_b, y_b = float(end_point.lon), float(end_point.lat)
    print(x_a, y_a)
    print(x_b, y_b)
    factor_a = y_b - y_a
    factor_b = x_a - x_b
    factor_c = x_b * y_a - x_a * y_b
    factor_bott = math.sqrt(factor_a**2 + factor_b**2)

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
SELECT 
	ST_AsGeoJSON(ST_LineMerge(ST_Collect(sq.geom))) "geojson",
	ST_LineMerge(ST_Collect(sq.geom)) "geom",
	sum(sq.length_m) "length_m",
    json_build_object(
        'roads_paved', sum(CASE WHEN road_type = 'roads_paved' THEN length_m ELSE 0 END),
        'roads_unpaved', sum(CASE WHEN road_type = 'roads_unpaved' THEN length_m ELSE 0 END),
        'roads_primary', sum(CASE WHEN road_type = 'roads_primary' THEN length_m ELSE 0 END),
        'roads_secondary', sum(CASE WHEN road_type = 'roads_secondary' THEN length_m ELSE 0 END),
        'roads_unknown_surface', sum(CASE WHEN road_type = 'roads_unknown_surface' THEN length_m ELSE 0 END),
        'cycleways', sum(CASE WHEN road_type = 'cycleways' THEN length_m ELSE 0 END)
    ) "length_m_road_types"
FROM (
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

	SELECT ST_Length(the_geom::geography) "length_m", ST_AsGeoJSON(the_geom) "geojson", the_geom "geom", road_type "road_type" FROM pgr_bdastar(
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
    INNER JOIN ways rd ON waypoints.edge = rd.gid
) sq;
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
            "lat_upper_bound": float(lat_upper_bound),
        }

        compiled = (
            text(stmt)
            .bindparams(**params)
            .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        print(compiled, flush=True)

        result = db_session.execute(text(stmt), params).fetchone()

    if result is None or result[0] is None:
        raise NoRouteError(f"No route found between {start_point} and {end_point}")

    return Route(
        start=start_point,
        end=end_point,
        length_m=result[2],
        geojson=result[0],
        geom=result[1],
        length_m_road_types=result[3],
    )


def build_route(points: list[Point], bike_type: BikeType) -> list[Route]:
    # todo compute based on bike type
    # lower weight <=> higher preference
    weights = BIKE_TYPE_WEIGHTS[bike_type]["routing_weights"]

    assert len(points) >= 2, f"build_route requires at least 2 points, got {len(points)}"

    with concurrent.futures.ThreadPoolExecutor() as executor:
        routes_to_futures = {
            (s_start, s_end): executor.submit(
                _find_path_astar,
                start_point=s_start,
                end_point=s_end,
                road_type_weights=weights,  # type: ignore[arg-type]
            )
            for s_start, s_end in itertools.pairwise(points)
        }

    routes = []
    for i, ((s_start, s_end), future) in enumerate(routes_to_futures.items(), start=1):
        try:
            route = future.result()
            routes.append(route)
        except NoRouteError as e:
            print(f"Error finding route between points {i} -> {i + 1} {s_start} and {s_end}: {e}")
            raise e
    return routes


def build_routes_multiple(segments: list[list[Point]], bike_type: BikeType) -> list[list[Route]]:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(build_route, segment, bike_type): segment for segment in segments}

    results = []
    for future, segment in futures.items():
        try:
            route = future.result()
            results.append(route)
        except NoRouteError as e:
            print(f"Error building route for segment {segment}: {e}")
            raise e
    return results
