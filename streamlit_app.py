import streamlit as st
import pandas as pd
import numpy as np
import html

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

# Function to get color for percentage values
def get_percentage_color(val):
    """Get background color for percentage values (0-100 range)"""
    if pd.isna(val) or val == 0:
        return '#f0f0f0'
    if val >= 50:
        return '#90EE90'  # Light green
    elif val >= 25:
        return '#FFE4B5'  # Light yellow
    else:
        return '#FFB6C1'  # Light pink

# Function to create HTML table with images and color formatting
def create_html_table(df, show_images=True):
    """Create HTML table with embedded images and color-coded percentage columns"""
    html = """
    <style>
        .dataframe-table {
            width: 100%;
            border-collapse: collapse;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }
        .dataframe-table th {
            background-color: #f0f2f6;
            padding: 8px;
            text-align: left;
            border-bottom: 2px solid #ddd;
            font-weight: bold;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .dataframe-table td {
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }
        .dataframe-table tr:hover {
            background-color: #f5f5f5;
        }
        .dataframe-table img {
            border-radius: 3px;
            display: block;
        }
    </style>
    <table class="dataframe-table">
        <thead>
            <tr>
    """
    
    # Add header row
    columns_to_show = ['Player', 'Player Image', 'Team', 'Team Image', 'Pos', 
                       'Total Points', 'Round Points', 'Global Own %', 
                       'League Own %', 'League Start %', 'League Cpt %']
    
    for col in columns_to_show:
        if col in df.columns:
            if col in ['Player Image', 'Team Image'] and not show_images:
                continue
            html += f"<th>{col}</th>"
    
    html += """
            </tr>
        </thead>
        <tbody>
    """
    
    # Add data rows
    for idx, row in df.iterrows():
        html += "<tr>"
        for col in columns_to_show:
            if col in df.columns:
                if col in ['Player Image', 'Team Image'] and not show_images:
                    continue
                
                val = row[col]
                
                # Handle image columns
                if col == 'Player Image' or col == 'Team Image':
                    if show_images and pd.notna(val) and val != '':
                        img_width = 50 if col == 'Player Image' else 30
                        html += f'<td><img src="{val}" width="{img_width}" alt="{col}" onerror="this.style.display=\'none\'"></td>'
                    else:
                        html += '<td></td>'
                # Handle percentage columns with color coding
                elif col in ['League Own %', 'League Start %', 'League Cpt %']:
                    bg_color = get_percentage_color(val)
                    formatted_val = f"{val:.1f}%" if pd.notna(val) else ""
                    html += f'<td style="background-color: {bg_color}">{formatted_val}</td>'
                # Handle numeric columns
                elif col in ['Total Points', 'Round Points', 'Global Own %']:
                    if pd.notna(val) and val != '':
                        if col == 'Global Own %':
                            formatted_val = f"{val:.1f}%"
                        else:
                            formatted_val = f"{val:.1f}"
                        html += f'<td>{formatted_val}</td>'
                    else:
                        html += '<td></td>'
                # Handle text columns
                else:
                    display_val = html.escape(str(val)) if pd.notna(val) else ""
                    html += f'<td>{display_val}</td>'
        
        html += "</tr>"
    
    html += """
        </tbody>
    </table>
    """
    return html

# Add toggle for showing images
show_images = st.sidebar.checkbox("Show Images", value=True)

# Display the HTML table
html_table = create_html_table(filtered_df, show_images=show_images)
st.markdown(html_table, unsafe_allow_html=True)

# Additional info
st.markdown("---")
st.caption(f"Showing {len(filtered_df)} of {len(df)} players")