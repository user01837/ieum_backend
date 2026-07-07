from fastapi import FastAPI
from app.db.database import test_connection

app = FastAPI()

test_connection()


@app.get("/")
def root():
    return {"message": "Hello IEUM Backend"}