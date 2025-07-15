import streamlit as st
from core_logic.data_loader import load_postal_data
from core_logic.address_parser import parse_address
from core_logic.matching_engine import find_dpo_and_pin
import pandas as pd
import re # For latitude/longitude validation

# --- Page Configuration ---
st.set_page_config(
    page_title="Interactive DPO Finder",
    page_icon="📧",
    layout="wide"
)

# --- Initialize Session State ---
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'quick_suggestions_df' not in st.session_state: # Full matched DF for current query
    st.session_state.quick_suggestions_df = pd.DataFrame()
if 'num_quick_suggestions_to_show' not in st.session_state:
    st.session_state.num_quick_suggestions_to_show = 5 # Initial number
if 'selected_office_details' not in st.session_state:
    st.session_state.selected_office_details = None
if 'deep_search_result' not in st.session_state:
    st.session_state.deep_search_result = None

# --- Data Loading ---
@st.cache_data
def cached_load_data():
    df = load_postal_data(file_path="data/postal_data.csv")
    return df

postal_data_df = cached_load_data()

if postal_data_df is None:
    st.error("CRITICAL ERROR: Postal data could not be loaded. Application cannot run.")
    st.stop()

# --- Helper Functions for Callbacks & Logic ---
def is_valid_lat_long(lat, lon):
    """Basic validation for latitude and longitude strings."""
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
            return True
    except (ValueError, TypeError):
        return False
    return False

def get_google_maps_link(lat, lon):
    if is_valid_lat_long(lat, lon):
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    return None

def update_quick_suggestions():
    """Updates the full set of quick_suggestions_df based on search_query."""
    query = st.session_state.search_query
    st.session_state.selected_office_details = None
    st.session_state.deep_search_result = None
    st.session_state.num_quick_suggestions_to_show = 5 # Reset display count

    if query and len(query) >= 2: # Reduced min length for quicker feedback
        parsed = parse_address(query)
        suggestions_list = []

        # Simplified quick suggestion logic:
        # 1. If PIN is parsed, prioritize matches on PIN.
        # 2. Then, match keywords against 'SearchableText'.
        # This is different from the deep search which has more complex scoring.
        
        temp_df = postal_data_df.copy() # Work on a copy

        if parsed['pincode']:
            pin_matches = temp_df[temp_df['PINCode'] == parsed['pincode']]
            suggestions_list.append(pin_matches)

        if parsed['locality_keywords']:
            valid_keywords = [kw for kw in parsed['locality_keywords'] if kw]
            if valid_keywords:
                try:
                    # Using 'SearchableText' which should be pre-processed by data_loader
                    pattern = '|'.join([re.escape(kw) for kw in valid_keywords]) # Escape keywords for regex
                    keyword_matches = temp_df[temp_df['SearchableText'].str.contains(pattern, case=False, na=False, regex=True)]
                    suggestions_list.append(keyword_matches)
                except Exception as e:
                    st.error(f"Error during quick search pattern matching: {e}")


        if suggestions_list:
            combined_suggestions = pd.concat(suggestions_list).drop_duplicates(subset=['OfficeName_lower'])
            # Select display columns
            display_cols = ['OfficeName_for_display', 'PINCode', 'District', 'State', 'OfficeName_lower', 'Latitude', 'Longitude']
            st.session_state.quick_suggestions_df = combined_suggestions[display_cols]
        else:
            st.session_state.quick_suggestions_df = pd.DataFrame()
    else:
        st.session_state.quick_suggestions_df = pd.DataFrame()

def view_office_details(office_name_lower):
    if office_name_lower and not postal_data_df.empty:
        detail_series = postal_data_df[postal_data_df['OfficeName_lower'] == office_name_lower]
        if not detail_series.empty:
            st.session_state.selected_office_details = detail_series.iloc[0]
        else:
            st.session_state.selected_office_details = None
    else:
        st.session_state.selected_office_details = None

def clear_views_and_reset_quick_suggestions_count():
    st.session_state.selected_office_details = None
    st.session_state.deep_search_result = None
    st.session_state.num_quick_suggestions_to_show = 5 # Reset for next search

def perform_deep_search():
    query = st.session_state.search_query
    clear_views_and_reset_quick_suggestions_count() # Clear other views

    if query:
        with st.spinner("Performing deep search..."):
            parsed_components = parse_address(query)
            suggestion_result = find_dpo_and_pin(parsed_components, postal_data_df)
            st.session_state.deep_search_result = suggestion_result
    else:
        st.session_state.deep_search_result = None

def load_more_suggestions():
    st.session_state.num_quick_suggestions_to_show += 5


# --- UI Layout ---
st.title("📬 Interactive DPO Finder")
st.caption("Type an address, PIN, or locality for live suggestions. Use sidebar for Deep Search.")

# --- Sidebar ---
with st.sidebar:
    st.subheader("Actions & Info")
    if st.button("🚀 Deep Search Full Address", on_click=perform_deep_search, help="Uses the full matching logic for the entered query."):
        pass
    st.markdown("---")
    st.caption(f"Built by [Your Name/Group]")
    if postal_data_df is not None and st.checkbox("Show sample of loaded postal data", key="cb_sample_data"):
        st.markdown("#### Sample Data (`data_loader` output)")
        st.dataframe(postal_data_df[['PINCode', 'OfficeName_for_display', 'Delivery', 'SearchableText']].head(3), height=150)

# --- Main Content Area ---
st.text_input(
    "Enter Address, Pincode, or Locality:",
    key='search_query',
    on_change=update_quick_suggestions, # Triggers update of the full suggestion list
    placeholder="e.g., Indiranagar Bangalore, or 560038"
)

# --- Display Logic ---
if st.session_state.selected_office_details is not None:
    # --- DETAILED VIEW ---
    details = st.session_state.selected_office_details
    st.subheader(f"Details for: {details.get('OfficeName_for_display', 'N/A')}")

    col1, col2 = st.columns([0.6, 0.4]) # Adjust ratios as needed

    with col1:
        with st.container(border=True):
            st.markdown("##### 🏢 Office Information")
            st.text(f"Office Name: {details.get('OfficeName_for_display', 'N/A')}")
            st.text(f"PIN Code: {details.get('PINCode', 'N/A')}")
            st.text(f"Office Type: {str(details.get('OfficeType', 'N/A')).upper()}") # BO, SO, HO
            delivery_status = str(details.get('Delivery', 'N/A')).title()
            st.markdown(f"Delivery Status: **{delivery_status}**")

        with st.container(border=True):
            st.markdown("##### 🌍 Geographical Hierarchy")
            st.text(f"District: {details.get('District', 'N/A').title()}")
            st.text(f"Division: {details.get('DivisionName', 'N/A').title()}")
            st.text(f"Region: {details.get('RegionName', 'N/A').title()}")
            st.text(f"Circle: {details.get('CircleName', 'N/A').title()}")
            st.text(f"State: {details.get('State', 'N/A').title()}")

    with col2:
        with st.container(border=True):
            st.markdown("##### 📍 Location Coordinates")
            lat = details.get('Latitude', 'N/A')
            lon = details.get('Longitude', 'N/A')
            st.text(f"Latitude: {lat}")
            st.text(f"Longitude: {lon}")
            maps_link = get_google_maps_link(lat, lon)
            if maps_link:
                st.markdown(f"[View on Google Maps]({maps_link})", unsafe_allow_html=True)
            else:
                st.caption("Coordinates not available or invalid for map link.")
        
        # You can add other details or actions in col2 if needed

    st.button("⬅️ Back / New Search", on_click=clear_views_and_reset_quick_suggestions_count)


elif st.session_state.deep_search_result is not None:
    # --- DEEP SEARCH RESULT ---
    st.subheader("💡 Deep Search Suggestion:")
    # ... (Your existing deep search display logic - keep it as it was good) ...
    suggestion = st.session_state.deep_search_result
    status = suggestion.get('status', 'error').lower()
    message = suggestion.get('message', 'No specific message.')
    pin_code = suggestion.get('pin', 'N/A')
    dpo_name = suggestion.get('dpo', 'N/A') 
    match_score = suggestion.get('score')

    if 'success' in status:
        st.success(f"✅ **Status: {status.replace('_', ' ').title()}**")
        col1_ds, col2_ds = st.columns(2)
        with col1_ds: st.metric(label="Suggested PIN Code", value=pin_code)
        with col2_ds: st.metric(label="Suggested DPO", value=dpo_name)
        if match_score is not None:
            st.metric(label="Match Score", value=f"{match_score:.2f}")
        st.info(f"ℹ️ Details: {message}")
    elif status.startswith('partial_match'):
        st.warning(f"⚠️ **Status: {status.replace('_', ' ').title()}**")
        col1_ds, col2_ds = st.columns(2)
        with col1_ds: st.metric(label="Input PIN (if any)", value=st.session_state.deep_search_result.get('parsed_pincode', 'N/A')) # Assuming find_dpo_and_pin might return this
        with col2_ds: st.metric(label="Suggested PIN", value=pin_code)
        st.text(f"Suggested DPO: {dpo_name}")
        if match_score is not None: st.metric(label="Match Score", value=f"{match_score:.2f}")
        st.info(f"ℹ️ Details: {message}")
    elif status == 'not_found':
        st.error(f"❌ **Status: Not Found**")
        st.write(f"ℹ️ Details: {message}")
    else:
        st.error(f"🚨 **Status: {status.title()}**")
        st.write(f"ℹ️ Details: {message}")

    with st.expander("Show Raw Deep Search Data"):
        st.json(suggestion)
    st.button("⬅️ New Search", on_click=clear_views_and_reset_quick_suggestions_count)


elif not st.session_state.quick_suggestions_df.empty:
    # --- QUICK SUGGESTIONS VIEW ---
    st.subheader("Quick Suggestions:")
    
    df_to_show = st.session_state.quick_suggestions_df.head(st.session_state.num_quick_suggestions_to_show)
    
    # Headers
    cols_def = [0.1, 0.4, 0.2, 0.3] # Eye, Office, PIN, District/State
    header_cols = st.columns(cols_def)
    header_cols[0].caption("View")
    header_cols[1].caption("Office Name")
    header_cols[2].caption("PIN Code")
    header_cols[3].caption("District, State")
    st.markdown("---") # Visual separator

    for index, row in df_to_show.iterrows():
        cols = st.columns(cols_def)
        button_key = f"view_{row['OfficeName_lower']}_{index}" # Unique key for button
        
        if cols[0].button("👁️", key=button_key, on_click=view_office_details, args=(row['OfficeName_lower'],), help="View full details"):
            pass # on_click handles state change & rerun
        
        cols[1].write(row['OfficeName_for_display'])
        cols[2].write(row['PINCode'])
        cols[3].write(f"{str(row['District']).title()}, {str(row['State']).title()}")
        # Display Lat/Long briefly or link to map directly if simple enough
        lat_qs, lon_qs = row.get('Latitude', 'N/A'), row.get('Longitude', 'N/A')
        maps_link_qs = get_google_maps_link(lat_qs, lon_qs)
        if maps_link_qs:
            cols[3].markdown(f"<small>[Map]({maps_link_qs})</small>", unsafe_allow_html=True)

    # "Load More" button
    if len(st.session_state.quick_suggestions_df) > st.session_state.num_quick_suggestions_to_show:
        st.button("Load More Suggestions", on_click=load_more_suggestions)
    
    st.caption(f"Showing {len(df_to_show)} of {len(st.session_state.quick_suggestions_df)} potential quick suggestions.")

else:
    if st.session_state.search_query and len(st.session_state.search_query) >= 2:
        st.info("No quick suggestions found. Try refining your query or use 'Deep Search'.")
    else:
        st.info("Type at least 2 characters to see live suggestions, or use 'Deep Search'.")