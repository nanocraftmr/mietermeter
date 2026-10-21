FROM python:3.10-slim-buster

WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variables (optional, but good practice - override in docker-compose.yml)
ENV HDGIP1=""
ENV HDGIP2=""
ENV SUPABASE_URL=""
ENV SUPABASE_KEY=""
ENV CAMERA=""
ENV QLOG_ADDRESS=""
ENV QLOG_CHANNEL="5"
ENV SUPABASE_HEATING_TABLE="heating_meter_readings"

# Command to run the script
CMD ["python", "main.py"]