"""
Harris County Commissioners Court Finance Transparency Tool
Public transparency tool for tracking money in Harris County politics
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# Page config
st.set_page_config(
    page_title="Harris County Money in Politics",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .big-number {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .red-flag {
        background-color: #ffe6e6;
        padding: 10px;
        border-left: 4px solid #e74c3c;
        margin: 10px 0;
    }
    .insight-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Current Harris County Commissioners Court
CURRENT_OFFICIALS = {
    "County Judge": ["Lina Hidalgo"],
    "Commissioner Precinct 1": ["Rodney Ellis"],
    "Commissioner Precinct 2": ["Adrian Garcia"],
    "Commissioner Precinct 3": ["Tom Ramsey"],
    "Commissioner Precinct 4": ["Lesley Briones"]
}

def get_official_names():
    """Get list of all current official names"""
    names = []
    for officials in CURRENT_OFFICIALS.values():
        names.extend(officials)
    return names

@st.cache_data
def load_data():
    """Load all data files"""
    data_dir = Path(__file__).parent / "data"

    # Load campaign finance data
    finance = pd.read_csv(data_dir / "harris_county_finance_2016_2025.csv")
    for col in ['Raised', 'Spent', 'Loans', 'CashOnHand']:
        if col in finance.columns:
            finance[col] = pd.to_numeric(finance[col], errors='coerce')

    # Load lobbyists
    lobbyists = pd.read_csv(data_dir / "harris_county_lobbyists.csv")

    # Load vendors
    vendors = pd.read_csv(data_dir / "harris_county_vendors.csv")

    return finance, lobbyists, vendors

def main():
    st.title("Harris County Money in Politics")
    st.markdown("**Transparency tool for tracking campaign finance in Harris County Commissioners Court**")

    # Load data
    try:
        finance, lobbyists, vendors = load_data()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Key Insights",
        "Campaign Finance",
        "Cash on Hand Trends",
        "Lobbyists & Vendors",
        "Data Explorer"
    ])

    # --- TAB 1: KEY INSIGHTS ---
    with tab1:
        st.header("Key Insights")

        # Get latest data
        latest_period = finance['ReportPeriod'].iloc[0]
        latest_data = finance[finance['ReportPeriod'] == latest_period]
        current_officials = get_official_names()
        latest_current = latest_data[latest_data['Name'].isin(current_officials)]

        st.subheader(f"Latest Report: {latest_period}")

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_raised = latest_current['Raised'].sum()
            st.metric("Total Raised", f"${total_raised:,.0f}")
        with col2:
            total_spent = latest_current['Spent'].sum()
            st.metric("Total Spent", f"${total_spent:,.0f}")
        with col3:
            total_cash = latest_current['CashOnHand'].sum()
            st.metric("Total Cash on Hand", f"${total_cash:,.0f}")
        with col4:
            st.metric("Officials Tracked", len(current_officials))

        st.divider()

        # Top fundraisers
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Top Fundraisers (Latest Period)")
            top_raised = latest_current.nlargest(5, 'Raised')[['Name', 'Position', 'Raised']]
            top_raised['Raised'] = top_raised['Raised'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(top_raised, use_container_width=True, hide_index=True)

        with col2:
            st.subheader("Largest War Chests")
            top_cash = latest_current.nlargest(5, 'CashOnHand')[['Name', 'Position', 'CashOnHand']]
            top_cash['CashOnHand'] = top_cash['CashOnHand'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(top_cash, use_container_width=True, hide_index=True)

        # Key observations
        st.subheader("Key Observations")

        # Find who's spending more than raising
        deficit_spenders = latest_current[latest_current['Spent'] > latest_current['Raised']]
        if not deficit_spenders.empty:
            st.markdown("**Officials spending more than they raised:**")
            for _, row in deficit_spenders.iterrows():
                deficit = row['Spent'] - row['Raised']
                st.markdown(f"- **{row['Name']}** ({row['Position']}): Spent ${row['Spent']:,.0f}, Raised ${row['Raised']:,.0f} (deficit: ${deficit:,.0f})")

        # Rodney Ellis war chest note
        ellis_data = latest_current[latest_current['Name'] == 'Rodney Ellis']
        if not ellis_data.empty:
            ellis_cash = ellis_data['CashOnHand'].iloc[0]
            st.info(f"Commissioner Rodney Ellis maintains the largest campaign war chest in Harris County with **${ellis_cash:,.0f}** cash on hand.")

    # --- TAB 2: CAMPAIGN FINANCE ---
    with tab2:
        st.header("Campaign Finance Reports")

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            selected_official = st.selectbox(
                "Select Official",
                ["All"] + sorted(finance['Name'].unique().tolist())
            )
        with col2:
            selected_year = st.selectbox(
                "Select Year",
                ["All"] + sorted(finance['Year'].unique().tolist(), reverse=True)
            )

        # Filter data
        filtered = finance.copy()
        if selected_official != "All":
            filtered = filtered[filtered['Name'] == selected_official]
        if selected_year != "All":
            filtered = filtered[filtered['Year'] == selected_year]

        # Display data
        st.dataframe(
            filtered[['ReportPeriod', 'Year', 'Name', 'Position', 'Precinct', 'Raised', 'Spent', 'Loans', 'CashOnHand']],
            use_container_width=True,
            hide_index=True
        )

        # Visualization
        if selected_official != "All":
            st.subheader(f"Fundraising History: {selected_official}")
            official_data = finance[finance['Name'] == selected_official].sort_values('Year')

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=official_data['ReportPeriod'],
                y=official_data['Raised'],
                name='Raised',
                marker_color='green'
            ))
            fig.add_trace(go.Bar(
                x=official_data['ReportPeriod'],
                y=official_data['Spent'],
                name='Spent',
                marker_color='red'
            ))
            fig.update_layout(barmode='group', title=f"{selected_official} - Raised vs Spent")
            st.plotly_chart(fig, use_container_width=True)

    # --- TAB 3: CASH ON HAND TRENDS ---
    with tab3:
        st.header("Cash on Hand Trends")

        # Get current officials' historical data
        current_names = get_official_names()
        trend_data = finance[finance['Name'].isin(current_names)].copy()

        # Create time series
        fig = px.line(
            trend_data,
            x='ReportPeriod',
            y='CashOnHand',
            color='Name',
            title='Cash on Hand Over Time',
            markers=True
        )
        fig.update_layout(yaxis_title='Cash on Hand ($)', xaxis_title='Report Period')
        st.plotly_chart(fig, use_container_width=True)

        # Comparison chart
        st.subheader("Current Cash on Hand Comparison")
        latest_current = finance[
            (finance['ReportPeriod'] == finance['ReportPeriod'].iloc[0]) &
            (finance['Name'].isin(current_names))
        ]

        fig2 = px.bar(
            latest_current.sort_values('CashOnHand', ascending=True),
            x='CashOnHand',
            y='Name',
            orientation='h',
            title='Cash on Hand by Official',
            color='CashOnHand',
            color_continuous_scale='Blues'
        )
        fig2.update_layout(xaxis_title='Cash on Hand ($)', yaxis_title='')
        st.plotly_chart(fig2, use_container_width=True)

    # --- TAB 4: LOBBYISTS & VENDORS ---
    with tab4:
        st.header("Registered Lobbyists & County Vendors")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Registered Lobbyists")
            st.markdown("*Lobbyists registered with Harris County Clerk's Office*")
            st.dataframe(lobbyists, use_container_width=True, hide_index=True)

            # Lobbyist by category
            st.subheader("Lobbyists by Category")
            lobby_cats = lobbyists['Category'].value_counts()
            fig = px.pie(values=lobby_cats.values, names=lobby_cats.index, title='Lobbyist Categories')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Major County Vendors")
            st.markdown("*Major contractors with Harris County agencies*")
            st.dataframe(vendors, use_container_width=True, hide_index=True)

            # Vendors by category
            st.subheader("Vendors by Category")
            vendor_cats = vendors['Category'].value_counts()
            fig2 = px.pie(values=vendor_cats.values, names=vendor_cats.index, title='Vendor Categories')
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        st.markdown("""
        **Data Sources:**
        - Lobbyist data: [Harris County Clerk's Ethics System](https://ethics.cclerk.hctx.net/)
        - Vendor data: [Harris County Auditor Vendor Payment Search](https://auditor.harriscountytx.gov/Accounts-Payable/Vendor-Payment-Search)
        """)

    # --- TAB 5: DATA EXPLORER ---
    with tab5:
        st.header("Data Explorer")

        dataset = st.selectbox(
            "Select Dataset",
            ["Campaign Finance", "Lobbyists", "Vendors"]
        )

        if dataset == "Campaign Finance":
            st.subheader("Campaign Finance Data (2016-2025)")
            st.dataframe(finance, use_container_width=True, hide_index=True)

            # Download button
            csv = finance.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                "harris_county_finance.csv",
                "text/csv"
            )

        elif dataset == "Lobbyists":
            st.subheader("Registered Lobbyists")
            st.dataframe(lobbyists, use_container_width=True, hide_index=True)
            csv = lobbyists.to_csv(index=False)
            st.download_button("Download CSV", csv, "harris_county_lobbyists.csv", "text/csv")

        else:
            st.subheader("County Vendors")
            st.dataframe(vendors, use_container_width=True, hide_index=True)
            csv = vendors.to_csv(index=False)
            st.download_button("Download CSV", csv, "harris_county_vendors.csv", "text/csv")

        st.divider()
        st.markdown("""
        **About This Data:**
        - Campaign finance data compiled from [Off the Kuff](https://www.offthekuff.com/) analysis of Texas Ethics Commission filings
        - Data covers Harris County Judge and Commissioners Court members from 2016-2025
        - Lobbyist data from Harris County Clerk's Office Ethics System
        - Vendor data from Harris County Auditor's Office
        """)

    # Footer
    st.divider()
    st.markdown("""
    ---
    **Harris County Finance Transparency Tool** | Data sources: [Texas Ethics Commission](https://www.ethics.state.tx.us/),
    [Off the Kuff](https://www.offthekuff.com/), [Harris County Clerk](https://ethics.cclerk.hctx.net/)
    """)

if __name__ == "__main__":
    main()
