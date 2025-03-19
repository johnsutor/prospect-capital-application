from unittest.mock import MagicMock, patch

import pytest
import streamlit as st

from main import fetch_holdings, main


# This is a helper for getting attributes from a dictionary using dot notation with session state and Streamlit.
class DotDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def __setattr__(self, key, value):
        self[key] = value


@pytest.fixture
def mock_successful_json_response():
    """Fixture for mocking a successful JSON response from SEC API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "filings": {
            "recent": {
                "form": ["NPORT-P", "10-Q", "8-K"],
                "accessionNumber": [
                    "0001234567-22-000123",
                    "0001234567-22-000122",
                    "0001234567-22-000121",
                ],
            }
        }
    }
    return mock_response


@pytest.fixture
def mock_successful_xml_response():
    """Fixture for mocking a successful XML response from SEC API."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    xml_content = """
    <report xmlns="http://www.sec.gov/edgar/nport">
        <holdings>
            <invstOrSec>
                <title>Company A Bond</title>
                <cusip>123456789</cusip>
                <balance>1000</balance>
                <valUSD>10000</valUSD>
            </invstOrSec>
            <invstOrSec>
                <title>Company B Stock</title>
                <cusip>987654321</cusip>
                <balance>500</balance>
                <valUSD>5000</valUSD>
            </invstOrSec>
        </holdings>
    </report>
    """.encode("utf-8")

    mock_response.content = xml_content
    return mock_response


@pytest.fixture
def mock_error_json_response():
    """Fixture for mocking a failed JSON response from SEC API."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    return mock_response


@pytest.fixture
def mock_no_nport_response():
    """Fixture for mocking a JSON response with no NPORT-P forms."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "filings": {
            "recent": {
                "form": ["10-Q", "8-K"],
                "accessionNumber": ["0001234567-22-000122", "0001234567-22-000121"],
            }
        }
    }
    return mock_response


@pytest.fixture
def mock_error_xml_response():
    """Fixture for mocking a failed XML response from SEC API."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    return mock_response


def test_fetch_holdings_success(
    mock_successful_json_response, mock_successful_xml_response
):
    """Test fetch_holdings function with successful responses."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = lambda url, headers: (
            mock_successful_json_response
            if "CIK" in url
            else mock_successful_xml_response
        )

        holdings = fetch_holdings("1234567890")

        assert holdings is not None
        assert len(holdings) == 2
        assert holdings[0]["Title"] == "Company A Bond"
        assert holdings[0]["CUSIP"] == "123456789"
        assert holdings[0]["Balance"] == "1000"
        assert holdings[0]["Value"] == "10000"
        assert holdings[1]["Title"] == "Company B Stock"


def test_fetch_holdings_json_error(mock_error_json_response):
    """Test fetch_holdings function with JSON API error."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_error_json_response

        with patch("streamlit.error") as mock_st_error:
            holdings = fetch_holdings("1234567890")

            assert holdings is None
            mock_st_error.assert_called_once()


def test_fetch_holdings_no_nport(mock_no_nport_response):
    """Test fetch_holdings function with no NPORT-P filings."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_no_nport_response

        with patch("streamlit.info") as mock_st_info:
            holdings = fetch_holdings("1234567890")

            assert holdings is None
            mock_st_info.assert_called_once_with("No NPORT-P filings found.")


def test_fetch_holdings_xml_error(
    mock_successful_json_response, mock_error_xml_response
):
    """Test fetch_holdings function with XML API error."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = [mock_successful_json_response, mock_error_xml_response]

        with patch("streamlit.error") as mock_st_error:
            holdings = fetch_holdings("1234567890")

            assert holdings is None
            mock_st_error.assert_called_once_with("Failed to fetch XML")


@pytest.mark.parametrize("with_holdings", [True, False])
def test_main_function(with_holdings, monkeypatch):
    """Test the main function with and without holdings data."""
    mock_session_state = DotDict()
    monkeypatch.setattr(st, "session_state", mock_session_state)

    with (
        patch("streamlit.title") as mock_title,
        patch("streamlit.text_input", return_value="1234567890") as mock_input,
        patch("streamlit.slider", return_value=3.0) as mock_slider,
        patch("streamlit.expander") as mock_expander,
        patch("streamlit.button", return_value=True) as mock_button,
        patch("streamlit.spinner") as mock_spinner,
        patch("main.fetch_holdings") as mock_fetch,
    ):
        if with_holdings:
            mock_data = [
                {
                    "Title": "Test Stock",
                    "CUSIP": "123456789",
                    "Balance": "100",
                    "Value": "1000",
                },
                {
                    "Title": "Test Bond",
                    "CUSIP": "987654321",
                    "Balance": "50",
                    "Value": "500",
                },
            ]
            mock_fetch.return_value = mock_data
        else:
            mock_fetch.return_value = None

        mock_context = MagicMock()
        mock_expander.return_value.__enter__.return_value = mock_context
        mock_context.slider = mock_slider

        with (
            patch("streamlit.success") as mock_success,
            patch("streamlit.dataframe"),
            patch("pandas.DataFrame") as mock_df_constructor,
            patch(
                "matplotlib.pyplot.subplots", return_value=(MagicMock(), MagicMock())
            ),
            patch("streamlit.pyplot"),
        ):
            if with_holdings:
                mock_df = MagicMock()
                mock_df.__getitem__.return_value = mock_df
                mock_df.copy.return_value = mock_df
                mock_df.dropna.return_value = mock_df
                mock_df_constructor.return_value = mock_df
                mock_str = MagicMock()
                mock_str.contains.return_value = mock_df
                type(mock_df).str = mock_str

            main()

            mock_title.assert_called_once()
            mock_input.assert_called()
            mock_button.assert_called_once()
            mock_spinner.assert_called_once()
            mock_fetch.assert_called_once_with("1234567890")

            if with_holdings:
                mock_success.assert_called_once()
                assert hasattr(st.session_state, "holdings_df")
