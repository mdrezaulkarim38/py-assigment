FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./main.py
COPY config.example.json ./config.json
COPY synthetic_generator.py ./synthetic_generator.py
COPY src ./src
# Output dir for result.json
RUN mkdir -p output
ENV MOCK_API_URL=http://mock_api:5000
ENV JOB_ID=docker-job-1
CMD ["python", "main.py", "--config", "/app/config.json", "--generate-feed"]
