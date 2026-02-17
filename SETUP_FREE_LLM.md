# Free LLM Setup Guide - Google Gemini API

## Why Google Gemini?

✅ **Completely FREE** (generous free tier)
- 60 requests per minute
- 1,500 requests per day
- No credit card required
- Good reasoning capabilities
- Perfect for your Rating Engine calculations

## Step 1: Get Free API Key

1. Go to: https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the API key (starts with `AIza...`)

## Step 2: Add to .env File

Create or edit `.env` file in project root:

```bash
# Free Google Gemini API Key
GOOGLE_API_KEY=AIza...your_key_here
```

## Step 3: Test It

```python
# Test script
from agents import DataAnalysisAgent

agent = DataAnalysisAgent()  # Uses Google Gemini by default
print("✅ LLM setup successful!")
```

## Free Tier Limits

- **60 requests/minute** - More than enough for your use case
- **1,500 requests/day** - Plenty for development and testing
- **No cost** - Completely free!

## Alternative Free Options

If you need more requests, consider:

1. **Hugging Face Inference API** (free tier)
   - Limited requests per month
   - Multiple models available

2. **Together AI** (free tier)
   - Good for experimentation
   - Multiple models

3. **OpenAI** ($5 one-time credit)
   - Very limited, not sustainable

## Recommendation

**Stick with Google Gemini** - It's the best free option for your Rating Engine project!
