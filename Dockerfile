FROM python:3.9-slim-buster

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

# Command to run the script
CMD ["python", "main.py"]