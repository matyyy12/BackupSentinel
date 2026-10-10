from fastapi import FastAPI
from monitoring_app.router import router

app = FastAPI(prefix="/api")

app.include_router(router)
