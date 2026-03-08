"""
Neeman's Creative Strategy Agent
=================================
Paste a product URL -> Get 10 static + 5 video ad concepts, brand-aligned and ready to produce.

Built with Streamlit + Claude API.
"""

import streamlit as st
import requests
import json
import re
import smtplib
from datetime import datetime
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from anthropic import Anthropic

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Neeman's Creative Strategy Agent",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CUSTOM CSS — Neeman's brand look
# ──────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap');

/* Global */
.stApp { background-color: #F3F2EE; }

/* Header */
.main-header {
    font-family: 'Bebas Neue', sans-serif;
    color: #3A3A3A;
    font-size: 2.6rem;
    text-transform: uppercase;
    letter-spacing: 3px;
    margin-bottom: 0;
}
.sub-header {
    font-family: 'Inter', sans-serif;
    color: #6B6B6B;
    font-size: 1.05rem;
    margin-top: -8px;
    margin-bottom: 24px;
}

/* Product card */
.product-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 28px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.06);
    margin: 12px 0 24px 0;
}

/* Concept cards */
.concept-card {
    background: #ffffff;
    border-radius: 10px;
    padding: 22px 24px;
    margin: 14px 0;
    border-left: 5px solid #AEC3AA;
    box-shadow: 0 1px 6px rgba(0,0,0,0.05);
}
.concept-card.video { border-left-color: #3A3A3A; }
.concept-card.priority { border-left-color: #D4A574; }

/* Tags */
.brand-tag {
    display: inline-block;
    background: #AEC3AA;
    color: #3A3A3A;
    padding: 3px 14px;
    border-radius: 20px;
    font-size: 0.82rem;
    margin: 3px 4px 3px 0;
    font-family: 'Inter', sans-serif;
}
.brand-tag.price {
    background: #3A3A3A;
    color: #F3F2EE;
    font-weight: 600;
}

/* Stats row */
.stat-box {
    background: #3A3A3A;
    color: #F3F2EE;
    border-radius: 10px;
    padding: 18px;
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.stat-box .stat-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2rem;
    letter-spacing: 1px;
}
.stat-box .stat-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.7;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #3A3A3A;
}
section[data-testid="stSidebar"] .stMarkdown { color: #F3F2EE; }
section[data-testid="stSidebar"] h3 { color: #EDD8C3; font-family: 'Inter', sans-serif; }
section[data-testid="stSidebar"] label { color: #F3F2EE !important; }

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Dividers */
hr { border-color: #D4D4D0; }
</style>
""",
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────
# UTILITY FUNCTIONS
# ──────────────────────────────────────────────

def extract_handle(url: str) -> str | None:
    """Pull the product handle from a Neeman's URL."""
    m = re.search(r"/products/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def scrape_product(url: str) -> tuple[dict | None, str | None]:
    """Fetch product JSON from Neeman's Shopify API."""
    handle = extract_handle(url)
    if not handle:
        return None, "Invalid URL — could not extract product handle."
    try:
        r = requests.get(
            f"https://neemans.com/products/{handle}.json",
            timeout=15,
            headers={"User-Agent": "NeemansCreativeAgent/1.0"},
        )
        if r.status_code == 200:
            return r.json().get("product", {}), None
        return None, f"Product not found (HTTP {r.status_code})."
    except Exception as e:
        return None, f"Network error: {e}"


def product_summary(p: dict) -> dict:
    """Turn raw Shopify product JSON into a display-friendly dict."""
    variants = p.get("variants", [])
    prices = [float(v["price"]) for v in variants if v.get("price")]
    compare = [
        float(v["compare_at_price"])
        for v in variants
        if v.get("compare_at_price")
    ]
    tags = (
        p.get("tags", "").split(", ")
        if isinstance(p.get("tags"), str)
        else p.get("tags", [])
    )
    sizes = sorted(
        {v.get("option1", "") for v in variants if v.get("available")},
        key=lambda s: float(s) if s.replace(".", "").isdigit() else 0,
    )
    return {
        "title": p.get("title", ""),
        "type": p.get("product_type", ""),
        "price": f"\u20b9{min(prices):,.0f}" if prices else "N/A",
        "compare": f"\u20b9{min(compare):,.0f}" if compare else None,
        "tags": tags,
        "images": [i["src"] for i in p.get("images", [])[:6]],
        "sizes": sizes,
        "body": re.sub(r"<[^>]+>", " ", p.get("body_html", "")),
        "handle": p.get("handle", ""),
        "published": p.get("published_at", "")[:10],
    }


def load_brand_context() -> str | None:
    """Load the brand knowledge-base markdown."""
    import os

    for name in ("brand_context.md", "neemans_brand.md"):
        for base in (
            os.path.dirname(os.path.abspath(__file__)),
            os.getcwd(),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
        ):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    return f.read()
    return None


SYSTEM_PROMPT_TEMPLATE = """You are the **Neeman's Creative Strategy Agent** — an elite D2C performance-creative strategist who lives and breathes the Neeman's brand.

─── BRAND KNOWLEDGE BASE ───
{brand_context}

─── YOUR MANDATE ───
When given scraped product data you MUST execute this pipeline:

**STEP 1 — PRODUCT ANALYSIS**
Analyze price position, materials, use-cases, audience fit, whether to lead with comfort / fashion / price / sustainability.

**STEP 2 — BRAND LENS**
Apply every relevant guideline:
• Personality → "The Conscious Explorer"
• Tone → Talk, don't write · Ask questions · Avoid clichés · US English
• 3 Pillars → Comfort (rational), Fashion (social), Responsibility (personal)
• Typography → Bebas Neue Pro ALL-CAPS headlines, DIN Regular body
• Color → Coal #3A3A3A · Ecru #F3F2EE · Wool #EDD8C3 · Forest #AEC3AA · Others per manual
• Rule → No price-first hooks for premium / full-MRP products
• Rule → Sustainability is layered, never the lead

**STEP 3 — GENERATE 10 STATIC AD CONCEPTS**
Each concept MUST include these fields in a markdown table:
| Field | Detail |
|---|---|
| concept_title | … |
| hook_text | ≤ 12 words |
| visual_direction | … |
| primary_copy | … |
| supporting_copy | … |
| ad_format | single / carousel / story |
| creative_reasoning | Why this works for THIS product |
| reference_brand | Real D2C brand that inspired the pattern |

**STEP 4 — GENERATE 5 VIDEO AD CONCEPTS**
Each concept MUST include:
| Field | Detail |
|---|---|
| concept_title | … |
| hook_text | ≤ 12 words |
| duration | e.g. 15s / 30s / 45s |
| scene_breakdown | 3-5 numbered scenes |
| script_notes | Key voiceover / super lines |
| performance_signals | When to use this ad (funnel stage, audience) |
| reference_brand | Real brand that inspired this |

**STEP 5 — PRIORITIZE**
• Rank all 15 concepts by expected ROAS potential.
• Flag TOP 3 must-produce concepts.
• Note production effort (Low / Medium / High).
• Ensure ≥ 2 concepts carry a sustainability angle.
• Include a Creative Reference Map: which competitor brands → which concepts.

─── OUTPUT FORMAT ───
Use these exact markdown headings so the app can parse your response:

# PRODUCT SUMMARY
# BRAND LENS APPLIED
# STATIC AD CONCEPTS
## STATIC 1: "title"
… (repeat for 2-10)
# VIDEO AD CONCEPTS
## VIDEO 1: "title"
… (repeat for 2-5)
# PRIORITY MATRIX
# CREATIVE REFERENCE MAP

Be hyper-specific. A junior designer should be able to produce every ad from your descriptions alone.
"""


def build_user_prompt(product: dict, url: str) -> str:
    """Build the user message containing scraped product data."""
    tags = product.get("tags", "")
    if isinstance(tags, list):
        tags = ", ".join(tags)
    variants = product.get("variants", [])
    body = re.sub(r"<[^>]+>", " ", product.get("body_html", ""))
    body = re.sub(r"\s+", " ", body).strip()[:2500]

    lines = [
        "Generate a complete Creative Strategy for this Neeman's product:\n",
        f"**Product:** {product.get('title', '')}",
        f"**Type:** {product.get('product_type', '')}",
        f"**Handle:** {product.get('handle', '')}",
        f"**Price:** \u20b9{variants[0].get('price', 'N/A') if variants else 'N/A'}",
    ]
    if variants and variants[0].get("compare_at_price"):
        lines.append(
            f"**Compare-at Price:** \u20b9{variants[0]['compare_at_price']}"
        )
    lines += [
        f"**Tags:** {tags}",
        f"**Published:** {product.get('published_at', 'N/A')[:10]}",
        f"\n**Variants ({len(variants)}):**",
    ]
    for v in variants[:6]:
        lines.append(
            f"  - {v.get('title','')}: \u20b9{v.get('price','')} "
            f"(available={v.get('available',False)})"
        )
    lines += [
        f"\n**Product Description:**\n{body}",
        f"\n**Product URL:** {url}",
        "\n---\nNow execute the full creative strategy pipeline.",
    ]
    return "\n".join(lines)


def stream_strategy(product, brand_ctx, api_key, model, url):
    """Generator — yields text chunks from Claude API."""
    client = Anthropic(api_key=api_key)
    system = SYSTEM_PROMPT_TEMPLATE.format(brand_context=brand_ctx)
    user = build_user_prompt(product, url)
    with client.messages.stream(
        model=model,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def send_email(to, subject, body, cfg):
    """Send strategy via SMTP (Gmail)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["email"]
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))
    html = (
        "<div style='font-family:Arial,sans-serif;max-width:800px;margin:auto'>"
        f"<pre style='white-space:pre-wrap'>{body}</pre></div>"
    )
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(cfg.get("server", "smtp.gmail.com"), int(cfg.get("port", 587))) as s:
            s.starttls()
            s.login(cfg["email"], cfg["password"])
            s.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)


def make_docx(title, strategy_md):
    """Convert strategy markdown to a DOCX file and return bytes."""
    from docx import Document
    from docx.shared import Pt, RGBColor

    doc = Document()

    # Title
    h = doc.add_heading(f"Creative Strategy: {title}", level=0)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x3A, 0x3A, 0x3A)
    doc.add_paragraph(
        f"Generated {datetime.now().strftime('%B %d, %Y')} by Neeman's Creative Strategy Agent"
    )
    doc.add_paragraph("")

    for line in strategy_md.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            doc.add_heading(stripped[2:], level=1)
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:], level=2)
        elif stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=3)
        elif stripped.startswith("|") and "---" not in stripped:
            # Simple table row → paragraph
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            doc.add_paragraph("  |  ".join(cells), style="List Bullet")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            doc.add_paragraph(stripped[2:], style="List Bullet")
        elif stripped:
            doc.add_paragraph(stripped)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────
# SESSION STATE DEFAULTS
# ──────────────────────────────────────────────
for key, default in {
    "strategy": None,
    "product_summary": None,
    "product_raw": None,
    "history": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h2 style='font-family:Bebas Neue,sans-serif;color:#EDD8C3;letter-spacing:3px;margin-bottom:0'>NEEMAN'S</h2>",
        unsafe_allow_html=True,
    )
    st.markdown("### Configuration")

    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-api03-...",
        help="[Get a key](https://console.anthropic.com/)",
    )

    model = st.selectbox(
        "Model",
        [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-haiku-4-20250514",
        ],
        help="Sonnet → best quality / cost. Haiku → fastest.",
    )

    st.divider()
    st.markdown("### Email Delivery")
    email_on = st.toggle("Enable email delivery")
    smtp_email = smtp_pass = deliver_to = ""
    if email_on:
        smtp_email = st.text_input("Gmail address", placeholder="you@gmail.com")
        smtp_pass = st.text_input(
            "App password",
            type="password",
            help="Create at myaccount.google.com → Security → App passwords",
        )
        deliver_to = st.text_input(
            "Send results to",
            placeholder="team@neemans.com",
        )

    st.divider()
    brand_ctx = load_brand_context()
    if brand_ctx:
        st.success(f"Brand context loaded ({len(brand_ctx):,} chars)")
    else:
        st.error(
            "brand_context.md not found — place it next to app.py"
        )

    st.divider()

    # History
    if st.session_state["history"]:
        st.markdown("### History")
        for i, h in enumerate(reversed(st.session_state["history"][-5:])):
            st.caption(f"{h['time']}  —  {h['title']}")

    st.markdown("---")
    st.caption("Neeman's Creative Strategy Agent v1.0")
    st.caption("Built with Claude API + Streamlit")


# ──────────────────────────────────────────────
# MAIN CONTENT
# ──────────────────────────────────────────────
st.markdown(
    '<p class="main-header">Neeman\'s Creative Strategy Agent</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="sub-header">Paste a product URL &rarr; get 10 static + 5 video ad concepts, brand-aligned and production-ready.</p>',
    unsafe_allow_html=True,
)

# URL input row
col_url, col_btn = st.columns([5, 1])
with col_url:
    product_url = st.text_input(
        "Product URL",
        placeholder="https://neemans.com/products/begin-walk-all-day-for-men-ivory-green",
        label_visibility="collapsed",
    )
with col_btn:
    go = st.button("Generate", type="primary", use_container_width=True)


# ──────────────────────────────────────────────
# GENERATE FLOW
# ──────────────────────────────────────────────
if go:
    # Guard-rails
    if not api_key:
        st.error("Enter your Anthropic API key in the sidebar.")
        st.stop()
    if not product_url or "neemans.com" not in product_url:
        st.error("Enter a valid neemans.com product URL.")
        st.stop()
    if not brand_ctx:
        st.error("Brand context file missing.")
        st.stop()

    # ── Step 1: Scrape ─────────────────────────
    with st.status("Scraping product data...", expanded=True) as status:
        product, err = scrape_product(product_url)
        if err:
            st.error(err)
            st.stop()
        summ = product_summary(product)
        status.update(label="Product scraped", state="complete")

    # ── Product preview card ───────────────────
    st.markdown("---")
    with st.container():
        img_col, info_col = st.columns([1, 2.4])
        with img_col:
            if summ["images"]:
                st.image(summ["images"][0], use_container_width=True)
        with info_col:
            st.markdown(f"### {summ['title']}")
            price_str = summ["price"]
            if summ["compare"]:
                price_str += f"  ~~{summ['compare']}~~"
            st.markdown(price_str)

            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Type", summ["type"] or "—")
            mcol2.metric("Sizes", f"{len(summ['sizes'])} available")
            mcol3.metric("Published", summ["published"] or "—")

            tags_html = " ".join(
                f'<span class="brand-tag">{t}</span>'
                for t in summ["tags"][:12]
            )
            st.markdown(tags_html, unsafe_allow_html=True)

    # ── Step 2: Generate ───────────────────────
    st.markdown("---")
    st.subheader("Creative Strategy")

    response_box = st.empty()
    full = ""
    with st.spinner("Generating creative strategy via Claude API..."):
        try:
            for chunk in stream_strategy(
                product, brand_ctx, api_key, model, product_url
            ):
                full += chunk
                response_box.markdown(full + " **|**")
            response_box.markdown(full)
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    # Save to session
    st.session_state["strategy"] = full
    st.session_state["product_summary"] = summ
    st.session_state["product_raw"] = product
    st.session_state["history"].append(
        {
            "title": summ["title"],
            "time": datetime.now().strftime("%H:%M"),
            "url": product_url,
        }
    )

    st.success("Creative strategy generated!")

    # ── Actions row ────────────────────────────
    st.markdown("---")
    act1, act2, act3 = st.columns(3)

    with act1:
        st.download_button(
            "Download .md",
            data=full,
            file_name=f"creative_strategy_{summ['handle']}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with act2:
        try:
            docx_buf = make_docx(summ["title"], full)
            st.download_button(
                "Download .docx",
                data=docx_buf,
                file_name=f"creative_strategy_{summ['handle']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except ImportError:
            st.info("Install `python-docx` for DOCX export.")

    with act3:
        if email_on and smtp_email and smtp_pass and deliver_to:
            if st.button("Send via Email", use_container_width=True):
                ok, err = send_email(
                    deliver_to,
                    f"Creative Strategy: {summ['title']}",
                    full,
                    {"email": smtp_email, "password": smtp_pass},
                )
                if ok:
                    st.success(f"Sent to {deliver_to}")
                else:
                    st.error(f"Email failed: {err}")
        else:
            st.button(
                "Email (configure in sidebar)",
                disabled=True,
                use_container_width=True,
            )


# ──────────────────────────────────────────────
# SHOW LAST RESULT (on re-run / no new generation)
# ──────────────────────────────────────────────
elif st.session_state["strategy"]:
    summ = st.session_state["product_summary"]
    full = st.session_state["strategy"]

    st.markdown("---")
    st.caption(f"Showing last generated strategy for **{summ['title']}**")
    st.markdown(full)

    st.markdown("---")
    a1, a2, _ = st.columns(3)
    with a1:
        st.download_button(
            "Download .md",
            data=full,
            file_name=f"creative_strategy_{summ['handle']}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with a2:
        try:
            docx_buf = make_docx(summ["title"], full)
            st.download_button(
                "Download .docx",
                data=docx_buf,
                file_name=f"creative_strategy_{summ['handle']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except ImportError:
            pass

else:
    # Landing state — show example cards
    st.markdown("---")
    st.markdown("#### How it works")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class="stat-box">
                <div class="stat-value">1</div>
                <div class="stat-label">Paste product URL</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="stat-box">
                <div class="stat-value">2</div>
                <div class="stat-label">AI generates strategy</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class="stat-box">
                <div class="stat-value">3</div>
                <div class="stat-label">Download or email</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown("**What you get:**")
    st.markdown(
        """
- 10 static ad concepts (hook, visual, copy, format, reasoning)
- 5 video ad concepts (scene-by-scene breakdown, scripts)
- Priority matrix with top 3 must-produce picks
- Every concept aligned to Neeman's brand guidelines
- Download as `.md` or `.docx`, or send via email
"""
    )
