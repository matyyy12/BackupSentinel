# monitoring-service

Szkielet serwisu RestoreCheck.

Uruchomienie z katalogu tego serwisu:

```sh
uv sync --locked
uv run uvicorn app.main:app --reload
```

Dokumentacja API: http://localhost:8000/docs
Przy jednoczesnym uruchamianiu lokalnym wybierz osobne porty przez `--port`.

## Docker

Z katalogu tego serwisu:

```sh
docker build -t restorecheck/monitoring-service:local .
docker run --rm -p 8000:8000 restorecheck/monitoring-service:local
```

Przy uruchamianiu kilku serwisów użyj różnych portów hosta, np. `8001:8000` i `8002:8000`.
