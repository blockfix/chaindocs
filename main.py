# main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ChainDocs API is alive!"}
