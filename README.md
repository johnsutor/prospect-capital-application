# Prospect Capital Application
This applications is built using Streamlit to fetch SEC data. It uses UV to manage packages as well. 

I created this application by first exploring the [EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces). Results are filtered out to retrieve the latest NPORT-P filing from the retrieved results, if possible. The XML is then parsed, and the proper fields are returned if they are available. This data is then displayed in a sortable table along with a pie chart that shows the holdings breakdown by the monetary amount. 

This application has the following extra features supported 
1. Error Handling: Errors are supported by default in Streamlit, and shown when requests fail or no data is retrieved.
2. Enhanced UI/UX: Streamlit dataframes (tables) natively support filtering by clicking on the title. This is also handled by filtering by asset name when retrieving data
3. Data Visualization: I create a pie chart to show holding breakdowns.
4. Cacheing and Performance: All calls to the EDGAR API are cached using [`@st.cache_data`](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data)
5. Testing: I went ahead and wrote unit tests for the code implemented. I also display the coverage when tests are run (simply run `make test` to see coverage results). I also perform static type checking using mypy, and formatting/linting using ruff. 
6. Containerization: I provide≥/ the Dockerfile for deploying this code with the application itself.
7. Security Enhancements: 

## Makefile
This file includes utilities for testing, formatting, and type-checking the code. 

## Application
To run the application, simply run `streamlit run main.py`. This assumes you have the necessary packages installed from the pyproject.toml.