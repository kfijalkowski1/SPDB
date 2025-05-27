from src.engine import Point
import random
from geopy.distance import geodesic  # type: ignore[import-untyped]

def split_route_by_sleeping_points(points: list[Point]) -> list[list[Point]]:
    segments = []
    current_segment = []

    for point in points:
        current_segment.append(point)
        if point.type == "sleep":
            segments.append(current_segment)
            current_segment = [point]  # start next day from this sleep point

    if len(current_segment) > 1:
        segments.append(current_segment)

    return segments

def find_nearby(click_latlon: tuple[float, float], candidates: list[Point], max_meters: int = 10000) -> Point | None:
    for obj in candidates:
        obj_latlon = (obj.lat, obj.lon)
        if geodesic(click_latlon, obj_latlon).meters < max_meters:
            return obj
    return None
