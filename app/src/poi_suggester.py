# poi_suggester.py
# poi_suggester.py
import json
import random
from typing import Any

import requests
from geojson.utils import coords  # type: ignore[import-untyped]
from shapely.geometry import LineString  # type: ignore[import-untyped]

from engine import Point, Route, PointTypes


def suggest_pois(bbox: tuple[float, float, float, float], n: int = 100) -> list[Point]:
    """
    Suggest Points of Interest using the Overpass API within the given bounding box.

    Args:
        bbox: Tuple of (min_lat, min_lon, max_lat, max_lon)
        n: Number of POIs to return (default: 5)

    Returns:
        List of Point objects representing interesting places
    """
    min_lat, min_lon, max_lat, max_lon = bbox

    # Overpass API query to find various types of POIs
    overpass_query = f"""
    [out:json][timeout:35];
    (
      // Tourist attractions
      node["tourism"~"^(attraction|museum|castle|monument|viewpoint|zoo|aquarium|theme_park)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["tourism"~"^(attraction|museum|castle|monument|viewpoint|zoo|aquarium|theme_park)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // Historic sites
      node["historic"~"^(castle|monument|memorial|archaeological_site|ruins|fort)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["historic"~"^(castle|monument|memorial|archaeological_site|ruins|fort)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // Natural features
      node["natural"~"^(peak|volcano|cave_entrance|hot_spring|geyser)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["natural"~"^(peak|volcano|cave_entrance|hot_spring|geyser)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center meta;
    """

    print(overpass_query)

    try:
        # Make request to Overpass API
        overpass_url = "http://overpass-api.de/api/interpreter"
        print("Waiting for Overpass API...")
        response = requests.post(overpass_url, data=overpass_query, timeout=35)
        response.raise_for_status()
        print("Overpass API response received, req took", response.elapsed.total_seconds(), "seconds")

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
            description = f"{name[:20]}..."

            poi = Point(lat, lon, description, type=PointTypes.POI)
            pois.append(poi)

            # Stop if we have enough POIs
            if len(pois) >= n:
                break

        return pois[:n]

    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error fetching POIs from Overpass API: {e}")




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
