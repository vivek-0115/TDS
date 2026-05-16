from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.messages import HumanMessage

import os
import json

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)

# Request schema
class SentimentRequest(BaseModel):
    sentences: List[str]


@app.post("/sentiment")
async def sentiment_analysis(request: SentimentRequest):

    prompt = f"""
You are an expert sentiment analysis system.

Analyze each sentence carefully and classify its emotional sentiment into exactly one of these labels:

- happy
- sad
- neutral

Guidelines:
- happy → positive emotions, excitement, satisfaction, praise, joy, love
- sad → negative emotions, anger, disappointment, frustration, sadness, hate
- neutral → factual, informational, or emotionally unclear statements

Rules:
- Return ONLY valid JSON
- Preserve the exact input sentence text
- Return results in the SAME ORDER as input
- Do not add explanations
- Do not use markdown
- Do not output anything except JSON

Required JSON format:

{{
  "results": [
    {{
      "sentence": "example",
      "sentiment": "happy"
    }}
  ]
}}

Sentences:
{json.dumps(request.sentences, ensure_ascii=False)}
"""

    response = llm.invoke([
        HumanMessage(content=prompt)
    ])

    try:
        result = json.loads(response.content)
        return result

    except Exception:
        # fallback rule-based backup
        results = []

        happy_words = [
            "love", "great", "happy", "awesome",
            "excellent", "good", "amazing", "fantastic"
        ]

        sad_words = [
            "sad", "terrible", "bad", "hate",
            "awful", "worst", "angry", "upset"
        ]

        for sentence in request.sentences:

            text = sentence.lower()

            sentiment = "neutral"

            if any(word in text for word in happy_words):
                sentiment = "happy"

            elif any(word in text for word in sad_words):
                sentiment = "sad"

            results.append({
                "sentence": sentence,
                "sentiment": sentiment
            })

        return {"results": results}