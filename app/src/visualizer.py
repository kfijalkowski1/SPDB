import traceback
from itertools import cycle
from typing import OrderedDict

import folium
import plotly.express as px  # type: ignore[import-untyped]
import streamlit as st
from streamlit_extras.stylable_container import stylable_container  # type: ignore[import-untyped]
from streamlit_folium import st_folium  # type: ignore[import-untyped]

from engine import Point, build_routes_multiple, get_closest_point
from enums import BikeType, FitnessLevel, RoadType
from helper import (
    calculate_day_endpoints,
    estimate_speed_kph,
    estimate_time_needed_s,
    find_nearby,
    split_route_by_sleeping_points,
    insert_multiple_points_logically,
)
from poi_suggester import (
    get_max_bounds_from_routes,
    suggest_pois,
    suggest_sleeping_places,
)
from gpx_utils import export_to_gpx

# Configure page
st.set_page_config(page_title="Bike Route Planner", layout="wide")

# Initialize session state
for key in [
    "points",
    "route",
    "segment_routes",
    "route_segments",
    "choosing_point_idx",
    "suggested_pois",
    "selected_pois",
    "suggested_sleeping",
    "selected_sleeping",
    "road_type_to_distance",
    "bike_type",
    "fitness_level",
]:
    if key not in st.session_state:
        if key in (
            "route",
            "segment_routes",
            "route_segments",
            "choosing_point_idx",
            "suggested_pois",
            "suggested_sleeping",
            "bike_type",
            "fitness_level",
        ):
            st.session_state[key] = None
        elif key in ("selected_pois", "selected_sleeping"):
            st.session_state[key] = set()
        else:
            st.session_state[key] = []

bike_type_name_mapping = OrderedDict(
    {
        "Road Bike": BikeType.road,
        "Mountain Bike": BikeType.mtb,
        "Gravel Bike": BikeType.gravel,
        "Trekking Bike": BikeType.trekking,
        "E-Bike": BikeType.ebike,
    }
)

fitness_level_name_mapping = OrderedDict(
    {
        "Low": FitnessLevel.low,
        "Medium": FitnessLevel.medium,
        "Good": FitnessLevel.good,
        "Very Good": FitnessLevel.very_good,
        "Excellent": FitnessLevel.excellent,
    }
)


# Sidebar - Trip Configuration
with st.sidebar:
    st.header("Trip Settings")
    trip_days = st.number_input("Trip Duration (days)", min_value=1, max_value=30, value=5, step=1)
    daily_km = st.number_input("Distance per Day (km)", min_value=10, max_value=300, value=40, step=5)
    bike_type = st.selectbox("Bike Type", list(bike_type_name_mapping.keys()), index=0)
    fitness_level = st.select_slider("Fitness Level", list(fitness_level_name_mapping.keys()), value="Good")

    st.session_state.trip_days = trip_days
    st.session_state.daily_m = daily_km * 1000
    st.session_state.bike_type = bike_type_name_mapping[bike_type]
    st.session_state.fitness_level = fitness_level_name_mapping[fitness_level]

# Main layout
map_col, config_col = st.columns([2, 1])

# --- Map Column ---
with map_col:
    st.subheader("Route Map")
    m = folium.Map(location=[52.2370, 21.0175], zoom_start=6)

    for idx, point in enumerate(st.session_state.points):
        if idx == 0:
            color = "green"
            tooltip = "Start Point"
        elif idx == len(st.session_state.points) - 1:
            color = "red"
            tooltip = "End Point"
        else:
            color = "orange"
            tooltip = point.short_desc

        if point.type == "sleep" and point not in (st.session_state.suggested_sleeping or []):
            folium.Marker(
                location=(point.lat, point.lon),
                icon=folium.Icon(color="darkblue", icon="bed", prefix="fa"),
                tooltip=point.short_desc,
            ).add_to(m)
        else:
            folium.Marker(
                location=(point.lat, point.lon),
                icon=folium.Icon(color=color),
                tooltip=tooltip,
            ).add_to(m)

    if st.session_state.segment_routes:
        color_cycle = cycle(["blue", "green", "orange", "red", "purple"])
        for segment_route in st.session_state.segment_routes:
            color = next(color_cycle)
            for route in segment_route:
                folium.GeoJson(
                    data=route.geojson,
                    name=f"Segment {len(st.session_state.segment_routes)}",
                    color = color
                ).add_to(m)

    if st.session_state.suggested_pois:
        for poi in st.session_state.suggested_pois:
            folium.Marker(
                location=(poi.lat, poi.lon),
                icon=folium.Icon(color="purple"),
                tooltip=poi.short_desc,
            ).add_to(m)

    if st.session_state.suggested_sleeping:
        for sleep in st.session_state.suggested_sleeping:
            folium.Marker(
                location=(sleep.lat, sleep.lon),
                icon=folium.Icon(color="cadetblue", icon="bed", prefix="fa"),
                tooltip=sleep.short_desc,
            ).add_to(m)

    map_data = st_folium(m, width=800, height=600, returned_objects=["last_clicked"])

    if st.session_state.route_segments:
        total_days = max(len(st.session_state.route_segments), st.session_state.trip_days)
        m_per_day = st.session_state.daily_m

        distance_by_day = {label: dist for label, dist in st.session_state.route_segments} | {
            f"Day {i + 1}": 0 for i in range(len(st.session_state.route_segments), total_days)
        }
        distance_by_road_type = {rt: 0 for rt in RoadType}
        for segment in st.session_state.segment_routes:
            for route in segment:
                for road_type, distance in route.length_m_road_types.items():
                    distance_by_road_type[RoadType(road_type)] += distance
        total_distance = sum(distance_by_day.values())
        speed_by_road_type = {
            road_type: estimate_speed_kph(
                bike_type=st.session_state.bike_type,
                road_type=road_type,
                fitness_level=st.session_state.fitness_level,
            )
            for road_type in distance_by_road_type.keys()
        }
        time_s_by_road_type = {
            road_type: estimate_time_needed_s(
                distance_m=distance_by_road_type[RoadType(road_type)],
                bike_type=st.session_state.bike_type,
                road_type=road_type,
                fitness_level=st.session_state.fitness_level,
            )
            for road_type in distance_by_road_type.keys()
        }
        time_s_by_day = {
            i: sum(
                [
                    sum(
                        [
                            estimate_time_needed_s(
                                distance_m=dist_m,
                                bike_type=st.session_state.bike_type,
                                road_type=RoadType(rt),
                                fitness_level=st.session_state.fitness_level,
                            )
                            for rt, dist_m in route.length_m_road_types.items()
                        ]
                    )
                    for route in seg
                ]
            )
            for i, seg in enumerate(st.session_state.segment_routes, start=1)
        } | {i: 0 for i in range(len(st.session_state.segment_routes) + 1, total_days + 1)}
        total_time_s = sum(time_s_by_day.values())

        st.write(f"### Total Distance: {total_distance / 1000:.2f} km")
        st.write(
            f"Estimated moving time: _**{sum(time_s_by_day.values()) // 3600}:{sum(time_s_by_day.values()) % 3600 // 60:02} h**_ at average speed of _**{total_distance / total_time_s * 3.6:.1f} km/h**_."
        )

        cols = st.columns([1, 1], vertical_alignment="center")

        with cols[0]:
            days_data = [
                {"Day": f"Day {i}", "Distance": dist / 1000}
                for i, (_, dist) in enumerate(distance_by_day.items(), start=1)
                if dist > 0
            ]
            fig = px.pie(
                days_data,
                values="Distance",
                names="Day",
                title="Distance by days",
                hole=0.7,
                category_orders={"Day": [f"Day {i}" for i in range(1, total_days + 1)]},
            )
            st.plotly_chart(fig, use_container_width=True)
        with cols[1]:
            st.table(
                {
                    "Day": [f"Day {i}" for i in range(1, len(distance_by_day) + 1)],
                    "Distance": [f"{round(dist / 1000, 2)} km " for dist in distance_by_day.values()],
                    "Plan": [
                        f"{round((abs(dist - m_per_day)) / 1000, 2)} km "
                        + ("ahead of plan" if dist > m_per_day else "behind plan")
                        for dist in distance_by_day.values()
                    ],
                    "Est. time": [
                        f"{time_s_by_day[i] // 3600}:{time_s_by_day[i] % 3600 // 60:02} h"
                        for i in range(1, len(distance_by_day) + 1)
                    ],
                }
            )

        cols = st.columns([1, 1], vertical_alignment="center")

        with cols[0]:
            name_mapping = OrderedDict(
                **{
                    RoadType.primary.value: "Primary",
                    RoadType.secondary.value: "Secondary",
                    RoadType.paved.value: "Paved",
                    RoadType.unpaved.value: "Unpaved",
                    RoadType.cycleway.value: "Cycleway",
                    RoadType.unknown_surface.value: "Unknown Surface",
                }
            )
            road_type_data = [
                {
                    "Road Type": name_mapping[road_type],
                    "Distance (km)": distance_by_road_type[RoadType(road_type)] / 1000,
                }
                for road_type in name_mapping.keys()
                if distance_by_road_type[RoadType(road_type)] > 0
            ]

            fig = px.pie(
                road_type_data,
                values="Distance (km)",
                names="Road Type",
                title="Distance by road types",
                hole=0.7,
                category_orders={"Road Type": list(name_mapping.values())},
            )
            st.plotly_chart(fig, use_container_width=True)
        with cols[1]:
            st.table(
                {
                    "Road Type": list(name_mapping.values()),
                    "Share": [
                        f"{round(distance_by_road_type[RoadType(road_type)] * 100 / total_distance, 2)} %"
                        for road_type in name_mapping.keys()
                    ],
                    "Distance": [
                        f"{round(distance_by_road_type[RoadType(road_type)] / 1000, 2)} km"
                        for road_type in name_mapping.keys()
                    ],
                }
            )

# --- Config Column ---
with config_col:
    tab1, tab2, tab3 = st.tabs(["Points", "POIs", "Sleeping Places"])

    with tab1:
        st.subheader("Route Points")
        if len(st.session_state.points) == 0:
            st.info('Start your next big adventure! Click "Add point" to select a point on the map.')

        # Flatten all route distances in order
        point_to_point_distances_km = [
            route.length_m / 1000
            for segment in st.session_state.segment_routes or []
            for route in segment
        ]

        for i, point in enumerate(st.session_state.points):
            cols = st.columns([1.3, 1.3, 10, 5], vertical_alignment="center")
            with cols[0]:
                with stylable_container(
                        key=f"points_number_{i}",
                        css_styles="""
                    h4{
                        margin-bottom: 5px;
                    }
                    """,
                ):
                    st.write(f"#### {i + 1}.")
            with cols[1]:
                with stylable_container(
                        key=f"point_actions_left_{i}",
                        css_styles="""
                    button{
                        float: left;
                        margin-bottom: 10px;
                    }
                    """,
                ):
                    if st.button("↑", key=f"move_up_{i}") and i > 0:
                        st.session_state.points[i - 1], st.session_state.points[i] = (
                            st.session_state.points[i],
                            st.session_state.points[i - 1],
                        )
                        st.rerun()
                    if st.button("↓", key=f"move_down_{i}") and i < len(st.session_state.points) - 1:
                        st.session_state.points[i + 1], st.session_state.points[i] = (
                            st.session_state.points[i],
                            st.session_state.points[i + 1],
                        )
                        st.rerun()
            with cols[2]:
                st.write(f"##### {point.short_desc}")
                st.write(f"`{point.lat:.5f}, {point.lon:.5f}`")
                # Add distance info if not the first point
                if i > 0 and i - 1 < len(point_to_point_distances_km):
                    st.write(f"📏 _Distance from previous_: **{point_to_point_distances_km[i - 1]:.2f} km**")
            with cols[3]:
                with stylable_container(
                        key=f"point_actions_right_{i}",
                        css_styles="""
                    button{
                        float: right;
                        margin-bottom: 10px;
                    }
                    """,
                ):
                    if st.button("Choose again", key=f"choose_again_{i}"):
                        st.session_state.choosing_point_idx = i
                    if st.button("Delete", key=f"delete_point_{i}"):
                        st.session_state.points.pop(i)
                        st.rerun()

        st.markdown("---")
        cols = st.columns([1, 1])
        with cols[0]:
            if st.button("Add point"):
                st.session_state.choosing_point_idx = len(st.session_state.points)
        with cols[1]:
            with stylable_container(
                key="clear_all_selections_style",
                css_styles="""
                button{
                    float: right;
                }
                """,
            ):
                if st.button("Clear All Selections"):
                    for key in [
                        "points",
                        "route",
                        "segment_routes",
                        "route_segments",
                        "choosing_point_idx",
                        "suggested_pois",
                        "selected_pois",
                        "suggested_sleeping",
                        "selected_sleeping",
                    ]:
                        if isinstance(st.session_state[key], list):
                            st.session_state[key] = []
                        elif isinstance(st.session_state[key], set):
                            st.session_state[key] = set()
                        else:
                            st.session_state[key] = None
                    st.rerun()

        if len(st.session_state.points) >= 2:
            with st.form("route_config"):
                st.subheader("Route Configuration")
                submitted = st.form_submit_button("Generate Route")
                if submitted:
                    with st.spinner("Generating optimal route..."):
                        try:
                            segment_points = split_route_by_sleeping_points(st.session_state.points)
                            segment_routes = []
                            route_segments = []

                            full_route_segments = build_routes_multiple(segment_points, st.session_state.bike_type)
                            for idx, seg_routes in enumerate(full_route_segments):
                                segment_routes.append(seg_routes)
                                route_segments.append(
                                    (
                                        f"Day {idx + 1}",
                                        sum([route.length_m for route in seg_routes]),
                                    )
                                )

                            st.session_state.segment_routes = segment_routes
                            st.session_state.route_segments = route_segments

                            pois_bbox = get_max_bounds_from_routes([r for seg in segment_routes for r in seg])
                            st.session_state.suggested_pois = suggest_pois(pois_bbox)
                            st.session_state.selected_pois = set()

                            # Calculate day endpoints based on daily distance
                            all_routes = [route for seg in segment_routes for route in seg]
                            day_endpoints = calculate_day_endpoints(all_routes, st.session_state.daily_m)

                            # Find sleeping places for each day endpoint
                            all_sleeping_places = []
                            SLEEP_SEARCH_RADIUS_DEG = 0.1

                            for endpoint in day_endpoints:
                                sleep_bbox = (
                                    float(endpoint.lat) - SLEEP_SEARCH_RADIUS_DEG,
                                    float(endpoint.lon) - SLEEP_SEARCH_RADIUS_DEG,
                                    float(endpoint.lat) + SLEEP_SEARCH_RADIUS_DEG,
                                    float(endpoint.lon) + SLEEP_SEARCH_RADIUS_DEG,
                                )
                                sleeping_places = suggest_sleeping_places(sleep_bbox)
                                all_sleeping_places.extend(sleeping_places)

                            st.session_state.suggested_sleeping = all_sleeping_places
                            st.session_state.selected_sleeping = set()

                            st.success("Route generated successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error generating route: {str(e)}")
                            print(e)
                            print(traceback.format_exc())
            st.download_button("Download GPX", export_to_gpx(st.session_state.segment_routes, "route.gpx"),mime="application/gpx+xml")

    with tab2:
        if st.session_state.suggested_pois:
            st.subheader("Suggested POIs")
            for i, poi in enumerate(st.session_state.suggested_pois):
                label = f"POI at ({poi.lat:.5f}, {poi.lon:.5f})"
                if st.checkbox(label, key=f"poi_{i}"):
                    st.session_state.selected_pois.add(i)
                else:
                    st.session_state.selected_pois.discard(i)
            if st.button("Add Selected POIs to Route"):
                selected_pois = [st.session_state.suggested_pois[i] for i in st.session_state.selected_pois]
                st.session_state.points = insert_multiple_points_logically(st.session_state.points, selected_pois)
                st.session_state.suggested_pois = None
                st.session_state.selected_pois = set()
                st.rerun()

    with tab3:
        if st.session_state.suggested_sleeping:
            st.subheader("Suggested Sleeping Places")
            for i, sleep in enumerate(st.session_state.suggested_sleeping):
                label = f"{sleep.short_desc} ({sleep.lat:.5f}, {sleep.lon:.5f})"
                if st.checkbox(label, key=f"sleep_{i}"):
                    st.session_state.selected_sleeping.add(i)
                else:
                    st.session_state.selected_sleeping.discard(i)
            if st.button("Add Selected Sleeping Places to Route"):
                selected_sleep = [st.session_state.suggested_sleeping[i] for i in st.session_state.selected_sleeping]
                st.session_state.points = insert_multiple_points_logically(st.session_state.points, selected_sleep)
                st.session_state.suggested_sleeping = None
                st.session_state.selected_sleeping = set()
                st.rerun()

# --- Handle map clicks ---
if map_data and map_data.get("last_clicked"):
    click_latlon = (map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"])

    # Handle user point placement
    if st.session_state.choosing_point_idx is not None:
        db_point = get_closest_point(Point(*click_latlon))
        desc = f"Waypoint #{len(st.session_state.points) + 1}"
        closest_point = Point(db_point.lat, db_point.lon, desc)

        if st.session_state.choosing_point_idx >= len(st.session_state.points):
            st.session_state.points.append(closest_point)
        else:
            st.session_state.points[st.session_state.choosing_point_idx] = closest_point

        st.session_state.choosing_point_idx = None
        st.rerun()

    else:
        # Check for nearby POI
        nearby_poi = find_nearby(click_latlon, st.session_state.suggested_pois or [])
        if nearby_poi:
            new_poi = Point(nearby_poi.lat, nearby_poi.lon, nearby_poi.short_desc, type="poi")
            st.session_state.points = insert_multiple_points_logically(
                st.session_state.points,
                [new_poi]
            )
            st.session_state.suggested_pois.remove(nearby_poi)
            st.rerun()

        # Check for nearby sleeping place
        nearby_sleep = find_nearby(click_latlon, st.session_state.suggested_sleeping or [])
        if nearby_sleep:
            new_sleep = Point(
                nearby_sleep.lat,
                nearby_sleep.lon,
                nearby_sleep.short_desc,
                type="sleep"
            )
            st.session_state.points = insert_multiple_points_logically(
                st.session_state.points,
                [new_sleep]
            )
            st.session_state.suggested_sleeping.remove(nearby_sleep)
            st.rerun()


