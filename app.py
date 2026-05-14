import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Product Ratings Analytics", layout="wide")

# Helper function to convert dataframe to CSV for download
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

@st.cache_data
def load_data():
    file_path = "Data.csv"
    encodings_to_try = ['utf-8', 'latin1', 'cp1252']
    df = None
    
    for encoding in encodings_to_try:
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            break  # Stop trying if successful
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            return None, "Data.csv not found in the current directory."
    
    if df is None:
        return None, "Failed to read the file. Please check the file format and encoding."

    required_cols = [
        "Product ID", "Group ID", "Product name", "Category name", "Sub-cat name",
        "Product type", "Brand name", "FAD", "MRP", "LID", "5 stars", "4 stars",
        "3 stars", "2 stars", "1 star", "Total Rating count", "Average Rating"
    ]
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return None, f"Missing required columns: {', '.join(missing_cols)}"

    # Parse dates explicitly expecting DD-MM-YYYY format.
    # We extract the first 10 characters to safely handle and ignore any trailing timestamp data (like HH:MM:SS)
    df['FAD'] = pd.to_datetime(df['FAD'].astype(str).str.strip().str[:10], format='%d-%m-%Y', errors='coerce')
    df['LID'] = pd.to_datetime(df['LID'].astype(str).str.strip().str[:10], format='%d-%m-%Y', errors='coerce')

    # Handle missing Group IDs: Replace empty strings/spaces with NaN, then fill with Product ID
    df['Group ID'] = df['Group ID'].replace(r'^\s*$', np.nan, regex=True)
    df['Group ID'] = df['Group ID'].fillna(df['Product ID'])

    # Handle missing LIDs: Fill missing 'Last Inward Date' with 'First Active Date'
    df['LID'] = df['LID'].fillna(df['FAD'])
    
    # Fill NaN values for rating counts with 0
    rating_cols = ['5 stars', '4 stars', '3 stars', '2 stars', '1 star', 'Total Rating count']
    df[rating_cols] = df[rating_cols].fillna(0)

    return df, None

def main():
    st.title("Product Ratings Analytics Dashboard")
    st.markdown("Analyze product performance, categorize rating trends, and identify areas for improvement.")

    df, error = load_data()

    if error:
        st.error(error)
        st.stop()

    # --- Sidebar Filters ---
    st.sidebar.header("Filter Data")

    # Category Filter
    categories = ["All"] + list(df['Category name'].dropna().unique())
    selected_category = st.sidebar.selectbox("Category", categories)
    if selected_category != "All":
        df = df[df['Category name'] == selected_category]

    # Cascading Sub-category Filter
    if 'Sub-cat name' in df.columns:
        subcats = ["All"] + list(df['Sub-cat name'].dropna().unique())
        selected_subcat = st.sidebar.selectbox("Sub-category", subcats)
        if selected_subcat != "All":
            df = df[df['Sub-cat name'] == selected_subcat]

    # Brand Filter
    if 'Brand name' in df.columns:
        brands = ["All"] + list(df['Brand name'].dropna().unique())
        selected_brand = st.sidebar.selectbox("Brand", brands)
        if selected_brand != "All":
            df = df[df['Brand name'] == selected_brand]

    # Min Ratings Filter with Slider and Number Input Sync
    max_total_ratings = int(df['Total Rating count'].max()) if not df['Total Rating count'].empty else 0
    
    if 'min_ratings' not in st.session_state:
        st.session_state.min_ratings = 0

    def sync_slider():
        st.session_state.min_ratings = st.session_state.num_input
        
    def sync_num():
        st.session_state.min_ratings = st.session_state.slider_input

    st.sidebar.markdown("**Min Total Ratings Filter**")
    
    col_sl, col_num = st.sidebar.columns([2, 1])
    with col_sl:
        st.slider(
            "Min Ratings Slider", 
            min_value=0, 
            max_value=max_total_ratings, 
            key="slider_input", 
            value=st.session_state.min_ratings, 
            on_change=sync_num, 
            label_visibility="collapsed"
        )
    with col_num:
        st.number_input(
            "Min Ratings Input", 
            min_value=0, 
            max_value=max_total_ratings, 
            key="num_input", 
            value=st.session_state.min_ratings, 
            on_change=sync_slider, 
            label_visibility="collapsed"
        )
    
    # Apply the rating threshold filter
    df_filtered = df[df['Total Rating count'] >= st.session_state.min_ratings].copy()

    if df_filtered.empty:
        st.warning("No products match the current filter criteria.")
        st.stop()

    # --- Top Level Metrics ---
    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.metric("Total Products", f"{len(df_filtered):,}")
    with kpi2:
        st.metric("Total Ratings Volume", f"{int(df_filtered['Total Rating count'].sum()):,}")
    with kpi3:
        avg_rating_overall = df_filtered['Average Rating'].mean()
        st.metric("Global Average Rating", f"{avg_rating_overall:.2f}" if pd.notna(avg_rating_overall) else "N/A")
    with kpi4:
        avg_mrp = df_filtered['MRP'].mean()
        st.metric("Average MRP", f"?{avg_mrp:.2f}" if pd.notna(avg_mrp) else "N/A")

    st.markdown("---")

    # --- Overall Rating Distribution ---
    st.subheader("Global Rating Distribution")
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        total_stars = {
            '5 Stars': df_filtered['5 stars'].sum(),
            '4 Stars': df_filtered['4 stars'].sum(),
            '3 Stars': df_filtered['3 stars'].sum(),
            '2 Stars': df_filtered['2 stars'].sum(),
            '1 Star': df_filtered['1 star'].sum()
        }
        
        fig_dist = go.Figure(data=[go.Bar(
            x=list(total_stars.keys()),
            y=list(total_stars.values()),
            text=list(total_stars.values()),
            textposition='auto',
            marker_color=['#2ecc71', '#27ae60', '#f1c40f', '#e67e22', '#e74c3c']
        )])
        fig_dist.update_layout(title_text="Total Ratings Breakup", xaxis_title="Star Rating", yaxis_title="Total Volume")
        st.plotly_chart(fig_dist, use_container_width=True)

    with col_dist2:
        # Average Rating Distribution Chart
        fig_avg_dist = px.histogram(
            df_filtered, 
            x="Average Rating", 
            nbins=20, 
            title="Average Rating Distribution (Per Product)",
            color_discrete_sequence=['#3498db']
        )
        fig_avg_dist.update_layout(xaxis_title="Average Rating", yaxis_title="Number of Products")
        st.plotly_chart(fig_avg_dist, use_container_width=True)

    # --- Categorical Deep Dive ---
    st.header("Categorical Deep Dive")
    st.markdown("Analyze metrics across different hierarchical levels. **Note:** When evaluating by *Product type*, hover over the bars to see the corresponding Sub-category.")
    
    deep_dive_col = st.selectbox(
        "Select Dimension for Deep Dive", 
        ["Category name", "Sub-cat name", "Product type", "Brand name"]
    )
    
    # Group by selected dimension; add Sub-cat to Product type grouping for hover context
    if deep_dive_col == "Product type":
        agg_df = df_filtered.groupby(['Sub-cat name', 'Product type']).agg(
            Avg_Rating=('Average Rating', 'mean'),
            Total_Volume=('Total Rating count', 'sum')
        ).reset_index()
        hover_cols = ['Sub-cat name']
        y_col = 'Product type'
    else:
        agg_df = df_filtered.groupby(deep_dive_col).agg(
            Avg_Rating=('Average Rating', 'mean'),
            Total_Volume=('Total Rating count', 'sum')
        ).reset_index()
        hover_cols = None
        y_col = deep_dive_col
        
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        top_avg = agg_df.sort_values('Avg_Rating', ascending=True).tail(10)
        fig_avg = px.bar(top_avg, x='Avg_Rating', y=y_col, orientation='h',
                         title=f"Top 10 {deep_dive_col}s by Avg Rating",
                         hover_data=hover_cols, color='Avg_Rating', color_continuous_scale='Viridis')
        fig_avg.update_layout(yaxis_title="")
        st.plotly_chart(fig_avg, use_container_width=True)
        
    with col_chart2:
        top_vol = agg_df.sort_values('Total_Volume', ascending=True).tail(10)
        fig_vol = px.bar(top_vol, x='Total_Volume', y=y_col, orientation='h',
                         title=f"Top 10 {deep_dive_col}s by Rating Volume",
                         hover_data=hover_cols, color='Total_Volume', color_continuous_scale='Blues')
        fig_vol.update_layout(yaxis_title="")
        st.plotly_chart(fig_vol, use_container_width=True)

    # --- Actionable Insights ---
    st.header("Actionable Insights")
    
    tab_att, tab_pol = st.tabs(["Products Needing Attention", "High Disparity (Love/Hate) Products"])
    
    with tab_att:
        st.subheader("Critical Products (High Volume, Low Rating)")
        st.write("Products with more than 50 ratings and an average rating below 3.0.")
        critical = df_filtered[(df_filtered['Total Rating count'] >= 50) & (df_filtered['Average Rating'] < 3.0)]
        # Sort by Total Volume
        critical = critical.sort_values(by='Total Rating count', ascending=False)
        
        if not critical.empty:
            st.dataframe(critical[['Product ID', 'Product name', 'Brand name', 'Average Rating', 'Total Rating count', '1 star', 'MRP']].head(20), use_container_width=True)
        else:
            st.success("No critical products found under these criteria!")

    with tab_pol:
        st.subheader("High Disparity (Polarizing) Products")
        st.write("Products that have a high concentration of both 5-star and 1-star ratings (indicates 'Love it or Hate it' scenarios or potential quality control issues on certain batches).")
        
        # Calculate a disparity score based only on explicit star counts to ignore empty/invalid total ratings
        actual_total_stars = df_filtered[['5 stars', '4 stars', '3 stars', '2 stars', '1 star']].sum(axis=1)
        df_filtered['Polarization Score'] = np.where(
            actual_total_stars > 0,
            (df_filtered['5 stars'] + df_filtered['1 star']) / actual_total_stars,
            0
        )
        
        polarizing = df_filtered[(df_filtered['Total Rating count'] > 30) & (df_filtered['Polarization Score'] > 0.8) & (df_filtered['1 star'] > 5) & (df_filtered['5 stars'] > 5)]
        # Sort by Total Volume
        polarizing = polarizing.sort_values(by='Total Rating count', ascending=False)
        
        if not polarizing.empty:
            st.dataframe(polarizing[['Product ID', 'Product name', 'Brand name', '5 stars', '1 star', 'Total Rating count', 'Polarization Score']].head(20), use_container_width=True)
        else:
            st.info("No highly polarizing products found with the current filters.")

    # --- Rating Velocity Analysis ---
    st.markdown("---")
    st.header("Rating Velocity Analysis")
    st.markdown("Understand the momentum of your products by analyzing the rate at which they accumulate ratings over their lifetime (based on First Active Date).")
    
    # Calculate Age and Velocity
    current_date = datetime.now()
    
    # Calculate Age in days. Will be NaN if FAD is missing/unparsable.
    df_filtered['Age_Days'] = (current_date - df_filtered['FAD']).dt.days
    
    # Clip valid ages to a minimum of 1 to prevent division by zero for items launched today.
    df_filtered['Age_Days'] = df_filtered['Age_Days'].clip(lower=1) 
    
    # Velocity: Ratings per 30 days (will naturally be NaN for items with missing FAD)
    df_filtered['Ratings_Per_Month'] = (df_filtered['Total Rating count'] / df_filtered['Age_Days']) * 30
    
    col_vel_chart1, col_vel_chart2 = st.columns(2)
    
    with col_vel_chart1:
        # Scatter plot: Age vs Total Ratings
        fig_vel_scatter = px.scatter(
            df_filtered, 
            x="Age_Days", 
            y="Total Rating count", 
            color="Average Rating",
            hover_data=["Product name", "Brand name", "Ratings_Per_Month"],
            title="Product Age vs. Total Ratings Accumulation",
            labels={"Age_Days": "Days Active (Since FAD)", "Total Rating count": "Total Ratings"},
            color_continuous_scale='Spectral'
        )
        st.plotly_chart(fig_vel_scatter, use_container_width=True)
        
    with col_vel_chart2:
        # Bar chart: Average Velocity by Category
        if 'Category name' in df_filtered.columns:
            avg_vel_cat = df_filtered.groupby('Category name')['Ratings_Per_Month'].mean().reset_index()
            avg_vel_cat = avg_vel_cat.sort_values('Ratings_Per_Month', ascending=True).tail(10) # Top 10
            fig_vel_bar = px.bar(
                avg_vel_cat, 
                x='Ratings_Per_Month', 
                y='Category name', 
                orientation='h',
                title="Top Categories by Avg Rating Velocity",
                labels={"Ratings_Per_Month": "Avg Ratings / Month", "Category name": "Category"},
                color='Ratings_Per_Month', 
                color_continuous_scale='Teal'
            )
            fig_vel_bar.update_layout(yaxis_title="")
            st.plotly_chart(fig_vel_bar, use_container_width=True)

    tab_fast, tab_slow = st.tabs(["High Velocity (Trending Products)", "Sloggers (Stagnant Products)"])
    
    display_cols_vel = ['Product ID', 'Product name', 'Brand name', 'FAD', 'Age_Days', 'Total Rating count', 'Ratings_Per_Month', 'Average Rating']

    with tab_fast:
        st.subheader("High Velocity Products")
        st.write("Products that are accumulating ratings at the fastest rate (Ratings per Month). Showing top 20 established products (active for more than 30 days).")
        fast_products = df_filtered[df_filtered['Age_Days'] > 30].sort_values(by='Ratings_Per_Month', ascending=False).head(20)
        
        fast_disp = fast_products[display_cols_vel].copy()
        fast_disp['Ratings_Per_Month'] = fast_disp['Ratings_Per_Month'].round(2)
        
        st.dataframe(fast_disp, use_container_width=True)

    with tab_slow:
        st.subheader("Sloggers (Stagnant Products)")
        st.write("Older products (Active > 180 days) that have historically struggled to accumulate ratings.")
        slow_products = df_filtered[(df_filtered['Age_Days'] > 180)].sort_values(by='Ratings_Per_Month', ascending=True).head(20)
        
        slow_disp = slow_products[display_cols_vel].copy()
        slow_disp['Ratings_Per_Month'] = slow_disp['Ratings_Per_Month'].round(2)
        
        st.dataframe(slow_disp, use_container_width=True)

    # --- Explore Raw Data & Dynamic Export ---
    st.markdown("---")
    with st.expander("Explore Raw Data & Custom Export", expanded=False):
        st.subheader("Dynamic Data Export")
        st.write("Filter the dataset across any combination of columns before downloading.")
        
        export_df = df_filtered.copy()
        
        # User selects which columns they want to actively filter by
        filter_cols = st.multiselect("Select columns to apply custom filters:", export_df.columns.tolist())
        
        if filter_cols:
            for col in filter_cols:
                # Dynamic filter: Numerical columns get a slider
                if pd.api.types.is_numeric_dtype(export_df[col]):
                    _min = float(export_df[col].min())
                    _max = float(export_df[col].max())
                    if _min == _max:
                        st.info(f"All values in '{col}' are exactly {_min}")
                    else:
                        user_num_input = st.slider(f"Filter {col}", min_value=_min, max_value=_max, value=(_min, _max), key=f"slider_{col}")
                        export_df = export_df[export_df[col].between(*user_num_input)]
                
                # Dynamic filter: Date columns get a date picker
                elif pd.api.types.is_datetime64_any_dtype(export_df[col]):
                    # Check if there are valid dates to avoid errors
                    if export_df[col].dropna().empty:
                        st.info(f"No valid dates found in '{col}'")
                        continue
                        
                    _min = export_df[col].min().date()
                    _max = export_df[col].max().date()
                    if _min == _max:
                         st.info(f"All dates in '{col}' are exactly {_min}")
                    else:
                        user_date_input = st.date_input(f"Filter {col}", value=(_min, _max), min_value=_min, max_value=_max, key=f"date_{col}")
                        if len(user_date_input) == 2:
                            export_df = export_df[export_df[col].dt.date.between(user_date_input[0], user_date_input[1])]
                
                # Dynamic filter: Categorical/String columns get a dropdown
                else:
                    unique_vals = export_df[col].dropna().unique().tolist()
                    user_cat_input = st.multiselect(f"Filter {col}", unique_vals, default=unique_vals, key=f"multi_{col}")
                    export_df = export_df[export_df[col].isin(user_cat_input)]
        
        st.write(f"Showing **{len(export_df)}** records matching your dynamic filters:")
        st.dataframe(export_df, use_container_width=True)
        
        # Download button uses the dynamically filtered data
        st.download_button(
            label="Download Custom Filtered Data (CSV)",
            data=convert_df_to_csv(export_df),
            file_name="custom_filtered_rating_data.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()