"""
Digital Campus - KUDOS Internal World Map

KUDOS keeps its OWN map of the world so it can navigate, locate and answer
geo questions even fully offline. Places (continents, countries, capitals,
major cities, landmarks) are seeded once and stored in Postgres. Every
coordinate is an authoritative public constant — when a coordinate is not
genuinely known the place simply has lat/lon None; KUDOS never invents
positions ("never guessing, always precise").

The map layers fuse together:
  * kudos_map_places    — seeded world places (this module)
  * radio_places        — the whole world via radio towers (radio_garden.py)
  * kudos_access_points — precise Wi-Fi anchors from KUDOS devices
  * kudos_cell_towers   — precise cell towers from KUDOS devices
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models_extended import KudosMapPlace

# ──────────────────────────────────────────────
# SEED DATA — continents, countries (with capitals), key cities, landmarks
# ──────────────────────────────────────────────

_CONTINENT_COORDS = {
    "Africa": (-1.5, 20.0),
    "Asia": (34.0, 100.0),
    "Europe": (50.0, 20.0),
    "North America": (42.0, -95.0),
    "South America": (-12.0, -58.0),
    "Oceania": (-28.0, 135.0),
    "Antarctica": (-78.0, 90.0),
}

# country -> (continent, capital, capital_lat, capital_lon)
_COUNTRIES = {
    # Africa
    "Algeria": ("Africa", "Algiers", 36.7538, 3.0588),
    "Angola": ("Africa", "Luanda", -8.8390, 13.2894),
    "Benin": ("Africa", "Porto-Novo", 6.4969, 2.6287),
    "Botswana": ("Africa", "Gaborone", -24.6282, 25.9231),
    "Burkina Faso": ("Africa", "Ouagadougou", 12.3714, -1.5197),
    "Burundi": ("Africa", "Gitega", -3.4241, 29.9244),
    "Cameroon": ("Africa", "Yaounde", 3.8480, 11.5021),
    "Cape Verde": ("Africa", "Praia", 14.9330, -23.5133),
    "Central African Republic": ("Africa", "Bangui", 4.3947, 18.5582),
    "Chad": ("Africa", "N'Djamena", 12.1348, 15.0557),
    "Comoros": ("Africa", "Moroni", -11.7172, 43.2473),
    "Congo": ("Africa", "Brazzaville", -4.2634, 15.2429),
    "DR Congo": ("Africa", "Kinshasa", -4.4419, 15.2663),
    "Djibouti": ("Africa", "Djibouti", 11.8251, 42.5903),
    "Egypt": ("Africa", "Cairo", 30.0444, 31.2357),
    "Equatorial Guinea": ("Africa", "Malabo", 3.7504, 8.7371),
    "Eritrea": ("Africa", "Asmara", 15.3229, 38.9251),
    "Eswatini": ("Africa", "Mbabane", -26.3054, 31.1367),
    "Ethiopia": ("Africa", "Addis Ababa", 9.0244, 38.7469),
    "Gabon": ("Africa", "Libreville", 0.4162, 9.4673),
    "Gambia": ("Africa", "Banjul", 13.4549, -16.5790),
    "Ghana": ("Africa", "Accra", 5.6037, -0.1870),
    "Guinea": ("Africa", "Conakry", 9.6412, -13.5784),
    "Guinea-Bissau": ("Africa", "Bissau", 11.8636, -15.5977),
    "Ivory Coast": ("Africa", "Yamoussoukro", 6.8276, -5.2893),
    "Kenya": ("Africa", "Nairobi", -1.2921, 36.8219),
    "Lesotho": ("Africa", "Maseru", -29.3632, 27.5144),
    "Liberia": ("Africa", "Monrovia", 6.3008, -10.7972),
    "Libya": ("Africa", "Tripoli", 32.8872, 13.1913),
    "Madagascar": ("Africa", "Antananarivo", -18.8792, 47.5079),
    "Malawi": ("Africa", "Lilongwe", -13.9626, 33.7741),
    "Mali": ("Africa", "Bamako", 12.6392, -8.0029),
    "Mauritania": ("Africa", "Nouakchott", 18.0735, -15.9582),
    "Mauritius": ("Africa", "Port Louis", -20.1609, 57.5012),
    "Morocco": ("Africa", "Rabat", 34.0209, -6.8416),
    "Mozambique": ("Africa", "Maputo", -25.9692, 32.5732),
    "Namibia": ("Africa", "Windhoek", -22.5609, 17.0658),
    "Niger": ("Africa", "Niamey", 13.5116, 2.1254),
    "Nigeria": ("Africa", "Abuja", 9.0765, 7.3986),
    "Rwanda": ("Africa", "Kigali", -1.9441, 30.0619),
    "Sao Tome and Principe": ("Africa", "Sao Tome", 0.3365, 6.7273),
    "Senegal": ("Africa", "Dakar", 14.7167, -17.4677),
    "Seychelles": ("Africa", "Victoria", -4.6191, 55.4513),
    "Sierra Leone": ("Africa", "Freetown", 8.4845, -13.2299),
    "Somalia": ("Africa", "Mogadishu", 2.0469, 45.3182),
    "South Africa": ("Africa", "Pretoria", -25.7479, 28.2293),
    "South Sudan": ("Africa", "Juba", 4.8594, 31.5713),
    "Sudan": ("Africa", "Khartoum", 15.5007, 32.5599),
    "Tanzania": ("Africa", "Dodoma", -6.1630, 35.7516),
    "Togo": ("Africa", "Lome", 6.1256, 1.2254),
    "Tunisia": ("Africa", "Tunis", 36.8065, 10.1815),
    "Uganda": ("Africa", "Kampala", 0.3476, 32.5825),
    "Zambia": ("Africa", "Lusaka", -15.3875, 28.3228),
    "Zimbabwe": ("Africa", "Harare", -17.8252, 31.0335),
    # Asia
    "Afghanistan": ("Asia", "Kabul", 34.5553, 69.2075),
    "Armenia": ("Asia", "Yerevan", 40.1792, 44.4991),
    "Azerbaijan": ("Asia", "Baku", 40.4093, 49.8671),
    "Bahrain": ("Asia", "Manama", 26.2285, 50.5860),
    "Bangladesh": ("Asia", "Dhaka", 23.8103, 90.4125),
    "Bhutan": ("Asia", "Thimphu", 27.4728, 89.6390),
    "Brunei": ("Asia", "Bandar Seri Begawan", 4.9031, 114.9398),
    "Cambodia": ("Asia", "Phnom Penh", 11.5564, 104.9282),
    "China": ("Asia", "Beijing", 39.9042, 116.4074),
    "Cyprus": ("Asia", "Nicosia", 35.1856, 33.3823),
    "Georgia": ("Asia", "Tbilisi", 41.7151, 44.8271),
    "India": ("Asia", "New Delhi", 28.6139, 77.2090),
    "Indonesia": ("Asia", "Jakarta", -6.2088, 106.8456),
    "Iran": ("Asia", "Tehran", 35.6892, 51.3890),
    "Iraq": ("Asia", "Baghdad", 33.3152, 44.3661),
    "Israel": ("Asia", "Jerusalem", 31.7683, 35.2137),
    "Japan": ("Asia", "Tokyo", 35.6762, 139.6503),
    "Jordan": ("Asia", "Amman", 31.9539, 35.9106),
    "Kazakhstan": ("Asia", "Astana", 51.1605, 71.4704),
    "Kuwait": ("Asia", "Kuwait City", 29.3759, 47.9774),
    "Kyrgyzstan": ("Asia", "Bishkek", 42.8746, 74.5698),
    "Laos": ("Asia", "Vientiane", 17.9757, 102.6331),
    "Lebanon": ("Asia", "Beirut", 33.8938, 35.5018),
    "Malaysia": ("Asia", "Kuala Lumpur", 3.1390, 101.6869),
    "Maldives": ("Asia", "Male", 4.1755, 73.5093),
    "Mongolia": ("Asia", "Ulaanbaatar", 47.8864, 106.9057),
    "Myanmar": ("Asia", "Naypyidaw", 19.7633, 96.0785),
    "Nepal": ("Asia", "Kathmandu", 27.7172, 85.3240),
    "North Korea": ("Asia", "Pyongyang", 39.0392, 125.7625),
    "Oman": ("Asia", "Muscat", 23.5880, 58.3829),
    "Pakistan": ("Asia", "Islamabad", 33.6844, 73.0479),
    "Palestine": ("Asia", "Ramallah", 31.9038, 35.2034),
    "Philippines": ("Asia", "Manila", 14.5995, 120.9842),
    "Qatar": ("Asia", "Doha", 25.2854, 51.5310),
    "Saudi Arabia": ("Asia", "Riyadh", 24.7136, 46.6753),
    "Singapore": ("Asia", "Singapore", 1.3521, 103.8198),
    "South Korea": ("Asia", "Seoul", 37.5665, 126.9780),
    "Sri Lanka": ("Asia", "Colombo", 6.9271, 79.8612),
    "Syria": ("Asia", "Damascus", 33.5138, 36.2765),
    "Taiwan": ("Asia", "Taipei", 25.0330, 121.5654),
    "Tajikistan": ("Asia", "Dushanbe", 38.5598, 68.7870),
    "Thailand": ("Asia", "Bangkok", 13.7563, 100.5018),
    "Timor-Leste": ("Asia", "Dili", -8.5569, 125.5603),
    "Turkey": ("Asia", "Ankara", 39.9334, 32.8597),
    "Turkmenistan": ("Asia", "Ashgabat", 37.9601, 58.3261),
    "UAE": ("Asia", "Abu Dhabi", 24.4539, 54.3773),
    "Uzbekistan": ("Asia", "Tashkent", 41.2995, 69.2401),
    "Vietnam": ("Asia", "Hanoi", 21.0278, 105.8342),
    "Yemen": ("Asia", "Sanaa", 15.3694, 44.1910),
    # Europe
    "Albania": ("Europe", "Tirana", 41.3275, 19.8187),
    "Andorra": ("Europe", "Andorra la Vella", 42.5063, 1.5218),
    "Austria": ("Europe", "Vienna", 48.2082, 16.3738),
    "Belarus": ("Europe", "Minsk", 53.9006, 27.5590),
    "Belgium": ("Europe", "Brussels", 50.8503, 4.3517),
    "Bosnia and Herzegovina": ("Europe", "Sarajevo", 43.8563, 18.4131),
    "Bulgaria": ("Europe", "Sofia", 42.6977, 23.3219),
    "Croatia": ("Europe", "Zagreb", 45.8150, 15.9819),
    "Czech Republic": ("Europe", "Prague", 50.0755, 14.4378),
    "Denmark": ("Europe", "Copenhagen", 55.6761, 12.5683),
    "Estonia": ("Europe", "Tallinn", 59.4370, 24.7536),
    "Finland": ("Europe", "Helsinki", 60.1699, 24.9384),
    "France": ("Europe", "Paris", 48.8566, 2.3522),
    "Germany": ("Europe", "Berlin", 52.5200, 13.4050),
    "Greece": ("Europe", "Athens", 37.9838, 23.7275),
    "Hungary": ("Europe", "Budapest", 47.4979, 19.0402),
    "Iceland": ("Europe", "Reykjavik", 64.1466, -21.9426),
    "Ireland": ("Europe", "Dublin", 53.3498, -6.2603),
    "Italy": ("Europe", "Rome", 41.9028, 12.4964),
    "Kosovo": ("Europe", "Pristina", 42.6629, 21.1655),
    "Latvia": ("Europe", "Riga", 56.9496, 24.1052),
    "Liechtenstein": ("Europe", "Vaduz", 47.1410, 9.5209),
    "Lithuania": ("Europe", "Vilnius", 54.6872, 25.2797),
    "Luxembourg": ("Europe", "Luxembourg", 49.6116, 6.1319),
    "Malta": ("Europe", "Valletta", 35.8989, 14.5146),
    "Moldova": ("Europe", "Chisinau", 47.0105, 28.8638),
    "Monaco": ("Europe", "Monaco", 43.7384, 7.4246),
    "Montenegro": ("Europe", "Podgorica", 42.4304, 19.2594),
    "Netherlands": ("Europe", "Amsterdam", 52.3676, 4.9041),
    "North Macedonia": ("Europe", "Skopje", 41.9973, 21.4280),
    "Norway": ("Europe", "Oslo", 59.9139, 10.7522),
    "Poland": ("Europe", "Warsaw", 52.2297, 21.0122),
    "Portugal": ("Europe", "Lisbon", 38.7223, -9.1393),
    "Romania": ("Europe", "Bucharest", 44.4268, 26.1025),
    "Russia": ("Europe", "Moscow", 55.7558, 37.6173),
    "San Marino": ("Europe", "San Marino", 43.9424, 12.4578),
    "Serbia": ("Europe", "Belgrade", 44.7866, 20.4489),
    "Slovakia": ("Europe", "Bratislava", 48.1486, 17.1077),
    "Slovenia": ("Europe", "Ljubljana", 46.0569, 14.5058),
    "Spain": ("Europe", "Madrid", 40.4168, -3.7038),
    "Sweden": ("Europe", "Stockholm", 59.3293, 18.0686),
    "Switzerland": ("Europe", "Bern", 46.9480, 7.4474),
    "Ukraine": ("Europe", "Kyiv", 50.4501, 30.5234),
    "United Kingdom": ("Europe", "London", 51.5074, -0.1278),
    "Vatican City": ("Europe", "Vatican City", 41.9029, 12.4534),
    # North America
    "Antigua and Barbuda": ("North America", "St. John's", 17.1274, -61.8468),
    "Bahamas": ("North America", "Nassau", 25.0443, -77.3504),
    "Barbados": ("North America", "Bridgetown", 13.0976, -59.6167),
    "Belize": ("North America", "Belmopan", 17.2510, -88.7712),
    "Canada": ("North America", "Ottawa", 45.4215, -75.6972),
    "Costa Rica": ("North America", "San Jose", 9.9281, -84.0907),
    "Cuba": ("North America", "Havana", 23.1136, -82.3666),
    "Dominica": ("North America", "Roseau", 15.3092, -61.3797),
    "Dominican Republic": ("North America", "Santo Domingo", 18.4861, -69.9312),
    "El Salvador": ("North America", "San Salvador", 13.6929, -89.2182),
    "Grenada": ("North America", "St. George's", 12.0561, -61.7488),
    "Guatemala": ("North America", "Guatemala City", 14.6349, -90.5069),
    "Haiti": ("North America", "Port-au-Prince", 18.5944, -72.3074),
    "Honduras": ("North America", "Tegucigalpa", 14.0723, -87.1921),
    "Jamaica": ("North America", "Kingston", 17.9714, -76.7936),
    "Mexico": ("North America", "Mexico City", 19.4326, -99.1332),
    "Nicaragua": ("North America", "Managua", 12.1150, -86.2362),
    "Panama": ("North America", "Panama City", 8.9824, -79.5199),
    "Saint Kitts and Nevis": ("North America", "Basseterre", 17.3026, -62.7177),
    "Saint Lucia": ("North America", "Castries", 14.0101, -60.9875),
    "Saint Vincent and the Grenadines": ("North America", "Kingstown", 13.1587, -61.2248),
    "Trinidad and Tobago": ("North America", "Port of Spain", 10.6549, -61.5019),
    "United States": ("North America", "Washington D.C.", 38.9072, -77.0369),
    # South America
    "Argentina": ("South America", "Buenos Aires", -34.6037, -58.3816),
    "Bolivia": ("South America", "Sucre", -19.0074, -65.2580),
    "Brazil": ("South America", "Brasilia", -15.7939, -47.8828),
    "Chile": ("South America", "Santiago", -33.4489, -70.6693),
    "Colombia": ("South America", "Bogota", 4.7110, -74.0721),
    "Ecuador": ("South America", "Quito", -0.1807, -78.4678),
    "Guyana": ("South America", "Georgetown", 6.8013, -58.1551),
    "Paraguay": ("South America", "Asuncion", -25.2637, -57.5759),
    "Peru": ("South America", "Lima", -12.0464, -77.0428),
    "Suriname": ("South America", "Paramaribo", 5.8520, -55.2038),
    "Uruguay": ("South America", "Montevideo", -34.9011, -56.1645),
    "Venezuela": ("South America", "Caracas", 10.4806, -66.9036),
    # Oceania
    "Australia": ("Oceania", "Canberra", -35.2809, 149.1300),
    "Fiji": ("Oceania", "Suva", -18.1416, 178.4419),
    "Kiribati": ("Oceania", "Tarawa", 1.3382, 173.0176),
    "Marshall Islands": ("Oceania", "Majuro", 7.1095, 171.1856),
    "Micronesia": ("Oceania", "Palikir", 6.9248, 158.1611),
    "Nauru": ("Oceania", "Yaren", -0.5477, 166.9209),
    "New Zealand": ("Oceania", "Wellington", -41.2866, 174.7756),
    "Palau": ("Oceania", "Ngerulmud", 7.5004, 134.6243),
    "Papua New Guinea": ("Oceania", "Port Moresby", -9.4438, 147.1803),
    "Samoa": ("Oceania", "Apia", -13.8507, -171.7514),
    "Solomon Islands": ("Oceania", "Honiara", -9.4456, 159.9729),
    "Tonga": ("Oceania", "Nuku'alofa", -21.1393, -175.2049),
    "Tuvalu": ("Oceania", "Funafuti", -8.5211, 179.1962),
    "Vanuatu": ("Oceania", "Port Vila", -17.7333, 168.3273),
    "United States": ("Oceania", "Washington D.C.", 38.9072, -77.0369),  # corrected below; kept for count
}

# _COUNTRY_CONTINENT override: 'United States' is North America, not Oceania.
_COUNTRIES["United States"] = ("North America", "Washington D.C.", 38.9072, -77.0369)

# Major non-capital cities: (name, country, region, lat, lon, continent)
_CITIES = [
    ("New York", "United States", "New York", 40.7128, -74.0060, "North America"),
    ("Los Angeles", "United States", "California", 34.0522, -118.2437, "North America"),
    ("Chicago", "United States", "Illinois", 41.8781, -87.6298, "North America"),
    ("Houston", "United States", "Texas", 29.7604, -95.3698, "North America"),
    ("San Francisco", "United States", "California", 37.7749, -122.4194, "North America"),
    ("Seattle", "United States", "Washington", 47.6062, -122.3321, "North America"),
    ("Miami", "United States", "Florida", 25.7617, -80.1918, "North America"),
    ("Boston", "United States", "Massachusetts", 42.3601, -71.0589, "North America"),
    ("Atlanta", "United States", "Georgia", 33.7490, -84.3880, "North America"),
    ("Toronto", "Canada", "Ontario", 43.6532, -79.3832, "North America"),
    ("Vancouver", "Canada", "British Columbia", 49.2827, -123.1207, "North America"),
    ("Montreal", "Canada", "Quebec", 45.5017, -73.5673, "North America"),
    ("Cancún", "Mexico", "Quintana Roo", 21.1619, -86.8515, "North America"),
    ("Guadalajara", "Mexico", "Jalisco", 20.6597, -103.3496, "North America"),
    ("Rio de Janeiro", "Brazil", "Rio de Janeiro", -22.9068, -43.1729, "South America"),
    ("São Paulo", "Brazil", "São Paulo", -23.5505, -46.6333, "South America"),
    ("Salvador", "Brazil", "Bahia", -12.9777, -38.5016, "South America"),
    ("Córdoba", "Argentina", "Córdoba", -31.4201, -64.1888, "South America"),
    ("Rosario", "Argentina", "Santa Fe", -32.9442, -60.6505, "South America"),
    ("Valparaíso", "Chile", "Valparaíso", -33.0472, -71.6127, "South America"),
    ("Medellín", "Colombia", "Antioquia", 6.2442, -75.5812, "South America"),
    ("Cartagena", "Colombia", "Bolívar", 10.3910, -75.4794, "South America"),
    ("Liverpool", "United Kingdom", "England", 53.4084, -2.9916, "Europe"),
    ("Manchester", "United Kingdom", "England", 53.4808, -2.2426, "Europe"),
    ("Birmingham", "United Kingdom", "England", 52.4862, -1.8904, "Europe"),
    ("Edinburgh", "United Kingdom", "Scotland", 55.9533, -3.1883, "Europe"),
    ("Barcelona", "Spain", "Catalonia", 41.3874, 2.1686, "Europe"),
    ("Seville", "Spain", "Andalusia", 37.3891, -5.9845, "Europe"),
    ("Milan", "Italy", "Lombardy", 45.4642, 9.1900, "Europe"),
    ("Naples", "Italy", "Campania", 40.8518, 14.2681, "Europe"),
    ("Munich", "Germany", "Bavaria", 48.1351, 11.5820, "Europe"),
    ("Hamburg", "Germany", "Hamburg", 53.5511, 9.9937, "Europe"),
    ("Amsterdam", "Netherlands", "North Holland", 52.3676, 4.9041, "Europe"),
    ("Rotterdam", "Netherlands", "South Holland", 51.9244, 4.4777, "Europe"),
    ("Lyon", "France", "Auvergne-Rhône-Alpes", 45.7640, 4.8357, "Europe"),
    ("Marseille", "France", "Provence", 43.2965, 5.3698, "Europe"),
    ("Nice", "France", "Provence-Alpes-Côte d'Azur", 43.7102, 7.2620, "Europe"),
    ("Bordeaux", "France", "Nouvelle-Aquitaine", 44.8378, -0.5792, "Europe"),
    ("Lisbon", "Portugal", "Lisbon", 38.7223, -9.1393, "Europe"),
    ("Porto", "Portugal", "Norte", 41.1579, -8.6291, "Europe"),
    ("Dubai", "UAE", "Dubai", 25.2048, 55.2708, "Asia"),
    ("Riyadh", "Saudi Arabia", "Riyadh Province", 24.7136, 46.6753, "Asia"),
    ("Istanbul", "Turkey", "Marmara", 41.0082, 28.9784, "Asia"),
    ("Mumbai", "India", "Maharashtra", 19.0760, 72.8777, "Asia"),
    ("Delhi", "India", "Delhi", 28.6139, 77.2090, "Asia"),
    ("Bengaluru", "India", "Karnataka", 12.9716, 77.5946, "Asia"),
    ("Chennai", "India", "Tamil Nadu", 13.0827, 80.2707, "Asia"),
    ("Kolkata", "India", "West Bengal", 22.5726, 88.3639, "Asia"),
    ("Shanghai", "China", "Eastern China", 31.2304, 121.4737, "Asia"),
    ("Guangzhou", "China", "Southern China", 23.1291, 113.2644, "Asia"),
    ("Shenzhen", "China", "Southern China", 22.5431, 114.0579, "Asia"),
    ("Chengdu", "China", "Southwest China", 30.5728, 104.0668, "Asia"),
    ("Hong Kong", "China", "Special Administrative Region", 22.3193, 114.1694, "Asia"),
    ("Bangkok", "Thailand", "Central Thailand", 13.7563, 100.5018, "Asia"),
    ("Jakarta", "Indonesia", "Java", -6.2088, 106.8456, "Asia"),
    ("Bali", "Indonesia", "Bali", -8.4095, 115.1889, "Asia"),
    ("Osaka", "Japan", "Kansai", 34.6937, 135.5023, "Asia"),
    ("Kyoto", "Japan", "Kansai", 35.0116, 135.7681, "Asia"),
    ("Busan", "South Korea", "Yeongnam", 35.1796, 129.0756, "Asia"),
    ("Taipei", "Taiwan", "Northern Taiwan", 25.0330, 121.5654, "Asia"),
    ("Kaohsiung", "Taiwan", "Southern Taiwan", 22.6273, 120.3014, "Asia"),
    ("Ho Chi Minh City", "Vietnam", "Southern Vietnam", 10.8231, 106.6297, "Asia"),
    ("Manila", "Philippines", "Metro Manila", 14.5995, 120.9842, "Asia"),
    ("Cebu", "Philippines", "Central Visayas", 10.3157, 123.8854, "Asia"),
    ("Karachi", "Pakistan", "Sindh", 24.8607, 67.0011, "Asia"),
    ("Lahore", "Pakistan", "Punjab", 31.5204, 74.3587, "Asia"),
    ("Dhaka", "Bangladesh", "Dhaka Division", 23.8103, 90.4125, "Asia"),
    ("Sydney", "Australia", "New South Wales", -33.8688, 151.2093, "Oceania"),
    ("Melbourne", "Australia", "Victoria", -37.8136, 144.9631, "Oceania"),
    ("Brisbane", "Australia", "Queensland", -27.4698, 153.0251, "Oceania"),
    ("Perth", "Australia", "Western Australia", -31.9505, 115.8605, "Oceania"),
    ("Auckland", "New Zealand", "Auckland", -36.8509, 174.7645, "Oceania"),
    ("Doha", "Qatar", "Ad-Dawhah", 25.2854, 51.5310, "Asia"),
    ("Abu Dhabi", "UAE", "Abu Dhabi", 24.4539, 54.3773, "Asia"),
    ("Cape Town", "South Africa", "Western Cape", -33.9249, 18.4241, "Africa"),
    ("Johannesburg", "South Africa", "Gauteng", -26.2041, 28.0473, "Africa"),
    ("Lagos", "Nigeria", "Lagos State", 6.5244, 3.3792, "Africa"),
    ("Abidjan", "Ivory Coast", "Abidjan District", 5.3599, -4.0083, "Africa"),
    ("Nairobi", "Kenya", "Nairobi County", -1.2921, 36.8219, "Africa"),
    ("Accra", "Ghana", "Greater Accra", 5.6037, -0.1870, "Africa"),
    ("Casablanca", "Morocco", "Casablanca-Settat", 33.5731, -7.5898, "Africa"),
    ("Marrakesh", "Morocco", "Marrakesh-Safi", 31.6295, -7.9811, "Africa"),
    ("Cairo", "Egypt", "Cairo Governorate", 30.0444, 31.2357, "Africa"),
    ("Alexandria", "Egypt", "Alexandria Governorate", 31.2001, 29.9187, "Africa"),
    ("Tel Aviv", "Israel", "Tel Aviv District", 32.0853, 34.7818, "Asia"),
    ("Beirut", "Lebanon", "Mount Lebanon", 33.8938, 35.5018, "Asia"),
    ("Tehran", "Iran", "Tehran Province", 35.6892, 51.3890, "Asia"),
    ("Baghdad", "Iraq", "Baghdad Governorate", 33.3152, 44.3661, "Asia"),
    ("Makkah", "Saudi Arabia", "Makkah Province", 21.3891, 39.8579, "Asia"),
    ("Medina", "Saudi Arabia", "Al Madinah Region", 24.5247, 39.5692, "Asia"),
    ("Kochi", "India", "Kerala", 9.9312, 76.2673, "Asia"),
    ("Goa", "India", "Goa", 15.2993, 74.1240, "Asia"),
    ("Nonthaburi", "Thailand", "Central Thailand", 13.8591, 100.5212, "Asia"),
]

# Notable landmarks: (name, town, country, lat, lon, description)
_LANDMARKS = [
    ("Eiffel Tower", "Paris", "France", 48.8584, 2.2945, "Cast-iron tower on the Champ de Mars, the symbol of Paris."),
    ("Louvre Museum", "Paris", "France", 48.8606, 2.3376, "The world's largest art museum, home of the Mona Lisa."),
    ("Notre-Dame", "Paris", "France", 48.8530, 2.3499, "Medieval cathedral famous for its gothic facade and towers."),
    ("Colosseum", "Rome", "Italy", 41.8902, 12.4922, "Ancient Roman amphitheatre that could seat over 50,000 spectators."),
    ("Trevi Fountain", "Rome", "Italy", 41.9009, 12.4833, "Baroque fountain where tradition says a coin thrown ensures a return to Rome."),
    ("Leaning Tower of Pisa", "Pisa", "Italy", 43.7230, 10.3966, "Campanile famous worldwide for its unintended tilt."),
    ("Big Ben", "London", "United Kingdom", 51.5007, -0.1246, "Clock tower of the Palace of Westminster at the River Thames."),
    ("Tower of London", "London", "United Kingdom", 51.5081, -0.0759, "Historic fortress and former royal castle."),
    ("Buckingham Palace", "London", "United Kingdom", 51.5014, -0.1419, "London residence of the British monarch."),
    ("Stonehenge", "Amesbury", "United Kingdom", 51.1789, -1.8262, "Prehistoric megalithic monument on Salisbury Plain."),
    ("Statue of Liberty", "New York", "United States", 40.6892, -74.0445, "Colossal neoclassical sculpture on Liberty Island."),
    ("Empire State Building", "New York", "United States", 40.7484, -73.9857, "102-storey Art Deco skyscraper in Midtown Manhattan."),
    ("Central Park", "New York", "United States", 40.7829, -73.9654, "870-acre public park in the heart of Manhattan."),
    ("Golden Gate Bridge", "San Francisco", "United States", 37.8199, -122.4783, "Art Deco suspension bridge spanning the Golden Gate strait."),
    ("Hollywood Sign", "Los Angeles", "United States", 34.1341, -118.3215, "Iconic sign overlooking Hollywood, Los Angeles."),
    ("Lincoln Memorial", "Washington D.C.", "United States", 38.8893, -77.0502, "Presidential memorial honouring Abraham Lincoln."),
    ("Niagara Falls", "Niagara", "Canada", 43.0962, -79.0377, "Three powerful waterfalls on the Niagara River border."),
    ("CN Tower", "Toronto", "Canada", 43.6426, -79.3871, "553-metre communications and observation tower in Toronto."),
    ("Christ the Redeemer", "Rio de Janeiro", "Brazil", -22.9519, -43.2105, "Art Deco statue of Jesus atop Corcovado mountain."),
    ("Sugarloaf Mountain", "Rio de Janeiro", "Brazil", -22.9495, -43.1538, "Granite peak reached by cable car above Guanabara Bay."),
    ("Machu Picchu", "Cusco", "Peru", -13.1631, -72.5450, "15th-century Inca citadel set high in the Andes."),
    ("Sagrada Familia", "Barcelona", "Spain", 41.4036, 2.1744, "Antoni Gaudi's still-unfinished basilica in Barcelona."),
    ("Alhambra", "Granada", "Spain", 37.1760, -3.5880, "Moorish palace and fortress complex in Andalusia."),
    ("Pyramids of Giza", "Giza", "Egypt", 29.9792, 31.1342, "Ancient pyramid complex on the Giza plateau."),
    ("Great Sphinx", "Giza", "Egypt", 29.9753, 31.1376, "Limestone statue of a recumbent sphinx guarding the Giza pyramids."),
    ("Table Mountain", "Cape Town", "South Africa", -33.9628, 18.4095, "Flat-topped mountain and national park above Cape Town."),
    ("Mount Kilimanjaro", "Kilimanjaro", "Tanzania", -3.0674, 37.3556, "Africa's highest peak at 5,895 metres."),
    ("Victoria Falls", "Livingstone", "Zambia", -17.9243, 25.8572, "One of the world's largest waterfalls on the Zambezi."),
    ("Great Wall of China", "Beijing", "China", 40.4319, 116.5704, "Ancient series of fortifications stretching across northern China."),
    ("Forbidden City", "Beijing", "China", 39.9163, 116.3972, "Imperial palace complex at the centre of Beijing."),
    ("Terracotta Army", "Xi'an", "China", 34.3841, 109.2785, "Tomb of the first Qin Emperor guarded by thousands of Terracotta warriors."),
    ("Mount Fuji", "Honshu", "Japan", 35.3606, 138.7273, "Japan's highest mountain and iconic stratovolcano."),
    ("Taj Mahal", "Agra", "India", 27.1751, 78.0421, "White marble mausoleum on the Yamuna riverbank."),
    ("Gateway of India", "Mumbai", "India", 18.9220, 72.8347, "Basalt archway overlooking Mumbai harbour."),
    ("Petra", "Wadi Musa", "Jordan", 30.3285, 35.4444, "Ancient Nabataean city carved into rose-red rock."),
    ("Burj Khalifa", "Dubai", "UAE", 25.1972, 55.2744, "The world's tallest building at 828 metres."),
    ("Sydney Opera House", "Sydney", "Australia", -33.8568, 151.2153, "Expressionist multi-venue performing arts centre on Bennelong Point."),
    ("Sydney Harbour Bridge", "Sydney", "Australia", -33.8523, 151.2108, "Steel through-arch bridge across Sydney Harbour."),
    ("Uluru", "Alice Springs", "Australia", -25.3444, 131.0369, "Vast sandstone monolith sacred to the Anangu people."),
    ("Brandenburg Gate", "Berlin", "Germany", 52.5163, 13.3777, "18th-century neoclassical gate at the heart of Berlin."),
    ("Berlin Wall Memorial", "Berlin", "Germany", 52.5354, 13.3896, "Preserved section of the Wall that divided Berlin."),
    ("St. Basil's Cathedral", "Moscow", "Russia", 55.7525, 37.6231, "Colourful onion-domed cathedral on Red Square."),
    ("Red Square", "Moscow", "Russia", 55.7539, 37.6208, "Central public square of Moscow."),
    ("Acropolis of Athens", "Athens", "Greece", 37.9715, 23.7257, "Ancient citadel crowned by the Parthenon."),
    ("Hagia Sophia", "Istanbul", "Turkey", 41.0086, 28.9802, "Historic mosque, formerly a Byzantine cathedral, in Istanbul."),
    ("Santorini", "Santorini", "Greece", 36.3932, 25.4615, "Volcanic island famed for white-washed villages and caldera views."),
    ("Chichen Itza", "Valladolid", "Mexico", 20.6843, -88.5678, "Mayan city with the great pyramid of El Castillo."),
    ("Palenque", "Chiapas", "Mexico", 17.4840, -92.0463, "Maya city-state in the Lacandon rainforest."),
    ("Statue of Christ", "Bogotá", "Colombia", 4.6059, -74.0880, "Landmark statue of Christ overlooking Bogotá."),
    ("Blue Mosque", "Istanbul", "Turkey", 41.0054, 28.9768, "Sultan Ahmed Mosque with six minarets and blue Iznik tiles."),
    ("Bondi Beach", "Sydney", "Australia", -33.8908, 151.2743, "Iconic surf beach and suburb in eastern Sydney."),
]

_GEO_TRIGGERS = re.compile(
    r"\b(where is|where's|how far|how do i get|navigate|directions|coordinates|"
    r"nearest|nearby|near |around |map of|in which country|which continent|"
    r"capital of|distance to|distance from|going to|head to|route to|london|paris|"
    r"france|germany|italy|china|india|usa|japan|australia|canada|brazil|egypt)\b",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────
# GEO HELPERS
# ──────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _cardinal(deg: float) -> str:
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((deg + 22.5) // 45) % 8]


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "place"


def _search_text(p) -> str:
    parts = [p.name, p.aliases, p.country, p.region, p.continent, p.place_type]
    return " ".join(x for x in parts if x)


# ──────────────────────────────────────────────
# SEEDING
# ──────────────────────────────────────────────

def seed_world_map(db: Session, force: bool = False) -> dict:
    """Upsert the internal world map. Returns counts seeded."""
    from sqlalchemy import func
    now = datetime.now(timezone.utc)

    def _put(key, name, country, region, continent, ptype, lat, lon, desc, aliases, importance):
        place = db.query(KudosMapPlace).filter(KudosMapPlace.key == key).first()
        if place is None:
            place = KudosMapPlace(key=key)
            db.add(place)
        elif not force and place.is_seed:
            return 0
        place.name = name
        place.country = country
        place.region = region
        place.continent = continent
        place.place_type = ptype
        place.lat = lat
        place.lon = lon
        place.description = desc
        place.aliases = aliases
        place.importance = importance
        place.is_seed = True
        place.search_text = _search_text(place)
        return 1

    counts = {"continent": 0, "country": 0, "capital": 0, "city": 0, "landmark": 0}

    for cname, (clat, clon) in _CONTINENT_COORDS.items():
        counts["continent"] += _put(
            f"continent:{_slug(cname)}", cname, "", "", cname, "continent", clat, clon,
            f"The continent of {cname}.", "", 100,
        )

    for cname, (continent, capital, clat, clon) in _COUNTRIES.items():
        counts["country"] += _put(
            f"country:{_slug(cname)}", cname, cname, "", continent, "country", clat, clon,
            f"{cname} is a sovereign country in {continent}. Capital: {capital}.",
            _slug(cname), 80,
        )
        counts["capital"] += _put(
            f"capital:{_slug(cname)}", capital, cname, "", continent, "capital", clat, clon,
            f"{capital} is the capital city of {cname}.",
            "", 70,
        )

    for (name, country, region, lat, lon, continent) in _CITIES:
        counts["city"] += _put(
            f"city:{_slug(name)}", name, country, region, continent, "city", lat, lon,
            f"{name} is a major city in {region + ' region, ' if region else ''}{country}, {continent}.",
            "", 50,
        )

    for (name, town, country, lat, lon, desc) in _LANDMARKS:
        continent = _COUNTRIES.get(country, ("Unknown", "", 0, 0))[0]
        counts["landmark"] += _put(
            f"landmark:{_slug(name)}", name, town, country, continent,
            "landmark", lat, lon, f"{desc} Located in {town}, {country}.",
            "", 40,
        )

    db.commit()
    counts["total"] = sum(counts.values())
    return counts


# ──────────────────────────────────────────────
# QUERIES
# ──────────────────────────────────────────────

def status(db: Session) -> dict:
    from sqlalchemy import func
    total = db.query(func.count(KudosMapPlace.id)).scalar() or 0
    with_coords = db.query(func.count(KudosMapPlace.id)).filter(KudosMapPlace.lat.isnot(None)).scalar() or 0
    by_type = {}
    for (ptype, count) in db.query(KudosMapPlace.place_type, func.count(KudosMapPlace.id)).group_by(
            KudosMapPlace.place_type).all():
        by_type[ptype] = count
    return {
        "mode": "walk", "total": total, "with_coordinates": with_coords,
        "without_coordinates": total - with_coords, "by_type": by_type,
    }


def search(db: Session, q: str, limit: int = 20) -> list[dict]:
    """Find internal-map places matching a query, best matches first."""
    q = (q or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    rows = (
        db.query(KudosMapPlace)
        .filter(
            KudosMapPlace.name.ilike(like)
            | KudosMapPlace.country.ilike(like)
            | KudosMapPlace.region.ilike(like)
            | KudosMapPlace.continent.ilike(like)
            | KudosMapPlace.place_type.ilike(like)
            | KudosMapPlace.aliases.ilike(like)
        )
        .order_by(KudosMapPlace.importance.desc())
        .limit(limit * 2)
        .all()
    )
    rows.sort(key=lambda p: (_priority(p, q), -p.importance), reverse=False)
    return [_as_dict(p) for p in rows[:limit]]


def _priority(p: KudosMapPlace, q: str) -> int:
    name = p.name.lower()
    ql = q.lower()
    if name == ql or p.key == ql:
        return 0
    if name.startswith(ql) or ql in name:
        return 1
    if ql in (p.aliases or "").lower():
        return 2
    return 3


def _as_dict(p: KudosMapPlace) -> dict:
    return {
        "id": p.id, "key": p.key, "name": p.name, "country": p.country,
        "region": p.region, "continent": p.continent, "place_type": p.place_type,
        "lat": p.lat, "lon": p.lon, "description": p.description,
        "aliases": p.aliases, "importance": p.importance,
    }


def near(db: Session, lat: float, lon: float, radius_km: float = 250, limit: int = 30) -> list[dict]:
    """Places within a radius of a coordinate, nearest first (precision shards)."""
    if lat is None or lon is None:
        return []
    rows = db.query(KudosMapPlace).filter(KudosMapPlace.lat.isnot(None)).all()
    results = []
    for p in rows:
        d = _haversine_km(lat, lon, p.lat, p.lon)
        if d <= radius_km:
            r = _as_dict(p)
            r["distance_km"] = round(d, 1)
            results.append(r)
    results.sort(key=lambda r: r["distance_km"])
    return results[:limit]


def resolve(db: Session, ref) -> dict:
    """Resolve a place id or name/alias reference into a place dict."""
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        p = db.get(KudosMapPlace, int(ref))
        if p:
            return _as_dict(p)
    if isinstance(ref, str):
        q = ref.strip()
        for p in db.query(KudosMapPlace).filter(KudosMapPlace.lat.isnot(None)).all():
            if (p.name or "").lower() == q.lower() or q.lower() in (p.aliases or "").lower():
                return _as_dict(p)
        hits = search(db, q, limit=1)
        if hits:
            return hits[0]
    return {}


def country_for(db: Session, lat: float, lon: float) -> dict:
    """Reverse-look up what KUDOS's world map says is around a coordinate."""
    if lat is None or lon is None:
        return {"found": False}
    continents = [
        ("Africa", -1.5, 20.0), ("Asia", 34.0, 100.0), ("Europe", 50.0, 20.0),
        ("North America", 42.0, -95.0), ("South America", -12.0, -58.0),
        ("Oceania", -28.0, 135.0), ("Antarctica", -78.0, 90.0),
    ]
    cont = min(continents, key=lambda c: _haversine_km(lat, lon, c[1], c[2]))[0]
    rows = (
        db.query(KudosMapPlace)
        .filter(KudosMapPlace.lat.isnot(None), KudosMapPlace.place_type.in_(["country", "city", "landmark"]))
        .all()
    )
    best = min(rows, key=lambda p: _haversine_km(lat, lon, p.lat, p.lon)) if rows else None
    if not best or _haversine_km(lat, lon, best.lat, best.lon) > 4000:
        return {"found": True, "continent": cont}
    return {
        "found": True,
        "continent": cont,
        "nearest": {"name": best.name, "place_type": best.place_type, "country": best.country,
                    "lat": best.lat, "lon": best.lon},
    }


def between(db: Session, a, b) -> dict:
    """Distance + bearing between two internal-map places (how to get)."""
    pa, pb = resolve(db, a), resolve(db, b)
    if not pa or not pb:
        missing = "a" if not pa else "b"
        return {"found": False, "missing": f"place {missing} unknown"}
    if pa.get("lat") is None or pb.get("lat") is None:
        return {"found": False, "missing": "coordinates unknown for one place"}
    dist = _haversine_km(pa["lat"], pa["lon"], pb["lat"], pb["lon"])
    brg = _bearing(pa["lat"], pa["lon"], pb["lat"], pb["lon"])
    route_hint = f"Head {_cardinal(brg)} from {pa['name']} for about {dist:.0f} km to reach {pb['name']}."
    return {
        "found": True,
        "from": pa, "to": pb, "distance_km": round(dist, 1), "bearing_deg": round(brg, 1),
        "direction": _cardinal(brg), "route_hint": route_hint,
    }


def is_geo_question(question: str) -> bool:
    return bool(_GEO_TRIGGERS.search(question or ""))


def maps_knowledge_context(db: Session, question: str = "") -> str:
    """Self-knowledge note: KUDOS can navigate offline with its own world map."""
    try:
        st = status(db)
    except Exception:
        return ""
    if not st["total"]:
        return ""
    lines = [
        f"- You carry an internal world map of the whole world for offline navigation: "
        f"{st['total']} seeded places ({st['with_coordinates']} with known coordinates) across "
        f"continents, countries, capitals, major cities and landmarks. You can locate places, "
        f"give coordinates, find distances and directions, and navigate EVEN when offline. "
        f"Never invent a coordinate on this map: if a place has no known coordinate, say so.",
    ]
    if is_geo_question(question) and question.strip():
        for hit in _candidates(db, question, limit=4):
            coord = f"({hit['lat']:.4f}, {hit['lon']:.4f})" if hit["lat"] is not None else "(coordinates not known)"
            lines.append(f"  - {hit['name']}: {hit['place_type']} in {hit['country'] or hit['continent']}, coord {coord}.")
    return "\n".join(lines)


_PLACE_PREFIX = re.compile(
    r"^(?:where\s+is|where's|how\s+far\s+(?:is|to)|coordinates?\s+of|find(?:\s+me)?|"
    r"which\s+country\s+is|what\s+country\s+is|distance\s+(?:to|from)|map\s+of|"
    r"search\s+for|locate|near)\s+",
    re.IGNORECASE,
)


def _extract_place_query(q: str) -> str:
    """Pull the place name out of a spoken geo question."""
    q2 = _PLACE_PREFIX.sub("", q.strip())
    q2 = q2.strip(" ?!.,;:").strip()
    return q2


def _candidates(db: Session, q: str, limit: int = 15) -> list[dict]:
    """Geo-aware place lookup: handles 'where is X' style phrasing and falls
    back to term matching so KUDOS finds places even inside a full sentence."""
    q2 = _extract_place_query(q)
    if q2:
        hits = search(db, q2, limit=limit)
        if hits:
            return hits
    from app.core.kudos_brain import brain_terms
    terms = [t for t in brain_terms(q) if len(t) >= 3]
    if not terms:
        return []
    hits = []
    for p in db.query(KudosMapPlace).all():
        hay = f"{p.name} {p.country} {p.aliases}".lower()
        name_l = (p.name or "").lower()
        if any(t in hay for t in terms) and any(t in name_l for t in terms):
            hits.append(_as_dict(p))
    return hits[:limit]


def world_map_offline_answer(db: Session, query: str, user_id=None) -> dict | None:
    """Deterministic geo answer from KUDOS's own map — used by the offline
    brain when there is no LLM. Returns the answer_offline shape or None."""
    from app.core.kudos_brain import brain_terms

    q = (query or "").strip()
    if not q or q.lower() in ("where am i", "where am i?") or len(q) > 160:
        return None

    hits = _candidates(db, q)
    scored = []
    terms = brain_terms(q)
    for h in hits:
        name_l = (h["name"] or "").lower()
        country_l = (h["country"] or "").lower()
        score = 0
        if q.lower() in name_l or name_l in q.lower():
            score += 3
        for t in terms:
            if t in name_l or t in country_l:
                score += 1
        if q.lower().startswith(("where is", "where's", "where")):
            if name_l in q.lower():
                score += 2
        scored.append((score, h))
    if not scored:
        return None
    score, hit = max(scored, key=lambda x: x[0])
    if score < 4:
        return None

    coord = f"{hit['lat']:.4f}, {hit['lon']:.4f}" if hit["lat"] is not None else "not yet known"
    kind = hit["place_type"]
    answer = (
        f"According to my internal world map, {hit['name']} is a {kind} in "
        f"{hit['country'] or hit['region'] or hit['continent']}{', ' + hit['continent'] if hit['country'] and hit['continent'] else ''}. "
        f"Its coordinates are {coord}. " + (hit["description"] or "").strip()
    )
    content = (
        f"{hit['name']} ({kind}): {hit['description']} Coordinates: {coord}. "
        f"Country: {hit['country']}. Continent: {hit['continent']}."
    )
    return {
        "answer": answer,
        "sources": [{"content": content, "source_type": "internal-map", "title": hit["name"], "confidence": 0.95}],
        "grounded": True,
        "confidence": round(min(1.0, score / 6 + 0.5), 3),
        "reasoning": f"matched {hit['name']} from the internal world map (score {score})",
        "steps": ["searched internal world map", "matched place by name/aliases", "assembled fact-only answer"],
        "mode": "internal-map",
    }