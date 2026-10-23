from fastapi import FastAPI
from verification_app.exception_handlers import register_exception_handlers
from verification_app.router import router

app = FastAPI()
register_exception_handlers(app)

app.include_router(router, prefix="/api")
