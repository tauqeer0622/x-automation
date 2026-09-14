import random
import re
from typing import Optional
from config import config
from database import add_log

class CommentGenerator:
    def __init__(self):
        pass

    def generate(self, tweet_text: str, author: str, keyword: str = "") -> str:
        """
        Generates a contextual, engaging reply to a tweet.
        Uses OpenAI LLM if an API key is configured; otherwise uses smart modular templates.
        """
        clean_text = self._sanitize_text(tweet_text)
        
        # Try LLM generation if API key is present
        if config.openai_api_key and config.openai_api_key.strip():
            try:
                ai_comment = self._generate_with_llm(clean_text, author, keyword)
                if ai_comment and len(ai_comment) > 10:
                    add_log("INFO", f"Generated AI comment for @{author}")
                    return ai_comment
            except Exception as e:
                add_log("WARN", f"LLM generation failed ({str(e)}). Falling back to smart templates.")

        # Fallback to smart dynamic template engine
        template_comment = self._generate_with_template(clean_text, author, keyword)
        add_log("INFO", f"Generated template comment for @{author}")
        return template_comment

    def _sanitize_text(self, text: str) -> str:
        # Remove URLs and extra whitespace
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _generate_with_llm(self, text: str, author: str, keyword: str) -> Optional[str]:
        from openai import OpenAI
        client = OpenAI(api_key=config.openai_api_key)

        prompt = f"""You are a community engagement expert representing {config.company_name}.
Company details: {config.company_one_liner}
Call-to-action / Website: {config.company_cta} ({config.company_url})

Tweet by @{author}:
"{text}"

Task:
Write a thoughtful, authentic reply to this post about {keyword or 'the markets'}.

Strict Requirements:
1. Length: MAXIMUM 230 characters (Strict limit!).
2. Be human, conversational, and direct. Validate or add an insightful perspective to their point.
3. Connect naturally to {config.company_name} without being pushy or spammy.
4. Do NOT use hashtags like #ad, #sponsored, or multiple hashtags.
5. Never repeat the exact prompt wording. Output ONLY the reply text."""

        response = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": "You are a concise, insightful financial & tech commentator on X."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=90,
            temperature=0.7
        )

        comment = response.choices[0].message.content.strip()
        # Clean quotes if model wrapped output
        comment = comment.strip('"\'')
        if len(comment) > 260:
            comment = comment[:257] + "..."
        return comment

    def _generate_with_template(self, text: str, author: str, keyword: str) -> str:
        text_lower = text.lower()

        # Categorize tweet topic
        is_btc = any(k in text_lower for k in ["btc", "bitcoin", "$btc"])
        is_crypto = any(k in text_lower for k in ["crypto", "eth", "ethereum", "sol", "altcoin", "defi", "web3"])
        is_stocks = any(k in text_lower for k in ["stock", "shares", "spy", "nasdaq", "earnings", "fed", "dividend", "nyse"])

        if is_btc:
            hooks = [
                "BTC volatility keeping everyone on their toes.",
                "Bitcoin's price action right now is definitely one to watch.",
                "Crucial levels being tested on BTC here.",
                "Solid perspective on Bitcoin.",
                "Patience is key with BTC cycles like this."
            ]
            insights = [
                f"Tracking real-time on-chain flows makes these swings much clearer.",
                f"Having sharp risk management in place is what separates wins from losses.",
                f"Data-driven signals help cut through the market noise right now.",
                f"Managing downside risk here is everything."
            ]
        elif is_stocks:
            hooks = [
                "Spot on observation about the stock market.",
                "Equities are reacting strongly to macro sentiment right now.",
                "Big moves happening across equities today.",
                "Interesting setup on this chart."
            ]
            insights = [
                f"Automated backtesting and volume analysis give such an edge in this market.",
                f"Watching institutional order flow closely gives the real picture here.",
                f"Staying disciplined with systematic trade rules pays off in these conditions."
            ]
        else: # General crypto or trading
            hooks = [
                "Great take on this market setup.",
                "Navigating these market conditions definitely requires precision.",
                "The shift in sentiment over the last few days has been noticeable.",
                "Interesting discussion on where the market heads next."
            ]
            insights = [
                f"Having automated analytics to filter the noise makes a massive difference.",
                f"Solid signals and speed are game-changers in fast-moving conditions.",
                f"Data-backed tools make spotting genuine trends much easier."
            ]

        # Company plugs / callouts
        plugs = [
            f"That's exactly what we focus on building at {config.company_name}.",
            f"We've been tracking this exact data flow at {config.company_name}.",
            f"Building tools to make this analysis effortless at {config.company_name}.",
            f"This is why we built {config.company_name} to simplify execution."
        ]

        # CTAs
        ctas = [
            f"{config.company_cta}",
            f"Feel free to check our profile for insights!",
            f"Always keen to share insights if you're interested!",
            f"More details on our profile if you're curious!"
        ]

        hook = random.choice(hooks)
        insight = random.choice(insights)
        plug = random.choice(plugs)
        cta = random.choice(ctas)

        # Build candidate comments with variation
        templates = [
            f"{hook} {insight} {plug} {cta}",
            f"{hook} {insight} We explore this regularly at {config.company_name}. {cta}",
            f"{insight} {plug} {cta}"
        ]

        comment = random.choice(templates)

        # Ensure fits within Twitter length buffer (max 260 chars)
        if len(comment) > 260:
            comment = f"{hook} {plug} {cta}"
            if len(comment) > 260:
                comment = f"{hook} That's our focus at {config.company_name}. {cta}"

        return comment

generator = CommentGenerator()
