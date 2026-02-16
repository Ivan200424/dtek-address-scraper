FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Browsers already installed in the base image, but ensure chromium is available
RUN playwright install chromium

COPY . .

CMD ["python", "main.py"]
