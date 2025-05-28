from enum import Enum

class RoadType(Enum):
    primary = "roads_primary"
    secondary = "roads_secondary"
    paved = "roads_paved"
    unpaved = "roads_unpaved"
    unknown_surface = "roads_unknown_surface"
    cycleway = "cycleways"


class BikeType(Enum):
    road = "road"
    gravel = "gravel"
    trekking = "trekking"
    mtb = "mtb"
    ebike = "ebike"


class FitnessLevel(Enum):
    low = "low"
    medium = "medium"
    good = "good"
    very_good = "very_good"
    excellent = "excellent"
