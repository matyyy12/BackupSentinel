from fastapi import FastAPI
from monitoring_app.exception_handlers import register_exception_handlers
from monitoring_app.router import router

app = FastAPI()
register_exception_handlers(app)

app.include_router(router, prefix="/api")
