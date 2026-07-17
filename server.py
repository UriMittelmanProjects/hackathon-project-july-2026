import json
import re
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prisma import Json, Prisma
from rocketride import RocketRideClient
from rocketride.core.exceptions import PipeException
from rocketride.schema import Question

import scraper

state: dict = {"tokens": {}}


async def get_pipeline_token(pipe_key: str, filepath: str) -> str:
    if pipe_key not in state["tokens"]:
        await refresh_pipeline_token(pipe_key, filepath)
    return state["tokens"][pipe_key]


async def refresh_pipeline_token(pipe_key: str, filepath: str) -> None:
    result = await state["client"].use(filepath=filepath, use_existing=True)
    state["tokens"][pipe_key] = result["token"]
    print(f"Pipeline '{pipe_key}' token refreshed: {result['token']}")


async def chat_with_retry(pipe_key: str, filepath: str, message: str) -> dict:
    token = await get_pipeline_token(pipe_key, filepath)
    question = Question()
    question.addQuestion(message)

    try:
        return await state["client"].chat(token=token, question=question)
    except PipeException:
        # Underlying pipeline task went stale (e.g. restarted by the VS Code
        # extension) - get a fresh token for the running/newly-started pipeline
        # and retry once.
        await refresh_pipeline_token(pipe_key, filepath)
        token = state["tokens"][pipe_key]
        return await state["client"].chat(token=token, question=question)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = RocketRideClient()
    await client.connect()
    state["client"] = client
    await refresh_pipeline_token("chat", "pipelines/chat.pipe")
    await refresh_pipeline_token("factcheck", "pipelines/factcheck.pipe")

    db = Prisma()
    await db.connect()
    state["db"] = db

    yield

    await db.disconnect()
    await client.disconnect()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(Exception)
async def json_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": f"Error: {exc}"})


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    response = await chat_with_retry("chat", "pipelines/chat.pipe", req.message)
    answers = response.get("answers", [])
    return {"answer": answers[0] if answers else "No answer received."}


# ---------------------------------------------------------------------------
# Fact-checking
# ---------------------------------------------------------------------------


class FactCheckRequest(BaseModel):
    url: str


def normalize_url(url: str) -> str:
    """Strip query string/fragment and trailing slash so trivial URL variants
    (tracking params, ?hl=en, trailing /) hit the same cache row."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_agent_json(raw_answer: str) -> dict:
    cleaned = _JSON_FENCE_RE.sub("", raw_answer).strip()
    return json.loads(cleaned)


NO_CONTENT_RESULT = {
    "has_claims": False,
    "claims": [],
    "evidence_for": [],
    "evidence_against": [],
    "verdict": "no_claims",
    "decision_summary": (
        "No spoken transcript or text content was found in this post "
        "(video descriptions/captions are not used as claim sources), so "
        "there is nothing to fact-check."
    ),
}


def serialize_evaluation(record) -> dict:
    return {
        "postUrl": record.postUrl,
        "platform": record.platform,
        "content": record.content,
        "hasClaims": record.hasClaims,
        "noContentReason": record.noContentReason,
        "claims": record.claims,
        "evidenceFor": record.evidenceFor,
        "evidenceAgainst": record.evidenceAgainst,
        "verdict": record.verdict,
        "decisionSummary": record.decisionSummary,
        "createdAt": record.createdAt.isoformat(),
    }


@app.post("/api/factcheck")
async def factcheck(req: FactCheckRequest):
    db: Prisma = state["db"]
    normalized_url = normalize_url(req.url)

    existing = await db.postevaluation.find_unique(where={"postUrl": normalized_url})
    if existing:
        return {"cached": True, **serialize_evaluation(existing)}

    try:
        scraped = await scraper.scrape(req.url)
    except scraper.UnsupportedPlatformError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except scraper.ScrapeError as e:
        return JSONResponse(status_code=502, content={"error": f"Scraping failed: {e}"})

    if scraped.content is None:
        result = NO_CONTENT_RESULT
    else:
        response = await chat_with_retry("factcheck", "pipelines/factcheck.pipe", scraped.content)
        answers = response.get("answers", [])
        if not answers:
            return JSONResponse(status_code=502, content={"error": "The fact-check agent returned no answer."})
        try:
            result = parse_agent_json(answers[0])
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=502,
                content={"error": "The fact-check agent's response wasn't valid JSON.", "raw": answers[0]},
            )

    saved = await db.postevaluation.create(
        data={
            "postUrl": normalized_url,
            "platform": scraped.platform,
            "content": scraped.content,
            "hasClaims": result["has_claims"],
            "noContentReason": scraped.no_content_reason,
            "claims": Json(result["claims"]),
            "evidenceFor": Json(result["evidence_for"]),
            "evidenceAgainst": Json(result["evidence_against"]),
            "verdict": result["verdict"],
            "decisionSummary": result["decision_summary"],
            "rawScraperOutput": Json(scraped.raw),
        }
    )

    return {"cached": False, **serialize_evaluation(saved)}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
