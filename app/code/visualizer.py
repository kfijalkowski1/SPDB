import streamlit as st
from streamlit_folium import st_folium
import folium
from engine import generate_path, get_closest_point, Point, build_route

# Configure page
st.set_page_config(page_title="Bike Route Planner", layout="wide")

# Initialize session state
for key in ['points', 'route', 'choosing_point_idx']:
    if key not in st.session_state:
        st.session_state[key] = None if key in ('route', 'choosing_point_idx') else []

# Page header
st.title("Bike Route Planner - Poland")

# Layout: Map on left, form on right
left_col, right_col = st.columns([2, 1])

with left_col:
    # Create base map
    m = folium.Map(location=[52.2370, 21.0175], zoom_start=6)

    # Add markers
    for idx, point in enumerate(st.session_state.points):
        if idx == 0:
            color = 'green'
            tooltip = "Start Point"
        elif idx == len(st.session_state.points) - 1:
            color = 'red'
            tooltip = "End Point"
        else:
            color = 'orange'
            tooltip = f"Stop {idx + 1}"
        folium.Marker(
            location=point,
            icon=folium.Icon(color=color),
            tooltip=tooltip
        ).add_to(m)

    if st.session_state.route:
        folium.PolyLine(
            locations=st.session_state.route,
            color='blue',
            weight=5,
            opacity=0.7
        ).add_to(m)

    # Display map
    map_data = st_folium(
        m,
        width=800,
        height=600,
        returned_objects=["last_clicked"]
    )

with right_col:
    st.subheader("Selection Status")
    
    for i, point in enumerate(st.session_state.points):
        st.write(point)
        col1, col2 = st.columns(2)
        if col1.button("Choose again", key=f"choose_again_{i}"):
            st.session_state.choosing_point_idx = i
        if col2.button("Delete point", key=f"delete_point_{i}"):
            st.session_state.points.pop(i)
            st.rerun()
    st.markdown("---")
    if st.button("Add point"):
        st.session_state.choosing_point_idx = len(st.session_state.points)

    # Route generation form
    if len(st.session_state.points) >= 2:
        with st.form("route_config"):
            st.subheader("Route Configuration")
            bike_type = st.selectbox(
                "Bike Type",
                ["Road Bike", "Mountain Bike", "Hybrid Bike", "Electric Bike"],
                index=0
            )
            submitted = st.form_submit_button("Generate Route")
            if submitted:
                with st.spinner("Generating optimal route..."):
                    try:
                        route = build_route(
                            points=st.session_state.points,
                            bike_type=bike_type
                        )
                        st.session_state.route = [
                            ((line.lat1, line.lon1), (line.lat2, line.lon2)) for line in route
                        ]
                        st.success("Route generated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generating route: {str(e)}")

    # Reset
    if st.button("Clear All Selections"):
        st.session_state.points = []
        st.session_state.route = None
        st.session_state.choosing_point_idx = None
        st.rerun()

# Handle map clicks
if map_data and map_data.get("last_clicked") and st.session_state.choosing_point_idx is not None:
    click_point = Point(map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"])

    closest_point = get_closest_point(click_point).point
    
    if st.session_state.choosing_point_idx >= len(st.session_state.points):
        st.session_state.points.append(closest_point)
        st.session_state.choosing_point_idx = None
        st.session_state.route = None
        st.rerun()
    else:
        st.session_state.points[st.session_state.choosing_point_idx] = closest_point
        st.session_state.choosing_point_idx = None
        st.session_state.route = None
        st.rerun()

# Instructions
st.markdown("""
**Instructions:**
1. Click 'Choose Start' or 'Choose End' before selecting a location on the map.
2. Hold **Ctrl** to pan/zoom the map.
3. Delete or update points using the buttons.
4. Select your bike type and generate the route.
5. Click 'Clear All Selections' to start over.
""")
