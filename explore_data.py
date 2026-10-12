"""
explore_data.py
Static, curated list of real places to see around Katra, the Vaishno
Devi trek route, and Jammu city — for the app's "Explore Katra" tab and
the itinerary/history features.

This is reference/informational content only (nothing here is
bookable or searched against seat inventory). Distances are drawn from
general pilgrimage-tourism sources and are approximate, not
survey-grade figures.

historical_background entries are grounded in real, cross-checked
sources for the well-documented sites (Bhairavnath Temple, Ardhkuwari,
Charan Paduka, Raghunath Temple, Bahu Fort, Amar Mahal Palace) - see
README "Data Sources" for citations. For sites without a widely
documented origin story (Baba Dhansar, Jhajjar Kotli, Patnitop), the
text says so honestly rather than inventing a legend.

video_search fields are constructed YouTube *search* URLs, not specific
video IDs - this guarantees a working, current results page rather than
a hardcoded video that could later be deleted, made private, or turn
out to be wrong.

Taxi fare figures in TAXI_INFO are grounded in real, researched
figures from multiple cab-booking sites (Jagat Travels, CabBazar,
Savaari, EaseMyTrip Cabs, etc.), cross-checked for consistency.
"""

import urllib.parse

# Real, researched: Jammu <-> Katra is ~44-55 km, ~1-1.5 hrs by road.
# Sedan fares commonly quoted ₹1,300-2,500 one-way; SUV/Tempo Traveller
# fares run higher, ₹2,500-3,800+. Figures cross-checked across several
# cab-booking sites; treated as a realistic range, not a live-quoted price.
TAXI_INFO = {
    "route": "Jammu (Airport / Railway Station) → Katra",
    "distance": "approx. 44-55 km",
    "duration": "approx. 1-1.5 hours by road",
    "options": [
        {"vehicle": "AC Sedan (Dzire, Etios, or similar)", "capacity": "up to 4", "fare_range": "₹1,300-2,500 one-way"},
        {"vehicle": "SUV (Innova or similar)", "capacity": "up to 7", "fare_range": "₹2,500-3,800 one-way"},
        {"vehicle": "Tempo Traveller", "capacity": "12-16", "fare_range": "₹3,800+ one-way, varies by group size"},
    ],
    "note": (
        "Prices vary by season, demand, and operator — treat these as a realistic planning "
        "range, not a live quote. Shared/shuttle options are usually cheaper than a private cab."
    ),
}

LOCAL_TRAVEL_NOTES = {
    "On the trek route": "Reached on foot (the pilgrimage trek itself) or by pony/palki/e-vehicle available along the route for a fee.",
    "Nearby temple": "Best reached by local taxi or auto-rickshaw from Katra town, typically a short ₹100-300 ride.",
    "Nature": "Usually a half/full-day taxi hire from Katra, roughly ₹1,500-3,000 depending on distance and wait time.",
    "Hill station": "Best reached by taxi from Jammu or Katra; a full-day hire for a hill-station trip commonly runs ₹2,500-4,500.",
    "Hill station / adventure": "Best reached by taxi from Jammu or Katra; a full-day hire for a hill-station trip commonly runs ₹2,500-4,500.",
    "Nature / heritage": "Usually a half/full-day taxi hire from Jammu, roughly ₹1,500-3,000.",
    "Jammu city": "Local taxi or auto-rickshaw from Katra, roughly ₹1,000-1,800 one-way given the distance to Jammu city.",
    "Kashmir": "Best reached using Srinagar as a hub via taxi or private vehicle; travelers from Jammu access the valley via NH-44.",
}

def _yt_search(query):
    """Builds a YouTube search URL (not a fabricated video ID) so links
    always resolve to real, current results rather than a specific video
    that might later be deleted or private."""
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)


PLACES = [
    {
        "name": "Bhairavnath Temple",
        "category": "On the trek route",
        "distance": "~3 km uphill from the main Bhawan",
        "timings": "5 AM-12 PM & 4 PM-9 PM (ropeway 8 AM-5 PM)",
        "entry_fee": "Free (₹100 one-way for the ropeway)",
        "description": (
            "A shrine many pilgrims visit right after Vaishno Devi darshan itself — "
            "local tradition holds the pilgrimage is considered incomplete without it."
        ),
        "historical_background": (
            "According to the legend, Bhairavnath was a powerful tantric sage who pursued "
            "the goddess Vaishnavi, who fled into the Trikuta hills and took the form of "
            "Mahakali to behead him at the cave entrance. Realizing her true divine nature in "
            "his dying moments, he begged forgiveness — and she granted it, along with a boon: "
            "no pilgrimage to Vaishno Devi would be complete without visiting his shrine too, "
            "which is why this stop remains a core part of the yatra to this day."
        ),
        "video_search": _yt_search("Bhairavnath Temple Vaishno Devi"),
        "image": "assets/images/places/Bhairavnath Temple.png",
        "image_file": "assets/images/places/Bhairavnath Temple.png",
    },
    {
        "name": "Ardhkuwari Cave",
        "category": "On the trek route",
        "distance": "Roughly halfway up the 13 km trek from Katra",
        "timings": "5 AM-9 PM (battery car 6:30 AM-10 PM)",
        "entry_fee": "Free (₹350 one-way for the battery car)",
        "description": (
            "A cave shrine associated with the goddess's own legend, and a natural "
            "resting point partway through the climb."
        ),
        "historical_background": (
            "Known as Garbh Joon (womb cave), this is where the goddess is said to have "
            "meditated undisturbed for nine months while fleeing Bhairavnath — mirroring a "
            "child's time in the womb. Many pilgrims crawl through the narrow original cave "
            "passage as an act of symbolic spiritual rebirth, alongside the wider passage now "
            "available for those who prefer it."
        ),
        "video_search": _yt_search("Ardhkuwari cave Vaishno Devi Garbh Joon"),
        "image": "assets/images/places/Ardhkuwari, Maa Vaishno Devi!.jpg",
        "image_file": "assets/images/places/Ardhkuwari, Maa Vaishno Devi!.jpg",
    },
    {
        "name": "Charan Paduka",
        "category": "On the trek route",
        "distance": "~1.5 km from Katra",
        "timings": "5 AM-9 PM",
        "entry_fee": "Free",
        "description": "A short, easy stop marking footprints said to belong to the goddess — good for a quick, low-effort detour early in the trek.",
        "historical_background": (
            "As the goddess paused to look back and check whether Bhairavnath was still "
            "following her, her footprints are said to have been permanently engraved into "
            "the rock at this spot — giving the place its name (charan = feet, paduka = "
            "footwear/footprints)."
        ),
        "video_search": _yt_search("Charan Paduka Vaishno Devi trek"),
        "image": "assets/images/places/Charan paduka.jpg",
        "image_file": "assets/images/places/Charan paduka.jpg",
    },
    {
        "name": "Nau Devi Cave Temple",
        "category": "Nearby temple",
        "distance": "~10 km from Katra",
        "timings": "Check locally - no fixed hours confirmed",
        "entry_fee": "Free",
        "description": "A cave temple dedicated to the nine forms of Durga, with naturally formed idols inside — a quieter, less-crowded alternative pilgrimage stop.",
        "historical_background": (
            "Dedicated to the Navadurga (nine forms of Goddess Durga), this cave temple is "
            "one of several sites in the region associated with Shakti (goddess) worship, "
            "predating and paralleling the more famous Vaishno Devi shrine itself."
        ),
        "video_search": _yt_search("Nau Devi cave temple Katra"),
        "image": "assets/images/places/Nau Devi Temple.avif",
        "image_file": "assets/images/places/Nau Devi Temple.avif",
    },
    {
        "name": "Baba Dhansar",
        "category": "Nature",
        "distance": "Day-trip distance from Katra",
        "timings": "Daytime visiting hours, not formally fixed",
        "entry_fee": "Free",
        "description": "A scenic spot with natural pools and a waterfall, popular for a relaxed break from the pilgrimage crowds.",
        "historical_background": (
            "A natural spring and waterfall site with an associated local shrine; historically "
            "significant mainly as a place of nature-worship and local pilgrimage rather than "
            "having a widely documented origin story like the main Vaishno Devi sites."
        ),
        "video_search": _yt_search("Baba Dhansar waterfall Jammu"),
        "image": "assets/images/places/Baba Dhansar.jpg",
        "image_file": "assets/images/places/Baba Dhansar.jpg",
    },
    {
        "name": "Jhajjar Kotli",
        "category": "Nature",
        "distance": "~15 km from Katra",
        "timings": "Open access, no fixed hours",
        "entry_fee": "Free",
        "description": "A picnic spot on a clear mountain stream, with a small tourism complex if you want to stay over.",
        "historical_background": (
            "A tourism-department-developed picnic spot along a mountain stream — valued "
            "mainly for its natural setting rather than any specific historical event or "
            "legend tied to the location."
        ),
        "video_search": _yt_search("Jhajjar Kotli Jammu tourism"),
        "image": "assets/images/places/Jhajjar Kotli.jpg",
        "image_file": "assets/images/places/Jhajjar Kotli.jpg",
    },
    {
        "name": "Patnitop",
        "category": "Hill station",
        "distance": "~112 km from Jammu",
        "timings": "Open access, no fixed hours",
        "entry_fee": "Free",
        "description": "A well-known Himalayan hill station with meadows and Chenab-valley views — trekking in summer, skiing in winter.",
        "historical_background": (
            "Originally called 'Patn da Talab' (pond of Patn) after a small lake near a local "
            "village, the name evolved to Patnitop over time. It developed as a hill station "
            "primarily in the 20th century, valued for its climate and scenery rather than any "
            "ancient monument."
        ),
        "video_search": _yt_search("Patnitop hill station Jammu"),
        "image": "assets/images/places/Patnitop.jpg",
        "image_file": "assets/images/places/Patnitop.jpg",
    },
    {
        "name": "Sanasar",
        "category": "Hill station / adventure",
        "distance": "Near Patnitop",
        "timings": "Open access, no fixed hours",
        "entry_fee": "Free",
        "description": "A quieter meadow destination popular for paragliding, rock climbing, and trekking.",
        "historical_background": (
            "A cup-shaped meadow (locally the name reflects its bowl-like valley shape), "
            "traditionally used by Gujjar and Bakarwal shepherd communities for grazing before "
            "it developed into an adventure-tourism destination in more recent decades."
        ),
        "video_search": _yt_search("Sanasar meadow Jammu paragliding"),
        "image": "assets/images/places/Sanasar.jpg",
        "image_file": "assets/images/places/Sanasar.jpg",
    },
    {
        "name": "Mansar Lake",
        "category": "Nature / heritage",
        "distance": "~60 km from Jammu",
        "timings": "7 AM-5 PM",
        "entry_fee": "Free entry (₹100 boating, ₹50 parking)",
        "description": "A lake with mythological ties to the Mahabharata, ringed by temples and greenery.",
        "historical_background": (
            "Local tradition connects Mansar Lake to the Mahabharata, with some accounts "
            "holding it sacred like Lake Mansarovar in Tibet. A temple dedicated to the snake "
            "deity Sheshnag stands on its banks, and the lake is a traditional site for the "
            "Hindu ritual of mundan (a child's first haircut)."
        ),
        "video_search": _yt_search("Mansar Lake Jammu"),
        "image": "assets/images/places/Mansar Lake.jpg",
        "image_file": "assets/images/places/Mansar Lake.jpg",
    },
    {
        "name": "Raghunath Temple, Jammu",
        "category": "Jammu city",
        "distance": "~45 minutes from Katra",
        "timings": "6 AM-8 PM",
        "entry_fee": "Free",
        "description": "One of North India's largest temple complexes, in the heart of Jammu city.",
        "historical_background": (
            "Construction began in 1835 under Maharaja Gulab Singh, founder of the Dogra "
            "dynasty, and was completed by his son Maharaja Ranbir Singh by 1860. The complex "
            "holds seven interconnected shrines, each with its own shikhara (spire), and is "
            "considered one of the largest temple complexes in North India. Its main deity is "
            "Lord Rama (Raghunath)."
        ),
        "video_search": _yt_search("Raghunath Temple Jammu"),
        "image": "assets/images/places/Raghunath Temple.webp",
        "image_file": "assets/images/places/Raghunath Temple.webp",
    },
    {
        "name": "Bahu Fort & Bagh-e-Bahu",
        "category": "Jammu city",
        "distance": "~45 minutes from Katra",
        "timings": "10 AM-5 PM",
        "entry_fee": "₹10/person (₹50 for camera)",
        "description": "A historic Dogra-era fort with a garden overlooking the Tawi river — a good sunset stop.",
        "historical_background": (
            "Believed to be the oldest structure in Jammu, with origins traced back roughly "
            "3,000 years to Raja Bahulochan, said to be the brother of Jammu's founder. The "
            "fort was rebuilt and expanded multiple times over the centuries, with its current "
            "form largely shaped by Maharaja Gulab Singh in the 19th century. It houses a Kali "
            "temple known locally as Bawey Wali Mata, and overlooks the terraced Mughal-style "
            "Bagh-e-Bahu gardens below."
        ),
        "video_search": _yt_search("Bahu Fort Jammu"),
        "image": "assets/images/places/Bahu Fort & Bagh-e-bahu.jpg",
        "image_file": "assets/images/places/Bahu Fort & Bagh-e-bahu.jpg",
    },
    {
        "name": "Amar Mahal Palace",
        "category": "Jammu city",
        "distance": "~45 minutes from Katra",
        "timings": "9 AM-1 PM & 2 PM-5 PM, closed Mondays & national holidays",
        "entry_fee": "₹20 adults, ₹10 children",
        "description": "A 19th-century palace built in a French-chateau style, now a museum with miniature paintings and manuscripts.",
        "historical_background": (
            "Commissioned by Raja Amar Singh and designed by a French architect in the style "
            "of a French chateau, the palace was planned in 1862 though actually built in the "
            "1890s. It later served as the last official residence of the Dogra dynasty. "
            "Converted into a museum in 1975 (inaugurated by then-Prime Minister Indira "
            "Gandhi), it now houses a 120 kg gold throne, Pahari and Kangra miniature "
            "paintings, and a library of roughly 25,000 antique books."
        ),
        "video_search": _yt_search("Amar Mahal Palace Jammu"),
        "image": "assets/images/places/amar mahal.jpg",
        "image_file": "assets/images/places/amar mahal.jpg",
    },
    {
        "name": "Ban Ganga",
        "category": "On the trek route",
        "distance": "~6 km from Katra, the first stop on the trek",
        "timings": "5 AM-9 PM",
        "entry_fee": "Free",
        "description": "A stream where pilgrims traditionally take a quick dip before continuing the climb — the very first stop on the route from Katra.",
        "historical_background": (
            "Tradition holds that when the goddess's companion grew thirsty partway up the trail, "
            "she struck the ground with an arrow (baan) and a stream sprang up — giving Ban Ganga "
            "its name. It's also called Bal Ganga in some tellings, said to be where she washed her "
            "hair. Either way, it's become the customary spot to pause and freshen up before the "
            "climb properly begins."
        ),
        "video_search": _yt_search("Ban Ganga Vaishno Devi trek"),
        "image": "assets/images/places/Ban Ganga.jpg",
        "image_file": "assets/images/places/Ban Ganga.jpg",
    },
    {
        "name": "Himkoti",
        "category": "On the trek route",
        "distance": "~15 km from Katra, on the newer Tarakote Marg route",
        "timings": "5 AM-9 PM (battery car 6:30 AM-10 PM)",
        "entry_fee": "Free (₹350 one-way for the battery car)",
        "description": "A viewpoint on the newer, gentler trek route, with sweeping valley views and a spot to rest partway up.",
        "historical_background": (
            "Unlike most stops on the yatra, Himkoti carries no religious legend of its own — it's "
            "valued purely for the view. It sits on the newer Tarakote Marg route, which is slightly "
            "shorter and less steep than the traditional path, and has been developed by the Shrine "
            "Board with gardens and rest areas for pilgrims taking that route."
        ),
        "video_search": _yt_search("Himkoti viewpoint Vaishno Devi"),
        "image": "assets/images/places/Himkoti.jpg",
        "image_file": "assets/images/places/Himkoti.jpg",
    },
    {
        "name": "Dera Baba Banda Bahadur",
        "category": "Nearby temple",
        "distance": "~28 km from Katra, on the banks of the Chenab",
        "timings": "5 AM-12 PM & 4 PM-9 PM",
        "entry_fee": "Free",
        "description": "A 300-year-old Sikh gurudwara on the Chenab riverbank, honoring a commander from Guru Gobind Singh's army.",
        "historical_background": (
            "This gurudwara is dedicated to Baba Banda Singh Bahadur, a commanding soldier under "
            "Guru Gobind Singh, and is said to hold relics from his life. The white-marble complex "
            "draws large crowds every April for a three-day mela around Vaisakhi, with continuous "
            "kirtan and the site lit up for the occasion."
        ),
        "video_search": _yt_search("Dera Baba Banda Bahadur gurudwara"),
        "image": "assets/images/places/Dera Baba Banda Bahadur.jpg",
        "image_file": "assets/images/places/Dera Baba Banda Bahadur.jpg",
    },
    {
        "name": "Shiv Khori",
        "category": "Nearby temple",
        "distance": "~80 km from Katra",
        "timings": "7 AM-5 PM",
        "entry_fee": "Free",
        "description": "A natural limestone cave shrine to Shiva, with a short trek in from Ransoo — a popular add-on trip for those with an extra day.",
        "historical_background": (
            "Shiv Khori (khori meaning 'cave') centers on a naturally formed Shivling inside a long, "
            "narrow limestone cave, constantly moistened by mineral-rich water dripping from the "
            "ceiling. Local tradition holds the cave continues on much further than the roughly "
            "130 metres pilgrims are actually permitted to walk, with the remainder considered too "
            "unsafe to explore. It draws large crowds during its own Maha Shivratri mela each year."
        ),
        "video_search": _yt_search("Shiv Khori cave temple Jammu"),
        "image": "assets/images/places/Shiv Khori.jpg",
        "image_file": "assets/images/places/Shiv Khori.jpg",
    },
    {
        "name": "Peer Kho Cave Temple",
        "category": "Jammu city",
        "region": "Jammu",
        "distance": "~45 minutes from Katra",
        "timings": "5 AM-7 PM",
        "entry_fee": "Free",
        "description": "An old Shiva cave temple overlooking the Tawi river in Jammu city, with three connected shrine caves.",
        "historical_background": (
            "The cave is named for a 15th-century saint who came to be known as Peer-i-Kho after "
            "residing here (kho means cave locally). It's also linked to Jamvant, the bear-god "
            "figure from the Ramayana, said to have meditated in the same cave system — giving it "
            "the alternate name Jamwant Cave. The complex holds three connected shrines dedicated "
            "to Shiva, Navadurga, and Jamvant."
        ),
        "video_search": _yt_search("Peer Kho cave temple Jammu"),
        "image": "assets/images/places/Peer Kho Cave Temple.jpg",
        "image_file": "assets/images/places/Peer Kho Cave Temple.jpg",
    },
    {
        "name": "Srinagar (Dal Lake & Gardens)",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "Within Srinagar (~290 km from Jammu)",
        "location_route": "Located within Srinagar. Jammu to Srinagar is approximately 290 km and 6–7 hours by road via NH-44. Local travel within Srinagar is required to reach the lake and individual gardens.",
        "timings": "Open access, Shikara rides 6 AM-8 PM",
        "entry_fee": "Shikara rides ₹500-1200/hr",
        "description": "The summer capital of J&K, world-famous for Dal Lake, iconic wooden Shikaras, houseboats, and royal Mughal gardens.",
        "historical_background": (
            "Srinagar was founded by Emperor Ashoka in the 3rd century BC as Srinagari. Later under Mughal emperors "
            "Jahangir and Shah Jahan, lush terraced gardens like Shalimar Bagh and Nishat Bagh were laid out along Dal Lake."
        ),
        "video_search": _yt_search("Srinagar Dal Lake Kashmir tourism"),
        "image": "assets/images/places/Dal Lake.jpg",
        "image_file": "assets/images/places/Dal Lake.jpg",
    },
    {
        "name": "Gulmarg (Snow Meadow)",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~60 km from Srinagar (~1.5–2.5 hrs)",
        "location_route": "About 60 km from Srinagar via Tangmarg, typically a 1.5–2.5-hour drive. Travellers coming from Jammu should allow additional time to reach Srinagar first.",
        "timings": "Gondola 9 AM-4 PM",
        "entry_fee": "Gondola Phase 1 ₹740, Phase 2 ₹950",
        "description": "Asia's premier skiing destination, featuring the Gulmarg Gondola (one of the world's highest cable cars) and pine meadows.",
        "historical_background": (
            "Originally named 'Gaurimarg' after Goddess Gauri, it was renamed 'Gulmarg' (Meadow of Flowers) by Sultan Yusuf Shah in the 16th century. "
            "It became a favorite retreat for Mughal Emperor Jahangir and later a British hill station."
        ),
        "video_search": _yt_search("Gulmarg Gondola skiing Kashmir"),
        "image": "assets/images/places/Gulmarg.jpg",
        "image_file": "assets/images/places/Gulmarg.jpg",
    },
    {
        "name": "Pahalgam (Valley of Shepherds)",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~90–96 km from Srinagar (~2–2.5 hrs)",
        "location_route": "Approximately 90–96 km from Srinagar, passing through the Anantnag area (around 2–2.5 hours by road). Travellers from Jammu should account for the Jammu–Srinagar journey plus the onward drive.",
        "timings": "Open access",
        "entry_fee": "Free (Pony rides extra)",
        "description": "A tranquil valley along the Lidder River, famous for Betaab Valley, Aru Valley, and lush pine forests.",
        "historical_background": (
            "Pahalgam (meaning 'Village of Shepherds') has historically been a nomadic grazing ground. It serves as the starting base for the annual Amarnath Yatra pilgrimage."
        ),
        "video_search": _yt_search("Pahalgam Betaab Valley Kashmir"),
        "image": "assets/images/places/Pahalgam.jpg",
        "image_file": "assets/images/places/Pahalgam.jpg",
    },
    {
        "name": "Sonamarg (Meadow of Gold)",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~80–87 km from Srinagar (~2–3 hrs)",
        "location_route": "Approximately 80–87 km from Srinagar along the Srinagar–Leh highway (NH-1), taking around 2–3 hours by road. Road conditions and seasonal restrictions may affect travel.",
        "timings": "Open access, best May-Oct",
        "entry_fee": "Free",
        "description": "Gateway to the Thajiwas Glacier and high-altitude alpine lakes with breathtaking mountain scenery.",
        "historical_background": (
            "Sonamarg (Meadow of Gold) derived its name from the golden hue of its meadows in spring and its historical role as a gateway on the ancient Silk Road connecting Kashmir to Ladakh and Tibet."
        ),
        "video_search": _yt_search("Sonamarg Thajiwas Glacier Kashmir"),
        "image": "assets/images/places/Sonmarg.jpg",
        "image_file": "assets/images/places/Sonmarg.jpg",
    },
    {
        "name": "Shankaracharya Temple, Srinagar",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "Within Srinagar city (Gopadri Hill)",
        "location_route": "Located on Shankaracharya Hill within Srinagar, overlooking Dal Lake. Requires local travel from Srinagar city, followed by the permitted approach to the hilltop temple.",
        "timings": "6 AM-8 PM",
        "entry_fee": "Free",
        "description": "An ancient hilltop temple dedicated to Lord Shiva, offering panoramic views of Srinagar city and Dal Lake.",
        "historical_background": (
            "Dedicated to Lord Shiva, the temple sits at a height of 1,100 feet above the valley floor. "
            "Saint Adi Shankaracharya visited the site in the 9th century AD, consecrating it and giving the hill its enduring name."
        ),
        "video_search": _yt_search("Shankaracharya Temple Srinagar Kashmir"),
        "image": "assets/images/places/Shankracharya Mandir.jpg",
        "image_file": "assets/images/places/Shankracharya Mandir.jpg",
    },
    {
        "name": "Kheer Bhawani Temple, Tulmulla",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~25–30 km from Srinagar (~45–60 mins)",
        "location_route": "Situated in Tulmulla, Ganderbal district, around 25–30 km from Srinagar. Usually reachable in 45–60 minutes by road.",
        "timings": "6 AM-8 PM",
        "entry_fee": "Free",
        "description": "A revered Hindu shrine dedicated to Ragnya Devi, famous for its sacred spring whose color is believed to change dynamically.",
        "historical_background": (
            "Deeply venerated by Kashmiri Pandits, the temple surrounds a natural spring associated with Goddess Ragnya. "
            "An annual mela on Jyeshta Ashtami draws thousands of devotees to Tulmulla."
        ),
        "video_search": _yt_search("Kheer Bhawani Temple Tulmulla Ganderbal"),
        "image": "assets/images/places/Kheer Bhawani Mandir.jpg",
        "image_file": "assets/images/places/Kheer Bhawani Mandir.jpg",
    },
    {
        "name": "Verinag Spring and Mughal Garden",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~78 km southeast of Srinagar (~2 hrs)",
        "location_route": "Located in South Kashmir along the Jammu–Srinagar road corridor, approximately 78 km southeast of Srinagar. A potential sightseeing stop when travelling towards the Kashmir Valley.",
        "timings": "9 AM-7 PM",
        "entry_fee": "₹20",
        "description": "The historic source of the Jhelum River, featuring an octagonal stone basin and lush Mughal garden built by Jahangir and Shah Jahan.",
        "historical_background": (
            "Emperor Jahangir was enchanted by the deep blue spring of Verinag and commissioned the octagonal stone basin in 1620 AD. "
            "His son Shah Jahan later laid out the cascading Mughal garden surrounding it."
        ),
        "video_search": _yt_search("Verinag Spring Mughal Garden Kashmir"),
        "image": "assets/images/places/Verinag.jpg",
        "image_file": "assets/images/places/Verinag.jpg",
    },
    {
        "name": "Achabal Mughal Garden",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~58 km from Srinagar (~1.5 hrs)",
        "location_route": "Located in Anantnag district, approximately 58 km from Srinagar, usually around 1.5 hours by road. It can be combined with other South Kashmir attractions.",
        "timings": "9 AM-7 PM",
        "entry_fee": "₹20",
        "description": "An exquisite Mughal garden built by Empress Noor Jahan, known for its freshwater springs, terraced lawns, and majestic chinar trees.",
        "historical_background": (
            "Designed in 1620 AD by Empress Noor Jahan as a royal pleasure retreat, Achabal features water channels fed by natural mountain springs cascading over carved stone stepped falls."
        ),
        "video_search": _yt_search("Achabal Mughal Garden Anantnag Kashmir"),
        "image": "assets/images/places/Achabal.jpg",
        "image_file": "assets/images/places/Achabal.jpg",
    },
    {
        "name": "Martand Sun Temple, Mattan",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~60–65 km from Srinagar (~1.5–2 hrs)",
        "location_route": "Located near Mattan in Anantnag district, roughly 60–65 km from Srinagar, usually around 1.5–2 hours by road. It can be combined with other South Kashmir destinations.",
        "timings": "6 AM-7 PM",
        "entry_fee": "Free",
        "description": "Impressive 8th-century stone temple ruins dedicated to Surya (the Sun God), showcasing grand Kashmiri Hindu architecture.",
        "historical_background": (
            "Built by King Lalitaditya Muktapida of the Karkota dynasty in the 8th century AD, the Martand Sun Temple was a pinnacle of Kashmiri architecture, "
            "blending Greek, Roman, and Indian stylistic elements atop a plateau overlooking the Kashmir Valley."
        ),
        "video_search": _yt_search("Martand Sun Temple Mattan Anantnag Kashmir"),
        "image": "assets/images/places/Martand Sun Temple.jpg",
        "image_file": "assets/images/places/Martand Sun Temple.jpg",
    },
    {
        "name": "Sinthan Top",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~105–130 km from Srinagar (~3–4.5 hrs)",
        "location_route": "A high-altitude mountain pass reached via Anantnag, Kokernag and Daksum, roughly 105–130 km from Srinagar (3–4.5 hours by road). Access depends on weather and road conditions, especially in winter.",
        "timings": "Daytime access (weather permitting)",
        "entry_fee": "Free",
        "description": "A majestic mountain pass (12,500 ft) connecting South Kashmir to Kishtwar, offering 360-degree views of snow-capped peaks.",
        "historical_background": (
            "Situated at an elevation of 3,748 metres on the Anantnag-Kishtwar road, Sinthan Top has emerged as a major offbeat destination in J&K, "
            "offering panoramic views of both Kashmir Valley and the Jammu region."
        ),
        "video_search": _yt_search("Sinthan Top Anantnag Kashmir pass"),
        "image": "assets/images/places/Sinthan top.jpg",
        "image_file": "assets/images/places/Sinthan top.jpg",
    },
    {
        "name": "Katra",
        "category": "Pilgrimage Base",
        "region": "Jammu",
        "distance": "Base town (~45 km from Jammu)",
        "location_route": "Located ~45 km from Jammu city, accessible via NH-44 and the Jammu-Udhampur-Katra rail line.",
        "timings": "Open access, 24/7 yatra base",
        "entry_fee": "Free (Yatra RFID Card mandatory)",
        "description": "Base town for the sacred 13 km trek to Shri Mata Vaishno Devi Bhawan, nestled at the foot of Trikuta hills.",
        "historical_background": (
            "Historically a small village in the Reasi district, Katra grew into the primary base camp "
            "for pilgrims visiting the holy shrine of Shri Mata Vaishno Devi. It now features modern hotel "
            "infrastructure, market bazaars for dry fruits and offerings, and the main Yatra registration counters."
        ),
        "video_search": _yt_search("Katra base town Vaishno Devi Yatra"),
        "image": "assets/images/places/vaishno devi.jpg",
        "image_file": "assets/images/places/vaishno devi.jpg",
    },
    {
        "name": "Kashmir Valley",
        "category": "Kashmir",
        "region": "Kashmir",
        "distance": "~290 km from Jammu (~6–7 hrs)",
        "location_route": "Located in northern Jammu & Kashmir, accessible from Jammu via NH-44 highway or direct flights to Srinagar Airport (SXR).",
        "timings": "Open access, seasonal activities",
        "entry_fee": "Varies by attraction",
        "description": "Explore Srinagar's Dal Lake, Gulmarg's snow gondola, Pahalgam's pristine alpine streams, and Sonamarg's golden meadows.",
        "historical_background": (
            "The Kashmir Valley is renowned worldwide for its majestic Himalayan landscapes, serene lakes, royal Mughal gardens, "
            "and rich cultural heritage spanning ancient Hindu and Buddhist eras to medieval Mughal patronage."
        ),
        "video_search": _yt_search("Kashmir Valley tourism Srinagar Gulmarg Pahalgam"),
        "image": "assets/images/places/Dal Lake.jpg",
        "image_file": "assets/images/places/Dal Lake.jpg",
    },
]

CATEGORIES = ["On the trek route", "Nearby temple", "Nature", "Hill station", "Hill station / adventure", "Nature / heritage", "Jammu city", "Kashmir"]


def get_places(category=None):
    if category:
        return [p for p in PLACES if p["category"] == category]
    return PLACES


def get_categories():
    seen = []
    for p in PLACES:
        if p["category"] not in seen:
            seen.append(p["category"])
    return seen


def get_taxi_info():
    return TAXI_INFO


def get_local_travel_note(category):
    return LOCAL_TRAVEL_NOTES.get(category, "Local taxi or auto-rickshaw hire recommended; check current rates locally.")


def get_place_by_name(name):
    for p in PLACES:
        if p["name"] == name:
            return p
    return None
