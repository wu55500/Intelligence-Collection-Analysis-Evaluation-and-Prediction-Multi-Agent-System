"""integration 的 lifespan 钩子与 /mcp/* 探针路由冒烟。"""
import logging
from contextlib import asynccontextmanager
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

logging.getLogger("mcp").setLevel(logging.ERROR)
logging.disable(logging.INFO)

from src.modules.m23_mcp.integration import m23_lifespan, create_m23_router, get_m23


def test_lifespan_and_probe_routes():
    @asynccontextmanager
    async def lifespan(app):
        async with m23_lifespan(app, backend="binutils"):
            yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(create_m23_router())
    with TestClient(app) as c:
        h = c.get("/mcp/health").json()
        t = c.get("/mcp/tools").json()
        assert h["status"] == "running" and "reverse" in h["alive"]
        assert len(t["tools"]) == 5
        assert get_m23() is not None
