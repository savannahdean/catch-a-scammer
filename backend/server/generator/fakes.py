"""Fictional-but-realistic building blocks.

Safety rule for the whole project: nothing in the game points at real
infrastructure. IPs come from reserved ranges (RFC 2544 198.18.0.0/15,
RFC 5737 documentation blocks) and every domain ends in a reserved TLD
(.example / .test, RFC 2606). Brand, vendor, malware and actor names are
invented. Write this up in the paper's ethics section.
"""
from __future__ import annotations

import base64
import random
import string

ADJ = ["amber", "arctic", "blue", "bright", "cedar", "coral", "crimson", "dusty", "ember",
       "silver", "golden", "granite", "harbor", "hollow", "iron", "jade", "lunar", "maple",
       "misty", "north", "oak", "pine", "quiet", "red", "river", "rustic", "sage", "stone",
       "summit", "swift", "timber", "urban", "velvet", "willow", "winter", "zen"]
NOUN = ["bakery", "books", "cafe", "clinic", "dental", "designs", "garage", "gardens",
        "goods", "yoga", "law", "media", "outfitters", "pets", "photo", "plumbing",
        "printing", "realty", "roasters", "studio", "supply", "tattoo", "tech", "tours",
        "vineyard", "works", "fitness", "florist", "brewing", "salon"]
BIZ_SUFFIX = ["", "", "", "co", "hq", "shop", "online", "llc", "tn", "usa"]

# Fictional brands the actors imitate: (brand, legit domain, sector)
BRANDS = [
    ("Northbridge Credit Union", "northbridgecu.example", "finance"),
    ("Veritas National Bank", "veritasbank.example", "finance"),
    ("Paylane", "paylane.example", "payments"),
    ("OneMail Workspace", "onemail.example", "saas"),
    ("CloudDrive Docs", "clouddrive.example", "saas"),
    ("ParcelPost Express", "parcelpost.example", "logistics"),
    ("Midstate University", "midstate.example", "education"),
]

PHISH_WORDS = ["secure", "account", "verify", "login", "update", "billing", "support",
               "auth", "portal", "signin", "alert", "service", "confirm", "recovery", "id"]

OP_ADJ = ["Crimson", "Silent", "Paper", "Glass", "Hollow", "Velvet", "Broken", "Frozen",
          "Copper", "Midnight", "Quiet", "Rusted", "Salt", "Static", "Winter", "Ashen",
          "Amber", "Bitter", "Cinder", "Distant", "Faded", "Gilded", "Hidden", "Iron",
          "Lucid", "Narrow", "Pale", "Restless", "Sunken", "Tangled", "Umber", "Wired"]
OP_NOUN = ["Ledger", "Harvest", "Lantern", "Tide", "Anchor", "Orchard", "Relay", "Mirror",
           "Compass", "Kettle", "Signal", "Thread", "Furnace", "Meridian", "Canal", "Hook",
           "Atlas", "Beacon", "Cellar", "Delta", "Ember", "Falcon", "Gate", "Harbor",
           "Isthmus", "Juniper", "Keystone", "Lattice", "Mosaic", "Needle", "Quarry", "Vessel"]

FORUM_PLATFORMS = ["underground forum 'Darkmarket.test'", "carding board 'Vault.test'",
                   "encrypted-messenger channel 'logs_shop'", "forum 'Exploitland.test'"]
SOCIAL_PLATFORMS = ["GitNest (code hosting)", "Chirper (social)", "Pixgram (photos)",
                    "Linkline (professional)", "Steamy (gaming)"]

HANDLE_A = ["dark", "zero", "cold", "ghost", "null", "hex", "shadow", "vip", "night", "rust",
            "grim", "lucky", "silent", "frost", "black", "void", "kilo", "neo"]
HANDLE_B = ["fox", "byte", "wolf", "coder", "lord", "hunter", "king", "cat", "raven", "boss",
            "mint", "smith", "pilot", "drake", "viper", "sage", "monk", "lynx"]

FIRST = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery", "Quinn",
         "Drew", "Elena", "Marco", "Priya", "Dmitri", "Aisha", "Tomas", "Mei", "Lukas",
         "Sofia", "Noah", "Ivan", "Chloe", "Mateo", "Hana", "Omar", "Greta", "Ravi", "Nadia"]
LAST = ["Hart", "Nolan", "Reyes", "Novak", "Kim", "Okafor", "Silva", "Brandt", "Petrov",
        "Walsh", "Moreau", "Tanaka", "Haddad", "Lindqvist", "Costa", "Ivanova", "Mbeki",
        "Kowalski", "Ferreira", "Nguyen", "Duarte", "Schmidt", "Rossi", "Adeyemi"]
CITIES = [("Nashville", "US"), ("Murfreesboro", "US"), ("Chicago", "US"), ("Toronto", "CA"),
          ("Leeds", "GB"), ("Lyon", "FR"), ("Porto", "PT"), ("Brno", "CZ"), ("Gdansk", "PL"),
          ("Tallinn", "EE"), ("Valencia", "ES"), ("Graz", "AT"), ("Cork", "IE"),
          ("Recife", "BR"), ("Osaka", "JP"), ("Pune", "IN"), ("Lagos", "NG"), ("Izmir", "TR")]
JOBS = ["Web Developer", "IT Support Technician", "Freelance Designer", "Student",
        "Network Administrator", "QA Tester", "Call Center Agent", "Marketing Assistant"]

PHISH_KIT_ARTIFACTS = [
    "/admin/panel.php exposed", "messenger bot token in JS", "antibot.php blocklist",
    "kit zip left in webroot (onemail_v4.zip)", "geo-filter .htaccess", "visitors.txt log file",
    "base64-encoded exfil endpoint in form action", "mobile-only redirect",
]
# what a scan of a fake trading platform turns up
FAKE_EXCHANGE_ARTIFACTS = [
    "balance and 'profit' computed in page JavaScript, not by any server",
    "withdraw button disabled in JS until a 'tax' is paid",
    "deposit address hard-coded in the page source",
    "live-chat widget opens a private messenger account",
    "copied exchange template with a renamed logo",
    "no regulator licence number anywhere on the site",
]
# what a scan of a fake security warning turns up
FAKE_ALERT_ARTIFACTS = [
    "full-screen request on page load", "audio alarm autoplays",
    "history.pushState loop (back button disabled)", "fake system-scan animation",
    "keyboard capture to block closing the tab", "obfuscated JS from a known scareware template",
]
X_MAILERS = ["PHPMailer 6.5.0", "PHPMailer 6.1.4", "Microsoft Outlook 16.0", "BulkMailr 3.2",
             "Swift Mailer 5.4", None]


def hexstr(rng: random.Random, nbytes: int) -> str:
    return "%0*x" % (nbytes * 2, rng.getrandbits(nbytes * 8))


def ssdeep(rng: random.Random, size: int) -> str:
    alphabet = string.ascii_letters + string.digits + "+/"
    block = 3 * 2 ** max(0, (size // 3000).bit_length())
    a = "".join(rng.choice(alphabet) for _ in range(rng.randint(40, 64)))
    b = "".join(rng.choice(alphabet) for _ in range(rng.randint(20, 32)))
    return f"{block}:{a}:{b}"


def mmh3_like(rng: random.Random) -> int:
    return rng.randint(-2**31, 2**31 - 1)


def jarm(rng: random.Random) -> str:
    return hexstr(rng, 31)


def handle(rng: random.Random) -> str:
    sep = rng.choice(["", "_", ".", ""])
    num = rng.choice(["", "", str(rng.randint(1, 99)), str(rng.randint(1990, 2006))])
    return f"{rng.choice(HANDLE_A)}{sep}{rng.choice(HANDLE_B)}{num}"


def person_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def op_name(rng: random.Random) -> str:
    return f"Operation {rng.choice(OP_ADJ)} {rng.choice(OP_NOUN)}"


def unique_op_name(rng: random.Random, taken) -> str:
    """A campaign name nobody has used. `taken(name)` says whether it exists.
    Vendors number a tracked operation's later waves ("... II"), so once random
    draws keep colliding the name gets a wave number instead of looping forever."""
    for _ in range(40):
        name = op_name(rng)
        if not taken(name):
            return name
    base = op_name(rng)
    wave = 2
    while taken(f"{base} {roman(wave)}"):
        wave += 1
    return f"{base} {roman(wave)}"


def roman(n: int) -> str:
    out = ""
    for value, digits in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out += digits
            n -= value
    return out


def benign_domain(rng: random.Random) -> str:
    return f"{rng.choice(ADJ)}{rng.choice(NOUN)}{rng.choice(BIZ_SUFFIX)}.example"


def lookalike(rng: random.Random, legit: str) -> str:
    """Realistic phishing domain families: combosquat, typosquat, subdomain abuse."""
    label = legit.split(".")[0]
    style = rng.choice(["combo", "combo", "typo", "hyphen", "tld"])
    w = rng.choice(PHISH_WORDS)
    if style == "combo":
        return f"{label}-{w}.example" if rng.random() < .5 else f"{w}-{label}.example"
    if style == "typo" and len(label) > 4:
        i = rng.randrange(1, len(label) - 1)
        ops = [label[:i] + label[i + 1:],                       # omission
               label[:i] + label[i] + label[i:],                # repetition
               label[:i] + label[i + 1] + label[i] + label[i + 2:]]  # swap
        sub = {"o": "0", "l": "1", "i": "1", "e": "3", "a": "4", "m": "rn"}
        for k, v in sub.items():
            if k in label:
                ops.append(label.replace(k, v, 1))
        return f"{rng.choice(ops)}.example"
    if style == "hyphen":
        return f"{label}-{w}-{rng.choice(PHISH_WORDS)}.example"
    return f"{label}{w}.test"


def token(rng: random.Random, n: int = 8) -> str:
    return "".join(rng.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def fake_password_hash(rng: random.Random, kind: str) -> str:
    if kind == "bcrypt":
        body = base64.b64encode(rng.randbytes(40)).decode()[:53].replace("+", ".")
        return "$2y$10$" + body
    if kind == "md5":
        return hexstr(rng, 16)
    return hexstr(rng, 20)  # sha1
