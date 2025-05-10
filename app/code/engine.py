def generate_path(start_point, end_point, bike_type, num_points=50):
    """Mock path generator, returns straight line between points"""
    print(f"Generating path from {start_point} to {end_point} for {bike_type}")
    lat1, lon1 = start_point
    lat2, lon2 = end_point

    path = [
        (
            lat1 + (lat2 - lat1) * i / (num_points - 1),
            lon1 + (lon2 - lon1) * i / (num_points - 1)
        )
        for i in range(num_points)
    ]
    print(path)
    return path