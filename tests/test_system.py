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
    import uuid
    database.init_db()
    
    test_id = f"test_{uuid.uuid4().hex[:10]}"
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

def test_government_compliance_filter():
    from compliance_filter import is_government_affiliated

    # Should detect known government handles
    assert is_government_affiliated("secgov") is True
    assert is_government_affiliated("whitehouse") is True
    assert is_government_affiliated("federalreserve") is True
    assert is_government_affiliated("cftc") is True

    # Should detect .gov or gov_ patterns
    assert is_government_affiliated("state_dept_gov") is True
    assert is_government_affiliated("energy.gov") is True

    # Should detect official political / regulatory titles in display name
    assert is_government_affiliated("john_doe", display_name="Senator John Doe") is True
    assert is_government_affiliated("jane_smith", display_name="Ministry of Economy") is True
    assert is_government_affiliated("alex_w", display_name="Governor of California") is True
    assert is_government_affiliated("bank_officer", display_name="Central Bank of Ireland") is True

    # Should detect X's official government badge labels
    assert is_government_affiliated("custom_acct", badge_label="United States government official") is True
    assert is_government_affiliated("news_outlet", badge_label="State-affiliated media") is True

    # Should NOT flag regular traders or companies
    assert is_government_affiliated("crypto_whale", display_name="Bitcoin HODLer") is False
    assert is_government_affiliated("tech_trader", display_name="Daily Stock Signals") is False
    assert is_government_affiliated("brightaxis2", display_name="BR Axis") is False
