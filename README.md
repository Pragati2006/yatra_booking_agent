# Vaishno Devi Yatra Booking Agent (Prototype)

A conversational, multi-agent AI prototype that plans and books Vaishno Devi
yatra slots + travel (flight, train, or bus) through a ChatGPT-style chat
interface. Built with Streamlit.

> **Important:** This is a prototype for demo purposes. Yatra darshan
> **prices** are real, researched figures (see Data Sources below); flight,
> train, bus, and hotel prices are realistic but synthetic. **Seat/slot/room
> availability for all of these is simulated** — no public dataset or API
> anywhere publishes real-time yatra slot, airline, rail, bus, or hotel
> inventory. **Payment is also simulated**. There is **no login/sign-up** —
> each browser session gets a temporary guest identity purely so booking
> history has something to group by; nothing personal is required or stored
> long-term.

## Architecture: multi-agent design

Rather than one monolithic script, the system is split into agents with
distinct responsibilities, orchestrated by a coordinator:

```
agents/
├── coordinator.py          # orchestrates every other agent for the conversation
├── conversation_agent.py   # multilingual understanding + devotional reply phrasing
├── itinerary_agent.py      # builds the day-wise pilgrimage itinerary
└── content_agent.py        # historical background + video links per place
```

Transport, darshan, and hotel search/ranking logic lives in the existing,
independently-tested `agent.py` (real-arrival-time-aware ranking - see
"Timing safety" below) and `db.py` at the project root; the coordinator
calls into those rather than duplicating that logic inside the agents
package. `app.py` only ever talks to `coordinator` - it doesn't call any
other agent directly, keeping the orchestration logic in one place.

## What's new in this version

- **Chat-first interface, no forms** — the old dropdown/date-picker search
  form is gone. You just type your trip in plain language, in whatever
  language you're comfortable with, and the agent takes it from there.
- **Multilingual conversational AI** — if an `ANTHROPIC_API_KEY` is
  configured (see below), Claude understands and can respond appropriately
  regardless of the language you write in (Hindi, Hinglish, English, etc.),
  with a respectful devotional tone ("🙏 Jai Mata Di") woven in naturally.
  Without a key, the app still works fully via rule-based English parsing —
  this is disclosed in the UI, not hidden.
- **No sign-up required** — removed the login/account system entirely.
  Each session gets a lightweight guest ID automatically.
- **Day-wise itinerary (new Step 5)** — once you've picked transport,
  darshan, an optional hotel, and optional sightseeing, the ItineraryAgent
  assembles a real day-by-day plan (arrival, rest days if needed, darshan
  day, sightseeing day, departure) before you pay.
- **Historical background + video links for every place** — both in the
  sightseeing step and the Explore Katra tab, each place now shows real,
  researched historical/mythological background and a "watch videos" link.
  Video links are constructed YouTube *search* URLs, not hardcoded video
  IDs, so they always resolve to real, current results rather than risking
  a broken or deleted specific video.
- **Multi-modal travel** — flights, trains, *and* buses, ranked together.
- **Hotel stay in Katra** — Budget/Mid-Range/Premium, real researched price
  tiers, room availability decrements per booking.
- **Jammu → Katra taxi guidance** — real researched fare ranges, shown
  both mid-booking and in the Explore Katra tab.
- **Timing safety** — transport + darshan combinations are only ever shown
  if they're actually reachable in time (real arrival time, a Jammu-Katra
  taxi buffer for flights, and a realistic trek/heli-and-queue buffer for
  the darshan category) - see `agent.py`'s `DARSHAN_PREP_BUFFER_HOURS`.
- **Mock payment gateway** — a card/UPI checkout screen before confirmation.
  No real transaction ever occurs.
- **A real 6-step flow** — *Tell us your trip (chat) → Review options → Add
  a stay → Sightseeing → Itinerary → Pay & confirm*.

## Data Sources

CSV datasets under `data/*_dataset.csv` are the actual data source — not a
live API, not random on-the-fly generation.

| Field | Status | Source |
|---|---|---|
| Yatra Registration (Normal Darshan) price | **Real** | Free, per Shrine Board (maavaishnodevi.org) |
| Helicopter Darshan price (₹4,640 round-trip) | **Real, verified** | Official Shrine Board rate, Katra–Sanjichhat route, revised Oct 2025 |
| VIP/Special Darshan price (~₹500) | **Commonly cited, not officially confirmed** | Consistent across multiple pilgrimage sites |
| Katra has its own railway station (SVDK) with direct trains from Delhi, Mumbai, Kolkata, Chennai, Ahmedabad | **Real** | Station opened 2014; widely documented. Bangalore has no confirmed direct service, so it's deliberately left out of the train dataset rather than invented. |
| Direct bus services to Katra | **Real, but Delhi-only in this dataset** | Regularly documented from Delhi; other cities' bus links weren't confirmed, so they're left out rather than guessed |
| Flight/train/bus *prices, schedules* | Realistic structure, synthetic exact figures | Flight fares calibrated against real Kaggle India flight-price datasets; train fares follow real IRCTC Sleeper/3AC/2AC tiering; none of this is live pricing |
| Jammu ↔ Katra taxi fares (₹1,300–3,800 by vehicle type) | **Real, researched** | Cross-checked across multiple cab-booking sites (Jagat Travels, CabBazar, Savaari, EaseMyTrip Cabs); ~44-55 km, ~1-1.5 hrs |
| Katra hotel price tiers (Budget ₹600-1,500 / Mid-Range ₹1,800-4,000 / Premium ₹5,000-12,000 per night) | **Real, researched price ranges; property names are generic/fictional** | Cross-checked across multiple hotel-booking sites; no real per-hotel room-inventory data exists publicly, so specific property names and room availability are simulated |
| Historical/mythological background for trek-route sites (Bhairavnath, Ardhkuwari, Charan Paduka) and Jammu heritage sites (Raghunath Temple, Bahu Fort, Amar Mahal) | **Real, cross-checked across multiple independent sources** | Legend details, construction dates, and founders verified across multiple pilgrimage-history and heritage sources |
| Historical background for Baba Dhansar, Jhajjar Kotli, Patnitop | **Honestly labeled as not having a widely documented origin story**, rather than an invented legend | — |
| Video links per place | **Real, but a search page, not a specific video** | Constructed YouTube search URLs, so they always resolve to current real results instead of a hardcoded video ID that could later break |
| All seat/slot/room availability | **Simulated** | Not public anywhere — gated behind each system's own booking backend |
| Explore Katra tourist info + local-travel notes | **Real places, general sourcing; travel cost notes are estimates** | Compiled from general pilgrimage-tourism sources; distances and local taxi/auto fares are approximate |
| Session identity | **No accounts** | Each browser session gets a temporary auto-generated guest ID; nothing personal is collected |

A real production version of this agent would need an official
data-sharing agreement with the Shrine Board, IRCTC, an airline/GDS
partner, state road transport corporations, and individual hotels for
live inventory.

## How the data layer works

- `build_dataset.py` — generates the master dataset CSVs: yatra slots,
  flights, trains, buses, and seed user accounts. Uses `day_offset`
  instead of fixed dates.
- `db.py` — on first app run, copies the dataset CSVs into "live" working
  copies with actual calendar dates computed in, plus `data/bookings.csv`.
  Bookings are **transport-mode-generic**: one booking row stores whichever
  mode (flight/train/bus) was chosen directly, rather than a foreign key
  into one specific mode's table.
- The dataset CSVs are committed to the repo; live/mutable files and
  bookings are gitignored (per-install state, not the dataset itself).

## Persistent storage (signups & bookings survive redeploys)

Optional, via a free Airtable base — see `airtable_store.py`. Setup is
unchanged from before **except the `bookings` table's columns**, which
now need to match the new transport-mode-generic, hotel-inclusive schema.
If you already set up Airtable, update your `bookings` table's fields to
exactly:

```
booking_id, user_name, pax_count, yatra_slot_id, category, slot_date,
slot_time, transport_mode, transport_no, transport_operator, origin,
destination, transport_date, departure_time, transport_price,
yatra_price, hotel_id, hotel_name, hotel_category, hotel_price_per_night,
hotel_nights, hotel_total, total_price, status, created_at
```

(All "Single line text" is fine.) There's no `users` table anymore, since
login/sign-up has been removed. If you haven't set up Airtable yet,
everything still works fine against local CSV files — this section is
optional.

## Conversational AI (multilingual mode)

By default (no API key configured), the app understands trip requests via
rule-based parsing — reliable, but English-only and keyword-based rather
than truly understanding free-form phrasing.

To enable full multilingual understanding (Hindi, Hinglish, English, or
anything else a pilgrim writes in) and warmer, more natural devotional
phrasing in replies, provide an Anthropic API key:

- **Locally:** `export ANTHROPIC_API_KEY=sk-ant-...` before running
  `streamlit run app.py`
- **On Streamlit Cloud:** add it under App settings → Secrets:
  ```toml
  ANTHROPIC_API_KEY = "sk-ant-..."
  ```

Without a key, the app is fully functional — `app.py` shows a small caption
disclosing which mode is active, rather than silently claiming multilingual
support it isn't actually providing.

## Payment

`payment.py` renders a mock card/UPI checkout between selecting a plan and
getting a confirmation ID. **Never contacts any real payment network** —
do not enter a real card number.

## Project structure

```
yatra-agent/
├── app.py                  # Streamlit UI: chat-first, tabs, 6-step booking flow
├── agents/
│   ├── coordinator.py         # orchestrates all agents for the conversation
│   ├── conversation_agent.py   # multilingual NLU + devotional reply phrasing
│   ├── itinerary_agent.py       # builds the day-wise itinerary
│   └── content_agent.py          # historical background + video links
├── agent.py                  # Transport/darshan search + real-timing-safe ranking (tested core)
├── payment.py                 # Mock payment gateway (card/UPI checkout)
├── airtable_store.py            # Optional: persist bookings to Airtable
├── db.py                          # CSV-backed data access layer (multi-modal transport + hotels)
├── explore_data.py                  # Curated places: history, video links, taxi/local-travel info
├── yatra_info.py                      # Aarti timings, registration, routes, packing, helpline
├── weather.py                           # Live forecast (Open-Meteo) + seasonal-average fallback
├── build_dataset.py                       # Builds the master CSV datasets (run once)
├── data_gen.py                              # Compatibility shim, bootstraps live data on first run
├── requirements.txt
├── .gitignore
└── data/
    ├── yatra_slots_dataset.csv   # master dataset (committed)
    ├── flights_dataset.csv        # master dataset (committed)
    ├── trains_dataset.csv          # master dataset (committed)
    ├── buses_dataset.csv            # master dataset (committed)
    ├── hotels_dataset.csv             # master dataset (committed)
    └── *_live.csv, bookings.csv         # generated on first run (gitignored)
```

Note: `auth.py` still exists in the repo from an earlier version but is no
longer called from `app.py` - login/sign-up has been removed per the "no
sign-up" requirement. It's kept only in case a future version wants to
reintroduce optional accounts.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Live data files are generated automatically on first run. No login needed —
just start typing your trip in the chat box.

### Optional: enable LLM-powered multilingual mode

```bash
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```
See "Conversational AI (multilingual mode)" above for details.

## Deploy for free (Streamlit Community Cloud)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub
3. "New app" → pick this repo/branch → main file `app.py` → Deploy
4. (Optional) Add `ANTHROPIC_API_KEY` and/or Airtable secrets under
   App settings → Secrets

## Example prompts to try

- "Book 2 people from Delhi next week"
- "I want VIP darshan for 4 pilgrims from Mumbai this week"
- "2 people from Delhi by train, helicopter darshan"
- "Book a bus for 3 people from Delhi next month"
- (With an API key configured) "2 log Delhi se agle hafte, VIP darshan chahiye"

## Roadmap / what a real version would need

- Official Shrine Board data-sharing agreement for real slot inventory
- IRCTC / airline-GDS / state transport-corporation API partnerships for
  real schedules, fares, and booking
- A real payment gateway integration (Razorpay/Stripe)
- Proper salted-hash auth or a real identity provider
- A proper database (Postgres/etc.) instead of CSV files

## Disclaimer

This project is an independent prototype and is not affiliated with or
endorsed by the Shri Mata Vaishno Devi Shrine Board, Indian Railways, or
any airline/bus operator.
