from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "FastAPI running on Vercel"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}