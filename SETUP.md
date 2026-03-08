# Neeman's Creative Strategy Agent — Setup & Deployment

## What This App Does
Paste any Neeman's product URL → the app auto-scrapes product data, feeds it through a brand-aligned Claude AI agent, and generates **10 static ad concepts + 5 video ad concepts** with hooks, visuals, copy, and priority recommendations.

---

## Run Locally (2 minutes)

```bash
# 1. Navigate to the app folder
cd neemans-creative-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

Open **http://localhost:8501** in your browser.
Enter your Anthropic API key in the sidebar, paste a product URL, and click **Generate**.

---

## Deploy to Streamlit Cloud (share with your team)

### Step 1: Push to GitHub

```bash
cd neemans-creative-agent

# Configure git (one-time)
git config user.email "your-email@example.com"
git config user.name "Your Name"

# Initialize and commit
git init
git add -A
git commit -m "Neeman's Creative Strategy Agent v1.0"

# Create GitHub repo and push
gh repo create neemans-creative-agent --private --push --source .
```

Or manually create a repo on github.com, then:
```bash
git remote add origin https://github.com/YOUR_USERNAME/neemans-creative-agent.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Streamlit Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io)**
2. Sign in with your GitHub account
3. Click **"New app"**
4. Select your `neemans-creative-agent` repository
5. Set **Main file path** to `app.py`
6. Click **Deploy**

### Step 3: Configure Secrets (for pre-set API key)

In Streamlit Cloud dashboard → your app → **Settings → Secrets**, add:

```toml
[secrets]
ANTHROPIC_API_KEY = "sk-ant-api03-..."
```

Then update `app.py` to read from secrets as a fallback:
```python
api_key = st.text_input("API Key", type="password") or st.secrets.get("ANTHROPIC_API_KEY", "")
```

---

## Share the App

Once deployed, you get a URL like:
**`https://neemans-creative-agent.streamlit.app`**

Share this link with anyone on your team. They just need to:
1. Open the link
2. Enter the API key (or it's pre-configured via secrets)
3. Paste a product URL
4. Click Generate

---

## Email Delivery Setup

To enable email delivery of generated strategies:

1. **Toggle "Email Delivery"** in the sidebar
2. Enter a **Gmail address** and **App Password**
   (Create an App Password at: Google Account → Security → 2-Step Verification → App Passwords)
3. Enter the **recipient email** (e.g., team@neemans.com)

---

## File Structure

```
neemans-creative-agent/
├── app.py                 # Main Streamlit application
├── brand_context.md       # Neeman's brand knowledge base (32K+ chars)
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── config.toml        # Streamlit theme (Neeman's brand colors)
├── .env.example           # Example environment variables
├── .gitignore             # Git ignore rules
└── SETUP.md               # This file
```

## Cost Per Generation

Each creative strategy generation uses ~20K input tokens + ~8K output tokens.
With Claude Sonnet: **~$0.12 per generation**
With Claude Haiku: **~$0.02 per generation** (faster, slightly less detailed)

---

## Updating the Brand Context

To update the brand guidelines, edit `brand_context.md` with new information and restart the app. The entire file is loaded as context for every generation.
