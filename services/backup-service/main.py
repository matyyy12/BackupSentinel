from fastapi import FastAPI
from backup_app.exception_handlers import register_exception_handlers
from backup_app.router import router

app = FastAPI()
register_exception_handlers(app)

app.include_router(router, prefix="/api")
