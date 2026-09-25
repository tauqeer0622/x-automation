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

        prompt = f"""You are writing a very brief reply to a post on X.
An image containing today's market news is attached alongside your reply.

Tweet by @{author}:
"{text}"

Task:
Write a VERY BRIEF reply directing the author to have a look at today's market news shown in the attached image.

Strict Requirements:
1. Length: VERY BRIEF (5 to 14 words maximum / under 90 characters).
2. Core Message: Direct them to "have a look at today's market news" shown in the attached image.
3. Natural Variations: Vary the wording across tweets so replies feel natural and not copy-pasted (e.g., "Have a look at today's market news.", "Take a look at today's market news!", "Check out today's market news breakdown.", "Here's today's market news, have a look.", "Have a look at today's top market updates.").
4. Language: Always write the reply in the SAME LANGUAGE as the tweet (e.g., if the tweet is in Spanish, write in Spanish like "Echa un vistazo a las noticias del mercado de hoy."; if in Japanese, in Japanese like "今日の市場ニュースをぜひご覧ください。"; if English, in English).
5. Do NOT include hashtags, URLs, or promotional boilerplate. Output ONLY the brief reply text."""

        response = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": "You write very brief, natural 1-sentence comments on X directing users to look at today's market news in the attached image, in the exact language of their tweet."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=40,
            temperature=0.85
        )

        comment = response.choices[0].message.content.strip()
        comment = comment.strip('"\'')
        if len(comment) > 130:
            comment = comment[:127] + "..."
        return comment

    def _generate_with_template(self, text: str, author: str, keyword: str) -> str:
        variations = [
            "Have a look at today's market news.",
            "Take a look at today's market news.",
            "Check out today's market news.",
            "Here's today's market news, have a look!",
            "Have a look at today's market news updates.",
            "Take a look at the latest market news for today.",
            "Here is a quick look at today's market news.",
            "Today's market news is out, have a look!",
            "Make sure to have a look at today's market news.",
            "Quick update: have a look at today's market news.",
            "Check out the breakdown in today's market news.",
            "Here's today's market news recap, take a look!",
            "A quick look at today's market news, check it out.",
            "Have a look at what's moving in today's market news."
        ]
        return random.choice(variations)

generator = CommentGenerator()
