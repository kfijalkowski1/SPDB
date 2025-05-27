from engine import Point
import random
from geopy.distance import geodesic

def split_route_by_sleeping_points(points: list[Point]) -> list[list[Point]]:
    segments = []
    current_segment = []

    for point in points:
        current_segment.append(point)
        if point.type == "sleep" and len(current_segment) > 1:
            segments.append(current_segment)
            current_segment = [point]  # start next day from this sleep point

    if len(current_segment) > 1:
        segments.append(current_segment)

    return segments


def fake_distance_for_segment(segment: list[Point]) -> float:
    return round(random.uniform(25.0, 60.0), 2)  # kilometers

def find_nearby(click_latlon, candidates, max_meters=10000):
    for obj in candidates:
        obj_latlon = (obj.lat, obj.lon)
        if geodesic(click_latlon, obj_latlon).meters < max_meters:
            return obj
    return None