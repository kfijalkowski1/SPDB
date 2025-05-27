# poi_suggester.py
# poi_suggester.py
import random
import json

from geojson.utils import coords  # type: ignore[import-untyped]
from shapely.geometry import LineString  # type: ignore[import-untyped]

from src.engine import Point, get_closest_point, Route

def suggest_pois(bbox: tuple[float, float, float, float], n: int = 5) -> list[Point]:
    min_lat, min_lon, max_lat, max_lon = bbox
    pois: set[Point] = set()
    attempts = 0
    max_attempts = n * 3

    while len(pois) < n and attempts < max_attempts:
        random_lat = random.uniform(min_lat, max_lat)
        random_lon = random.uniform(min_lon, max_lon)
        try:
            db_point = get_closest_point(Point(random_lat, random_lon))
            rand_id = random.randint(1000, 9999)
            poi = Point(db_point.lat, db_point.lon, f"Generated Point #{rand_id}")
            pois.add(poi)
        except Exception:
            pass
        attempts += 1

    return list(pois)

def suggest_sleeping_places(bbox: tuple[float, float, float, float], n: int = 5) -> list[Point]:
    min_lat, min_lon, max_lat, max_lon = bbox
    sleep_points: set[Point] = set()
    attempts = 0
    max_attempts = n * 3

    while len(sleep_points) < n and attempts < max_attempts:
        random_lat = random.uniform(min_lat, max_lat)
        random_lon = random.uniform(min_lon, max_lon)
        try:
            db_point = get_closest_point(Point(random_lat, random_lon))
            idx = len(sleep_points) + 1
            point = Point(db_point.lat, db_point.lon, f"Sleeping Place {idx}", type="sleep")
            sleep_points.add(point)
        except Exception:
            pass
        attempts += 1

    return list(sleep_points)


def get_max_bounds_from_routes(routes: list[Route]) -> tuple[float, float, float, float]:
    route_bounds = [LineString(coords(json.loads(r.geojson))).bounds for r in routes]
    
    lons = [pt[0] for pt in route_bounds] + [pt[2] for pt in route_bounds]
    lats = [pt[1] for pt in route_bounds] + [pt[3] for pt in route_bounds]
    return min(lats), min(lons), max(lats), max(lons)
