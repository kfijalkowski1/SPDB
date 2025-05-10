import streamlit as st
from streamlit_folium import st_folium
import folium
from engine import generate_path

# Configure page
st.set_page_config(page_title="Bike Route Planner", layout="wide")

# Initialize session state
for key in ['points', 'route', 'choose_start', 'choose_end']:
    if key not in st.session_state:
        st.session_state[key] = None if key == 'route' else []

# Page header
st.title("Bike Route Planner - Poland")

# Layout: Map on left, form on right
left_col, right_col = st.columns([2, 1])

with left_col:
    # Create base map
    m = folium.Map(location=[52.2370, 21.0175], zoom_start=6)

    # Add markers
    for idx, point in enumerate(st.session_state.points):
        folium.Marker(
            location=point,
            icon=folium.Icon(color='red' if idx == 0 else 'green'),
            tooltip=f"{'Start' if idx == 0 else 'End'} Point"
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

    # Start Point
    st.markdown("**Start Point:**")
    if len(st.session_state.points) > 0:
        st.write(st.session_state.points[0])
        col1, col2 = st.columns(2)
        if col1.button("Choose Start"):
            st.session_state.choose_start = True
            st.session_state.choose_end = False
        if col2.button("Delete Start"):
            st.session_state.points.pop(0)
            st.session_state.route = None
            st.rerun()
    else:
        st.write("Not selected")
        if st.button("Choose Start"):
            st.session_state.choose_start = True
            st.session_state.choose_end = False

    # End Point
    st.markdown("**End Point:**")
    if len(st.session_state.points) > 1:
        st.write(st.session_state.points[1])
        col1, col2 = st.columns(2)
        if col1.button("Choose End"):
            st.session_state.choose_end = True
            st.session_state.choose_start = False
        if col2.button("Delete End"):
            st.session_state.points.pop(1)
            st.session_state.route = None
            st.rerun()
    else:
        st.write("Not selected")
        if st.button("Choose End"):
            st.session_state.choose_end = True
            st.session_state.choose_start = False

    # Route generation form
    if len(st.session_state.points) == 2:
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
                        route = generate_path(
                            start_point=st.session_state.points[0],
                            end_point=st.session_state.points[1],
                            bike_type=bike_type
                        )
                        st.session_state.route = route
                        st.success("Route generated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generating route: {str(e)}")

    # Reset
    if st.button("Clear All Selections"):
        st.session_state.points = []
        st.session_state.route = None
        st.session_state.choose_start = False
        st.session_state.choose_end = False
        st.rerun()

# Handle map clicks
if map_data and map_data.get("last_clicked"):
    click_point = (map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"])

    if st.session_state.choose_start:
        if len(st.session_state.points) >= 1:
            st.session_state.points[0] = click_point
        else:
            st.session_state.points.insert(0, click_point)
        st.session_state.choose_start = False
        st.session_state.route = None
        st.rerun()

    elif st.session_state.choose_end:
        if len(st.session_state.points) == 0:
            st.session_state.points.append((0, 0))  # placeholder
        if len(st.session_state.points) >= 2:
            st.session_state.points[1] = click_point
        elif len(st.session_state.points) == 1:
            st.session_state.points.append(click_point)
        st.session_state.choose_end = False
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
