#!/usr/bin/env python3
"""
api.py — FastAPI server for the Price Compare PWA

Run with:
    uvicorn api:app --host 0.0.0.0 --port 8000
"""
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING, format="%(levelname)s [%(name)s] %(message)s")

app = FastAPI(title="Price Compare")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class CompareRequest(BaseModel):
    product: str
    zip_code: str
    retailers: Optional[list[str]] = None
    max_results: int = 10


@app.post("/api/compare")
async def compare(req: CompareRequest):
    if not req.product.strip():
        raise HTTPException(status_code=400, detail="Product name is required.")
    if not req.zip_code.strip():
        raise HTTPException(status_code=400, detail="ZIP code is required.")

    from orchestrator import run_comparison
    try:
        results = await run_comparison(
            query=req.product.strip(),
            zip_code=req.zip_code.strip(),
            retailer_filter=req.retailers or None,
            max_results=req.max_results,
            render=False,
        )
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    return {"results": results}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
