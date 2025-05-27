import streamlit as st
from streamlit_folium import st_folium
import folium
from engine import generate_path, get_closest_point, Point, build_route, build_routes_multiple
from poi_suggester import suggest_pois, get_route_bounds, suggest_sleeping_places
from helper import split_route_by_sleeping_points, fake_distance_for_segment, find_nearby
from itertools import cycle

# Configure page
st.set_page_config(page_title="Bike Route Planner", layout="wide")

# Initialize session state
for key in [
    'points', 'route', 'segment_routes', 'route_segments',
    'choosing_point_idx', 'suggested_pois', 'selected_pois',
    'suggested_sleeping', 'selected_sleeping'
]:
    if key not in st.session_state:
        if key in ('route', 'segment_routes', 'route_segments', 'choosing_point_idx', 'suggested_pois', 'suggested_sleeping'):
            st.session_state[key] = None
        elif key in ('selected_pois', 'selected_sleeping'):
            st.session_state[key] = set()
        else:
            st.session_state[key] = []


# Sidebar - Trip Configuration
with st.sidebar:
    st.header("Trip Settings")
    trip_days = st.number_input("Trip Duration (days)", min_value=1, max_value=30, value=5, step=1)
    daily_km = st.number_input("Distance per Day (km)", min_value=10, max_value=300, value=40, step=5)
    bike_type = st.selectbox("Bike Type", ["Road Bike", "Mountain Bike", "Hybrid Bike", "Electric Bike"], index=0)

    st.session_state.trip_days = trip_days
    st.session_state.daily_km = daily_km

# Main layout
map_col, config_col = st.columns([2, 1])

# --- Map Column ---
with map_col:
    st.subheader("Route Map")
    m = folium.Map(location=[52.2370, 21.0175], zoom_start=6)

    for idx, point in enumerate(st.session_state.points):
        if idx == 0:
            color = 'green'
            tooltip = "Start Point"
        elif idx == len(st.session_state.points) - 1:
            color = 'red'
            tooltip = "End Point"
        else:
            color = 'orange'
            tooltip = point.short_desc

        if point.type == "sleep" and point not in (st.session_state.suggested_sleeping or []):
            folium.Marker(
                location=(point.lat, point.lon),
                icon=folium.Icon(color='darkblue', icon="bed", prefix="fa"),
                tooltip=point.short_desc
            ).add_to(m)
        else:
            folium.Marker(
                location=(point.lat, point.lon),
                icon=folium.Icon(color=color),
                tooltip=tooltip
            ).add_to(m)

    if st.session_state.segment_routes:
        color_cycle = cycle(["blue", "green", "orange", "red", "purple"])
        for segment_route in st.session_state.segment_routes:
            color = next(color_cycle)
            folium.PolyLine(
                locations=[(line.lat1, line.lon1) for line in segment_route] + [(segment_route[-1].lat2, segment_route[-1].lon2)],
                color=color,
                weight=5,
                opacity=0.8
            ).add_to(m)

    if st.session_state.suggested_pois:
        for poi in st.session_state.suggested_pois:
            folium.Marker(
                location=(poi.lat, poi.lon),
                icon=folium.Icon(color='purple'),
                tooltip=poi.short_desc
            ).add_to(m)

    if st.session_state.suggested_sleeping:
        for sleep in st.session_state.suggested_sleeping:
            folium.Marker(
                location=(sleep.lat, sleep.lon),
                icon=folium.Icon(color='cadetblue', icon="bed", prefix="fa"),
                tooltip=sleep.short_desc
            ).add_to(m)

    map_data = st_folium(m, width=800, height=600, returned_objects=["last_clicked"])

    if st.session_state.route_segments:
        with st.expander("Daily Route Lengths", expanded=True):
            total_distance = 0
            for label, dist in st.session_state.route_segments:
                st.write(f"{label}: {dist} km")
                total_distance += dist
            st.write(f"**Total Distance:** {total_distance} km")

# --- Config Column ---
with config_col:
    tab1, tab2, tab3 = st.tabs(["Points", "POIs", "Sleeping Places"])

    with tab1:
        st.subheader("Route Points")
        for i, point in enumerate(st.session_state.points):
            st.write(f"**{point.short_desc}**")
            cols = st.columns([1, 1, 2, 1])
            if cols[0].button("↑", key=f"move_up_{i}") and i > 0:
                st.session_state.points[i - 1], st.session_state.points[i] = st.session_state.points[i], st.session_state.points[i - 1]
                st.rerun()
            if cols[1].button("↓", key=f"move_down_{i}") and i < len(st.session_state.points) - 1:
                st.session_state.points[i + 1], st.session_state.points[i] = st.session_state.points[i], st.session_state.points[i + 1]
                st.rerun()
            if cols[2].button("Choose again", key=f"choose_again_{i}"):
                st.session_state.choosing_point_idx = i
            if cols[3].button("Delete", key=f"delete_point_{i}"):
                st.session_state.points.pop(i)
                st.rerun()

        st.markdown("---")
        if st.button("Add point"):
            st.session_state.choosing_point_idx = len(st.session_state.points)

        if len(st.session_state.points) >= 2:
            with st.form("route_config"):
                st.subheader("Route Configuration")
                submitted = st.form_submit_button("Generate Route")
                if submitted:
                    with st.spinner("Generating optimal route..."):
                        try:
                            segment_points = split_route_by_sleeping_points(st.session_state.points)
                            full_route = []
                            segment_routes = []
                            route_segments = []
                            
                            full_route_segments = build_routes_multiple(segment_points, bike_type)
                            for idx, seg_route in enumerate(full_route_segments):
                                segment_routes.append(seg_route)
                                full_route.extend([((line.lat1, line.lon1), (line.lat2, line.lon2)) for line in seg_route])
                                route_segments.append((f"Day {idx + 1}", fake_distance_for_segment(seg_route)))

                            st.session_state.route = full_route
                            st.session_state.segment_routes = segment_routes
                            st.session_state.route_segments = route_segments

                            bbox = get_route_bounds(st.session_state.route)
                            st.session_state.suggested_pois = suggest_pois(bbox)
                            st.session_state.selected_pois = set()
                            st.session_state.suggested_sleeping = suggest_sleeping_places(bbox)
                            st.session_state.selected_sleeping = set()

                            st.success("Route generated successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error generating route: {str(e)}")

        if st.button("Clear All Selections"):
            for key in ['points', 'route', 'segment_routes', 'route_segments', 'choosing_point_idx', 'suggested_pois', 'selected_pois', 'suggested_sleeping', 'selected_sleeping']:
                if isinstance(st.session_state[key], list):
                    st.session_state[key] = []
                elif isinstance(st.session_state[key], set):
                    st.session_state[key] = set()
                else:
                    st.session_state[key] = None
            st.rerun()

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
                for i in st.session_state.selected_pois:
                    st.session_state.points.insert(-1, st.session_state.suggested_pois[i])
                st.session_state.route = None
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
                for i in st.session_state.selected_sleeping:
                    st.session_state.points.insert(-1, st.session_state.suggested_sleeping[i])
                st.session_state.route = None
                st.session_state.suggested_sleeping = None
                st.session_state.selected_sleeping = set()
                st.rerun()

# --- Handle map clicks ---
if map_data and map_data.get("last_clicked"):
    click_latlon = (
        map_data["last_clicked"]["lat"],
        map_data["last_clicked"]["lng"]
    )

    # Handle user point placement
    if st.session_state.choosing_point_idx is not None:
        db_point = get_closest_point(Point(*click_latlon))
        desc = f"User Point {len(st.session_state.points) + 1}"
        closest_point = Point(db_point.lat, db_point.lon, desc)

        if st.session_state.choosing_point_idx >= len(st.session_state.points):
            st.session_state.points.append(closest_point)
        else:
            st.session_state.points[st.session_state.choosing_point_idx] = closest_point

        st.session_state.choosing_point_idx = None
        st.session_state.route = None
        st.rerun()

    # If not placing user point, check for POIs and sleep clicks
    else:
        # Check for nearby POI
        nearby_poi = find_nearby(click_latlon, st.session_state.suggested_pois or [])
        if nearby_poi:
            st.session_state.points.insert(-1, Point(nearby_poi.lat, nearby_poi.lon, nearby_poi.short_desc, type="poi"))
            st.session_state.suggested_pois.remove(nearby_poi)
            st.session_state.route = None
            st.rerun()

        # Check for nearby sleeping place
        nearby_sleep = find_nearby(click_latlon, st.session_state.suggested_sleeping or [])
        if nearby_sleep:
            st.session_state.points.insert(-1, Point(nearby_sleep.lat, nearby_sleep.lon, nearby_sleep.short_desc, type="sleep"))
            st.session_state.suggested_sleeping.remove(nearby_sleep)
            st.session_state.route = None
            st.rerun()



# Instructions
st.markdown("""
**Instructions:**
1. Click 'Add point' or 'Choose again' before selecting a location on the map.
2. Hold **Ctrl** to pan/zoom the map.
3. Use the tabs to manage points, POIs, and sleeping places.
4. Click 'Clear All Selections' to reset the planner.
""")
