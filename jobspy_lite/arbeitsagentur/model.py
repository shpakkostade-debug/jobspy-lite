from datetime import date

from pydantic import BaseModel, ConfigDict


class Address(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plz: str | None = None
    ort: str | None = None
    region: str | None = None
    land: str | None = None


class JobLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    adresse: Address | None = None
    breite: float | None = None
    laenge: float | None = None


class JobSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stellenangebotsTitel: str
    firma: str | None = None
    referenznummer: str
    datumErsteVeroeffentlichung: date | None = None
    externeURL: str | None = None
    stellenlokationen: list[JobLocation] = []
    arbeitszeitVollzeit: bool = False
    arbeitszeitTeilzeitVormittag: bool = False
    arbeitszeitTeilzeitNachmittag: bool = False
    arbeitszeitTeilzeitAbend: bool = False
    arbeitszeitTeilzeitFlexibel: bool = False
    homeofficemoeglich: bool | None = None
    verguetungsangabe: str | None = None
    hauptberuf: str | None = None
    stellenangebotsart: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ergebnisliste: list[JobSummary] = []
    maxErgebnisse: int | None = None


class JobDetails(JobSummary):
    stellenangebotsBeschreibung: str | None = None
