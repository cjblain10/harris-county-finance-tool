"""
Harris County Commissioners Court Finance Transparency Tool
Public transparency tool for tracking money in Harris County politics
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import networkx as nx
from pyvis.network import Network
import tempfile
import streamlit.components.v1 as components

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
    .warning-box {
        background-color: #fff3cd;
        padding: 15px;
        border-left: 4px solid #ffc107;
        margin: 10px 0;
        border-radius: 4px;
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

ALL_OFFICIALS = [name for names in CURRENT_OFFICIALS.values() for name in names]

# Official party affiliations and notes
OFFICIAL_INFO = {
    "Lina Hidalgo": {"party": "Democrat", "since": 2019, "notes": "First woman and Latina elected County Judge"},
    "Rodney Ellis": {"party": "Democrat", "since": 2017, "notes": "Former State Senator, largest war chest in county"},
    "Adrian Garcia": {"party": "Democrat", "since": 2019, "notes": "Former Harris County Sheriff"},
    "Tom Ramsey": {"party": "Republican", "since": 2021, "notes": "Only Republican on Commissioners Court"},
    "Lesley Briones": {"party": "Democrat", "since": 2023, "notes": "Defeated incumbent Jack Cagle in 2022"}
}

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


def create_money_flow_network(finance, lobbyists, vendors):
    """Create network showing relationships between officials, lobbyists, and vendors"""
    G = nx.Graph()

    # Get latest finance data for current officials
    latest_period = finance['ReportPeriod'].iloc[0]
    latest = finance[finance['ReportPeriod'] == latest_period]

    # Add official nodes
    for official in ALL_OFFICIALS:
        official_data = latest[latest['Name'] == official]
        if not official_data.empty:
            cash = official_data['CashOnHand'].iloc[0]
            info = OFFICIAL_INFO.get(official, {})
            tooltip = f"<b>{official}</b><br>{info.get('party', '')}<br>Cash: ${cash:,.0f}"
            G.add_node(official, node_type='official', title=tooltip,
                      color='#e74c3c', size=40 + (cash / 200000))

    # Add lobbyist nodes and connections
    for _, lobby in lobbyists.iterrows():
        name = lobby['LobbyistName']
        client = lobby['Client']
        category = lobby['Category']

        tooltip = f"<b>{name}</b><br>Client: {client}<br>Category: {category}"
        G.add_node(name, node_type='lobbyist', title=tooltip, color='#f39c12', size=20)

        # Connect lobbyists to all officials (they lobby the whole court)
        for official in ALL_OFFICIALS:
            if official in G.nodes():
                G.add_edge(name, official, weight=1, color='#f39c12',
                          title=f"Lobbies on {category}")

    # Add vendor nodes
    for _, vendor in vendors.iterrows():
        name = vendor['VendorName']
        category = vendor['Category']
        dept = vendor['Department']

        tooltip = f"<b>{name}</b><br>Category: {category}<br>Dept: {dept}"
        G.add_node(name, node_type='vendor', title=tooltip, color='#9b59b6', size=15)

        # Connect vendors to officials (contracts approved by court)
        for official in ALL_OFFICIALS:
            if official in G.nodes():
                G.add_edge(name, official, weight=0.5, color='#9b59b6',
                          title=f"County contractor - {category}")

    return G


def render_network(G, height=600):
    """Render network graph to HTML"""
    if G is None or len(G.nodes()) == 0:
        return None

    net = Network(height=f"{height}px", width="100%", bgcolor="#ffffff", font_color="#333333")
    net.from_nx(G)
    net.set_options("""
    {
        "nodes": {"font": {"size": 12}},
        "edges": {"color": {"inherit": true}, "smooth": {"type": "continuous"}},
        "physics": {
            "forceAtlas2Based": {"gravitationalConstant": -80, "centralGravity": 0.01, "springLength": 200},
            "solver": "forceAtlas2Based",
            "stabilization": {"iterations": 100}
        },
        "interaction": {"hover": true, "tooltipDelay": 100}
    }
    """)

    with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w') as f:
        net.save_graph(f.name)
        return f.name


def create_sankey_diagram(finance):
    """Create Sankey diagram showing money flow"""
    # Get latest data
    latest_period = finance['ReportPeriod'].iloc[0]
    latest = finance[(finance['ReportPeriod'] == latest_period) &
                     (finance['Name'].isin(ALL_OFFICIALS))]

    # Create flow: Donors -> Officials -> Spending Categories
    labels = ['Donors/Fundraising'] + list(latest['Name']) + ['Campaign Operations', 'Political Consulting', 'Media/Advertising', 'Events/Outreach']

    sources = []
    targets = []
    values = []

    # Raised flows to each official
    for i, (_, row) in enumerate(latest.iterrows()):
        sources.append(0)  # Donors
        targets.append(i + 1)  # Official
        values.append(row['Raised'] if pd.notna(row['Raised']) else 0)

    # Officials spend on categories (estimated distribution)
    for i, (_, row) in enumerate(latest.iterrows()):
        spent = row['Spent'] if pd.notna(row['Spent']) else 0
        if spent > 0:
            # Campaign Operations (40%)
            sources.append(i + 1)
            targets.append(len(latest) + 1)
            values.append(spent * 0.4)
            # Political Consulting (30%)
            sources.append(i + 1)
            targets.append(len(latest) + 2)
            values.append(spent * 0.3)
            # Media (20%)
            sources.append(i + 1)
            targets.append(len(latest) + 3)
            values.append(spent * 0.2)
            # Events (10%)
            sources.append(i + 1)
            targets.append(len(latest) + 4)
            values.append(spent * 0.1)

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels,
            color=['#3498db'] + ['#e74c3c'] * len(latest) + ['#2ecc71', '#9b59b6', '#f39c12', '#1abc9c']
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color='rgba(150,150,150,0.3)'
        )
    )])

    fig.update_layout(title_text="Money Flow: Fundraising to Spending", font_size=12, height=500)
    return fig


def main():
    st.title("Harris County Money in Politics")
    st.markdown("**Transparency tool for tracking campaign finance in Harris County Commissioners Court**")

    # Load data
    try:
        finance, lobbyists, vendors = load_data()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # Tabs - now with investigative features
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Key Insights",
        "Follow the Money",
        "Red Flags",
        "Official Profiles",
        "Data Explorer"
    ])

    # Get latest data for reuse
    latest_period = finance['ReportPeriod'].iloc[0]
    latest_data = finance[finance['ReportPeriod'] == latest_period]
    latest_current = latest_data[latest_data['Name'].isin(ALL_OFFICIALS)]

    # --- TAB 1: KEY INSIGHTS ---
    with tab1:
        st.header("Key Insights")

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
            st.metric("Combined War Chests", f"${total_cash:,.0f}")
        with col4:
            st.metric("Officials Tracked", len(ALL_OFFICIALS))

        st.divider()

        # Key visualizations
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("War Chest Comparison")
            fig = px.bar(
                latest_current.sort_values('CashOnHand', ascending=True),
                x='CashOnHand',
                y='Name',
                orientation='h',
                color='CashOnHand',
                color_continuous_scale='Reds',
                labels={'CashOnHand': 'Cash on Hand ($)', 'Name': ''}
            )
            fig.update_layout(height=350, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Raised vs Spent (Latest Period)")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Raised',
                x=latest_current['Name'],
                y=latest_current['Raised'],
                marker_color='green'
            ))
            fig.add_trace(go.Bar(
                name='Spent',
                x=latest_current['Name'],
                y=latest_current['Spent'],
                marker_color='red'
            ))
            fig.update_layout(barmode='group', height=350)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Key observations
        st.subheader("Key Observations")

        col1, col2 = st.columns(2)

        with col1:
            # Rodney Ellis dominance
            ellis_data = latest_current[latest_current['Name'] == 'Rodney Ellis']
            if not ellis_data.empty:
                ellis_cash = ellis_data['CashOnHand'].iloc[0]
                others_cash = latest_current[latest_current['Name'] != 'Rodney Ellis']['CashOnHand'].sum()
                st.markdown(f"""
                <div class="warning-box">
                <b>Rodney Ellis's War Chest</b><br>
                Commissioner Ellis has <b>${ellis_cash:,.0f}</b> in campaign funds -
                more than all other Commissioners Court members <i>combined</i> (${others_cash:,.0f}).
                </div>
                """, unsafe_allow_html=True)

        with col2:
            # Deficit spenders
            deficit_spenders = latest_current[latest_current['Spent'] > latest_current['Raised']]
            if not deficit_spenders.empty:
                st.markdown("""
                <div class="red-flag">
                <b>Spending More Than Raising</b><br>
                """, unsafe_allow_html=True)
                for _, row in deficit_spenders.iterrows():
                    deficit = row['Spent'] - row['Raised']
                    st.markdown(f"- **{row['Name']}**: ${deficit:,.0f} deficit")
                st.markdown("</div>", unsafe_allow_html=True)

        # Party breakdown
        st.subheader("Political Landscape")
        col1, col2, col3 = st.columns(3)

        dem_cash = sum(latest_current[latest_current['Name'].isin(['Lina Hidalgo', 'Rodney Ellis', 'Adrian Garcia', 'Lesley Briones'])]['CashOnHand'])
        rep_cash = sum(latest_current[latest_current['Name'] == 'Tom Ramsey']['CashOnHand'])

        with col1:
            st.metric("Democrats (4)", f"${dem_cash:,.0f}", help="Combined war chest")
        with col2:
            st.metric("Republicans (1)", f"${rep_cash:,.0f}", help="Tom Ramsey")
        with col3:
            ratio = dem_cash / rep_cash if rep_cash > 0 else 0
            st.metric("Dem/Rep Ratio", f"{ratio:.1f}x", help="Democratic fundraising advantage")

    # --- TAB 2: FOLLOW THE MONEY ---
    with tab2:
        st.header("Follow the Money")
        st.markdown("Visualize the relationships between officials, lobbyists, and county vendors")

        viz_type = st.radio(
            "Visualization Type:",
            ["Network Graph", "Money Flow (Sankey)", "Cash Trends"],
            horizontal=True
        )

        if viz_type == "Network Graph":
            st.markdown("""
            **Node colors:**
            - Red = Elected Official
            - Orange = Registered Lobbyist
            - Purple = County Vendor/Contractor
            """)

            with st.spinner("Building network..."):
                G = create_money_flow_network(finance, lobbyists, vendors)
                html_file = render_network(G, height=550)

            if html_file:
                with open(html_file, 'r') as f:
                    components.html(f.read(), height=570, scrolling=True)

            st.info(f"Showing {len(lobbyists)} registered lobbyists and {len(vendors)} major vendors connected to Commissioners Court")

        elif viz_type == "Money Flow (Sankey)":
            st.markdown("Track how campaign money flows from fundraising to spending categories")
            fig = create_sankey_diagram(finance)
            st.plotly_chart(fig, use_container_width=True)

            st.caption("*Spending categories are estimated based on typical campaign expenditure patterns*")

        else:  # Cash Trends
            st.subheader("Cash on Hand Over Time")

            trend_data = finance[finance['Name'].isin(ALL_OFFICIALS)].copy()

            fig = px.line(
                trend_data,
                x='ReportPeriod',
                y='CashOnHand',
                color='Name',
                title='Cash on Hand Trends (2016-2025)',
                markers=True
            )
            fig.update_layout(yaxis_title='Cash on Hand ($)', xaxis_title='Report Period', height=500)
            st.plotly_chart(fig, use_container_width=True)

            # Year-over-year comparison
            st.subheader("Year-over-Year Fundraising")
            yearly = finance[finance['Name'].isin(ALL_OFFICIALS)].groupby(['Year', 'Name'])['Raised'].sum().reset_index()

            fig2 = px.bar(
                yearly,
                x='Year',
                y='Raised',
                color='Name',
                barmode='group',
                title='Annual Fundraising by Official'
            )
            st.plotly_chart(fig2, use_container_width=True)

    # --- TAB 3: RED FLAGS ---
    with tab3:
        st.header("Potential Conflicts of Interest")
        st.markdown("""
        Automated detection of patterns that warrant public scrutiny.
        **These are not accusations** - but patterns that informed citizens should know about.
        """)

        # 1. Lobbyist-Vendor Overlap
        st.subheader("1. Lobbyist-Vendor Connections")
        st.markdown("*Organizations that both lobby the county AND receive contracts*")

        # Check for matches between lobbyist clients and vendors
        lobby_clients = set(lobbyists['Client'].str.upper().dropna())
        vendor_names = set(vendors['VendorName'].str.upper().dropna())

        potential_overlaps = []
        for client in lobby_clients:
            for vendor in vendor_names:
                # Simple word matching
                client_words = set(client.split())
                vendor_words = set(vendor.split())
                if len(client_words & vendor_words) >= 2:
                    potential_overlaps.append({
                        'Lobbyist Client': client,
                        'Vendor Name': vendor,
                        'Common Words': ', '.join(client_words & vendor_words)
                    })

        if potential_overlaps:
            st.warning(f"Found {len(potential_overlaps)} potential lobbyist-vendor connections")
            st.dataframe(pd.DataFrame(potential_overlaps), use_container_width=True)
        else:
            st.success("No direct lobbyist-vendor overlaps detected")

        st.divider()

        # 2. Spending Anomalies
        st.subheader("2. Spending Anomalies")
        st.markdown("*Officials spending significantly more than they raise*")

        # Calculate spending ratio over time
        for official in ALL_OFFICIALS:
            official_data = finance[finance['Name'] == official]
            total_raised = official_data['Raised'].sum()
            total_spent = official_data['Spent'].sum()

            if total_raised > 0:
                ratio = total_spent / total_raised
                if ratio > 1.2:  # Spending 20% more than raised
                    st.markdown(f"""
                    <div class="red-flag">
                    <b>{official}</b>: Lifetime spending ratio of {ratio:.1%}<br>
                    Total Raised: ${total_raised:,.0f} | Total Spent: ${total_spent:,.0f}
                    </div>
                    """, unsafe_allow_html=True)

        st.divider()

        # 3. Large Loans
        st.subheader("3. Self-Funded Campaigns")
        st.markdown("*Officials with significant personal loans to their campaigns*")

        loans_data = latest_current[latest_current['Loans'] > 0].sort_values('Loans', ascending=False)
        if not loans_data.empty:
            for _, row in loans_data.iterrows():
                st.markdown(f"- **{row['Name']}**: ${row['Loans']:,.0f} in outstanding loans")
        else:
            st.info("No officials with significant campaign loans in latest period")

        st.divider()

        # 4. Concentrated Vendor Categories
        st.subheader("4. Concentrated Vendor Industries")
        st.markdown("*Which industries dominate county contracting?*")

        vendor_cats = vendors['Category'].value_counts()
        fig = px.pie(
            values=vendor_cats.values,
            names=vendor_cats.index,
            title='County Vendor Distribution by Category'
        )
        st.plotly_chart(fig, use_container_width=True)

        if vendor_cats.iloc[0] / vendor_cats.sum() > 0.5:
            st.warning(f"**{vendor_cats.index[0]}** represents {vendor_cats.iloc[0]/vendor_cats.sum():.0%} of tracked vendors - high concentration")

        st.divider()

        st.markdown("""
        ### Why This Matters

        - **Lobbyist-vendors** may receive favorable treatment in contract negotiations
        - **Spending anomalies** may indicate financial mismanagement or undisclosed funding
        - **Self-funded campaigns** may expect return on investment from policy decisions
        - **Industry concentration** in contracting may indicate limited competition

        *Harris County's $4+ billion budget is controlled by Commissioners Court. Always investigate further.*
        """)

    # --- TAB 4: OFFICIAL PROFILES ---
    with tab4:
        st.header("Official Profiles")

        selected = st.selectbox("Select Official:", ALL_OFFICIALS)

        if selected:
            info = OFFICIAL_INFO.get(selected, {})
            official_finance = finance[finance['Name'] == selected].sort_values('Year', ascending=False)

            col1, col2 = st.columns([1, 2])

            with col1:
                st.subheader(selected)
                st.markdown(f"**Party:** {info.get('party', 'Unknown')}")
                st.markdown(f"**In Office Since:** {info.get('since', 'Unknown')}")
                st.markdown(f"**Note:** {info.get('notes', '')}")

                if not official_finance.empty:
                    latest = official_finance.iloc[0]
                    st.metric("Current Cash on Hand", f"${latest['CashOnHand']:,.0f}")
                    st.metric("Latest Raised", f"${latest['Raised']:,.0f}")
                    st.metric("Latest Spent", f"${latest['Spent']:,.0f}")

            with col2:
                st.subheader("Fundraising History")

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=official_finance['ReportPeriod'],
                    y=official_finance['CashOnHand'],
                    mode='lines+markers',
                    name='Cash on Hand',
                    line=dict(color='blue', width=2)
                ))
                fig.add_trace(go.Bar(
                    x=official_finance['ReportPeriod'],
                    y=official_finance['Raised'],
                    name='Raised',
                    marker_color='green',
                    opacity=0.6
                ))
                fig.add_trace(go.Bar(
                    x=official_finance['ReportPeriod'],
                    y=official_finance['Spent'],
                    name='Spent',
                    marker_color='red',
                    opacity=0.6
                ))
                fig.update_layout(title=f"{selected} - Financial History", barmode='overlay', height=400)
                st.plotly_chart(fig, use_container_width=True)

            # Full history table
            st.subheader("Complete Finance History")
            display_cols = ['ReportPeriod', 'Year', 'Raised', 'Spent', 'Loans', 'CashOnHand']
            st.dataframe(
                official_finance[display_cols].style.format({
                    'Raised': '${:,.0f}',
                    'Spent': '${:,.0f}',
                    'Loans': '${:,.0f}',
                    'CashOnHand': '${:,.0f}'
                }),
                use_container_width=True,
                hide_index=True
            )

    # --- TAB 5: DATA EXPLORER ---
    with tab5:
        st.header("Data Explorer")

        dataset = st.selectbox(
            "Select Dataset",
            ["Campaign Finance", "Lobbyists", "Vendors"]
        )

        if dataset == "Campaign Finance":
            st.subheader("Campaign Finance Data (2016-2025)")

            # Filters
            col1, col2 = st.columns(2)
            with col1:
                name_filter = st.multiselect("Filter by Official:", finance['Name'].unique())
            with col2:
                year_filter = st.multiselect("Filter by Year:", sorted(finance['Year'].unique(), reverse=True))

            filtered = finance.copy()
            if name_filter:
                filtered = filtered[filtered['Name'].isin(name_filter)]
            if year_filter:
                filtered = filtered[filtered['Year'].isin(year_filter)]

            st.dataframe(filtered, use_container_width=True, hide_index=True)

            csv = filtered.to_csv(index=False)
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
        **Data Sources:**
        - Campaign finance data: [Off the Kuff](https://www.offthekuff.com/) analysis of Texas Ethics Commission filings
        - Lobbyist data: [Harris County Clerk's Ethics System](https://ethics.cclerk.hctx.net/)
        - Vendor data: [Harris County Auditor's Office](https://auditor.harriscountytx.gov/)
        """)

    # Footer
    st.divider()
    st.markdown("""
    ---
    **Harris County Finance Transparency Tool** |
    Data: [Texas Ethics Commission](https://www.ethics.state.tx.us/),
    [Off the Kuff](https://www.offthekuff.com/),
    [Harris County Clerk](https://ethics.cclerk.hctx.net/)

    *Harris County Commissioners Court controls a $4+ billion annual budget serving 4.7 million residents.*
    """)

if __name__ == "__main__":
    main()
