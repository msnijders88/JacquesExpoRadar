import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def get_new_exhibitions():
    prompt = """
    Zoek actuele galerie- en architectuurtentoonstellingen in Nederland op. 
    Geef het resultaat UITSLUITEND terug als een JSON-array met objecten. 
    Geen markdown opmaak rondom de JSON, geen extra tekst.
    
    Format per item:
    {
        "title": "Naam tentoonstelling",
        "location": "Galerie/Museum, Stad",
        "url": "https://directe-link-naar-expo.nl",
        "description": "Korte beschrijving van 1-2 zinnen"
    }
    """
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        tools=[{"type": "web_search", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )
    
    text_content = ""
    for block in response.content:
        if block.type == "text":
            text_content += block.text

    clean_json = text_content.strip()
    if clean_json.startswith("```json"):
        clean_json = clean_json[7:-3].strip()
    elif clean_json.startswith("```"):
        clean_json = clean_json[3:-3].strip()

    return json.loads(clean_json)

def load_state():
    if os.path.exists("state.json"):
        with open("state.json", "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_state(state):
    with open("state.json", "w") as f:
        json.dump(state, f, indent=2)

def send_email(new_items):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    email_to = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Nieuwe Expo's in Nederland ({len(new_items)})"
    msg["From"] = smtp_user
    msg["To"] = email_to

    body = "Hier zijn de nieuw gevonden tentoonstellingen:\n\n"
    for item in new_items:
        # Veilige checks met defaults als Claude andere namen gebruikt
        title = item.get("title", "Onbekende titel")
        location = item.get("location") or item.get("venue") or item.get("city", "")
        description = item.get("description") or item.get("summary", "")
        url = item.get("url", "#")

        body += f"• {title} - {location}\n  {description}\n  Link: {url}\n\n"

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print("E-mail succesvol verzonden!")
    except Exception as e:
        print(f"Fout bij versturen van e-mail: {e}")
        raise e

def main():
    print("Ophalen van tentoonstellingen...")
    current_items = get_new_exhibitions()
    
    previous_state = load_state()
    previous_urls = {item.get("url") for item in previous_state if "url" in item}

    # Filter items op basis van unieke URL
    new_items = [item for item in current_items if item.get("url") not in previous_urls]

    if new_items:
        print(f"{len(new_items)} nieuwe expo's gevonden. E-mail verzenden...")
        send_email(new_items)
    else:
        print("Geen nieuwe expo's gevonden deze week.")

    # Geheugen bijwerken
    all_known = {item.get("url"): item for item in previous_state + current_items if "url" in item}
    save_state(list(all_known.values()))
    print("State succesvol bijgewerkt.")

if __name__ == "__main__":
    main()
