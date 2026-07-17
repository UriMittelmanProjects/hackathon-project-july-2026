from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rocketride import RocketRideClient
from rocketride.core.exceptions import PipeException
from rocketride.schema import Question

state: dict = {}


async def refresh_token():
    result = await state["client"].use(filepath="pipelines/chat.pipe", use_existing=True)
    state["token"] = result["token"]
    print(f"Pipeline token refreshed: {state['token']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = RocketRideClient()
    await client.connect()
    state["client"] = client
    await refresh_token()
    yield
    await client.disconnect()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(Exception)
async def json_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"answer": f"Error: {exc}"})


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    question = Question()
    question.addQuestion(req.message)

    try:
        response = await state["client"].chat(token=state["token"], question=question)
    except PipeException:
        # Underlying pipeline task went stale (e.g. restarted by the VS Code
        # extension) - get a fresh token for the running/newly-started pipeline
        # and retry once.
        await refresh_token()
        response = await state["client"].chat(token=state["token"], question=question)

    answers = response.get("answers", [])
    return {"answer": answers[0] if answers else "No answer received."}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
