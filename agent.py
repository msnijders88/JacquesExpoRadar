"""
Expo-agent: verzamelt wekelijks nieuwe galerie- en architectuurtentoonstellingen/events
in Nederland en mailt een update met alleen wat nieuw is t.o.v. vorige week.

Hoe het werkt (het "agent"-patroon):
1. RESEARCH  - vraag Claude (met de web_search tool) om actuele expo's op te zoeken
               en als gestructureerde JSON terug te geven.
2. GEHEUGEN  - vergelijk die lijst met state.json (wat we vorige week al kenden).
               Dit bestand is het "geheugen" van de agent tussen runs door.
3. FILTER    - bepaal welke items nieuw zijn.
4. ACTIE     - stuur een e-mail met alleen de nieuwe items (of sla het over als er niets nieuws is).
5. OPSLAAN   - schrijf de bijgewerkte lijst terug naar state.json, zodat volgende week
               weer een goede vergelijking gemaakt kan worden.

Dit script wordt wekelijks getriggerd door GitHub Actions (zie
.github/workflows/weekly-digest.yml). Je kunt het ook gewoon lokaal draaien
met `python agent.py` om te testen.
"""

import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

STATE_FILE = "state.json"
MODEL = "claude-sonnet-5"

# De zoekopdracht die aan Claude wordt gegeven. Pas dit gerust aan qua scope
# (bijv. alleen bepaalde steden, of ook musea toevoegen).
RESEARCH_PROMPT = """\
Zoek op het web naar tentoonstellingen en events die deze en komende maand
in Nederland van start gaan of lopen, in de volgende twee categorieën:
1. Galerietentoonstellingen (moderne/hedendaagse kunst, kleine en grote galeries)
2. Architectuurtentoonstellingen of -events (bijv. Nieuwe Instituut, ARCAM,
   architectuurcentra, biënnales, lezingenreeksen met een fysieke expo-component)

Focus op ACTUELE, recent aangekondigde of net geopende tentoonstellingen/events
(niet tentoonstellingen die al maanden lopen en breed bekend zijn, tenzij ze
net begonnen zijn).

Geef het resultaat terug als PUUR JSON (geen markdown, geen uitleg eromheen),
in dit formaat:

[
  {
    "title": "Naam van de tentoonstelling/event",
    "venue": "Naam van de galerie/instelling",
    "city": "Plaats",
    "category": "galerie" of "architectuur",
    "dates": "Periode, bijv. '12 sep - 9 nov 2026'",
    "url": "Link naar de aankondiging/pagina",
    "summary": "1-2 zinnen waarom dit interessant is"
  },
  ...
]

Geef maximaal 15 items, de meest relevante/actuele eerst.
"""

EMAIL_TO = os.environ["EMAIL_TO"]
EMAIL_FROM = os.environ["SMTP_USER"]
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]


# ---------------------------------------------------------------------------
# Stap 1: Research via Claude + web search
# ---------------------------------------------------------------------------

def fetch_current_exhibitions() -> list[dict]:
    client = anthropic.Anthropic()  # leest ANTHROPIC_API_KEY uit env

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": RESEARCH_PROMPT}],
    )

    # Pak alleen de tekstblokken (web_search tool-calls zitten er tussen,
    # die negeren we hier: we willen het uiteindelijke antwoord van Claude).
    text_parts = [block.text for block in response.content if block.type == "text"]
    raw = "".join(text_parts).strip()

    # Claude antwoordt soms met een ```json code block, ook al is dat niet gevraagd.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.lower().startswith("json"):
            raw = raw[4:]

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Kon Claude's antwoord niet als JSON parsen:\n{raw}") from e

    return items


# ---------------------------------------------------------------------------
# Stap 2 + 3: Geheugen laden en nieuwe items bepalen
# ---------------------------------------------------------------------------

def load_known_urls() -> set[str]:
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
    return {item["url"] for item in state.get("items", [])}


def save_state(items: list[dict]) -> None:
    state = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Stap 4: E-mail samenstellen en versturen
# ---------------------------------------------------------------------------

def build_email_html(new_items: list[dict]) -> str:
    rows = ""
    for item in new_items:
        rows += f"""
        <div style="margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #eee;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.05em;color:#888;">
            {item.get('category', '')}
          </div>
          <div style="font-size:17px;font-weight:600;margin:2px 0;">
            <a href="{item.get('url', '#')}" style="color:#111;text-decoration:none;">
              {item.get('title', 'Zonder titel')}
            </a>
          </div>
          <div style="font-size:14px;color:#444;">
            {item.get('venue', '')} — {item.get('city', '')} · {item.get('dates', '')}
          </div>
          <div style="font-size:14px;color:#666;margin-top:4px;">
            {item.get('summary', '')}
          </div>
        </div>
        """

    return f"""
    <html>
      <body style="font-family: -apple-system, Arial, sans-serif; max-width:600px; margin:0 auto;">
        <h2>Nieuwe expo's & architectuur-events deze week</h2>
        <p style="color:#666;font-size:13px;">
          {len(new_items)} nieuw(e) item(s) sinds vorige week.
        </p>
        {rows}
      </body>
    </html>
    """


def send_email(new_items: list[dict]) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Expo-update: {len(new_items)} nieuwe tentoonstelling(en)"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(build_email_html(new_items), "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())


# ---------------------------------------------------------------------------
# Orkestratie
# ---------------------------------------------------------------------------

def main() -> None:
    print("Ophalen van actuele tentoonstellingen...")
    current_items = fetch_current_exhibitions()
    print(f"Gevonden: {len(current_items)} items")

    known_urls = load_known_urls()
    new_items = [item for item in current_items if item.get("url") not in known_urls]
    print(f"Nieuw t.o.v. vorige week: {len(new_items)}")

    if new_items:
        send_email(new_items)
        print("E-mail verstuurd.")
    else:
        print("Niets nieuws, geen e-mail verstuurd.")

    # Sla altijd de volledige huidige lijst op als nieuw geheugen voor volgende week
    save_state(current_items)


if __name__ == "__main__":
    main()
