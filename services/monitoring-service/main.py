from fastapi import FastAPI
from monitoring_app.router import router

app = FastAPI()

app.include_router(router, prefix="/api")
