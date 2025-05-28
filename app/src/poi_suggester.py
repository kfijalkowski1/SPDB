# poi_suggester.py
# poi_suggester.py
import json
import random
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

import requests
from geojson.utils import coords  # type: ignore[import-untyped]
from shapely.geometry import LineString  # type: ignore[import-untyped]

from engine import Point, Route, PointTypes


def _calculate_bbox_area(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box in square degrees."""
    min_lat, min_lon, max_lat, max_lon = bbox
    return (max_lat - min_lat) * (max_lon - min_lon)


def _split_bbox(bbox: tuple[float, float, float, float], max_area: float = 0.01) -> list[tuple[float, float, float, float]]:
    """
    Split a large bounding box into smaller chunks if it exceeds max_area.
    
    Args:
        bbox: Original bounding box (min_lat, min_lon, max_lat, max_lon)
        max_area: Maximum area per chunk in square degrees (default: 0.01)
    
    Returns:
        List of smaller bounding boxes
    """
    min_lat, min_lon, max_lat, max_lon = bbox
    area = _calculate_bbox_area(bbox)
    
    if area <= max_area:
        return [bbox]
    
    # Calculate how many splits we need in each dimension
    splits_needed = math.ceil(area / max_area)
    splits_per_dim = math.ceil(math.sqrt(splits_needed))
    
    lat_step = (max_lat - min_lat) / splits_per_dim
    lon_step = (max_lon - min_lon) / splits_per_dim
    
    chunks = []
    for i in range(splits_per_dim):
        for j in range(splits_per_dim):
            chunk_min_lat = min_lat + i * lat_step
            chunk_max_lat = min(min_lat + (i + 1) * lat_step, max_lat)
            chunk_min_lon = min_lon + j * lon_step
            chunk_max_lon = min(min_lon + (j + 1) * lon_step, max_lon)
            
            chunks.append((chunk_min_lat, chunk_min_lon, chunk_max_lat, chunk_max_lon))
    
    return chunks


def _query_overpass_chunk(bbox: tuple[float, float, float, float]) -> list[Point]:
    """
    Query Overpass API for a single bounding box chunk.
    
    Args:
        bbox: Bounding box (min_lat, min_lon, max_lat, max_lon)
        max_results: Maximum number of results to return for this chunk
    
    Returns:
        List of Point objects from this chunk
    """
    min_lat, min_lon, max_lat, max_lon = bbox
    
    # Optimized Overpass query with exact matches instead of regex
    overpass_query = f"""
    [out:json][timeout:25];
    (
      // Tourist attractions
      node["tourism"="attraction"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["tourism"="museum"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["tourism"="castle"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["tourism"="monument"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["tourism"="viewpoint"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["tourism"="zoo"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["tourism"="aquarium"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["tourism"="theme_park"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      way["tourism"="attraction"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"="museum"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"="castle"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"="monument"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"="viewpoint"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"="zoo"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"="aquarium"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"="theme_park"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // Historic sites
      node["historic"="castle"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["historic"="monument"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["historic"="memorial"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["historic"="archaeological_site"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["historic"="ruins"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["historic"="fort"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      way["historic"="castle"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["historic"="monument"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["historic"="memorial"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["historic"="archaeological_site"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["historic"="ruins"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["historic"="fort"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // Natural features
      node["natural"="peak"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["natural"="volcano"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["natural"="cave_entrance"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["natural"="hot_spring"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["natural"="geyser"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      way["natural"="peak"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["natural"="volcano"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["natural"="cave_entrance"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["natural"="hot_spring"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["natural"="geyser"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center meta;
    """

    try:
        overpass_url = "http://overpass-api.de/api/interpreter"
        response = requests.post(overpass_url, data=overpass_query, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        elements = data.get("elements", [])
        
        pois: list[Point] = []
        
        for element in elements:
            # Get coordinates (handle both nodes and ways)
            if element["type"] == "node":
                lat, lon = element["lat"], element["lon"]
            elif element["type"] == "way" and "center" in element:
                lat, lon = element["center"]["lat"], element["center"]["lon"]
            else:
                continue

            # Extract name and create description
            tags = element.get("tags", {})
            name = tags.get("name", "Unknown POI")

            # shorten name to max 20 characters
            description = f"{name[:20]}..." if len(name) > 20 else name

            poi = Point(lat, lon, description, type=PointTypes.POI)
            pois.append(poi)

        return pois
        
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error fetching POIs from chunk {bbox}: {e}")
        return []


def suggest_pois(bbox: tuple[float, float, float, float]) -> list[Point]:
    """
    Suggest Points of Interest using the Overpass API within the given bounding box.
    Large bounding boxes are split into smaller chunks and queried in parallel.

    Args:
        bbox: Tuple of (min_lat, min_lon, max_lat, max_lon)

    Returns:
        List of Point objects representing interesting places
    """
    min_lat, min_lon, max_lat, max_lon = bbox
    bbox_area = _calculate_bbox_area(bbox)
    
    # Calculate target number of POIs based on area
    n = min(round(bbox_area * 50), 100)
    print(f"Target POIs: {n}, Bbox area: {bbox_area:.4f} sq degrees")
    
    # Split large bounding boxes into smaller chunks
    chunks = _split_bbox(bbox, max_area=max(0.8, bbox_area / 9))
    print(f"Split bbox into {len(chunks)} chunks for parallel processing")
    
    # Calculate max results per chunk
    
    # Query chunks in parallel using ThreadPoolExecutor
    all_pois: list[Point] = []
    
    with ThreadPoolExecutor() as executor:
        # Submit all chunk queries
        future_to_chunk = {
            executor.submit(_query_overpass_chunk, chunk): chunk 
            for chunk in chunks
        }
        
        print("Waiting for Overpass API responses...")
        
        # Collect results as they complete
    for future in as_completed(future_to_chunk):
        chunk = future_to_chunk[future]
        try:
            chunk_pois = future.result()
            all_pois.extend(chunk_pois)
            print(f"Chunk {chunk} returned {len(chunk_pois)} POIs")
        except Exception as e:
            print(f"Error processing chunk {chunk}: {e}")
    
    # Remove duplicates (POIs that might appear in multiple chunks)
    unique_pois = _deduplicate_pois(all_pois)
    
    # Randomly sample to target number if we have too many
    if len(unique_pois) > n:
        unique_pois = random.sample(unique_pois, n)
    
    print(f"Total unique POIs found: {len(unique_pois)}")
    return unique_pois


def _deduplicate_pois(pois: list[Point]) -> list[Point]:
    """
    Remove duplicate POIs based on proximity (within ~50 meters).
    
    Args:
        pois: List of POI points
        
    Returns:
        List of unique POI points
    """
    if not pois:
        return []
    
    unique_pois = []
    min_distance_deg = 0.0005  # Approximately 50 meters
    
    for poi in pois:
        is_duplicate = False
        for unique_poi in unique_pois:
            # Simple distance check (Euclidean distance in degrees)
            lat_diff = abs(poi.lat - unique_poi.lat)
            lon_diff = abs(poi.lon - unique_poi.lon)
            if lat_diff < min_distance_deg and lon_diff < min_distance_deg:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_pois.append(poi)
    
    return unique_pois




def suggest_sleeping_places(bbox: tuple[float, float, float, float]) -> list[Point]:
    """
    Suggest sleeping places using the Overpass API within the given bounding box.

    Args:
        bbox: Tuple of (min_lat, min_lon, max_lat, max_lon)
        n: Number of sleeping places to return (default: 5)

    Returns:
        List of Point objects representing accommodation options
    """
    min_lat, min_lon, max_lat, max_lon = bbox

    # Overpass API query to find accommodation
    overpass_query = f"""
    [out:json][timeout:25];
    (
      // Hotels and accommodations
      node["tourism"~"^(hotel|motel|hostel|guest_house|bed_and_breakfast|apartment|chalet)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"~"^(hotel|motel|hostel|guest_house|bed_and_breakfast|apartment|chalet)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // Camping
      node["tourism"~"^(camp_site|caravan_site|alpine_hut|wilderness_hut)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"~"^(camp_site|caravan_site|alpine_hut|wilderness_hut)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center meta;
    """
    print(overpass_query)

    try:
        # Make request to Overpass API
        overpass_url = "http://overpass-api.de/api/interpreter"
        response = requests.post(overpass_url, data=overpass_query, timeout=30)
        response.raise_for_status()

        print("Sleeping places: Overpass API response received, req took", response.elapsed.total_seconds(), "seconds")

        data = response.json()
        elements = data.get("elements", [])

        sleep_points: list[Point] = []

        for element in elements:
            # Get coordinates (handle both nodes and ways)
            if element["type"] == "node":
                lat, lon = element["lat"], element["lon"]
            elif element["type"] == "way" and "center" in element:
                lat, lon = element["center"]["lat"], element["center"]["lon"]
            else:
                continue

            # Extract name and create description
            tags = element.get("tags", {})
            name = tags.get("name", "Unnamed Accommodation")

            # Determine accommodation type
            accommodation_type = _determine_accommodation_type(tags)
            description = f"{name} ({accommodation_type})"

            point = Point(lat, lon, description, type=PointTypes.SLEEPING)
            sleep_points.append(point)


        # Randomly sample at most 20 results
        if len(sleep_points) > 20:
            sleep_points = random.sample(sleep_points, 20)
        return sleep_points

    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error fetching sleeping places from Overpass API: {e}")


def _determine_accommodation_type(tags: dict[str, Any]) -> str:
    """Determine the type of accommodation based on OSM tags."""
    tourism_type = tags.get("tourism", "")

    type_mapping = {
        "hotel": "Hotel",
        "motel": "Motel",
        "hostel": "Hostel",
        "guest_house": "Guest House",
        "bed_and_breakfast": "B&B",
        "apartment": "Apartment",
        "chalet": "Chalet",
        "camp_site": "Campsite",
        "caravan_site": "Caravan Site",
        "alpine_hut": "Alpine Hut",
        "wilderness_hut": "Wilderness Hut"
    }

    return type_mapping.get(tourism_type, "Accommodation")


def get_max_bounds_from_routes(
    routes: list[Route],
) -> tuple[float, float, float, float]:
    route_bounds = [LineString(coords(json.loads(r.geojson))).bounds for r in routes]

    lons = [pt[0] for pt in route_bounds] + [pt[2] for pt in route_bounds]
    lats = [pt[1] for pt in route_bounds] + [pt[3] for pt in route_bounds]
    return min(lats), min(lons), max(lats), max(lons)


# if __name__ == "__main__":
#     pois = suggest_pois((53.274035, 16.872313, 54.220317, 18.741565))
#     print(pois)
#     # sleeping_places = suggest_sleeping_places((53.274035, 16.872313, 54.220317, 18.741565))
#     # print(sleeping_places)
