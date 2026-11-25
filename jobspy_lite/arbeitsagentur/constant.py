import os

api_url = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
jobs_per_page = 100

# The public client id of the agency's own web app; not a secret.
default_api_key = os.getenv("JOBSUCHE_API_KEY") or "jobboerse-jobsuche"

headers = {
    "accept": "application/json",
    "accept-language": "de-DE,de;q=0.9,en;q=0.8",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}

job_detail_url = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"

# Search results only say which kind of pay is given, never the amount.
salary_intervals = {
    "STUNDENLOHN": "hourly",
    "TAGESLOHN": "daily",
    "WOCHENLOHN": "weekly",
    "MONATSGEHALT": "monthly",
    "JAHRESGEHALT": "yearly",
}
