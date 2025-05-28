from src.enums import BikeType, FitnessLevel, RoadType

# arbitrary mapping
BIKE_TYPE_WEIGHTS: dict[BikeType, dict[str, dict[FitnessLevel, float] | dict[RoadType, float]]] = {
    BikeType.road: {
        "speed": {
            FitnessLevel.low: 20.0,
            FitnessLevel.medium: 24.0,
            FitnessLevel.good: 28.0,
            FitnessLevel.very_good: 30.0,
            FitnessLevel.excellent: 32.0
        },
        "routing_weights": {
            RoadType.primary: 1.7,
            RoadType.secondary: 1.3,
            RoadType.paved: 1.0,
            RoadType.unpaved: 3.0,
            RoadType.unknown_surface: 3.0,
            RoadType.cycleway: 0.8
        },
        "speed_multipliers": {
            RoadType.primary: 1.0,
            RoadType.secondary: 1.0,
            RoadType.paved: 1.0,
            RoadType.unpaved: 0.5,
            RoadType.unknown_surface: 0.6,
            RoadType.cycleway: 1.0
        }
    },
    BikeType.gravel: {
        "speed": {
            FitnessLevel.low: 18.0,
            FitnessLevel.medium: 22.0,
            FitnessLevel.good: 26.0,
            FitnessLevel.very_good: 28.0,
            FitnessLevel.excellent: 30.0
        },
        "routing_weights": {
            RoadType.primary: 2,
            RoadType.secondary: 1.6,
            RoadType.paved: 1.0,
            RoadType.unpaved: 1.2,
            RoadType.unknown_surface: 1.2,
            RoadType.cycleway: 0.8
        },
        "speed_multipliers": {
            RoadType.primary: 1.0,
            RoadType.secondary: 1.0,
            RoadType.paved: 1.0,
            RoadType.unpaved: 0.8,
            RoadType.unknown_surface: 0.8,
            RoadType.cycleway: 1.0
        }
    },
    BikeType.trekking: {
        "speed": {
            FitnessLevel.low: 13.0,
            FitnessLevel.medium: 16.0,
            FitnessLevel.good: 19.0,
            FitnessLevel.very_good: 22.0,
            FitnessLevel.excellent: 25.0
        },
        "routing_weights": {
            RoadType.primary: 3,
            RoadType.secondary: 3,
            RoadType.paved: 1.0,
            RoadType.unpaved: 1.2,
            RoadType.unknown_surface: 1.2,
            RoadType.cycleway: 0.8
        },
        "speed_multipliers": {
            RoadType.primary: 1.0,
            RoadType.secondary: 1.0,
            RoadType.paved: 1.0,
            RoadType.unpaved: 0.8,
            RoadType.unknown_surface: 0.8,
            RoadType.cycleway: 1.0
        }
    },
    BikeType.mtb: {
        "speed": {
            FitnessLevel.low: 13.0,
            FitnessLevel.medium: 16.0,
            FitnessLevel.good: 19.0,
            FitnessLevel.very_good: 22.0,
            FitnessLevel.excellent: 25.0
        },
        "routing_weights": {
            RoadType.primary: 3,
            RoadType.secondary: 3,
            RoadType.paved: 1.0,
            RoadType.unpaved: 0.7,
            RoadType.unknown_surface: 0.7,
            RoadType.cycleway: 1.0
        },
        "speed_multipliers": {
            RoadType.primary: 1.0,
            RoadType.secondary: 1.0,
            RoadType.paved: 1.0,
            RoadType.unpaved: 0.9,
            RoadType.unknown_surface: 0.9,
            RoadType.cycleway: 1.0
        }
    },
    BikeType.ebike: {
        "speed": {
            FitnessLevel.low: 21.0,
            FitnessLevel.medium: 22.0,
            FitnessLevel.good: 23.0,
            FitnessLevel.very_good: 24.0,
            FitnessLevel.excellent: 25.0
        },
        "routing_weights": {
            RoadType.primary: 3,
            RoadType.secondary: 3,
            RoadType.paved: 1.0,
            RoadType.unpaved: 1.2,
            RoadType.unknown_surface: 1.2,
            RoadType.cycleway: 0.8
        },
        "speed_multipliers": {
            RoadType.primary: 1.0,
            RoadType.secondary: 1.0,
            RoadType.paved: 1.0,
            RoadType.unpaved: 0.9,
            RoadType.unknown_surface: 0.9,
            RoadType.cycleway: 1.0
        }
    }
}
