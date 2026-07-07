from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv(".env.local")

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Hello IEUM Backend"}