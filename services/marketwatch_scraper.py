import logging
import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException, status
from typing import List, Dict, Any, Optional
import re

from models import PerformanceData, Competitor, MarketCap

logger = logging.getLogger(__name__)


class MarketWatchScraper:
    MARKETWATCH_BASE_URL = "https://www.marketwatch.com/investing/stock/{symbol}"
    # It seems you've provided updated headers from your browser.
    # Let's use these comprehensive headers.
    HEADERS = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
        'cache-control': 'max-age=0',
        'dnt': '1',
        'priority': 'u=0, i',
        'referer': 'https://www.marketwatch.com/investing/stock/aapl', # This should ideally be dynamic
        'sec-ch-device-memory': '8',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-arch': '"x86"',
        'sec-ch-ua-full-version-list': '"Chromium";v="137.0.7151.119", "Not/A)Brand";v="24.0.0.0"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    }

    def __init__(self, marketwatch_cookie: str = ""):
        """
        Initializes the scraper with an optional MarketWatch cookie.
        The cookie is crucial for bypassing bot detection.
        """
        self.headers = self.HEADERS.copy()
        if marketwatch_cookie:
            self.headers['Cookie'] = marketwatch_cookie
            logger.info("MarketWatchScraper initialized with provided cookie.")
        else:
            logger.warning("MarketWatchScraper initialized WITHOUT a cookie. Scraping may be blocked.")

    def _parse_market_cap_string(self, market_cap_str: str) -> Optional[float]:
        """Parses market capitalization string (e.g., '1.23B', '45.6M') into a float."""
        if not market_cap_str:
            return None
        
        # Remove common currency symbols and commas before processing, keep B, M, T, K
        cleaned_str = re.sub(r'[^\dBMKTbmkt.]', '', market_cap_str).strip().upper()
        
        # Regex to capture the numerical part (digits and periods) and the unit (B, M, T, K)
        # Ensure the numerical part starts with a digit.
        match = re.match(r'(\d[\d.]*)([BMKT])?', cleaned_str)
        
        if match:
            numerical_part_str = match.group(1)
            unit = match.group(2) # This could be None if no unit is present

            # Validate numerical_part_str is not empty or just a period
            if not numerical_part_str or numerical_part_str == '.':
                logger.warning(f"Market cap numerical part is invalid: '{numerical_part_str}' from original '{market_cap_str}'")
                return None
            
            try:
                value = float(numerical_part_str)
            except ValueError:
                logger.warning(f"Could not convert '{numerical_part_str}' to float for market cap. Original: '{market_cap_str}'")
                return None

            if unit == 'B':
                return value * 1_000_000_000
            elif unit == 'M':
                return value * 1_000_000
            elif unit == 'T': # Trillion
                return value * 1_000_000_000_000
            elif unit == 'K': # Thousand
                return value * 1_000
            else: # No unit, assume it's already the raw value
                return value
        
        logger.warning(f"Market cap string did not match expected format after cleaning: '{cleaned_str}' from original '{market_cap_str}'")
        return None

    async def scrape_performance_and_competitors(self, symbol: str) -> Dict[str, Any]:
        """Scrapes performance data and competitor information from MarketWatch."""
        url = self.MARKETWATCH_BASE_URL.format(symbol=symbol.lower())
        logger.info(f"Scraping MarketWatch for performance and competitors for {symbol} at {url}")

        performance_data = PerformanceData()
        competitors = []

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            
            soup = BeautifulSoup(response.text, 'html.parser')

            # --- Scrape Performance Data ---
            # Locate the header for "Performance" first
            performance_header_span = soup.find('span', class_='label', string='Performance')
            performance_table = None
            if performance_header_span:
                # Find the parent <header> and then its next sibling <table>
                performance_header = performance_header_span.find_parent('header', class_='header--secondary')
                if performance_header:
                    # The table containing performance data is a sibling of the header
                    performance_table = performance_header.find_next_sibling('table', class_=['table', 'table--primary', 'no-heading', 'c2'])
                    logger.debug(f"Found performance_table for {symbol}: {performance_table is not None}")
            
            if performance_table:
                rows = performance_table.find_all('tr', class_='table__row')
                logger.debug(f"Performance rows found for {symbol}: {len(rows)}")
                for row in rows:
                    cells = row.find_all('td', class_='table__cell')
                    if len(cells) == 2:
                        label_text = cells[0].get_text(strip=True).lower().replace(' ', '_').replace('-', '_').replace('.', '')
                        
                        # The value is inside a ul > li with class 'content__item value'
                        ul_content = cells[1].find('ul', class_=['content', 'u-flex'])
                        value_tag = None
                        if ul_content:
                            value_tag = ul_content.find('li', class_=['content__item', 'value'])

                        if value_tag:
                            value_text = value_tag.get_text(strip=True).replace('%', '')
                            try:
                                float_value = float(value_text)
                                if '5_day' in label_text:
                                    performance_data.five_days = float_value
                                elif '1_month' in label_text:
                                    performance_data.one_month = float_value
                                elif '3_month' in label_text:
                                    performance_data.three_months = float_value
                                elif 'ytd' in label_text: # Year to Date
                                    performance_data.year_to_date = float_value
                                elif '1_year' in label_text:
                                    performance_data.one_year = float_value
                                logger.debug(f"Parsed performance: {label_text}={float_value}")
                            except ValueError:
                                logger.warning(f"Could not parse performance value '{value_text}' for {label_text} for {symbol}.")
                        else:
                            logger.warning(f"Value tag (content__item value) not found for performance label '{label_text}' for {symbol}.")
            else:
                logger.warning(f"Performance table or its containing section not found for {symbol}. This is normal if the section doesn't exist.")


            # --- Scrape Competitors ---
            # Locate the header for "Competitors" first
            competitors_header_span = soup.find('span', class_='label', string='Competitors')
            competitors_table = None
            if competitors_header_span:
                # Find the parent <header> and then its next sibling <table>
                competitors_header = competitors_header_span.find_parent('header', class_='header--secondary')
                if competitors_header:
                    competitors_table = competitors_header.find_next_sibling('table', class_=['table', 'table--primary'])
                    logger.debug(f"Found competitors_table for {symbol}: {competitors_table is not None}")
            
            if competitors_table:
                # Find the table body which contains the competitor rows
                table_body = competitors_table.find('tbody', class_='table__body')
                if table_body:
                    competitor_rows = table_body.find_all('tr', class_='table__row')
                    logger.debug(f"Competitor rows found for {symbol}: {len(competitor_rows)}")
                    for row in competitor_rows:
                        # Competitor name is in the first td, market cap in the third td
                        # Use the combined class string for finding cells
                        name_tag = row.find('td', class_='table__cell w50') 
                        market_cap_tag = row.find('td', class_='table__cell w25 number') 
                        
                        if name_tag and market_cap_tag:
                            name = name_tag.get_text(strip=True)
                            market_cap_str = market_cap_tag.get_text(strip=True)
                            
                            currency = "USD" # Default currency
                            if '¥' in market_cap_str:
                                currency = "JPY"
                            elif '₩' in market_cap_str:
                                currency = "KRW"
                            
                            # The _parse_market_cap_string now handles the cleaning of currency symbols internally
                            market_cap_value = self._parse_market_cap_string(market_cap_str) 
                            
                            if market_cap_value is not None:
                                competitors.append(Competitor(
                                    name=name,
                                    market_cap=MarketCap(currency=currency, value=market_cap_value)
                                ))
                                logger.debug(f"Parsed competitor: {name}, Market Cap: {market_cap_value}")
                            else:
                                logger.warning(f"Could not parse market cap for competitor {name}: '{market_cap_str}' for {symbol}.")
                        else:
                            logger.debug(f"Skipping competitor row due to missing name/market cap tags: {row} for {symbol}.")
                else:
                    logger.warning(f"Table body for competitors not found for {symbol}.")
            else:
                logger.warning(f"Competitors table or its containing section not found for {symbol}. This is normal if the section doesn't exist.")


        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                logger.error(f"MarketWatch scraping failed with 401 Unauthorized for {symbol}. Check MARKETWATCH_COOKIE.")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"MarketWatch scraping failed: 401 Unauthorized. Ensure a valid MARKETWATCH_COOKIE is set.")
            elif response.status_code == 404:
                logger.warning(f"MarketWatch page not found for {symbol}.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MarketWatch page not found for {symbol}.")
            logger.error(f"HTTP error from MarketWatch ({response.status_code}): {e}")
            raise HTTPException(status_code=response.status_code, detail=f"MarketWatch HTTP error: {e}")
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to MarketWatch.")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to MarketWatch.")
        except requests.exceptions.Timeout:
            logger.error("MarketWatch scraping timed out.")
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="MarketWatch scraping timed out.")
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred during MarketWatch scraping: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred with MarketWatch scraping: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while parsing MarketWatch data: {e}", exc_info=True)
            # Only raise 500 if it's truly a parsing error, not a network/HTTP error
            if not isinstance(e, HTTPException):
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred while parsing MarketWatch data: {e}")
            else:
                raise e # Re-raise original HTTPException

        return {
            "performance_data": performance_data,
            "competitors": competitors
        }