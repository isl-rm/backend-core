<!-- Run pytest with coverage report -->
uv run pytest --cov-report=html

<!-- Run docker compose -->
docker compose up -d

<!-- Build docker compose -->
docker-compose up --build
