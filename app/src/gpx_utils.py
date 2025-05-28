import json
from typing import Any

import gpxpy.gpx

from engine import Route


def export_to_gpx(routes: list[Route], filename: str) -> bytes:
    """
    Export a list of routes to a GPX file.
    
    Args:
        routes: List of Route objects containing start, end, and geojson data
        filename: Name of the output GPX file
    """
    # Create a new GPX object
    gpx = gpxpy.gpx.GPX()
    
    # Set GPX metadata
    gpx.name = "Bike Route"
    gpx.description = f"Generated bike route with {len(routes)} segments"
    
    # Create a single track for all route segments
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.name = "Bike Route Track"
    gpx.tracks.append(gpx_track)
    
    # Add waypoints for start and end points
    if routes:
        # Start waypoint
        start_point = routes[0].start
        start_wpt = gpxpy.gpx.GPXWaypoint(
            latitude=start_point.lat,
            longitude=start_point.lon,
            name=f"Start: {start_point.short_desc}",
            symbol="Flag, Green"
        )
        gpx.waypoints.append(start_wpt)
        
        # End waypoint
        end_point = routes[-1].end
        end_wpt = gpxpy.gpx.GPXWaypoint(
            latitude=end_point.lat,
            longitude=end_point.lon,
            name=f"End: {end_point.short_desc}",
            symbol="Flag, Red"
        )
        gpx.waypoints.append(end_wpt)
    
    # Process each route segment
    for i, route in enumerate(routes):
        # Create a track segment for this route
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        
        # Parse the GeoJSON and extract coordinates
        try:
            geojson_data = json.loads(route.geojson)
            coordinates = _extract_coordinates_from_geojson(geojson_data)
            
            # Add track points
            for coord in coordinates:
                lon, lat = coord[0], coord[1]
                elevation = coord[2] if len(coord) > 2 else None
                
                track_point = gpxpy.gpx.GPXTrackPoint(
                    latitude=lat,
                    longitude=lon,
                    elevation=elevation
                )
                gpx_segment.points.append(track_point)
                
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Error processing route {i}: {e}")
            continue
    
    # return the gpx as bytes
    return gpx.to_xml().encode('utf-8')



def _extract_coordinates_from_geojson(geojson_data: dict[str, Any]) -> list[list[float]]:
    """
    Extract coordinates from GeoJSON data.
    
    Args:
        geojson_data: Parsed GeoJSON object
        
    Returns:
        List of coordinate arrays [lon, lat, elevation?]
    """
    geom_type = geojson_data.get('type')
    coordinates = geojson_data.get('coordinates', [])
    
    if geom_type == 'LineString':
        return coordinates
    elif geom_type == 'MultiLineString':
        # Flatten multiple line strings into a single coordinate list
        flattened = []
        for linestring in coordinates:
            flattened.extend(linestring)
        return flattened
    elif geom_type == 'Point':
        return [coordinates]
    elif geom_type == 'MultiPoint':
        return coordinates
    elif geom_type == 'Polygon':
        # Use the exterior ring
        return coordinates[0] if coordinates else []
    elif geom_type == 'MultiPolygon':
        # Use the first polygon's exterior ring
        return coordinates[0][0] if coordinates and coordinates[0] else []
    elif geom_type == 'GeometryCollection':
        # Process all geometries and combine coordinates
        all_coords = []
        for geometry in geojson_data.get('geometries', []):
            all_coords.extend(_extract_coordinates_from_geojson(geometry))
        return all_coords
    else:
        print(f"Unsupported geometry type: {geom_type}")
        return []


def export_routes_with_pois_to_gpx(routes: list[Route], pois: list[Any], filename: str):
    """
    Export routes and POIs to a GPX file.
    
    Args:
        routes: List of Route objects
        pois: List of Point objects representing POIs
        filename: Name of the output GPX file
    """
    # Create a new GPX object
    gpx = gpxpy.gpx.GPX()
    
    # Set GPX metadata
    gpx.name = "Bike Route with POIs"
    gpx.description = f"Generated bike route with {len(routes)} segments and {len(pois)} POIs"
    
    # Export routes (same as above)
    if routes:
        # Create a single track for all route segments
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_track.name = "Bike Route Track"
        gpx.tracks.append(gpx_track)
        
        # Add start/end waypoints
        start_point = routes[0].start
        start_wpt = gpxpy.gpx.GPXWaypoint(
            latitude=start_point.lat,
            longitude=start_point.lon,
            name=f"Start: {start_point.short_desc}",
            symbol="Flag, Green"
        )
        gpx.waypoints.append(start_wpt)
        
        end_point = routes[-1].end
        end_wpt = gpxpy.gpx.GPXWaypoint(
            latitude=end_point.lat,
            longitude=end_point.lon,
            name=f"End: {end_point.short_desc}",
            symbol="Flag, Red"
        )
        gpx.waypoints.append(end_wpt)
        
        # Process route segments
        for i, route in enumerate(routes):
            gpx_segment = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)
            
            try:
                geojson_data = json.loads(route.geojson)
                coordinates = _extract_coordinates_from_geojson(geojson_data)
                
                for coord in coordinates:
                    lon, lat = coord[0], coord[1]
                    elevation = coord[2] if len(coord) > 2 else None
                    
                    track_point = gpxpy.gpx.GPXTrackPoint(
                        latitude=lat,
                        longitude=lon,
                        elevation=elevation
                    )
                    gpx_segment.points.append(track_point)
                    
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                print(f"Error processing route {i}: {e}")
                continue
    
    # Add POI waypoints
    for poi in pois:
        # Determine symbol based on POI type
        symbol = "Information"  # Default symbol
        if hasattr(poi, 'type'):
            if poi.type == "sleep":
                symbol = "Lodging"
            elif poi.type == "poi":
                symbol = "Scenic Area"
        
        poi_wpt = gpxpy.gpx.GPXWaypoint(
            latitude=poi.lat,
            longitude=poi.lon,
            name=poi.short_desc,
            symbol=symbol
        )
        gpx.waypoints.append(poi_wpt)
    
    # Write GPX file
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(gpx.to_xml())
        print(f"GPX file with POIs saved as {filename}")
    except IOError as e:
        print(f"Error writing GPX file: {e}")
        raise


