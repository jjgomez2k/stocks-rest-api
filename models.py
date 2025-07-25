from datetime import date
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class StockValues(BaseModel):
    open: float
    high: float
    low: float
    close: float

class PerformanceData(BaseModel):
    five_days: Optional[float] = None
    one_month: Optional[float] = None
    three_months: Optional[float] = None
    year_to_date: Optional[float] = None
    one_year: Optional[float] = None

class MarketCap(BaseModel):
    currency: str
    value: float

class Competitor(BaseModel):
    name: str
    market_cap: MarketCap

class Stock(BaseModel):
    status: str = Field(..., description="Status of the stock data retrieval.")
    purchased_amount: Optional[float] = Field(None, description="Amount of stock purchased (only if retrieved from DB).")
    purchased_status: Optional[str] = Field(None, description="Status of the purchased stock record (only if retrieved from DB).")
    request_data: date = Field(..., description="Date of the stock data request (YYYY-MM-DD).")
    company_code: str = Field(..., description="Stock ticker symbol.")
    company_name: str = Field(..., description="Full company name.")
    stock_values: StockValues
    performance_data: PerformanceData
    competitors: List[Competitor]