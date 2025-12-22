import streamlit as st
import pandas as pd
import numpy as np

# Page configuration
st.set_page_config(
    page_title="AFCON Fantasy Data",
    page_icon="⚽",
    layout="wide"
)

# Title
st.title("⚽ AFCON Fantasy Data")
st.markdown("---")

round = 1

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv(f"data/afcon_fantasy_market_{round}_with_league_ownership.csv")
    # Convert percentage columns to numeric, handling empty strings
    percentage_cols = ['League Own %', 'League Start %', 'League Cpt %']
    for col in percentage_cols:
        df[col] = df[col].fillna(0)
        df[col] = df[col].round(2)
    # Multiply by 100 to convert from decimal to percentage
    for col in percentage_cols:
        df[col] = df[col] * 100
    
    return df

df = load_data()

# Sidebar filters
st.sidebar.header("🔍 Filters")

# Position filter
positions = ['All'] + sorted(df['Pos'].dropna().unique().tolist())
selected_position = st.sidebar.selectbox("Position", positions)

# Team filter
teams = ['All'] + sorted(df['Team'].dropna().unique().tolist())
selected_team = st.sidebar.selectbox("Team", teams)

# Apply filters
filtered_df = df.copy()
if selected_position != 'All':
    filtered_df = filtered_df[filtered_df['Pos'] == selected_position]
if selected_team != 'All':
    filtered_df = filtered_df[filtered_df['Team'] == selected_team]

# Display stats
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Players", len(filtered_df))
col2.metric("Unique Teams", filtered_df['Team'].nunique())
col3.metric("Unique Positions", filtered_df['Pos'].nunique())
col4.metric("Avg League Own %", f"{filtered_df['League Own %'].mean():.1f}%")

st.markdown("---")

# 

# Configure column display
column_config = {
    "Player": st.column_config.TextColumn("Player", width="medium"),
    "Player Image": st.column_config.ImageColumn("Player Image", width="small"),
    "Team": st.column_config.TextColumn("Team", width="small"),
    "Team Image": st.column_config.ImageColumn("Team Image", width="small"),
    "Pos": st.column_config.TextColumn("Position", width="small"),
    "Total Points": st.column_config.NumberColumn("Total Points", format="%.1f"),
    "Round Points": st.column_config.NumberColumn("Round Points", format="%.1f"),
    "Global Own %": st.column_config.NumberColumn("Global Own %", format="%.1f%%"),
    "League Own %": st.column_config.NumberColumn("League Own %", format="%.1f%%"),
    "League Start %": st.column_config.NumberColumn("League Start %", format="%.1f%%"),
    "League Cpt %": st.column_config.NumberColumn("League Cpt %", format="%.1f%%"),
}

# Prepare dataframe for display
display_df = filtered_df.copy()

# Create a styled dataframe with color formatting
def color_percentage(val):
    """Color code percentage values (now in 0-100 range)"""
    if pd.isna(val) or val == 0:
        return 'background-color: #f0f0f0'
    # Green for high values (>=50%), yellow for medium (25-50%), pink for low (<25%)
    if val >= 50:
        return 'background-color: #90EE90'  # Light green
    elif val >= 25:
        return 'background-color: #FFE4B5'  # Light yellow
    else:
        return 'background-color: #FFB6C1'  # Light pink

# Apply color formatting to percentage columns
styled_df = display_df.style.applymap(
    color_percentage,
    subset=['League Own %', 'League Start %', 'League Cpt %']
)

# Display the dataframe
# Try with column_config first (for images), fallback to styled if needed
st.dataframe(
    filtered_df,
    column_config=column_config,
    use_container_width=True,
    hide_index=True,
    height=600
)

import requests
from PIL import Image
from io import BytesIO

st.markdown(
    '<img src="https://img.sofascore.com/api/v1/player/914309/image" width="100" style="border-radius: 5px;">',
    unsafe_allow_html=True
)

url = "https://img.sofascore.com/api/v1/player/914309/image"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.sofascore.com/',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'image',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'cross-site'
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    st.write(f"Status Code: {response.status_code}")
    st.write(f"Content Type: {response.headers.get('Content-Type')}")
    if response.status_code == 200:
        img = Image.open(BytesIO(response.content))
        st.image(img)
    else:
        st.error(f"Failed with status {response.status_code}")
except Exception as e:
    st.error(f"Error: {str(e)}")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.sofascore.com/',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
})

url = "https://img.sofascore.com/api/v1/player/914309/image"
try:
    response = session.get(url, timeout=10)
    if response.status_code == 200:
        img = Image.open(BytesIO(response.content))
        st.image(img)
    else:
        st.error(f"Status: {response.status_code}")
except Exception as e:
    st.error(f"Error: {str(e)}")