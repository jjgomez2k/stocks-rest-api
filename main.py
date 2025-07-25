import logging
import os
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from services.polygon_service import PolygonService
from services.marketwatch_scraper import MarketWatchScraper
from database import create_db_and_tables, get_db, StockRecord
from cache import TTLCache
from models import Stock, StockValues, PerformanceData, Competitor, MarketCap

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Stocks REST API",
    description="A REST API to retrieve stock data from Polygon.io and MarketWatch, with caching and PostgreSQL persistence.",
    version="1.0.0",
)

# --- Service and Cache Initialization ---
polygon_service = PolygonService()
# Pass the MarketWatch cookie from environment variable to the scraper
marketwatch_cookie = os.getenv("MARKETWATCH_COOKIE", "")
if not marketwatch_cookie:
    logger.warning("MARKETWATCH_COOKIE environment variable is not set. MarketWatch scraping may fail.")
marketwatch_scraper = MarketWatchScraper(marketwatch_cookie=marketwatch_cookie)
stock_cache = TTLCache(ttl_seconds=300) # Cache for 5 minutes (300 seconds)

@app.on_event("startup")
def on_startup():
    """
    Event handler that runs when the FastAPI application starts up.
    Creates database tables if they don't exist.
    """
    logger.info("Application startup: Creating database tables...")
    create_db_and_tables()
    logger.info("Database tables created (if they didn't exist).")

# --- API Endpoints ---
@app.get("/stock/{stock_symbol}", response_model=Stock, summary="Get comprehensive stock data")
async def get_stock_data(stock_symbol: str):
    """
    Retrieves comprehensive stock data for a given symbol, including daily values,
    performance metrics, and competitor information. Data is cached for 5 minutes.
    """
    symbol_upper = stock_symbol.upper()
    logger.info(f"Received GET request for stock symbol: {symbol_upper}")

    # 1. Check Cache
    cached_stock = stock_cache.get(symbol_upper)
    if cached_stock:
        logger.info(f"Serving {symbol_upper} from cache.")
        return cached_stock

    logger.info(f"Cache miss for {symbol_upper}. Fetching data from external sources.")

    today = date.today()
    yesterday = today - timedelta(days=2)
    
    today_str = yesterday.strftime("%Y-%m-%d")
    
    # Initialize fields with defaults or empty lists
    company_name = "N/A"
    stock_values = StockValues(open=0.0, high=0.0, low=0.0, close=0.0)
    performance_data = PerformanceData()
    competitors = []
    status_message = "Success"

    try:
        # 2. Fetch Daily Open/Close from Polygon.io
        polygon_data = await polygon_service.get_daily_open_close(symbol_upper, today_str)
        if polygon_data:
            stock_values = StockValues(
                open=polygon_data.get("open", 0.0),
                high=polygon_data.get("high", 0.0),
                low=polygon_data.get("low", 0.0),
                close=polygon_data.get("close", 0.0)
            )
            logger.info(f"Successfully fetched daily open/close for {symbol_upper} from Polygon.io.")
        else:
            status_message += " (Polygon daily data not available)"
            logger.warning(f"Polygon daily data not available for {symbol_upper} on {today_str}.")

        # 3. Fetch Company Name from Polygon.io
        company_details = await polygon_service.get_company_details(symbol_upper)
        if company_details and company_details.get("name"):
            company_name = company_details["name"]
            logger.info(f"Successfully fetched company name for {symbol_upper} from Polygon.io.")
        else:
            status_message += " (Company name not found)"
            logger.warning(f"Company name not found for {symbol_upper} from Polygon.io.")

        # 4. Scrape Performance and Competitors from MarketWatch
        scraped_data = await marketwatch_scraper.scrape_performance_and_competitors(symbol_upper)
        if scraped_data:
            performance_data = scraped_data["performance_data"]
            competitors = scraped_data["competitors"]
            logger.info(f"Successfully scraped performance and competitors for {symbol_upper} from MarketWatch.")
        else:
            status_message += " (MarketWatch data not available)"
            logger.warning(f"MarketWatch data not available for {symbol_upper}.")

    except HTTPException as e:
        logger.error(f"HTTPException while fetching data for {symbol_upper}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching data for {symbol_upper}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An internal server error occurred: {e}")

    # 5. Construct Stock Model
    stock_data = Stock(
        status=status_message,
        request_data=date.today(),
        company_code=symbol_upper,
        company_name=company_name,
        stock_values=stock_values,
        performance_data=performance_data,
        competitors=competitors
    )

    # 6. Cache the result
    stock_cache.set(symbol_upper, stock_data)
    logger.info(f"Cached data for {symbol_upper}.")

    return stock_data

class PurchasedAmountRequest(BaseModel):
    amount: float = Field(..., description="The amount of stock purchased.")

@app.post("/stock/{stock_symbol}", status_code=status.HTTP_201_CREATED, summary="Add purchased stock record")
async def add_purchased_stock(stock_symbol: str, request: PurchasedAmountRequest, db: Session = Depends(get_db)):
    """
    Adds a record of a purchased stock amount to the database.
    """
    symbol_upper = stock_symbol.upper()
    logger.info(f"Received POST request to add {request.amount} units of {symbol_upper}.")

    new_stock_record = StockRecord(
        company_code=symbol_upper,
        purchased_amount=request.amount,
        request_data=date.today(),
        purchased_status="recorded" # Default status
    )

    try:
        db.add(new_stock_record)
        db.commit()
        db.refresh(new_stock_record)
        logger.info(f"Successfully added {request.amount} units of {symbol_upper} to database (ID: {new_stock_record.id}).")
        return {"message": f"{request.amount} units of stock {symbol_upper} were added to your stock record"}
    except Exception as e:
        db.rollback()
        logger.error(f"Database error while adding stock record for {symbol_upper}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add stock record: {e}")
