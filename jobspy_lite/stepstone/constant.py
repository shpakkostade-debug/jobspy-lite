import re

from jobspy_lite.model import CompensationInterval

base_url = "https://www.stepstone.de"
jobs_per_page = 25
max_pages = 40

# curl_cffi's TLS/HTTP2 fingerprint; "chrome" is what the site expects.
default_impersonate = "chrome"

headers = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "accept-language": "de-DE,de;q=0.9,en;q=0.8",
}

umlauts = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"}
)

pay_units = {
    "HOUR": CompensationInterval.HOURLY,
    "DAY": CompensationInterval.DAILY,
    "WEEK": CompensationInterval.WEEKLY,
    "MONTH": CompensationInterval.MONTHLY,
    "YEAR": CompensationInterval.YEARLY,
}

job_type_keywords = {
    "Feste Anstellung": "fulltime",
    "Vollzeit": "fulltime",
    "Teilzeit": "parttime",
    "Freelance": "contract",
    "Freiberuflich": "contract",
    "Befristet": "temporary",
    "Praktikum": "internship",
    "Ausbildung": "internship",
}

remote_keywords = ["homeoffice", "remote", "mobiles arbeiten", "work from home"]

timeago = re.compile(
    r"(?:vor\s+)?(\d+)\s*(Stunde|Stunden|Tag|Tage|Tagen|Woche|Wochen|Monat|Monaten)",
    re.IGNORECASE,
)

job_id = re.compile(r"job-item-(\d+)")
job_id_from_url = re.compile(r"--(\d+)(?:-inline)?\.html")
