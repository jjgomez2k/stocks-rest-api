# Use an official Python runtime as a parent image
FROM python:3.10-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for psycopg2-binary
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose port 8000
EXPOSE 8000

# Define environment variables
ENV PYTHONUNBUFFERED 1
# DATABASE_URL will be provided by docker-compose for the 'app' service
# It should point to the 'db' service name within the docker-compose network.
# Example: postgresql://user:password@db:5432/stocks_db

# Run the application
# Use a shell form for the command to allow environment variable expansion
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
