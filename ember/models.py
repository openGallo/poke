"""Validated API boundaries. Unknown money is None, never a coerced zero."""
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit
import ipaddress
import re
import unicodedata
import hashlib
from .conditions import RAW_CONDITIONS, CONDITION_SCALES, DEFAULT_FALLBACKS, bucket_options, condition_data, infer_condition, is_psa10
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LANGUAGES = {"en": "English", "fr": "French", "de": "German", "it": "Italian", "es": "Spanish", "es-mx": "Spanish (Latin America)", "pt": "Portuguese (Brazil)", "ja": "Japanese", "ko": "Korean", "zh-tw": "Traditional Chinese", "zh-cn": "Simplified Chinese", "id": "Indonesian", "th": "Thai"}
CURRENCIES = {"EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD"}
Money = Annotated[float, Field(ge=0, le=100_000_000, allow_inf_nan=False)]
Text = Annotated[str, Field(max_length=2000)]


def public_url(value: str) -> str:
    if not value:
        return ""
    u = urlsplit(value.strip())
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in {None, 443}:
        raise ValueError("Use a public HTTPS URL without credentials or a non-standard port.")
    h = u.hostname.lower()
    if h in {"localhost", "metadata.google.internal"} or h.endswith((".local", ".internal")):
        raise ValueError("Private URLs are not permitted.")
    try:
        if not ipaddress.ip_address(h).is_global:
            raise ValueError("Private IP addresses are not permitted.")
    except ValueError as e:
        if "Private" in str(e):
            raise
    if len(value) > 2000:
        raise ValueError("URL too long")
    return urlunsplit((u.scheme, u.netloc.lower(), u.path, u.query, ""))


def canonical_url(value: str) -> str:
    """Conservative sale identity: query retained for auctions whose lot identity is in it."""
    from urllib.parse import parse_qsl, urlencode
    u = urlsplit(public_url(value))
    if not value:
        return ""
    m = re.search(r"/(?:itm)/(?:[^/]+/)?(\d{9,15})", u.path)
    if m and re.fullmatch(r"(?:(?:www|m)\.)?ebay\.(?:com|co\.uk|com\.au|de|fr|be|ca|it|es|nl|at|ch|ie)",u.hostname or ""):
        return "https://www.ebay.com/itm/" + m[1]
    query = urlencode(sorted((k,v) for k,v in parse_qsl(u.query) if not k.lower().startswith("utm_") and k not in {"ref", "fbclid", "gclid"}))
    return urlunsplit((u.scheme, u.netloc, u.path.rstrip("/"), query, ""))


def norm(value) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SetupIn(Model):
    password: str = Field(min_length=12, max_length=1024)
    confirmation: str = Field(min_length=12, max_length=1024)

    @model_validator(mode="after")
    def matching_passwords(self):
        if self.password != self.confirmation:
            raise ValueError("Passwords must match.")
        return self


class SavedSearchIn(Model):
    name: str = Field(min_length=1, max_length=80)
    filters: dict[str, str | int] = Field(default_factory=dict, max_length=12)

    @field_validator("filters")
    @classmethod
    def safe_filters(cls, values):
        keys={"q","status","language","set","year","finish","sort","price","page"}
        if set(values)-keys or any(len(str(x))>300 for x in values.values()):
            raise ValueError("Unsupported or oversized search filter.")
        return values


class ConditionFields(Model):
    grader: Literal["PSA", "BGS", "CGC", "RAW", "UNKNOWN"] = "PSA"
    grade: float | None = Field(default=10, ge=1, le=10, allow_inf_nan=False)
    designation: str = Field(default="", max_length=40)
    grading_scale: Literal["current", "legacy", "unspecified"] = "current"
    raw_condition: str = Field(default="Unknown", max_length=40)
    condition_scale: Literal["seller", "ebay", "tcgplayer", "cardmarket"] = "seller"
    condition_original: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def validate_condition(self):
        if self.raw_condition not in RAW_CONDITIONS:
            raise ValueError("Unsupported raw condition; use Unknown for an unmapped label.")
        if self.grader in {"RAW", "UNKNOWN"}:
            if self.grade is not None or self.designation:
                raise ValueError("Raw or unknown copies cannot carry a numeric grade or slab designation.")
            if self.grader=="UNKNOWN" and self.raw_condition!="Unknown":
                raise ValueError("Select RAW for an ungraded condition.")
        else:
            if self.raw_condition!="Unknown":
                raise ValueError("A graded copy cannot also be classified as a raw condition.")
            if self.grade is not None and self.grade*2!=int(self.grade*2):
                raise ValueError("Only supported whole or half grades are accepted.")
            if self.grader=="PSA":
                if self.grade==9.5 or self.grading_scale!="current":
                    raise ValueError("PSA 9.5 or a nonstandard PSA scale is not supported.")
                expected={10:"Gem Mint",9:"Mint"}.get(self.grade, "")
                if self.designation not in {"", expected}:
                    raise ValueError("Designation contradicts the PSA grade.")
                self.designation=expected
            elif self.grader=="BGS":
                allowed={"", "Pristine", "Black Label"} if self.grade==10 else {"", "Gem Mint"} if self.grade==9.5 else {""}
                if self.designation not in allowed or self.grading_scale!="current":
                    raise ValueError("Unsupported BGS designation or scale.")
                if self.grade==9.5: self.designation="Gem Mint"
            elif self.grader=="CGC":
                allowed={""}
                if self.grade==10:
                    allowed|={"Pristine"}
                    if self.grading_scale in {"current","unspecified"}: allowed.add("Gem Mint")
                    if self.grading_scale in {"legacy","unspecified"}: allowed.add("Perfect")
                if self.designation not in allowed:
                    raise ValueError("CGC designation conflicts with the selected grade or scale era.")
        return self


def validate_buckets(keys):
    valid={x["key"] for x in bucket_options()}
    if any(k not in valid for k in keys):
        raise ValueError("Unknown condition bucket; choose an offered condition/grade and scale.")
    return list(dict.fromkeys(keys))


class Preferences(Model):
    languages: list[str] = Field(default_factory=lambda: ["en", "fr"], max_length=20)
    release_types: list[str] = Field(default_factory=list, max_length=20)
    finishes: list[str] = Field(default_factory=list, max_length=30)
    editions: list[str] = Field(default_factory=list,max_length=30)
    stamps: list[str] = Field(default_factory=list,max_length=40)
    sizes: list[Literal["standard","jumbo"]] = Field(default_factory=list,max_length=2)
    artwork_only: bool = False
    include_announced: bool = False
    country: str = "BE"
    currency: str = "EUR"
    budget: Money | None = None
    bargain_pct: float = Field(default=15, ge=1, le=80)
    expensive_pct: float = Field(default=15, ge=1, le=100)
    min_sales: int = Field(default=5, ge=3, le=30)
    lookback_days: int = Field(default=180, ge=7, le=730)
    half_life_days: int = Field(default=60, ge=7, le=365)
    monitor_mode: Literal["missing", "watchlist"] = "missing"
    paused: bool = True
    refresh_hours: int = Field(default=12, ge=1, le=168)
    stale_hours: int = Field(default=48, ge=1, le=168)
    ebay_marketplace: Literal["EBAY_BE", "EBAY_FR", "EBAY_DE", "EBAY_GB", "EBAY_US", "EBAY_CA", "EBAY_AU", "EBAY_IT", "EBAY_ES", "EBAY_NL"] = "EBAY_FR"
    notifications: bool = True
    fallback_enabled: bool = True
    fallback_buckets: list[str] = Field(default_factory=lambda:list(DEFAULT_FALLBACKS), max_length=150)
    buying_priority: Literal["psa_first", "value_first"] = "psa_first"
    min_seller_feedback: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    seller_countries: list[str] = Field(default_factory=list, max_length=60)

    @field_validator("fallback_buckets")
    @classmethod
    def buckets_ok(cls,v): return validate_buckets(v)

    @field_validator("seller_countries")
    @classmethod
    def countries_ok(cls,v):
        if any(not re.fullmatch(r"[A-Z]{2}",x) for x in v):
            raise ValueError("Seller countries must use uppercase two-letter codes.")
        return list(dict.fromkeys(v))

    @field_validator("languages")
    @classmethod
    def languages_ok(cls, v):
        if not v or any(x not in LANGUAGES for x in v):
            raise ValueError("Select at least one supported language.")
        return list(dict.fromkeys(v))

    @field_validator("country")
    @classmethod
    def country_ok(cls, v):
        if not re.fullmatch(r"[A-Z]{2}", v):
            raise ValueError("Use a two-letter uppercase country code.")
        return v

    @field_validator("currency")
    @classmethod
    def currency_ok(cls, v):
        if v not in CURRENCIES:
            raise ValueError("Unsupported currency")
        return v


class Variant(Model):
    id: str = ""
    base_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=150)
    set_name: str = Field(min_length=1, max_length=150)
    set_code: str = Field(min_length=1, max_length=100)
    number: str = Field(min_length=1, max_length=40)
    year: int | None = Field(default=None, ge=1996, le=2100)
    language: str
    edition: str = Field(default="unspecified", max_length=100)
    finish: str = Field(default="unspecified", max_length=100)
    stamp: str = Field(default="none", max_length=120)
    size: Literal["standard", "jumbo"] = "standard"
    print_run: str = Field(default="standard", max_length=120)
    release_type: Literal["Expansion", "Promo", "Deck", "Jumbo"] = "Expansion"
    artwork_only: bool = False
    announced: bool = False
    identity_status: Literal["documented", "provisional"] = "provisional"
    source_url: str
    image_url: str = ""
    notes: Text = ""
    source_checked_at: str = ""
    provider_id: str = ""
    retired: bool = False
    reference_image: str = Field(default="", pattern=r"^(?:|[A-Za-z0-9_.-]+)$", max_length=200)
    image_note: str = Field(default="", max_length=1200)
    legacy_id: str = Field(default="", max_length=300)
    number_type: str = Field(default="printed", max_length=40)
    evidence_sources: list[dict[str, str]] = Field(default_factory=list, max_length=20)

    @field_validator("language")
    @classmethod
    def check_language(cls, v):
        if v not in LANGUAGES:
            raise ValueError("Unsupported language")
        return v

    @field_validator("source_url", "image_url")
    @classmethod
    def url_valid(cls, v):
        return public_url(v)

    @model_validator(mode="after")
    def stable_identity(self):
        if not self.source_url:
            raise ValueError("A catalogue source is required.")
        if self.identity_status == "documented" and (self.finish == "unspecified" or self.edition == "unspecified"):
            raise ValueError("Documented identities need explicit edition and finish.")
        names=["charmander","salamèche","salameche","glumanda","ヒトカゲ","파이리","小火龍","小火龙","ฮิโตคาเงะ"]
        if not self.artwork_only and not any(n in norm(self.name) for n in names):
            raise ValueError("Only named Charmander cards belong here unless artwork-only is explicitly enabled.")
        # Zero-padding is presentation, not a different collectible.
        number=re.sub(r"(?<![0-9])0+(?=[0-9])", "", norm(self.number).replace(" ",""))
        fields = [self.language, self.set_code, number, self.edition, self.finish, self.stamp, self.size, self.print_run]
        ident = "ember_" + hashlib.sha256("\x1f".join(norm(x) for x in fields).encode()).hexdigest()[:24]
        if self.id and self.id != ident:
            raise ValueError("ID does not match the immutable printing identity.")
        self.id = ident
        return self


class CopyIn(ConditionFields):
    variant_id: str
    status: Literal["Owned", "Ordered"] = "Owned"
    cert: str = Field(default="", max_length=40)
    purchase_price: Money | None = None
    shipping: Money | None = None
    fees: Money | None = None
    import_cost: Money | None = None
    currency: str = "EUR"
    purchase_date: date | None = None
    seller: str = Field(default="", max_length=160)
    notes: Text = ""
    psa10_confirmed: bool = False
    condition_confirmed: bool = False

    @field_validator("currency")
    @classmethod
    def currency_ok(cls, v):
        return Preferences.currency_ok(v)

    @field_validator("purchase_date")
    @classmethod
    def date_ok(cls, v):
        if v and v > date.today():
            raise ValueError("Purchase date cannot be in the future.")
        return v

    @model_validator(mode="after")
    def validate_copy(self):
        if not self.condition_confirmed and not (self.psa10_confirmed and is_psa10(self.model_dump())):
            raise ValueError("Confirm the exact printing and this copy's recorded condition/grade.")
        if self.psa10_confirmed and not is_psa10(self.model_dump()):
            raise ValueError("An alternative condition cannot be confirmed as PSA Gem Mint 10.")
        if self.grader=="UNKNOWN":
            raise ValueError("Record a raw condition or a named grading company for ownership.")
        if self.grader=="RAW" and self.cert:
            raise ValueError("Raw cards cannot have a grading certificate.")
        if self.cert and not re.fullmatch(r"[A-Za-z0-9-]{6,32}", self.cert):
            raise ValueError("Use a 6–32 character alphanumeric certification number.")
        if self.grader=="PSA" and self.cert and not re.fullmatch(r"\d{6,12}",self.cert):
            raise ValueError("PSA certification number must have 6–12 digits.")
        if self.status=="Owned" and self.grader!="RAW" and (not self.cert or self.grade is None):
            raise ValueError("Owned graded copies require a numeric grade and certification number.")
        return self


class WatchIn(Model):
    variant_id: str
    fallback_enabled: bool | None = None
    fallback_buckets: list[str] | None = Field(default=None, max_length=150)
    targets: dict[str, Money] = Field(default_factory=dict, max_length=150)

    @field_validator("fallback_buckets")
    @classmethod
    def watch_buckets(cls,v): return validate_buckets(v) if v is not None else None

    @field_validator("targets")
    @classmethod
    def watch_targets(cls,v):
        validate_buckets(list(v)); return v

    target_price: Money | None = None
    currency: str = "EUR"
    priority: int = Field(default=1, ge=1, le=5)
    notes: Text = ""

    @field_validator("currency")
    @classmethod
    def currency_ok(cls, v):
        return Preferences.currency_ok(v)


class ListingIn(ConditionFields):
    grader: Literal["PSA", "BGS", "CGC", "RAW", "UNKNOWN"] = "UNKNOWN"
    grade: float | None = Field(default=None, ge=1, le=10, allow_inf_nan=False)
    seller_country: str = Field(default="", max_length=2)
    seller_feedback: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    delivery_eligible: bool | None = None
    cost_notes: str = Field(default="", max_length=1000)

    @model_validator(mode="before")
    @classmethod
    def parse_seller_evidence(cls, values):
        if isinstance(values, dict) and "grader" not in values:
            parsed=infer_condition(values.get("title",""), values.get("condition_original",""), values.get("source","Manual"))
            parsed.pop("condition_mapping",None)
            return {**parsed,**values}
        return values

    @field_validator("seller_country")
    @classmethod
    def seller_country_ok(cls,v):
        if v and not re.fullmatch(r"[A-Z]{2}",v): raise ValueError("Use a two-letter seller country.")
        return v
    variant_id: str
    title: str = Field(min_length=3, max_length=400)
    url: str
    image_url: str = ""
    source: str = Field(default="Manual", max_length=60)
    seller: str = Field(default="", max_length=160)
    price: Money
    currency: str = "EUR"
    shipping: Money | None = None
    fees: Money | None = None
    import_cost: Money | None = None
    destination_country: str = "BE"
    listing_type: Literal["fixed", "auction"] = "fixed"
    end_at: str = ""
    cert: str = Field(default="", max_length=40)
    notes: Text = ""

    @field_validator("url", "image_url")
    @classmethod
    def urls(cls, v):
        return public_url(v)

    @field_validator("currency")
    @classmethod
    def currency_ok(cls, v):
        return Preferences.currency_ok(v)

    @field_validator("destination_country")
    @classmethod
    def country_ok(cls, v):
        return Preferences.country_ok(v)

    @field_validator("cert")
    @classmethod
    def cert_ok(cls,v):
        if v and not re.fullmatch(r"[A-Za-z0-9-]{6,32}",v):
            raise ValueError("Certificate must contain 6–32 alphanumeric characters")
        return v

    @field_validator("end_at")
    @classmethod
    def end_ok(cls, v):
        if v:
            from datetime import datetime
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if d.tzinfo is None:
                raise ValueError("Auction end must include a timezone.")
        return v

    @model_validator(mode="after")
    def url_required(self):
        if not self.url:
            raise ValueError("Listing URL is required")
        return self


class MatchReview(Model):
    variant_id: str
    identity_confirmed: bool
    photo_checked: bool
    label_checked: bool = False
    cert_checked: bool = False
    condition_checked: bool = False
    cert: str = Field(default="", max_length=40)
    notes: str = Field(min_length=12, max_length=2000)

    @field_validator("cert")
    @classmethod
    def cert_ok(cls,v): return ListingIn.cert_ok(v)


class SaleIn(ConditionFields):
    variant_id: str
    source: str = Field(min_length=1, max_length=80)
    source_url: str
    transaction_id: str = Field(default="", max_length=160)
    sold_date: date
    item_price: Money | None = None
    currency: str = "EUR"
    price_disclosed: bool = False
    completed: bool = False
    exact_variant_confirmed: bool = False
    condition_confirmed: bool = False
    cert: str = Field(default="", max_length=40)
    notes: Text = ""

    @field_validator("cert")
    @classmethod
    def cert_ok(cls,v):
        return ListingIn.cert_ok(v)

    @field_validator("source_url")
    @classmethod
    def url_ok(cls, v):
        if not v:
            raise ValueError("A sale evidence URL is required.")
        return public_url(v)

    @field_validator("currency")
    @classmethod
    def currency_ok(cls, v):
        return Preferences.currency_ok(v)

    @field_validator("sold_date")
    @classmethod
    def date_ok(cls, v):
        if v > date.today():
            raise ValueError("A completed sale cannot be future-dated.")
        return v

    @model_validator(mode="after")
    def disclosed_amount(self):
        if self.grader=="RAW" and self.cert:
            raise ValueError("Raw evidence cannot carry a slab certificate.")
        if self.completed and self.exact_variant_confirmed and not is_psa10(self.model_dump()) and not self.condition_confirmed:
            raise ValueError("Confirm the condition or grade of this completed-sale observation.")
        if self.price_disclosed and (self.item_price is None or self.item_price <= 0):
            raise ValueError("A disclosed sale price must be positive.")
        if not self.price_disclosed and self.item_price is not None:
            raise ValueError("Do not enter a price for an undisclosed accepted offer.")
        return self


class CredentialsIn(Model):
    client_id: str = Field(min_length=5, max_length=250)
    client_secret: str = Field(min_length=5, max_length=500)


class PriceChartingCredentials(Model):
    token: str = Field(min_length=20,max_length=100)

class AggregateRequest(Model):
    variant_id: str
    product_id: str = Field(pattern=r"^\d{1,12}$")
    product_identity_confirmed: bool = False

class PublicGuideRequest(Model):
    provider_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    base_card_confirmed: bool = False

class ImportIn(Model):
    kind: Literal["copies", "sales", "listings", "watchlist"]
    csv_text: str = Field(max_length=1_000_000)
    commit: bool = False


class LoginIn(Model):
    password: str = Field(min_length=1, max_length=1024)
