from geopy.distance import geodesic  # type: ignore[import-untyped]

from engine import Point
from enums import BikeType, FitnessLevel, RoadType
from weights import BIKE_TYPE_WEIGHTS
from typing import List
from engine import Point



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


def estimate_speed_kph(bike_type: BikeType, road_type: RoadType, fitness_level: FitnessLevel) -> float:
    speed_base = BIKE_TYPE_WEIGHTS[bike_type]["speed"][fitness_level]  # type: ignore[index]
    speed_multiplier = BIKE_TYPE_WEIGHTS[bike_type]["speed_multipliers"][road_type]  # type: ignore[index]
    return speed_base * speed_multiplier


def estimate_time_needed_s(
    distance_m: float,
    bike_type: BikeType,
    road_type: RoadType,
    fitness_level: FitnessLevel,
) -> int:
    """
    Estimate the time needed to cover a distance based on bike type and fitness level.
    """
    return round(
        distance_m / (estimate_speed_kph(bike_type=bike_type, road_type=road_type, fitness_level=fitness_level) / 3.6)
    )




def insert_multiple_points_logically(existing_points: List[Point], new_points: List[Point]) -> List[Point]:
    for new_point in new_points:
        if len(existing_points) < 2:
            existing_points.append(new_point)
            continue

        best_idx = 1
        min_added_distance = float("inf")

        for i in range(len(existing_points) - 1):
            p1 = existing_points[i]
            p2 = existing_points[i + 1]

            original_dist = geodesic((p1.lat, p1.lon), (p2.lat, p2.lon)).meters
            with_new = (
                geodesic((p1.lat, p1.lon), (new_point.lat, new_point.lon)).meters +
                geodesic((new_point.lat, new_point.lon), (p2.lat, p2.lon)).meters
            )
            added = with_new - original_dist

            if added < min_added_distance:
                min_added_distance = added
                best_idx = i + 1

        existing_points = existing_points[:best_idx] + [new_point] + existing_points[best_idx:]

    return existing_points
