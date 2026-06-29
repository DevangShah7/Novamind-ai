"""Vercel serverless entrypoint.

Vercel's Python runtime looks for `api/<file>.py` and treats any `handler`
export as the AWS-Lambda-style function. This module re-exports the Mangum
wrapper from `app.main` so we don't double-define the ASGI bridge.

Local dev (`uvicorn app.main:app`) doesn't touch this file.
"""
from app.main import handler  # noqa: F401  — Mangum-wrapped ASGI app