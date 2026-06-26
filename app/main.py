from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.router.endpoint import router

app = FastAPI(title="Bailian Knowledge Base Service")
app.include_router(router)


@app.get("/")
def health_check():
    return {"message": "Bailian knowledge base service is running."}
