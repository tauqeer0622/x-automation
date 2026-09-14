import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure root dir is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import config
import database
from comment_generator import generator
from server import app

client = TestClient(app)

def test_database_operations():
    database.init_db()
    
    test_id = "test_tweet_99999"
    assert not database.is_tweet_processed(test_id)
    
    # Save post
    database.save_post(
        tweet_id=test_id,
        author="satoshi",
        content="Bitcoin block reward halving complete!",
        matched_keyword="BTC",
        url="https://x.com/satoshi/status/test_tweet_99999"
    )
    
    assert database.is_tweet_processed(test_id)
    
    # Save comment
    database.save_comment(
        tweet_id=test_id,
        author="satoshi",
        reply_text="Huge milestone for BTC. Data signals look great.",
        mode="dry_run",
        status="success"
    )
    
    comments = database.get_recent_comments(limit=5)
    assert any(c["tweet_id"] == test_id for c in comments)
    
    stats = database.get_stats()
    assert stats["total_scanned"] >= 1
    assert stats["dry_comments"] >= 1

def test_comment_generation():
    # Test Bitcoin / BTC
    btc_reply = generator.generate("Bitcoin is holding steady above 95,000", "trader_dan", "BTC")
    assert len(btc_reply) <= 280
    assert config.company_name in btc_reply
    
    # Test Stocks
    stock_reply = generator.generate("S&P 500 reached all time highs today after CPI numbers", "market_watch", "stocks")
    assert len(stock_reply) <= 280
    assert config.company_name in stock_reply

    # Test General Crypto
    crypto_reply = generator.generate("Ethereum and layer 2 ecosystems are booming", "defi_guru", "crypto")
    assert len(crypto_reply) <= 280
    assert config.company_name in crypto_reply

def test_api_endpoints():
    # Status endpoint
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "engine" in data
    assert "stats" in data
    assert "config" in data

    # Test simulation generation endpoint
    sim_res = client.post("/api/test/generate", json={
        "tweet_text": "Massive Bitcoin liquidation cascade happening right now!",
        "author": "btc_whale",
        "keyword": "BTC"
    })
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert "reply" in sim_data
    assert sim_data["length"] <= 280
    assert sim_data["author"] == "btc_whale"

    # Test settings update endpoint
    cfg_res = client.post("/api/config", json={
        "company_name": "ApexTradingPro",
        "daily_comment_limit": 30
    })
    assert cfg_res.status_code == 200
    assert config.company_name == "ApexTradingPro"
    assert config.daily_comment_limit == 30
