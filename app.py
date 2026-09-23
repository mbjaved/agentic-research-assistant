"""FastAPI wrapper + minimal web UI.

Run:
    uvicorn app:app --reload
Then open http://localhost:8000
"""
import traceback

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from orchestrator import run_research

app = FastAPI(title="Agentic Research Assistant")


class RunRequest(BaseModel):
    goal: str
    rounds: int = 2


class RunResponse(BaseModel):
    title: str
    report: str
    score: int
    rounds: int
    log: list
    fact_check: dict | None = None
    sources: list = []


@app.post("/api/run")
def run(req: RunRequest):
    try:
        result = run_research(req.goal, max_rounds=req.rounds)
    except Exception as exc:
        traceback.print_exc()  # full traceback in the server terminal
        return JSONResponse(status_code=500, content={"error": f"{type(exc).__name__}: {exc}"})
    return RunResponse(
        title=result.title,
        report=result.report,
        score=result.score,
        rounds=result.rounds,
        log=result.log,
        fact_check=result.fact_check,
        sources=result.sources,
    ).model_dump()


@app.get("/")
def index():
    return FileResponse("static/index.html")


# Serve any other static assets (kept minimal for the demo).
app.mount("/static", StaticFiles(directory="static"), name="static")
