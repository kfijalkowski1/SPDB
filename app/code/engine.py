from typing import NamedTuple

from sqlalchemy import text

from db_utils import session


# default SRID for geography is 4326
# http://postgis.net/docs/using_postgis_dbmanagement.html#PostGIS_Geography
SRID = 4326


class Point(NamedTuple):
    lat: float
    lon: float
    
    def __str__(self):
        return f"({self.lat}, {self.lon})"


class Line(NamedTuple):
    lat1: float
    lon1: float
    lat2: float
    lon2: float
    
    def __str__(self):
        return f"({self.lat1}, {self.lon1}) -> ({self.lat2}, {self.lon2})"


class DbPoint(NamedTuple):
    id: int
    osm_id: int
    lat: float
    lon: float
    geom: str

    def __str__(self):
        return f"id={self.id} ({self.lat}, {self.lon})"
    
    @property
    def point(self):
        return Point(self.lat, self.lon)


def generate_path(start_point: Point, end_point: Point, bike_type, num_points=50):
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


def get_closest_points(reference_point: Point, n: int) -> list[DbPoint]:
    
    # note lat and lon are swapped!
    stmt = """
    SELECT id, osm_id, lat, lon, the_geom
    FROM ways_vertices_pgr "vert"
    ORDER BY vert.the_geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), :srid)::geometry ASC
    LIMIT :n
    """

    with session() as db_session:
        result = db_session.execute(
            text(stmt),
            {
                "lat": reference_point.lat,
                "lon": reference_point.lon,
                "srid": SRID,
                "n": n
            }
        )
    return [
        DbPoint(
            id=row[0],
            osm_id=row[1],
            lat=row[2],
            lon=row[3],
            geom=row[4]
        )
        for row in result
    ]


def get_closest_point(reference_point: Point) -> DbPoint:
    return get_closest_points(reference_point, 1)[0]


def _find_path_astar(
    start_point: DbPoint,
    end_point: DbPoint,
) -> list[Line]:
    stmt = """
    SELECT y1 "lat1", x1 "lon1", y2 "lat2", x2 "lon2" FROM pgr_bdastar(
        'SELECT gid "id", source, target, cost, reverse_cost, x1, y1, x2, y2
        FROM ways',
        :start_point_id,
        :end_point_id,
        directed => true, heuristic => 4
    ) as waypoints
    INNER JOIN ways rd ON waypoints.edge = rd.gid;
    """
    
    with session() as db_session:
        result = db_session.execute(
            text(stmt),
            {
                "start_point_id": start_point.id,
                "end_point_id": end_point.id
            }
        )
    return [
        Line(
            lat1=row[0],
            lon1=row[1],
            lat2=row[2],
            lon2=row[3]
        )
        for row in result
    ]


def build_route(start_point: Point, end_point: Point, bike_type: str) -> list[Line]:
    # TODO closest points can be searched directly in the a* query
    start_point = get_closest_point(start_point)
    end_point = get_closest_point(end_point)
    route = _find_path_astar(start_point, end_point)
    return route
