from geopy.distance import geodesic  # type: ignore[import-untyped]

from src.engine import Point
from src.enums import BikeType, FitnessLevel, RoadType
from src.weights import BIKE_TYPE_WEIGHTS


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
