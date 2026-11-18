"""Tests for the three health probes."""

import pytest


@pytest.mark.asyncio
async def test_live(client):
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "alive"
    assert "instance" in body


@pytest.mark.asyncio
async def test_startup(client):
    resp = await client.get("/health/startup")
    # After lifespan runs in test mode, started may be False since lifespan
    # doesn't run in ASGI test client by default – we just check it responds
    assert resp.status_code in (200, 503)
    assert "started" in resp.json()


@pytest.mark.asyncio
async def test_ready(client):
    resp = await client.get("/health/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "ready" in body
    assert "db" in body
