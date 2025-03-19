import time
from typing import Any, Dict, List, Optional, Tuple, cast

import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st
from lxml import etree
from streamlit.runtime.scriptrunner import get_script_run_ctx

# Rate limit utilities
IP_REQUESTS: Dict[str, List[float]] = {}
RATE_LIMIT = 10
MAX_REQUESTS = 5


def validate_cik(cik_input: str) -> Optional[str]:
    """
    Validates CIK input to ensure it only contains digits and is not too long.

    Args:
        cik_input (str): The CIK provided by the user.

    Returns:
        Optional[str]: None if valid, or an error message if invalid.
    """
    if not cik_input.strip().isdigit():
        return "Invalid CIK input. Please enter digits only."

    if len(cik_input.strip()) > 10:
        return "Invalid CIK input. CIK should be 10 digits or less."

    return None


@st.cache_data(show_spinner=False)
def fetch_holdings(cik_input: str) -> Optional[List[Dict[str, Optional[str]]]]:
    """
    Fetch holdings data for the given CIK. Cached to reduce redundant API calls.

    Args:
        cik_input (str): The CIK provided by the user.

    Returns:
        Optional[List[Dict[str, Optional[str]]]]: A list of holdings dictionaries if successful, else None.
    """
    cik_padded = cik_input.zfill(10)
    json_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    headers = {"User-Agent": "Your Name contact@yourdomain.com"}
    response = requests.get(json_url, headers=headers)
    if response.status_code != 200:
        st.error(f"Failed to fetch JSON data. Status code: {response.status_code}")
        return None

    data = response.json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])

    # Find indices where form == 'NPORT-P' for latest NPORT-P filing
    nport_p_indices = [i for i, form in enumerate(forms) if form == "NPORT-P"]
    if not nport_p_indices:
        st.info("No NPORT-P filings found.")
        return None

    latest_index = nport_p_indices[0]
    acc_no_clean = recent["accessionNumber"][latest_index].replace("-", "")
    xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{acc_no_clean}/primary_doc.xml"
    response_xml = requests.get(xml_url, headers=headers)
    if response_xml.status_code != 200:
        st.error("Failed to fetch XML")
        return None

    decoded_content = response_xml.content
    parser = etree.XMLParser(
        recover=True
    )  # We recover since the SEC can have strange XML sometimes
    root = etree.fromstring(decoded_content, parser=parser)
    ns_default = root.nsmap.get(None)
    nsmap = {"nport": ns_default} if ns_default else {}

    holdings: List[Dict[str, Optional[str]]] = []
    for sec in root.xpath(".//nport:invstOrSec", namespaces=nsmap):
        holding = {
            "Title": sec.findtext("nport:title", namespaces=nsmap),
            "CUSIP": sec.findtext("nport:cusip", namespaces=nsmap),
            "Balance": sec.findtext("nport:balance", namespaces=nsmap),
            "Value": sec.findtext("nport:valUSD", namespaces=nsmap),
        }
        holdings.append(holding)
    return holdings


def main() -> None:
    """
    Streamlit application entry point to display prospect capital holdings.
    """
    st.title("Prospect Capital Holdings Viewer")

    ctx = get_script_run_ctx()
    client_ip = (
        ctx.request.client.host
        if ctx and hasattr(ctx, "request") and ctx.request
        else "unknown"
    )
    if client_ip not in IP_REQUESTS:
        IP_REQUESTS[client_ip] = []
    current_time = time.time()
    IP_REQUESTS[client_ip] = [
        t for t in IP_REQUESTS[client_ip] if current_time - t < RATE_LIMIT
    ]
    if len(IP_REQUESTS[client_ip]) >= MAX_REQUESTS:
        st.warning("Rate limit exceeded. Please try again later.")
        return
    IP_REQUESTS[client_ip].append(current_time)

    if "holdings_df" not in st.session_state:
        st.session_state.holdings_df = None

    cik_input = st.text_input("Enter CIK", "")
    filter_keyword = st.text_input("Filter by Title", "")

    error_message = validate_cik(cik_input) if cik_input else None
    if error_message:
        st.error(error_message)
        return

    with st.expander("Pie Chart Options"):
        threshold_pct = st.slider(
            "Minimum % for individual slice",
            min_value=0.5,
            max_value=10.0,
            value=3.0,
            step=0.5,
            help="Holdings below this percentage will be grouped as 'Other'",
        )
        top_n = st.slider(
            "Number of holdings in legend",
            min_value=5,
            max_value=30,
            value=15,
            step=1,
            help="Maximum number of individual holdings to display in the legend",
        )

    if st.button("Fetch Holdings") and cik_input:
        with st.spinner("Fetching data..."):
            holdings = fetch_holdings(cik_input.strip())
            if holdings is not None:
                st.success("Data fetched successfully.")
                st.session_state.holdings_df = pd.DataFrame(holdings)

    if st.session_state.holdings_df is not None:
        df = st.session_state.holdings_df.copy()

        if filter_keyword:
            df = df[df["Title"].str.contains(filter_keyword, case=False, na=False)]

        st.dataframe(df)  # Create the sortable table

        # Creates a pie chart if there is a 'Value' column in the DataFrame
        if "Value" in df.columns:
            chart_data = df[["Title", "Value"]].dropna()
            chart_data["Value"] = pd.to_numeric(chart_data["Value"], errors="coerce")
            chart_data = chart_data.sort_values("Value", ascending=False)

            if not chart_data.empty:
                fig, ax = plt.subplots(figsize=(10, 8))

                ax.set_title("Holdings by Total USD Value", fontsize=16, pad=20)

                total_value = chart_data["Value"].sum()

                main_holdings = chart_data[
                    chart_data["Value"] / total_value * 100 >= threshold_pct
                ].copy()
                small_holdings = chart_data[
                    chart_data["Value"] / total_value * 100 < threshold_pct
                ].copy()

                if not small_holdings.empty:
                    other_value = small_holdings["Value"].sum()
                    other_row = pd.DataFrame(
                        {"Title": ["Other"], "Value": [other_value]}
                    )
                    plot_data = pd.concat([main_holdings, other_row])
                else:
                    plot_data = main_holdings

                wedges, texts, autotexts = cast(
                    Tuple[List[Any], List[Any], List[Any]],
                    ax.pie(
                        plot_data["Value"],
                        labels=plot_data["Title"],
                        autopct="%1.1f%%",
                        startangle=90,
                        pctdistance=0.85,
                    ),
                )

                ax.axis("equal")
                legend_items = chart_data["Title"].head(top_n).tolist()
                if len(chart_data) > top_n:
                    legend_items.append(f"Others ({len(chart_data) - top_n} holdings)")

                plt.legend(
                    title="Holdings Detail",
                    loc="center left",
                    bbox_to_anchor=(1, 0, 0.5, 1),
                )

                footnote = f"Note: Holdings below {threshold_pct}% shown as 'Other'"
                fig.text(
                    0.5, 0.01, footnote, ha="center", fontsize=10, fontstyle="italic"
                )

                plt.setp(autotexts, size=10, weight="bold")
                plt.setp(texts, size=11)

                plt.tight_layout()
                st.pyplot(fig)
        else:
            st.error(
                "The data does not contain 'Value' information required for visualization."
            )


if __name__ == "__main__":
    main()
