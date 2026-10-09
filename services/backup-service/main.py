from fastapi import FastAPI
from backup_app.router import router

app = FastAPI()

app.include_router(router, prefix="/api")
