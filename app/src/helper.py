from geopy.distance import geodesic  # type: ignore[import-untyped]
from geojson.utils import coords  # type: ignore[import-untyped]
from shapely.geometry import LineString  # type: ignore[import-untyped]
import json

from enums import BikeType, FitnessLevel, RoadType
from weights import BIKE_TYPE_WEIGHTS
from typing import List
from engine import Point, Route



def calculate_day_endpoints(route: Route, daily_distance_m: float) -> list[Point]:
    """
    Calculate day endpoints based on daily distance limits along a single route.
    
    Args:
        route: Single Route object
        daily_distance_m: Daily distance limit in meters

    Returns:
        List of Point objects representing end points for each day
    """
    day_endpoints = []
    
    print(f"DEBUG: Processing route with length: {route.length_m/1000:.1f}km, daily limit: {daily_distance_m/1000:.1f}km")
    
    # Calculate how many complete days we can have
    num_complete_days = int(route.length_m // daily_distance_m)
    print(f"DEBUG: Number of complete days: {num_complete_days}")
    
    if num_complete_days == 0:
        # Route is shorter than daily limit, just return the end point
        day_endpoints.append(route.end)
        print(f"DEBUG: Route shorter than daily limit, adding end point")
        return day_endpoints
    
    try:
        # Parse the GeoJSON to get coordinates
        geojson_data = json.loads(route.geojson)
        
        if geojson_data.get('type') == 'LineString':
            coordinates = geojson_data['coordinates']
        elif geojson_data.get('type') == 'MultiLineString':
            # Flatten coordinates from multiple linestrings
            coordinates = []
            for linestring in geojson_data['coordinates']:
                coordinates.extend(linestring)
        else:
            print(f"DEBUG: Unsupported geometry type: {geojson_data.get('type')}")
            day_endpoints.append(route.end)
            return day_endpoints
        
        if len(coordinates) < 2:
            print(f"DEBUG: Not enough coordinates")
            day_endpoints.append(route.end)
            return day_endpoints
        
        # Calculate cumulative distances along the route
        segment_distances = []
        total_geodesic_distance = 0.0
        
        for i in range(len(coordinates) - 1):
            point1 = (coordinates[i][1], coordinates[i][0])  # (lat, lon)
            point2 = (coordinates[i + 1][1], coordinates[i + 1][0])  # (lat, lon)
            
            segment_distance = geodesic(point1, point2).meters
            segment_distances.append(segment_distance)
            total_geodesic_distance += segment_distance
        
        print(f"DEBUG: Total geodesic distance: {total_geodesic_distance/1000:.1f}km")
        
        # For each complete day, find the point at that distance
        for day in range(1, num_complete_days + 1):
            target_distance = day * daily_distance_m
            
            # Scale the target distance based on the ratio between route.length_m and geodesic distance
            if total_geodesic_distance > 0:
                scaled_target_distance = target_distance * (total_geodesic_distance / route.length_m)
            else:
                continue
            
            print(f"DEBUG: Day {day}: target {target_distance/1000:.1f}km, scaled {scaled_target_distance/1000:.1f}km")
            
            # Find the point at the scaled target distance
            cumulative_distance = 0.0
            
            for i, segment_distance in enumerate(segment_distances):
                if cumulative_distance + segment_distance >= scaled_target_distance:
                    # Target distance is within this segment
                    remaining_distance = scaled_target_distance - cumulative_distance
                    ratio = remaining_distance / segment_distance if segment_distance > 0 else 0
                    
                    # Interpolate between the two points
                    point1 = (coordinates[i][1], coordinates[i][0])  # (lat, lon)
                    point2 = (coordinates[i + 1][1], coordinates[i + 1][0])  # (lat, lon)
                    
                    lat = point1[0] + (point2[0] - point1[0]) * ratio
                    lon = point1[1] + (point2[1] - point1[1]) * ratio
                    
                    endpoint = Point(lat, lon, f"Day {day} endpoint", type=None)
                    day_endpoints.append(endpoint)
                    print(f"DEBUG: Day {day} endpoint created at {lat:.5f}, {lon:.5f}")
                    break
                
                cumulative_distance += segment_distance
        
        # Add final endpoint if there's remaining distance
        remaining_distance = route.length_m % daily_distance_m
        if remaining_distance > 0:
            day_endpoints.append(route.end)
            print(f"DEBUG: Final endpoint added (remaining: {remaining_distance/1000:.1f}km)")
        
    except (json.JSONDecodeError, KeyError, IndexError, ZeroDivisionError) as e:
        print(f"DEBUG: Error processing route: {e}")
        day_endpoints.append(route.end)
    
    print(f"DEBUG: Total day endpoints created: {len(day_endpoints)}")
    return day_endpoints


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
