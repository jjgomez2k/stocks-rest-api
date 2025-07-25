# Stocks REST API

This project implements a REST API for retrieving stock data from external financial APIs and performing minor data scraping from MarketWatch. It is built using **Python** with **FastAPI**, integrates with a **PostgreSQL** database for persistence, employs a caching mechanism, and is fully containerized using **Docker** and **Docker Compose** for easy deployment and management.

---

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Environment Variables](#environment-variables)
  - [Running with Docker Compose (Recommended)](#running-with-docker-compose-recommended)
  - [Running Locally (Without Docker Compose)](#running-locally-without-docker-compose)
- [API Endpoints](#api-endpoints)
  - [Get Comprehensive Stock Data](#get-comprehensive-stock-data)
  - [Add Purchased Stock Record](#add-purchased-stock-record)
- [Testing](#testing)
- [Data Sources](#data-sources)
- [Logging](#logging)
- [Contributing](#contributing)
- [License](#license)

---

## Features
- **RESTful API**: Exposes JSON-based endpoints for stock data.
- **Stock Data Retrieval**: Fetches comprehensive stock information including daily open/close/high/low, company details, performance data, and competitors.
- **Data Persistence**: Stores purchased stock records in a PostgreSQL database.
- **Caching**: Implements a Time-To-Live (TTL) cache for GET requests to reduce external API calls and improve response times.
- **Web Scraping**: Scrapes performance metrics and competitor information from MarketWatch.
- **Containerization**: Uses Docker and Docker Compose for isolated and reproducible development/deployment environments.
- **Logging**: Comprehensive logging for monitoring and debugging.
- **Unit Tests**: Ensures the correctness and reliability of the API.

---

## Architecture

The application follows a modular and layered architecture:

- **FastAPI Application (`main.py`)**: The core of the API, handling routing, request validation, and orchestrating calls to various services.
- **Services Layer (`services/`)**: Contains dedicated modules for interacting with external APIs (Polygon.io) and performing web scraping (MarketWatch). This separation ensures clear responsibilities and makes it easier to swap or update data sources.
- **Database Layer (`database.py`)**: Manages the connection to PostgreSQL using SQLAlchemy ORM, defining the data model and providing session management.
- **Caching Layer (`cache.py`)**: A simple in-memory TTL cache to store frequently accessed stock data.
- **Models (`models.py`)**: Pydantic models for request/response validation and clear API documentation.
- **Docker Compose**: Orchestrates the app (FastAPI) and db (PostgreSQL) services, providing a fully containerized environment.

```mermaid
graph TD
    A["Client"] -->|"HTTP Request"| B("FastAPI App")
    B --> C{"Cache"}
    C -->|"Cache Hit"| A
    C -->|"Cache Miss"| D("Polygon.io Service")
    C -->|"Cache Miss"| E("MarketWatch Scraper")
    D -->|"HTTP Request"| F["Polygon.io API"]
    E -->|"HTTP Request & Scrape"| G["MarketWatch Website"]
    B --> H("PostgreSQL Database")
    H -->|"SQLAlchemy ORM"| I["db Service"]
    I -- "Docker Network" --> B
```

---

## Prerequisites
Before you begin, ensure you have the following installed:

- **Python 3.10+**
- **pip** (Python package installer)
- **Docker Desktop** (includes Docker Engine and Docker Compose)

---

## Project Structure

```
stocks_api/
├── .env                  # Environment variables (for local dev)
├── .env.example          # Example .env file
├── Dockerfile            # Docker build instructions for the app
├── docker-compose.yml    # Defines multi-container application
├── main.py               # Main FastAPI application
├── requirements.txt      # Python dependencies
├── cache.py              # TTL caching implementation
├── database.py           # SQLAlchemy ORM setup and database model
├── models.py             # Pydantic models for API data structures
├── services/             # External service integrations
│   ├── __init__.py
│   ├── marketwatch_scraper.py # Logic for scraping MarketWatch
│   └── polygon_service.py     # Logic for interacting with Polygon.io
└── tests/                # Unit tests
    ├── __init__.py
    └── test_api.py
```

---

## Getting Started

### Environment Variables
Create a `.env` file in the root of your project. This file will be used for local development outside Docker Compose. When running with Docker Compose, the `DATABASE_URL` will be passed directly via `docker-compose.yml`.

```env
# .env
DATABASE_URL="postgresql://user:password@localhost:5432/stocks_db"
```

> **Note:** Replace `user`, `password`, and `stocks_db` with your desired PostgreSQL credentials and database name. For Docker Compose, the `db` hostname will resolve to the PostgreSQL service.

---

### Running with Docker Compose (Recommended)
This is the easiest way to get the entire application stack (API + Database) up and running.

1. **Navigate to the project root:**
   ```sh
   cd stocks-rest-api
   ```
2. **Build and start the services:**
   ```sh
   docker-compose up --build -d
   ```
   - `--build`: Builds the app image (and any other images that need building) before starting.
   - `-d`: Runs the containers in detached mode (in the background).
3. **Verify services are running:**
   ```sh
   docker-compose ps
   ```
   You should see `stocks_db` and `stocks_api_app` listed as Up.
4. **Access the API Documentation:**
   - [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)
   - [http://localhost:8000/redoc](http://localhost:8000/redoc) (ReDoc)
5. **Stop the services:**
   ```sh
   docker-compose down
   ```
   To remove persistent database data as well, use:
   ```sh
   docker-compose down -v
   ```

---

### Running Locally (Without Docker Compose)
If you prefer to run the application directly on your machine (requires a local PostgreSQL instance):

1. **Create and activate a virtual environment:**
   ```sh
   python -m venv venv
   # On macOS/Linux
   source venv/bin/activate
   # On Windows
   .\venv\Scripts\activate
   ```
2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
3. **Ensure PostgreSQL is running locally:**
   Make sure your `.env` file's `DATABASE_URL` points to your local PostgreSQL instance (e.g., `postgresql://user:password@localhost:5432/stocks_db`).
4. **Run the FastAPI application:**
   ```sh
   uvicorn main:app --reload
   ```
   The API will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## API Endpoints
All endpoints return JSON responses.

### Get Comprehensive Stock Data
**GET** `/stock/{stock_symbol}`

Returns comprehensive data for a given stock symbol, including daily values, performance metrics, and competitor information. Data is cached for 5 minutes.

- **Path Parameters:**
  - `stock_symbol` (string, required): The ticker symbol of the stock (e.g., AAPL, MSFT).

- **Response:** `200 OK` with a JSON object conforming to the Stock model.

#### Example Response (partial):
```json
{
  "status": "Success",
  "request_data": "2024-07-22",
  "company_code": "AAPL",
  "company_name": "Apple Inc.",
  "stock_values": {
    "open": 190.0,
    "high": 192.5,
    "low": 189.8,
    "close": 191.2
  },
  "performance_data": {
    "five_days": 1.5,
    "one_month": 5.0,
    "three_months": 10.0,
    "year_to_date": 15.0,
    "one_year": 20.0
  },
  "competitors": [
    {
      "name": "Microsoft Corp.",
      "market_cap": {
        "currency": "USD",
        "value": 3000000000000.0
      }
    }
  ]
}
```

---

### Add Purchased Stock Record
**POST** `/stock/{stock_symbol}`

Adds a record of a purchased stock amount to the database.

- **Path Parameters:**
  - `stock_symbol` (string, required): The ticker symbol of the stock.

- **Request Body:**
```json
{
  "amount": 5.33
}
```

- **Response:** `201 Created`

#### Example Response:
```json
{
  "message": "5.33 units of stock MSFT were added to your stock record"
}
```

---

## Testing
Unit tests are implemented using `pytest` and `httpx`. External API calls and database interactions are mocked to ensure fast and isolated tests.

1. Ensure dependencies are installed (including `pytest` and `httpx` from `requirements.txt`).
2. Run tests:
   ```sh
   pytest tests/
   ```

---

## Data Sources
- **Polygon.io:**
  - **Service:** Daily Open/Close, Company Details
  - **Endpoint:** `/v1/open-close/{stocksTicker}/{date}`, `/v3/reference/tickers/{ticker}`
  - **API Key:** `bmN7i7CrzrpKqFvgbB1fEaztCwZKSUjJ` (provided)
- **MarketWatch:**
  - **Website:** `https://www.marketwatch.com/investing/stock/{stock_symbol}`
  - **Data:** Performance and Competitors (scraped)

---

## Logging
The application uses Python's standard `logging` module. Logs are configured to output to the console, providing information about API requests, data fetching, scraping, caching, and database operations.

---

## Contributing
Contributions are welcome! Please open issues or submit pull requests for improvements or bug fixes.

---

## License
This project is licensed under the MIT License.
