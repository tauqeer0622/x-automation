import os
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class AppConfig(BaseModel):
    # Company Profile
    company_name: str = Field(default_factory=lambda: os.getenv("COMPANY_NAME", "ApexTrading"))
    company_one_liner: str = Field(default_factory=lambda: os.getenv("COMPANY_ONE_LINER", "Next-gen AI trading terminal for crypto & equities."))
    company_cta: str = Field(default_factory=lambda: os.getenv("COMPANY_CTA", "Check out our live market insights or DM us for early access!"))
    company_url: str = Field(default_factory=lambda: os.getenv("COMPANY_URL", "https://apextrading.ai"))

    # Keywords & Targeting
    target_keywords_raw: str = Field(default_factory=lambda: os.getenv("TARGET_KEYWORDS", "crypto, BTC, bitcoin, stocks, stock market, $BTC, $ETH, crypto trading"))
    negative_keywords_raw: str = Field(default_factory=lambda: os.getenv("NEGATIVE_KEYWORDS", "airdrop, giveaway, free coins, whatsapp, presale, claim free, 100x gem"))

    # AI Configuration
    openai_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # Anti-Ban / Rate Limits
    dry_run: bool = Field(default_factory=lambda: os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes"))
    min_delay_seconds: int = Field(default_factory=lambda: int(os.getenv("MIN_DELAY_SECONDS", "90")))
    max_delay_seconds: int = Field(default_factory=lambda: int(os.getenv("MAX_DELAY_SECONDS", "240")))
    daily_comment_limit: int = Field(default_factory=lambda: int(os.getenv("DAILY_COMMENT_LIMIT", "25")))

    # Browser
    headless: bool = Field(default_factory=lambda: os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes"))
    browser_data_dir: str = Field(default_factory=lambda: os.getenv("BROWSER_DATA_DIR", "./browser_data"))

    # Direct Auth Token (optional - bypass manual login)
    x_auth_token: Optional[str] = Field(default_factory=lambda: os.getenv("X_AUTH_TOKEN", ""))

    # Server
    web_host: str = Field(default_factory=lambda: os.getenv("WEB_HOST", "127.0.0.1"))
    web_port: int = Field(default_factory=lambda: int(os.getenv("WEB_PORT", "8000")))

    @property
    def target_keywords(self) -> List[str]:
        return [k.strip() for k in self.target_keywords_raw.split(",") if k.strip()]

    @property
    def negative_keywords(self) -> List[str]:
        return [k.strip().lower() for k in self.negative_keywords_raw.split(",") if k.strip()]

    def update_from_dict(self, data: dict):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

config = AppConfig()
