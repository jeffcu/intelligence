import os
import json
import logging
from google import genai
from google.genai import types

# Best Practice: Engage proper logging matrix instead of print()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the client. It automatically picks up GEMINI_API_KEY from environment variables.
try:
    client = genai.Client()
except Exception as e:
    logger.error(f"Failed to initialize Gemini Client. Is GEMINI_API_KEY set? Error: {e}")
    client = None

SYSTEM_PROMPT = """
You are an AI intelligence analyst for a private financial command center.
Your objective is 'De-Hype' normalization.
Analyze the provided news article (Title and Content).
1. Strip all sensationalism, emotional language, and bias.
2. Extract the core factual intelligence.
3. Calculate a 'hype_score' (0-100) based on the original emotional exaggeration.
4. Calculate an 'impact_score' (0-100) based on actual material consequence.
5. Output ONLY a raw JSON object with exactly these keys: "hype_score" (int), "impact_score" (int), and "dehyped_summary" (string).
"""

async def normalize_article(title: str, content: str) -> dict:
    """
    Takes a raw article title and content, processes it through Gemini 2.5 Flash,
    and returns a normalized intelligence dictionary.
    """
    if not client:
        logger.warning("Gemini Client offline. Returning raw fallback telemetry.")
        return {"hype_score": 0, "impact_score": 0, "dehyped_summary": f"{title} - {content}"}

    combined_text = f"Title: {title}\n\nContent: {content}"

    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=combined_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        result = json.loads(response.text)
        return {
            "hype_score": int(result.get("hype_score", 0)),
            "impact_score": int(result.get("impact_score", 0)),
            "dehyped_summary": str(result.get("dehyped_summary", ""))
        }
    except Exception as e:
        logger.error(f"De-Hype Engine misfire on article '{title}': {e}")
        # Failsafe return
        return {
            "hype_score": 0, 
            "impact_score": 0, 
            "dehyped_summary": content
        }
