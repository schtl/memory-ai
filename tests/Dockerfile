FROM python:3.12-slim
WORKDIR /app
COPY memory-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt pytest==8.3.5
COPY memory-service/app.py /app/app.py
COPY tests /app/tests
CMD ["python", "-m", "pytest", "-q", "tests/test_gateway.py"]
