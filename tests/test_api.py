
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

# Adjust import path based on your project structure
from main import app, Stock, StockValues, PerformanceData, Competitor, MarketCap
from database import get_db, StockRecord
from cache import TTLCache
from services.polygon_service import PolygonService
from services.marketwatch_scraper import MarketWatchScraper

client = TestClient(app)

# --- Fixtures for Mock Data ---

@pytest.fixture
def mock_polygon_daily_success():
    return {
        "status": "OK",
        "from": "2023-01-09",
        "symbol": "AAPL",
        "open": 130.0,
        "high": 132.0,
        "low": 129.5,
        "close": 131.5,
        "volume": 10000000,
        "afterHours": 131.6,
        "preMarket": 129.8
    }

@pytest.fixture
def mock_polygon_company_details_success():
    return {
        "results": {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "market_cap": 2500000000000,
            "currency_name": "usd"
        }
    }

@pytest.fixture
def mock_marketwatch_scrape_success():
    return {
        "performance_data": PerformanceData(
            five_days=1.5,
            one_month=5.0,
            three_months=10.0,
            year_to_date=15.0,
            one_year=20.0
        ),
        "competitors": [
            Competitor(name="Microsoft Corp.", market_cap=MarketCap(currency="USD", value=2000000000000.0)),
            Competitor(name="Alphabet Inc.", market_cap=MarketCap(currency="USD", value=1800000000000.0))
        ]
    }

@pytest.fixture
def mock_db_session():
    """Fixture to mock SQLAlchemy session."""
    session = MagicMock()
    yield session
    session.close()

# Override the get_db dependency for tests
@pytest.fixture(autouse=True)
def override_get_db(mock_db_session):
    app.dependency_overrides[get_db] = lambda: mock_db_session
    yield
    app.dependency_overrides = {} # Clean up after test

# Clear cache before each test
@pytest.fixture(autouse=True)
def clear_cache():
    app.stock_cache.clear()
    yield

# --- Tests for GET /stock/{stock_symbol} ---

@patch.object(PolygonService, 'get_daily_open_close')
@patch.object(PolygonService, 'get_company_details')
@patch.object(MarketWatchScraper, 'scrape_performance_and_competitors')
def test_get_stock_data_success(
    mock_scrape, mock_company_details, mock_open_close,
    mock_polygon_daily_success, mock_polygon_company_details_success, mock_marketwatch_scrape_success
):
    """Test successful retrieval of comprehensive stock data."""
    mock_open_close.return_value = mock_polygon_daily_success
    mock_company_details.return_value = mock_polygon_company_details_success
    mock_scrape.return_value = mock_marketwatch_scrape_success

    response = client.get("/stock/AAPL")
    assert response.status_code == 200
    data = response.json()

    assert data["company_code"] == "AAPL"
    assert data["company_name"] == "Apple Inc."
    assert data["stock_values"]["open"] == 130.0
    assert data["performance_data"]["one_month"] == 5.0
    assert len(data["competitors"]) == 2
    assert data["competitors"][0]["name"] == "Microsoft Corp."
    assert data["status"] == "Success"

    mock_open_close.assert_called_once_with("AAPL", date.today().strftime("%Y-%m-%d"))
    mock_company_details.assert_called_once_with("AAPL")
    mock_scrape.assert_called_once_with("AAPL")

@patch.object(PolygonService, 'get_daily_open_close')
@patch.object(PolygonService, 'get_company_details')
@patch.object(MarketWatchScraper, 'scrape_performance_and_competitors')
def test_get_stock_data_cache_hit(
    mock_scrape, mock_company_details, mock_open_close,
    mock_polygon_daily_success, mock_polygon_company_details_success, mock_marketwatch_scrape_success
):
    """Test that data is served from cache on subsequent requests."""
    mock_open_close.return_value = mock_polygon_daily_success
    mock_company_details.return_value = mock_polygon_company_details_success
    mock_scrape.return_value = mock_marketwatch_scrape_success

    # First request - should hit external APIs
    response1 = client.get("/stock/AAPL")
    assert response1.status_code == 200
    mock_open_close.assert_called_once()
    mock_company_details.assert_called_once()
    mock_scrape.assert_called_once()

    # Reset mocks for second request
    mock_open_close.reset_mock()
    mock_company_details.reset_mock()
    mock_scrape.reset_mock()

    # Second request - should hit cache
    response2 = client.get("/stock/AAPL")
    assert response2.status_code == 200
    assert mock_open_close.call_count == 0
    assert mock_company_details.call_count == 0
    assert mock_scrape.call_count == 0
    assert response2.json()["company_code"] == "AAPL" # Verify cached data content

@patch.object(PolygonService, 'get_daily_open_close', side_effect=HTTPException(status_code=404, detail="Not found"))
@patch.object(PolygonService, 'get_company_details', return_value={}) # Assume company details might still work or return empty
@patch.object(MarketWatchScraper, 'scrape_performance_and_competitors', return_value={})
def test_get_stock_data_polygon_error(
    mock_scrape, mock_company_details, mock_open_close
):
    """Test error handling when Polygon.io data fetching fails."""
    response = client.get("/stock/UNKNOWN")
    assert response.status_code == 404
    assert "Polygon.io: Not found" in response.json()["detail"]

@patch.object(PolygonService, 'get_daily_open_close', return_value={}) # No daily data
@patch.object(PolygonService, 'get_company_details', return_value={"results": {"name": "Test Co"}})
@patch.object(MarketWatchScraper, 'scrape_performance_and_competitors', side_effect=HTTPException(status_code=503, detail="MarketWatch down"))
def test_get_stock_data_marketwatch_error(
    mock_scrape, mock_company_details, mock_open_close
):
    """Test error handling when MarketWatch scraping fails."""
    response = client.get("/stock/MWFAIL")
    assert response.status_code == 503
    assert "MarketWatch down" in response.json()["detail"]

# --- Tests for POST /stock/{stock_symbol} ---

def test_add_purchased_stock_success(mock_db_session):
    """Test successful addition of a purchased stock record."""
    mock_db_session.add.return_value = None
    mock_db_session.commit.return_value = None
    mock_db_session.refresh.return_value = None # Mock refresh to avoid error on non-existent object
    mock_db_session.query.return_value.filter.return_value.first.return_value = None # Ensure no existing record check

    response = client.post("/stock/MSFT", json={"amount": 10.5})
    assert response.status_code == 201
    assert response.json()["message"] == "10.5 units of stock MSFT were added to your stock record"

    mock_db_session.add.assert_called_once()
    # Check if the added object is an instance of StockRecord and has correct attributes
    added_record = mock_db_session.add.call_args[0][0]
    assert isinstance(added_record, StockRecord)
    assert added_record.company_code == "MSFT"
    assert added_record.purchased_amount == 10.5
    assert added_record.request_data == date.today()
    assert added_record.purchased_status == "recorded"
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_add_purchased_stock_db_error(mock_db_session):
    """Test error handling when adding a purchased stock record to the database fails."""
    mock_db_session.add.side_effect = Exception("Database connection failed")
    mock_db_session.commit.side_effect = Exception("Database connection failed")

    response = client.post("/stock/GOOG", json={"amount": 5.0})
    assert response.status_code == 500
    assert "Failed to add stock record" in response.json()["detail"]
    mock_db_session.rollback.assert_called_once() # Ensure rollback is called on error
