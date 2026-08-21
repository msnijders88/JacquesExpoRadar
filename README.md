# Expo-agent

Een minimaal voorbeeld van een "agent": een script dat zelfstandig (1) informatie
verzamelt, (2) die vergelijkt met wat het al wist, en (3) actie onderneemt —
in dit geval elke week een e-mail met nieuwe galerie- en architectuurtentoonstellingen
in Nederland.

## Hoe het in elkaar zit

```
expo-agent/
├── agent.py                          # de agent zelf
├── requirements.txt                  # Python-dependencies
├── state.json                        # "geheugen": wat de agent vorige keer al wist
└── .github/workflows/weekly-digest.yml  # de planning (draait elke maandag)
```

Het patroon is expres simpel gehouden zodat je het stap voor stap kan volgen
in `agent.py`:

1. **Research** — Claude krijgt de `web_search` tool en zoekt actuele expo's op.
   Het antwoord wordt als JSON teruggevraagd, zodat het script het kan verwerken
   zonder de tekst zelf te hoeven interpreteren.
2. **Geheugen** — `state.json` staat gewoon in de repo en bevat de lijst van
   vorige week. Dat is het hele "geheugen" van deze agent — geen database nodig.
3. **Filteren** — nieuwe items = items waarvan de URL nog niet in `state.json` stond.
4. **Actie** — als er nieuwe items zijn, wordt er een e-mail gestuurd. Zo niet,
   dan gebeurt er niets (geen spam bij een rustige week).
5. **Opslaan** — de volledige actuele lijst wordt teruggeschreven, GitHub Actions
   committed dat bestand terug naar de repo zodat volgende week weer vergeleken
   kan worden.

## Setup

1. **Maak een nieuwe GitHub-repo** en zet deze bestanden erin (of fork/kopieer dit mapje).

2. **Anthropic API key** — haal er een op via [console.anthropic.com](https://console.anthropic.com).

3. **E-mail versturen** — makkelijkste optie is een Gmail-account met een
   ["app-wachtwoord"](https://myaccount.google.com/apppasswords) (niet je gewone
   wachtwoord). Werkt ook met elke andere SMTP-provider (SendGrid, Mailgun, etc.)
   door `SMTP_HOST`/`SMTP_PORT` aan te passen.

4. **Secrets instellen** in de GitHub-repo onder
   `Settings → Secrets and variables → Actions → New repository secret`:
   - `ANTHROPIC_API_KEY`
   - `SMTP_USER` — het afzender-mailadres
   - `SMTP_PASS` — het (app-)wachtwoord
   - `EMAIL_TO` — waar de update naartoe moet

5. **Testen** — ga naar het tabblad *Actions* in GitHub, kies de workflow
   "Wekelijkse expo-update" en klik *Run workflow* om hem handmatig te starten
   zonder op maandag te wachten.

Na de eerste run is `state.json` nog leeg geweest, dus dan komt alles wat
gevonden wordt binnen als "nieuw". Vanaf de tweede run krijg je alleen het
verschil.

## Wat is hier het "agent"-aspect?

Geen framework, geen magie — een agent is in de kern gewoon: een LLM-call die
een taak (zoeken + structureren) uitvoert, plus code eromheen die bepaalt
*wanneer* het draait, *wat* het onthoudt, en *wat* het vervolgens doet met de
uitkomst. Dit voorbeeld laat elk van die onderdelen apart zien, zodat je ze
kan aanpassen (andere bron, ander filter, andere actie dan e-mail) zonder de
rest te snappen.

## Ideeën om uit te breiden

- Meerdere ontvangers, of per stad een aparte digest
- Ook musea of kunstbeurzen meenemen
- In plaats van e-mail: een Slack-bericht of RSS-feed genereren
- Claude vragen om ook een korte "waarom dit de moeite waard is"-duiding per stad te geven
