# app.py
import streamlit as st
from auth import login
from sqlalchemy import extract
from database import init_db, Session, User, Emission
from datetime import date
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.io as pio
import io, zipfile
import plotly.graph_objects as go
from sqlalchemy import func

FACILITIES = [
    "Residential Areas",
    "Hostels",
    "Academic Area",
    "Health Centre",
    "Schools",
    "Visitor's Hostel",
    "Servants Quarters",
    "Shops/Bank/PO"
]
MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

st.markdown("""
    <style>
    .blink {
        animation: blinker 1.5s linear infinite;
        color: red;
        font-weight: bold;
    }
    @keyframes blinker {
        50% { opacity: 0; }
    }
    </style>
""", unsafe_allow_html=True)


# Centering + Card Shadow styling
st.markdown("""
    <style>
    .centered {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 10px;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);  /* Soft card shadow */
        margin-bottom: 20px;
    }
    .centered-red {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 10px;
        background: #ffe6e6; /* light red */
        border-radius: 15px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

CATEGORY_ICONS = {
    "Fossil Fuels": "⛽️",
    "Fugitive": "🏭",
    "Electricity": "⚡",
    "Water": "💧",
    "Waste": "🗑️",
    "Travel": "✈️"
}

# Custom colored progress bar
def custom_progress_bar(value, safe_limit):
    percentage = min(value / safe_limit, 1.0) * 100  # calculate percentage
    color = "green" if value <= safe_limit else "red"  # pick color based on safe limit

    st.markdown(f"""
        <div style="position: relative; height: 20px; background-color: #e0e0e0; border-radius: 10px; margin: 10px 0;">
            <div style="background-color: {color}; width: {percentage}%; height: 100%; border-radius: 10px;"></div>
            <div style="position: absolute; top: 0; left: 50%; transform: translateX(-50%); font-size: 12px; color: black;">
                {value:.0f} kg / {safe_limit:.0f} kg
            </div>
        </div>
    """, unsafe_allow_html=True)

# 1. Initialize DB
init_db()

# 2. Authentication
if not st.session_state.get("logged_in", False):
    login()
    st.stop()


# 3. Greeting & "Let’s get started" button
if menu_options == "Home":
    name = st.session_state.get("username", "")
    st.write(f"👋 Welcome {name}, let’s get started with your Carbon Foot Calculator.")

    if st.button("Let’s get started"):
        st.session_state.started = True
        st.experimental_rerun()  

if not st.session_state.get("started"):
    st.stop()

admin_username = "dhamarukanath"
# 4. Sidebar menu
menu_options = [
    "Home"
    "Carbon Data",
    "Carbon Metre",
    "Emission Analysis",
    "Year and Facility Analysis",
    "Download",
    "Offset Contribution"
]
if st.session_state.get("username") == admin_username:
    menu_options.append("Manage Database")

menu = st.sidebar.radio("Menu", menu_options)
if not st.session_state.get("started", False) and menu != "Home":
    st.warning("🚫 Please start from the Home tab.")
    st.stop()
# 5. Get DB session & current user
db = Session()
user = db.query(User).filter_by(name=name).first()

# Emission factor dictionaries
emission_factors = {
    "Fossil Fuels": {"CNG": 2.21},
    "Fossil Fuels per litre": {"Petrol/Gasoline": 2.315, "Diesel": 2.68, "LPG": 1.51},
    "Fossil Fuels per scm": {"PNG": 2.1},
    "Electricity": {"Coal/Thermal": 0.85, "Solar": 0.00}
}
f_e_f = {
    "Domestic Refrigeration": 1430,
    "Commercial Refrigeration": 3922,
    "Industrial Refrigeration": 2088,
    "Residential and Commercial A/C": 1650
}
of_e_f = {
    "tree": 1.75,
    "soil": 0.0515,
    "grass": 0.0309,
    "water": 0.0412
}
e_e_f = {
    "Coal/Thermal": 0.92,
    "Solar": 0.05
}
w_e_f = 0.344
wa_e_f = {
    "Household Residue": {"Landfills": 1.0, "Combustion": 0.7, "Recycling": 0.2, "Composting": 0.1},
    "Food and Drink Waste": {"Landfills": 1.9, "Combustion": 0.8, "Recycling": 0.3, "Composting": 0.05},
    "Garden Waste": {"Landfills": 0.6, "Combustion": 0.4, "Recycling": 0.2, "Composting": 0.03},
    "Commercial and Industrial Waste": {"Landfills": 2.0, "Combustion": 1.5, "Recycling": 0.6, "Composting": 0.2}
}
SAFE_LIMITS = {
    "Fossil Fuels": 5000,
    "Fugitive": 3000,
    "Electricity": 4000,
    "Water": 2000,
    "Waste": 1500,
    "Travel": 3500
}
def log_emission(category, facility, year, month, value):
    entry = Emission(
        user_id=user.id,
        date=date(int(year), MONTHS.index(month)+1, 1),
        facility=facility,
        category=category,
        value=abs(value) if category == "Offset" else value
    )
    db.add(entry)
    db.commit()

def plot_gauge(current_value, category, safe_limit):
    icon = CATEGORY_ICONS.get(category, "🌍")  # default globe if not found
    title_text = f"{icon} {category}"
    color = "green" if current_value <= safe_limit else "red"
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = current_value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"{icon} {category}" , 'font': {'size': 20}},
        number = {'suffix': " kg CO₂", 'font': {'size': 18}},
        delta = {'reference': safe_limit, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
        gauge = {
            'axis': {'range': [0, safe_limit * 1.5], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': color},
            'steps': [
                {'range': [0, safe_limit], 'color': "lightgreen"},
                {'range': [safe_limit, safe_limit*1.5], 'color': "salmon"},
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': safe_limit
            }
        }
    ))
    
   
    fig.update_layout(
        margin = {'t': 40, 'b': 0, 'l': 0, 'r': 0},
        height=300,
        transition = {'duration': 1000, 'easing': 'cubic-in-out'}
    )
    return fig

# Initialize session state for emissions log
if "emission_log" not in st.session_state:
    st.session_state.emission_log = []

# 6. Handle each menu choice
if menu == "Carbon Data":
    # Header for Carbon Data
    st.header("Enter Carbon Data")
    # Common inputs
    facility = st.selectbox("Facility", ["Choose Facility"] + FACILITIES)
    month = st.selectbox("Month", ["Choose Month"] + MONTHS)
    year = st.number_input("Year", min_value=0, format="%d", value=date.today().year)

    # Fossil Fuels
    with st.expander("Fossil Fuels"):
        st.subheader("Fossil Fuel Emissions")
        with st.form("fossil_form"):
            fuel_type = st.selectbox("Fuel Type", ["Choose Fuel Type", "CNG", "Petrol/Gasoline", "Diesel", "PNG", "LPG"])
            unit = st.selectbox("Unit", ["Choose Unit", "Kg", "Tonne", "litre", "SCM"])
            amount_consumed = st.number_input("Amount Consumed", min_value=0.0, format="%f")
            submitted = st.form_submit_button("Submit Fossil Fuels Data")
        if submitted:
            if facility == "Choose Facility" or month == "Choose Month":
                st.warning("Please select facility and month.")
            elif fuel_type == "Choose Fuel Type" or unit == "Choose Unit":
                st.warning("Please select fuel type and unit.")
            else:
                factor = None
                amt = amount_consumed
                if unit == "Tonne":
                    amt *= 1000  # convert to kg
                    factor = emission_factors["Fossil Fuels"].get(fuel_type)
                elif unit == "litre":
                    factor = emission_factors["Fossil Fuels per litre"].get(fuel_type)
                elif unit == "SCM":
                    factor = emission_factors["Fossil Fuels per scm"].get(fuel_type)
                elif unit == "Kg":
                    factor = emission_factors["Fossil Fuels"].get(fuel_type)
                if factor is not None:
                    carbon_footprint = amt * factor
                    st.success(f"Your estimated CO₂ emission: **{carbon_footprint:.2f} kg**")
                    st.session_state["Fossil Fuels Emission"] = carbon_footprint
                    if facility != "Choose Facility" and month != "Choose Month":
                        log_emission("Fossil Fuels", facility, year, month, carbon_footprint)
                        st.session_state.emission_log.append({
                            "Year": year,
                            "Month": month,
                            "Facility": facility,
                            "Factor": "Fossil Fuels",
                            "Emission": carbon_footprint
                        })

    # Fugitive
    with st.expander("Fugitive"):
        st.subheader("Fugitive Emissions")
        with st.form("fugitive_form"):
            application_type = st.selectbox("Application Type", ["Choose Application Type"] + list(f_e_f.keys()))
            unit2 = st.selectbox("Unit", ["Choose Unit", "Kg", "Tonne"])
            amt2 = st.number_input("Number of Units", min_value=0.0, format="%f")
            submitted2 = st.form_submit_button("Submit Fugitive Data")
        if submitted2:
            if facility == "Choose Facility" or month == "Choose Month":
                st.warning("Please select facility and month.")
            elif application_type == "Choose Application Type":
                st.warning("Please select an application type.")
            else:
                gwp_factor = f_e_f.get(application_type, 0)
                units_consumed = amt2
                if unit2 == "Tonne":
                    units_consumed *= 1000  # Convert to kg
                fugitive_emission = units_consumed * gwp_factor
                st.success(f"Your estimated CO₂ equivalent emission: **{fugitive_emission:.2f} kg**")
                st.session_state["Fugitive Emission"] = fugitive_emission
                if facility != "Choose Facility" and month != "Choose Month":
                    log_emission("Fugitive", facility, year, month, fugitive_emission)
                    st.session_state.emission_log.append({
                        "Year": year,
                        "Month": month,
                        "Facility": facility,
                        "Factor": "Fugitive",
                        "Emission": fugitive_emission
                    })

    # Electricity
    with st.expander("Electricity"):
        st.subheader("Electricity Emissions")
        with st.form("electricity_form"):
            electricity_type = st.selectbox("Electricity Type", ["Choose electricity Type", "Coal/Thermal", "Solar"])
            electricity_source = st.selectbox("Electricity Source", ["Choose Electricity Source", "Purchased", "Self-Produced"])
            unit3 = st.selectbox("Unit", ["Choose Unit", "KWH"])
            amt3 = st.number_input("Amount Consumed (kWh)", min_value=0.0, format="%f")
            submitted3 = st.form_submit_button("Submit Electricity Data")
        if submitted3:
            if facility == "Choose Facility" or month == "Choose Month":
                st.warning("Please select facility and month.")
            elif electricity_type == "Choose electricity Type":
                st.warning("Please select electricity type.")
            else:
                emission_factor = e_e_f.get(electricity_type, 0)
                electricity_emission = amt3 * emission_factor
                st.success(f"Your estimated CO₂ equivalent emission: **{electricity_emission:.2f} kg**")
                st.session_state["Electricity Emission"] = electricity_emission
                if facility != "Choose Facility" and month != "Choose Month":
                    log_emission("Electricity", facility, year, month, electricity_emission)
                    st.session_state.emission_log.append({
                        "Year": year,
                        "Month": month,
                        "Facility": facility,
                        "Factor": "Electricity",
                        "Emission": electricity_emission
                    })

    # Water
    with st.expander("Water"):
        st.subheader("Water Emissions")
        with st.form("water_form"):
            water_type = st.selectbox("Water Type", ["Choose Water Type", "Supplied Water", "Treated water"])
            discharge_site = st.text_input("Discharge Site")
            unit4 = st.selectbox("Unit", ["Choose Unit", "Cubic metre", "million litres"])
            amt4 = st.number_input("Amount", min_value=0.0, format="%f")
            submitted4 = st.form_submit_button("Submit Water Data")
        if submitted4:
            if facility == "Choose Facility" or month == "Choose Month":
                st.warning("Please select facility and month.")
            else:
                water_emission = 0.0
                if unit4 == "Cubic metre":
                    water_emission = amt4 * w_e_f
                elif unit4 == "million litres":
                    water_emission = amt4 * 1000 * w_e_f
                st.success(f"Your estimated CO₂ equivalent emission from water usage is: **{water_emission:.2f} kg**")
                st.session_state["Water Emission"] = water_emission
                if facility != "Choose Facility" and month != "Choose Month":
                    log_emission("Water", facility, year, month, water_emission)
                    st.session_state.emission_log.append({
                        "Year": year,
                        "Month": month,
                        "Facility": facility,
                        "Factor": "Water",
                        "Emission": water_emission
                    })

    # Waste
    with st.expander("Waste"):
        st.subheader("Waste Emissions")
        with st.form("waste_form"):
            waste_type = st.selectbox("Waste Type", ["Choose Waste Type", "Household Residue",
                                                     "Food and Drink Waste", "Garden Waste", "Commercial and Industrial Waste"])
            treatment_type = st.selectbox("Treatment Type", ["Choose Treatment Type", "Landfills", "Combustion", "Recycling", "Composting"])
            unit5 = st.selectbox("Unit", ["Choose Unit", "Kg", "Tonne"])
            amt5 = st.number_input("Amount", min_value=0.0, format="%f")
            submitted5 = st.form_submit_button("Submit Waste Data")
        if submitted5:
            if facility == "Choose Facility" or month == "Choose Month":
                st.warning("Please select facility and month.")
            elif waste_type == "Choose Waste Type" or treatment_type == "Choose Treatment Type":
                st.warning("Please select waste type and treatment type.")
            else:
                emission_factor = wa_e_f.get(waste_type, {}).get(treatment_type, 0)
                amount_kg = amt5
                if unit5 == "Tonne":
                    amount_kg = amt5 * 1000
                waste_emission = amount_kg * emission_factor
                st.success(f"Your estimated CO₂ equivalent emission from waste is: **{waste_emission:.2f} kg**")
                st.session_state["Waste Emission"] = waste_emission
                if facility != "Choose Facility" and month != "Choose Month":
                    log_emission("Waste", facility, year, month, waste_emission)
                    st.session_state.emission_log.append({
                        "Year": year,
                        "Month": month,
                        "Facility": facility,
                        "Factor": "Waste",
                        "Emission": waste_emission
                    })

    # Travel
    with st.expander("Travel"):
        st.subheader("Travel Emissions")
        with st.form("travel_form"):
            travel_mode = st.selectbox("Mode of Transport", ["Choose Mode of Transport", "Airways", "Roadways", "Railways"])
            emission = 0.0
            flight_emissions = {"Short Haul": 0.15, "Long Haul": 0.11, "Domestic": 0.18, "International": 0.13}
            train_emission_factors = {"Electric": 0.035, "Diesel": 0.06, "Hydrogen": 0.04}
            personal_emission_factors = {"Small Sized Car": 0.12, "Medium Sized Car": 0.17, "Large Sized Car": 0.22, "Motorcycle": 0.09}
            bus_emission_factors = {"Electricity": 0.03, "Diesel": 0.09, "Hydrogen": 0.05}
            taxi_emission_factors = {"Electricity": 0.06, "Petrol": 0.16, "Hydrogen": 0.07, "CNG": 0.13}

            if travel_mode == "Airways":
                flight_length = st.selectbox("Flight Length", ["Short Haul", "Long Haul", "Domestic", "International"])
                distance = st.number_input("Enter distance traveled (km)", min_value=0.0, step=1.0)
                if distance:
                    emission = distance * flight_emissions.get(flight_length, 0)
            elif travel_mode == "Railways":
                rail_type = st.selectbox("Rail Type", ["Metro", "National Railways"])
                if rail_type == "Metro":
                    distance = st.number_input("Enter distance traveled (km)", min_value=0.0, step=1.0)
                    if distance:
                        emission = distance * 0.04
                elif rail_type == "National Railways":
                    train_type = st.selectbox("Train Type", ["Electric", "Diesel", "Hydrogen"])
                    distance = st.number_input("Enter distance traveled (km)", min_value=0.0, step=1.0)
                    if distance:
                        emission = distance * train_emission_factors.get(train_type, 0)
            elif travel_mode == "Roadways":
                ownership = st.selectbox("Vehicle Ownership", ["Public", "Personal"])
                if ownership == "Personal":
                    vehicle_type = st.selectbox("Vehicle Type", ["Small Sized Car", "Medium Sized Car", "Large Sized Car", "Motorcycle"])
                    distance = st.number_input("Enter distance traveled (km)", min_value=0.0, step=1.0)
                    if distance:
                        emission = distance * personal_emission_factors.get(vehicle_type, 0)
                elif ownership == "Public":
                    vehicle_type = st.selectbox("Vehicle Type", ["Bus", "Taxi"])
                    if vehicle_type == "Bus":
                        bus_fuel = st.selectbox("Bus Runs On", ["Electricity", "Diesel", "Hydrogen"])
                        distance = st.number_input("Enter distance traveled (km)", min_value=0.0, step=1.0)
                        if distance:
                            emission = distance * bus_emission_factors.get(bus_fuel, 0)
                    elif vehicle_type == "Taxi":
                        taxi_fuel = st.selectbox("Taxi Runs On", ["Electricity", "Petrol", "Hydrogen", "CNG"])
                        distance = st.number_input("Enter distance traveled (km)", min_value=0.0, step=1.0)
                        if distance:
                            emission = distance * taxi_emission_factors.get(taxi_fuel, 0)
            submitted6 = st.form_submit_button("Submit Travel Data")
        if submitted6:
            if facility == "Choose Facility" or month == "Choose Month":
                st.warning("Please select facility and month.")
            elif travel_mode == "Choose Mode of Transport":
                st.warning("Please select a mode of transport.")
            else:
                st.success(f"Your estimated CO₂ emission from travel is: **{emission:.2f} kg**")
                st.session_state["Travel Emission"] = emission
                if facility != "Choose Facility" and month != "Choose Month":
                    log_emission("Travel", facility, year, month, emission)
                    st.session_state.emission_log.append({
                        "Year": year,
                        "Month": month,
                        "Facility": facility,
                        "Factor": "Travel",
                        "Emission": emission
                    })
    with st.expander("Offset Contribution"):
        st.subheader("Carbon Offset")
        with st.form("offset_form"):
            col1, col2 = st.columns(2)
            with col1:
                trees = st.number_input("Number of Trees", min_value=0, format="%d")
                soil_area = st.number_input("Soil Area (m²)", min_value=0.0, format="%f")
            with col2:
                grass_area = st.number_input("Grass Area (m²)", min_value=0.0, format="%f")
                water_area = st.number_input("Water Area (m²)", min_value=0.0, format="%f")
        
            submitted_offset = st.form_submit_button("Submit Offset Data")
    
        if submitted_offset:
             if facility == "Choose Facility" or month == "Choose Month":
                 st.warning("Please select facility and month first.")
             else:
            # Calculate offset
                  offset_value = (trees * of_e_f["tree"] + 
                          soil_area * of_e_f["soil"] + 
                          grass_area * of_e_f["grass"] + 
                          water_area * of_e_f["water"])
            
                  log_emission("Offset", facility, year, month, offset_value)
                  st.session_state.emission_log.append({
                      "Year": year,
                      "Month": month,
                      "Facility": facility,
                      "Factor": "Offset",
                      "Emission": offset_value
                  })
                  st.success(f"Offset contribution recorded: {offset_value:.2f} kg CO₂e")  

elif menu == "Carbon Metre":
    st.header("Carbon Footprint Summary")

    # Year/Month/Facility Filters
    col1, col2 = st.columns(2)
    with col1:
        selected_facility = st.selectbox("Facility", ["Choose Facility"] + FACILITIES)
        selected_year = st.number_input("Year", min_value=0, format="%d", value=date.today().year)
    with col2:
        selected_month = st.selectbox("Select Month", ["Choose Month"] + MONTHS)

    if (
        selected_facility != "Choose Facility" and
        selected_month != "Choose Month" and
        selected_year > 0
    ):
        # Initialize totals per category
        category_totals = {cat: 0.0 for cat in SAFE_LIMITS}
        records = db.query(Emission).filter(
            Emission.user_id == user.id,
            Emission.facility == selected_facility,
            extract('year', Emission.date) == selected_year,
            extract('month', Emission.date) == MONTHS.index(selected_month) + 1
        ).all()

        for rec in records:
            if rec.category in category_totals:
                category_totals[rec.category] += abs(rec.value)

        

        # Display gauge meters
        cols = st.columns(3)
        for idx, (category, emission) in enumerate(category_totals.items()):
            with cols[idx % 3]:
                with st.container():
                    card_class = "centered" if emission <= SAFE_LIMITS[category] else "centered-red"
                    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
                    fig = plot_gauge(emission, category, SAFE_LIMITS[category])
                    st.plotly_chart(fig, use_container_width=True)
                    custom_progress_bar(emission, SAFE_LIMITS[category])

                    if emission <= SAFE_LIMITS[category]:
                        st.success(f"✅ {category} emissions within limits.")
                    else:
                        excess = emission - SAFE_LIMITS[category]
                        st.markdown(f"<span class='blink'>🚨 Exceeded {excess/1000:.2f} tons in {category} emissions.</span>", unsafe_allow_html=True)

                    st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Please select a facility, month, and valid year.")



elif menu == "Emission Analysis":
    st.header("Emission Overview")

    # Fetch all emission records
    records = db.query(Emission).filter(Emission.user_id == user.id).all()
    df = pd.DataFrame([{
        "Year": rec.date.year,
        "Month": rec.date.strftime("%B"),
        "Facility": rec.facility,
        "Category": rec.category,
        "Emission": rec.value,
        "Emissions (kg CO₂)": rec.value if rec.category != "Offset" else -rec.value    
    } for rec in records])
    

    if df.empty:
        st.info("No emissions data available.")
    else:
        # --- Selection Inputs First ---
        st.subheader("Select Facility, Year, and Month")

        selected_facility = st.selectbox("Select Facility", ["Choose Facility"] + FACILITIES, key="summary_facility")
        selected_year = st.number_input("Select Year", min_value=2000, max_value=date.today().year, value=date.today().year, key="summary_year")
        selected_month = st.selectbox("Select Month", ["Choose Month"] + MONTHS, key="summary_month")

        if selected_facility != "Choose Facility" and selected_month != "Choose Month":
            # --- Filter dataset based on selection ---
            df_filtered = df[
                (df["Facility"] == selected_facility) &
                (df["Year"] == selected_year) &
                (df["Month"] == selected_month)
            ]

            if not df_filtered.empty:
                # --- Emissions Breakdown ---
                st.subheader("Emissions Breakdown")

                df_breakdown = df_filtered.groupby("Category")["Emission"].sum().reset_index()

                categories = ["Fossil Fuels", "Fugitive", "Electricity", "Water", "Waste", "Travel","Offset"]
                

                cols = st.columns(3)
                for idx, category in enumerate(categories):
                    value = df_breakdown[df_breakdown["Category"] == category]["Emission"].sum()
                    with cols[idx % 3]:
                        st.metric(
                             label=f"**{category}**",
                             value=f"{value:.2f} kg CO₂e"
                        )

                # Totals
                total_emission = df_filtered[df_filtered["Category"] != "Offset"]["Emission"].sum()
                total_offset= df_filtered[df_filtered["Category"] == "Offset"]["Emission"].sum()
                net_emission = total_emission - total_offset 

                st.divider()

                total_cols = st.columns(3)
                with total_cols[0]:
                    st.metric(
                        label="**Total Emission (before offset)**",
                        value=f"{total_emission:.2f} kg CO₂e"
                    )
                with total_cols[1]:
                    st.metric(
                        label="**Offset**",
                        value=f"{total_offset:.2f} kg CO₂e"
                    )

                with total_cols[2]:
                    st.metric(
                        label="**Net Emission**",
                        value=f"{net_emission:.2f} kg CO₂e",
                        delta=f"{'Reduction' if net_emission <=0 else 'Increase'}",
                        delta_color="inverse"
                    )
                st.divider()

                # --- Charts and Table ---
                # Bar Chart
                st.subheader("📊 Emission Breakdown (Bar Chart)")
                fig_bar = px.bar(
                    df_filtered,
                    x="Category",
                    y="Emission",
                    color="Category",
                    title=f"<b>Emission Breakdown for {selected_facility} - {selected_month} {selected_year}</b>",
                    text_auto='.2s'
                )
                fig_bar.update_layout(
                    plot_bgcolor="white",
                    yaxis_title="Emission (kg CO₂)"
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                # Pie Chart
                st.subheader("🥧 Emission Breakdown (Pie Chart)")
                fig_pie = px.pie(
                    df_filtered,
                    names="Category",
                    values="Emission",
                    title=f"<b>Emission Distribution for {selected_facility} - {selected_month} {selected_year}</b>",
                    hole=0.4
                )
                fig_pie.update_traces(textinfo="percent+label")
                st.plotly_chart(fig_pie, use_container_width=True)

                # Table
                st.subheader("📋 Emission Details Table")
                st.dataframe(df_filtered.style.format({"Emission": "{:.2f}"}))

            else:
                st.warning("No emissions data found for the selected facility, year, and month.")

        else:
            st.info("Please select a facility, year, and month to view emissions.")
    

elif menu == "Year and Facility Analysis":
    st.header("Year and Facility Analysis")
    
    # Fetch records
    records = db.query(Emission).filter(Emission.user_id==user.id).all()
    df = pd.DataFrame([{
        "Year": rec.date.year,
        "Month": rec.date.strftime("%B"),
        "Facility": rec.facility,
        "Category": rec.category,
        "Emission": rec.value
    } for rec in records])

    if df.empty:
        st.info("No emissions data to analyze.")
    else:
        # Common Month order
        month_order = ["January","February","March","April","May","June","July","August","September","October","November","December"]
        
        ### 1️⃣ Month-wise Evaluation
        st.subheader("📅 Month-wise Emission Evaluation")
        selected_facility = st.selectbox("Select Facility", FACILITIES)
        selected_year = st.number_input("Select Year", min_value=2000, max_value=date.today().year, value=date.today().year)

        df_monthwise = df[(df["Facility"] == selected_facility) & (df["Year"] == selected_year)]

        if not df_monthwise.empty:
            df_monthwise = df_monthwise.groupby("Month")["Emission"].sum().reindex(month_order).reset_index()
            
            fig_month = px.line(
                df_monthwise,
                x="Month",
                y="Emission",
                markers=True,
                title=f"<b>Month-wise Emission for {selected_facility} in {selected_year}</b>",
                line_shape="spline"
            )
            fig_month.update_layout(
                plot_bgcolor="white",
                xaxis=dict(categoryorder="array", categoryarray=month_order),
                yaxis_title="Emission (kg CO₂)"
            )
            st.plotly_chart(fig_month, use_container_width=True)
        else:
            st.warning("No emission data found for selected facility and year.")

        ### 2️⃣ Facility-wise Analysis
        st.subheader("🏢 Facility-wise Emission Analysis")
        facwise = df.groupby(["Year", "Facility", "Category"]).sum().reset_index()
        fig_fac = px.bar(
            facwise,
            x="Facility",
            y="Emission",
            color="Category",
            facet_col="Year",
            barmode="group",
            title="<b>Facility-wise Emission by Category (Multiple Years)</b>"
        )
        st.plotly_chart(fig_fac, use_container_width=True)

        ### 3️⃣ Comparison between Selected Years for a Facility
        st.subheader("🔄 Yearly Comparison for a Facility")

        col1, col2 = st.columns(2)
        with col1:
           compare_facility = st.selectbox("Facility to Compare", FACILITIES, key="compare_facility")

        with col2:
            available_years = sorted(df["Year"].unique())
            years_to_compare = st.multiselect(
                "Select Years to Compare",
                available_years,
                default=[available_years[0]] if available_years else []
            )

        if compare_facility and years_to_compare:
            df_compare = df[(df["Facility"] == compare_facility) & (df["Year"].isin(years_to_compare))]
    
            if not df_compare.empty:
                df_compare = df_compare.groupby(["Year", "Month"]).sum().reset_index()
                month_order = ["January","February","March","April","May","June","July","August","September","October","November","December"]
                df_compare["Month"] = pd.Categorical(df_compare["Month"], categories=month_order, ordered=True)
                df_compare = df_compare.sort_values("Month")

                fig_compare = px.line(
                    df_compare,
                    x="Month",
                    y="Emission",
                    color="Year",
                    markers=True,
                    title=f"<b>Emission Comparison for {compare_facility}: {', '.join(map(str, years_to_compare))}</b>",
                    line_shape="spline"
                )
                fig_compare.update_layout(
                    plot_bgcolor="white",
                    xaxis=dict(categoryorder="array", categoryarray=month_order),
                    yaxis_title="Emission (kg CO₂)"
                )
                st.plotly_chart(fig_compare, use_container_width=True)
            else:
                st.warning("No emission data found for selected years and facility.")

           

elif menu == "Download":
    st.header("Download Reports")
    # Prepare CSV of all data
    records = db.query(Emission).filter(Emission.user_id==user.id).all()
    df_all = pd.DataFrame([{"Year": rec.date.year, "Month": rec.date.month, "Facility": rec.facility,
                            "Category": rec.category, "Emission": rec.value} for rec in records])
    csv = df_all.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", data=csv, file_name="emissions.csv", mime="text/csv")
    # Generate charts and zip
    if not df_all.empty:
        # Bar and pie
        summary = df_all.groupby("Category")["Emission"].sum().reset_index()
        fig_bar = px.bar(summary, x="Category", y="Emission", title="Emissions by Category", color="Category", template="plotly_white")
        fig_pie = px.pie(summary, values="Emission", names="Category", title="Emissions Distribution", hole=0.4)
        # Monthly trend
        df_all["MonthName"] = df_all["Month"].apply(lambda m: ["January","February","March","April","May","June","July","August","September","October","November","December"][m-1])
        monthly = df_all.groupby(["Year","MonthName"])["Emission"].sum().reset_index()
        fig1 = px.line(monthly, x="MonthName", y="Emission", color="Year", markers=True, title="Monthly Emission Trend")
        fig1.update_xaxes(categoryorder="array", categoryarray=["January","February","March","April","May","June","July","August","September","October","November","December"])
        # Create ZIP
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr("emissions.csv", csv.decode('utf-8'))
            charts = {"bar_chart.png": fig_bar, "pie_chart.png": fig_pie, "monthly_trend.png": fig1}
            for name, fig in charts.items():
                img_buf = pio.to_image(fig, format='png')
                z.writestr(name, img_buf)
        buf.seek(0)
        st.download_button("📥 Download All Charts and Data (ZIP)", data=buf.getvalue(), file_name="reports.zip", mime="application/zip")
    else:
        st.info("No emissions data to download.")

elif menu == "Offset Contribution":
    st.header("Offset Contribution")
    col1, = st.columns(1)
    with col1:
        trees_count7 = st.number_input("Number of Trees", min_value=0, format="%d", key="offset_trees_count"
)
        soil_area7 = st.number_input("Area Covered Under Soil (m²)", min_value=0.0, format="%.2f", key="offset_soil_area")
        grass_area7 = st.number_input("Area Covered Under Grass (m²)", min_value=0.0, format="%.2f", key="offset_grass_area"
)
        water_consum7 = st.number_input("Area Covered Under Water (m²)", min_value=0.0, format="%.2f", key="offset_water_area")

    tree_offset = trees_count7 * of_e_f["tree"]
    soil_offset = soil_area7 * of_e_f["soil"]
    grass_offset = grass_area7 * of_e_f["grass"]
    water_offset = water_consum7 * of_e_f["water"]
    total_offset = tree_offset + soil_offset + grass_offset + water_offset
    # Display
    st.subheader("Offset Contribution Summary")
    st.markdown(f"""
   🌳 You planted **{trees_count7} trees**, used:
    - **{soil_area7:.2f} m^2** for tree planting
    - **{grass_area7:.2f} m^2** covered in grass
    - **{water_consum7:.2f} m^2** covered in water

    ✅ This helped you reduce approximately:
    - **{tree_offset:.2f} kg CO₂/year** via trees
    - **{soil_offset:.2f} kg CO₂/year** from tree-planted land
    - **{grass_offset:.2f} kg CO₂/year** from grassy land
    - **{water_offset:.2f} kg CO₂/year** from water-covered area

    💚 **Total Estimated Offset:** **{total_offset:.2f} kg CO₂/year**
     """)

    
elif menu == "Manage Database":
    st.header("🛠 Manage Database (Admin Only)")

    # 1. Overall Emission Record Stats
    total_records = db.query(Emission).count()
    zero_emission_count = db.query(Emission).filter(Emission.value == 0).count()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("📋 Total Emission Records", total_records)
    with col2:
        st.metric("🚫 Zero Emission Records", zero_emission_count)

    st.divider()

    # 2. Registered Users
    total_users = db.query(User).count()
    st.metric("👥 Total Registered Users", total_users)

    st.divider()

    # 3. User-wise Emission Entry Count
    st.subheader("👤 Entries Per User")
    user_emission_counts = db.query(User.name, func.count(Emission.id))\
                             .join(Emission, Emission.user_id == User.id)\
                             .group_by(User.name)\
                             .all()

    if user_emission_counts:
        df_user_emissions = pd.DataFrame(user_emission_counts, columns=["Username", "Emission Entries"])
        st.dataframe(df_user_emissions)
    else:
        st.info("No user emission entries yet.")

    st.divider()

    # 4. Clean Zero Emission Records
    st.subheader("🧹 Clean Zero Emission Records")

    if st.button("Delete Zero Emission Records"):
        if zero_emission_count > 0:
            zero_records = db.query(Emission).filter(Emission.value == 0).all()
            for record in zero_records:
                db.delete(record)
            db.commit()
            st.success(f"✅ Successfully deleted {zero_emission_count} zero-emission record(s)!")
        else:
            st.info("No zero-emission records found.")

    st.divider()

    # 5. Backup Download
    st.subheader("📥 Backup Emission Data")

    records = db.query(Emission).all()
    if records:
        df_backup = pd.DataFrame([{
            "Year": rec.date.year,
            "Month": rec.date.strftime("%B"),
            "Facility": rec.facility,
            "Category": rec.category,
            "Emission (kg CO₂)": rec.value
        } for rec in records])

        backup_csv = df_backup.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Download Emission Backup (CSV)",
            data=backup_csv,
            file_name="emission_backup.csv",
            mime="text/csv"
        )
    else:
        st.warning("No emission data available to backup.")

    st.divider()
 
    st.subheader("📥 Backup Users List")

    users = db.query(User).all()

    if users:
        df_users = pd.DataFrame([{
            "User ID": u.id,
            "Username": u.name,
            "Email": getattr(u, 'email', 'N/A')  # if your User model has email
        } for u in users])

        users_csv = df_users.to_csv(index=False).encode('utf-8')

        st.download_button(
            label="📄 Download Users Backup (CSV)",
            data=users_csv,
            file_name="users_backup.csv",
            mime="text/csv"
        )
    else:
        st.warning("No registered users found.")    
    # 6. Emission Category Chart
    st.subheader("📊 Emission Records by Category")
    if records:
        df_summary = pd.DataFrame([rec.category for rec in records], columns=["Category"])
        category_counts = df_summary["Category"].value_counts()
        st.bar_chart(category_counts)
    else:
        st.info("No emission data available for category summary.")
