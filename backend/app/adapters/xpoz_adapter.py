import random
import hashlib
import inspect
import re
import traceback
from importlib.metadata import PackageNotFoundError, version
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import logging
import httpx
from app.adapters.base import VendorAdapter
from app.adapters.cancellation import CancellationSignal, CollectionCancelled
from app.adapters.provider_limits import (
    ProviderRepeated502Error,
    ProviderRetryBudgetExceeded,
    xpoz_request_controller,
)
from app.adapters.provider_progress import (
    PaginationSafeguardReached,
    ProviderProgressTracker,
)
from app.config import settings

logger = logging.getLogger(__name__)
XPOZ_DEFAULT_START_DATE = "2023-01-01"

XPOZ_TWITTER_FIELDS = [
    "id",
    "text",
    "author_id",
    "author_username",
    "like_count",
    "retweet_count",
    "reply_count",
    "quote_count",
    "impression_count",
    "lang",
    "hashtags",
    "mentions",
    "media_urls",
    "urls",
    "created_at_date",
    "conversation_id",
    "reply_to_tweet_id",
]

XPOZ_INSTAGRAM_POST_FIELDS = [
    "id",
    "username",
    "full_name",
    "caption",
    "media_type",
    "image_url",
    "video_url",
    "like_count",
    "comment_count",
    "reshare_count",
    "video_play_count",
    "created_at_date",
]

XPOZ_REDDIT_POST_FIELDS = [
    "id",
    "title",
    "selftext",
    "author_username",
    "subreddit_name",
    "score",
    "upvotes",
    "comments_count",
    "url",
    "permalink",
    "post_url",
    "created_at_date",
]


def _redact_xpoz_diagnostic(value, api_key: str = "", max_length: int = 500) -> str:
    """Format provider diagnostics without exposing credentials or multiline payloads."""
    if value is None:
        return "not_available"
    text = str(value)
    if api_key:
        text = text.replace(api_key, "[redacted]")
    text = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+",
        r"\1[redacted]",
        text,
    )
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", text)
    text = re.sub(
        r"(?i)((?:api[_-]?key|access[_-]?key|token)\s*[:=]\s*)[^\s,;]+",
        r"\1[redacted]",
        text,
    )
    text = " ".join(text.split())
    return text[:max_length] if text else "not_available"


def _xpoz_sdk_version() -> str:
    try:
        return version("xpoz")
    except PackageNotFoundError:
        return "not_available"


def _xpoz_exception_status(exc: Exception):
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) or getattr(exc, "status_code", None)


def _xpoz_traceback_location(exc: Exception) -> str:
    frames = traceback.extract_tb(exc.__traceback__)[-8:]
    if not frames:
        return "not_available"
    return " <- ".join(
        f"{frame.filename}:{frame.lineno} in {frame.name}"
        for frame in frames
    )


def _log_xpoz_failure(event: str, exc: Exception, api_key: str) -> None:
    cause = exc.__cause__ or exc.__context__
    logger.error(
        "%s: sdk_version=%s exception_type=%s status_code=%s operation_id=%s "
        "message=%s provider_error=%s cause_type=%s cause_message=%s traceback=%s",
        event,
        _xpoz_sdk_version(),
        type(exc).__name__,
        _xpoz_exception_status(exc) or "not_available",
        _redact_xpoz_diagnostic(getattr(exc, "operation_id", None), api_key),
        _redact_xpoz_diagnostic(exc, api_key),
        _redact_xpoz_diagnostic(getattr(exc, "error", None), api_key),
        type(cause).__name__ if cause else "not_available",
        _redact_xpoz_diagnostic(cause, api_key),
        _xpoz_traceback_location(exc),
    )


def _power_law_int(min_val: int, max_val: int, exponent: float = 2.0) -> int:
    """Generate a number following a power-law distribution (most values near min)."""
    u = random.random()
    val = min_val + (max_val - min_val) * (u ** exponent)
    return int(val)


def _seeded_choice(seed: str, choices: list):
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(choices)
    return choices[idx]


TWITTER_USERNAMES = [
    "migraine_warrior", "health_optimist", "chronic_pain_life", "neuro_news_daily",
    "headache_free_2024", "wellness_pulse", "neurology_watch", "pain_mgmt_pro",
    "patient_advocate_rx", "migraine_meds_info", "ev_enthusiast_mark", "green_car_guy",
    "charging_ahead", "zero_emission_life", "plugged_in_pete", "ev_road_tripper",
    "tesla_owner_club", "future_mobility", "clean_energy_now", "electric_jane",
    "health_researcher", "clinical_trials_info", "pharma_watch_daily", "patient_network",
    "digital_health_hub", "med_innovation", "rx_news_daily", "biotech_observer",
    "wellness_trends", "science_daily_feed", "ev_charging_review", "range_anxiety_no_more",
    "automaker_news", "ev_policy_watch", "sustainable_transport", "grid_insights",
    "battery_tech_fan", "smart_grid_life", "charging_station_map", "electric_vehicle_org",
]

REDDIT_USERS = [
    "throwaway_migraine_help", "neurology_nerd", "chronic_illness_support",
    "asking_for_a_friend_meds", "headache_diary_keeper", "wellness_skeptic",
    "ev_convert_2022", "range_tracker_pro", "charging_network_critic",
    "tesla_model3_owner", "nissan_leaf_daily", "phev_then_bev",
    "pharma_research_lurker", "clinical_trial_veteran", "drug_pricing_angry",
    "migraine_diet_experiments", "preventive_care_advocate", "headache_specialist_patient",
    "ev_infrastructure_critic", "home_charger_diy", "level2_charger_install",
    "workplace_ev_charging", "road_trip_ev_2024", "charging_while_you_sleep",
]

INSTAGRAM_USERS = [
    "wellness.by.sarah", "chronic.pain.diary", "neurology.nurse.life",
    "migraine.mom.of.3", "headache.free.journey", "rx.real.talk",
    "ev.lifestyle.blog", "clean.commute.crew", "charging.my.future",
    "zero.emissions.daily", "electric.family.life", "sustainable.jane",
    "health.advocate.official", "patient.power.movement", "clinical.truth",
    "pharma.transparency.now", "brain.health.tips", "migraine.warrior.ig",
    "ev.road.adventures", "plug.in.america", "battery.life.lover",
    "green.transport.fan", "charge.anywhere", "ev.charging.guide",
]

DISPLAY_NAMES = [
    "Sarah M.", "Alex Chen", "Jordan B.", "Maria R.", "Kevin P.",
    "Dr. Lisa N.", "Tom H.", "Ashley W.", "Chris D.", "Diana L.",
    "Ryan T.", "Emma S.", "James K.", "Rachel F.", "Matt G.",
    "Sophie A.", "Dan C.", "Olivia P.", "Mark Z.", "Jessica W.",
    "Carlos M.", "Amanda H.", "Steve B.", "Nicole T.", "Brian L.",
]

BIOS = {
    "twitter": [
        "Sharing my journey with chronic migraines 💊 | Patient advocate",
        "Neurologist | Headache specialist | Evidence-based medicine",
        "Living with migraines for 15 years. Found what works.",
        "EV enthusiast ⚡ | Sustainable transport advocate | Early adopter",
        "Charged my car 300+ times. Sharing what I've learned.",
        "Zero emissions by 2025 | Solar + EV lifestyle | Charging tips",
        "Healthcare researcher | Watching the pharma landscape | Opinions my own",
        "Chronic illness community builder | Support > suffering alone",
    ],
    "instagram": [
        "🌿 Wellness journey | Chronic pain management | DMs open",
        "⚡ EV lifestyle content | Sustainable living | Collab: dm me",
        "🧠 Neurological health advocate | Sharing my story daily",
        "🚗💚 All-electric family life | Charging tips & road trips",
        "Migraine warrior 💜 | Finding hope one day at a time",
    ],
    "reddit": [None],
}

MIGRAINE_POSTS = [
    "Just started Ubrelvy last month and I'm honestly shocked at how fast it works. 2 hours and my migraine was gone. No brain fog like I had with triptans.",
    "Three weeks on Ubrelvy and still adjusting. The nausea side effect is real but manageable. Anyone else experience this fading after a few uses?",
    "My neurologist switched me from sumatriptan to a CGRP inhibitor and the difference is night and day. Finally feel like I have my life back.",
    "Insurance denied my Ubrelvy prescription again. This is the 4th time. Does anyone have tips for fighting step therapy requirements?",
    "Trying to understand the difference between preventive and acute migraine treatments. My doctor mentioned Ubrelvy but I want to know more before filling.",
    "Day 45 with a new migraine preventive. Went from 18 migraine days/month to 6. Game changer for my quality of life.",
    "The cost of migraine medications is absolutely insane. $800/month without insurance? How is anyone supposed to afford this?",
    "Did anyone else notice Ubrelvy works better when taken early in the attack? My neurologist confirmed this is the recommended approach.",
    "Support group meeting tonight for chronic migraine. If you're in the Phoenix area, we meet at 7pm at the library. DM me for details.",
    "Tried every triptan on the market over 10 years. The newer gepants like Ubrelvy and rimegepant are genuinely different. Worth asking your doctor.",
    "Managing migraines and working full-time is exhausting. Just called in sick for the 3rd time this month. Considering FMLA.",
    "Heard about a clinical trial for a new CGRP monoclonal antibody. Anyone have experience participating in migraine research?",
    "My triggers: red wine, stress, skipped meals, weather changes. Been tracking for 6 months with the Migraine Buddy app. Highly recommend.",
    "Botox for migraines — 18 months in. Getting injections every 3 months. Went from chronic to episodic. Ask me anything.",
    "The migraine community is so supportive. Thank you all for being here. Rough week but getting through it together.",
    "Ubrelvy coupon from the manufacturer knocked my copay down to $10. Check their website if you're struggling with cost.",
    "Vestibular migraines are so misunderstood. Spinning, vertigo, nausea — and people think it's 'just a headache'.",
    "Finally got an appointment with a headache specialist. 6 month wait was worth it. Comprehensive evaluation and new treatment plan.",
    "OTC meds stopped working years ago. Went through 5 prescription options before finding one that actually works. Don't give up.",
    "Sharing my migraine diary with my doctor actually changed my treatment. Data matters. Track your attacks.",
]

EV_POSTS = [
    "Just completed a 400-mile road trip using only DC fast chargers. Total charging time: 45 minutes. The network has improved dramatically.",
    "Home charging setup complete! Level 2 EVSE installed in the garage. 30 miles of range added per hour. Morning commute covered.",
    "Frustrating experience at the charging station today. 2 of 4 chargers were out of service. This is the real barrier to EV adoption.",
    "Two years with my EV and I've spent $0 on gas and $180 on electricity for charging. The math is undeniable at this point.",
    "Range anxiety is mostly a myth if you plan ahead. 90% of trips are under 50 miles. Home charging handles everything.",
    "The new 350kW charging stations are incredible. Added 200 miles of range in 18 minutes. This is the future.",
    "Apartment dwellers: the lack of home charging infrastructure is a real barrier. Pushing my building management to install chargers.",
    "Workplace charging at my office has been a game-changer. Cars charge during the workday. No evening charging needed.",
    "EV charging etiquette PSA: please move your car when charging is complete. Others are waiting and you're blocking the stall.",
    "Tested 8 different public charging networks. Ranked them by reliability: ChargePoint > EVgo > Blink. YMMV.",
    "Cold weather reduced my range by 25%. Still made the trip but need to plan differently in winter. Preconditioning helps a lot.",
    "The V2H (vehicle-to-home) feature on my new EV is incredible. Powered my house during a 6-hour outage last week.",
    "Bought my EV knowing charging would require adjustments. 18 months later, it's completely natural. Don't overthink it.",
    "Fast charger pricing has gotten expensive. Was 28 cents/kWh, now 48 cents. Still cheaper than gas but the advantage is shrinking.",
    "Talked to 5 different EV owners at a charger today. Everyone loves their car. Anecdotal but the satisfaction is real.",
    "Concerned about the pace of public charging infrastructure vs EV adoption. We need more chargers before pushing everyone to EVs.",
    "Plugged in at the grocery store, the mall, and the gym today. Everywhere I go there are chargers now. 2019 me wouldn't believe it.",
    "DC fast charging is overhyped for daily use. Level 2 at home overnight is more economical and easier on the battery.",
    "My electricity rate is $0.12/kWh. Charging my EV to full costs $9. Equivalent tank of gas would be $60. Tell me again why you're hesitant.",
    "The charging network in rural areas is still inadequate. Had to plan 3 stops for a trip that would have been one gas fill-up.",
]

SENTIMENT_MAP = {
    "positive": (0.4, 1.0),
    "negative": (-1.0, -0.2),
    "neutral": (-0.15, 0.15),
    "mixed": (-0.1, 0.4),
}

SENTIMENT_WEIGHTS = [
    ("positive", 0.40),
    ("neutral", 0.30),
    ("negative", 0.20),
    ("mixed", 0.10),
]


def _pick_sentiment() -> tuple[str, float]:
    sentiments, weights = zip(*SENTIMENT_WEIGHTS)
    sentiment = random.choices(sentiments, weights=weights, k=1)[0]
    lo, hi = SENTIMENT_MAP[sentiment]
    score = round(random.uniform(lo, hi), 3)
    return sentiment, score


def _random_timestamp(date_from: Optional[datetime], date_to: Optional[datetime]) -> datetime:
    if not date_from:
        date_from = datetime.now(timezone.utc) - timedelta(days=180)
    if not date_to:
        date_to = datetime.now(timezone.utc)
    delta = (date_to - date_from).total_seconds()
    return date_from + timedelta(seconds=random.random() * delta)


def _parse_xpoz_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return _parse_xpoz_unix_timestamp(value)
    if isinstance(value, str) and value.strip().isdigit():
        return _parse_xpoz_unix_timestamp(value)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_xpoz_unix_timestamp(value) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(str(value)), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _format_xpoz_date(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.date().isoformat()


def _build_xpoz_date_kwargs(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    default_start_date: str = XPOZ_DEFAULT_START_DATE,
) -> dict:
    return {
        key: value
        for key, value in {
            "start_date": _format_xpoz_date(date_from) or default_start_date,
            "end_date": _format_xpoz_date(date_to),
        }.items()
        if value
    }


def _get_instagram_url(full_id: Optional[str]) -> Optional[str]:
    if not full_id:
        return None
    try:
        media_id = int(str(full_id).split("_")[0])
    except (TypeError, ValueError):
        return None

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    shortcode = ""

    while media_id > 0:
        media_id, remainder = divmod(media_id, 64)
        shortcode = alphabet[remainder] + shortcode

    if not shortcode:
        return None

    return f"https://instagram.com/p/{shortcode}/"


def _normalize_twitter_urls(urls) -> list[str]:
    if not urls:
        return []
    normalized = []
    for item in urls:
        if isinstance(item, str):
            normalized.append(item)
            continue
        expanded = getattr(item, "expanded_url", None) or getattr(item, "url", None)
        if expanded:
            normalized.append(expanded)
    return normalized


def _normalize_sequence(values) -> list[str]:
    if not values:
        return []
    normalized = []
    for item in values:
        if isinstance(item, str):
            normalized.append(item)
            continue
        value = getattr(item, "text", None) or getattr(item, "username", None) or getattr(item, "tag", None)
        if value:
            normalized.append(value)
    return normalized


def _generate_twitter_post(query: str, idx: int, date_from, date_to) -> dict:
    seed = f"twitter_{query}_{idx}"
    username = _seeded_choice(seed + "u", TWITTER_USERNAMES)
    display = _seeded_choice(seed + "d", DISPLAY_NAMES)
    bio = _seeded_choice(seed + "b", BIOS["twitter"])
    followers = _power_law_int(50, 85000, exponent=3)

    is_ev_query = any(w in query.lower() for w in ["ev", "electric", "charging", "tesla"])
    posts_pool = EV_POSTS if is_ev_query else MIGRAINE_POSTS
    body = _seeded_choice(seed + "body", posts_pool)

    hashtags = []
    if is_ev_query:
        hashtags = random.sample(["#EV", "#ElectricVehicle", "#EVCharging", "#CleanEnergy",
                                   "#ZeroEmissions", "#Tesla", "#Rivian", "#EVLife"], k=random.randint(1, 4))
    else:
        hashtags = random.sample(["#Migraine", "#ChronicPain", "#Ubrelvy", "#CGRP",
                                   "#HeadacheRelief", "#HealthAdvocate", "#MigraineWarrior"], k=random.randint(1, 3))

    likes = _power_law_int(0, 5000, exponent=3)
    shares = _power_law_int(0, int(likes * 0.3) + 1, exponent=2)
    comments = _power_law_int(0, int(likes * 0.15) + 1, exponent=2)
    engagement = round((likes + shares * 2 + comments * 1.5) / max(followers, 1) * 100, 4)
    sentiment, score = _pick_sentiment()
    published_at = _random_timestamp(date_from, date_to)

    return {
        "external_id": f"tw_{idx}_{hashlib.md5(seed.encode()).hexdigest()[:8]}",
        "platform": "twitter",
        "vendor": "xpoz",
        "author_username": username,
        "author_display_name": display,
        "author_followers": followers,
        "bio": bio,
        "body": body,
        "url": f"https://twitter.com/{username}/status/{random.randint(10**17, 10**18)}",
        "published_at": published_at,
        "likes": likes,
        "shares": shares,
        "comments": comments,
        "views": _power_law_int(likes, likes * 80, exponent=1.5),
        "engagement_score": engagement,
        "sentiment": sentiment,
        "sentiment_score": score,
        "hashtags": hashtags,
        "mentions": [],
        "media_urls": [],
        "language": "en",
        "extra_metadata": {"bio": bio},
    }


def _generate_instagram_post(query: str, idx: int, date_from, date_to) -> dict:
    seed = f"instagram_{query}_{idx}"
    username = _seeded_choice(seed + "u", INSTAGRAM_USERS)
    display = _seeded_choice(seed + "d", DISPLAY_NAMES)
    bio = _seeded_choice(seed + "b", BIOS["instagram"])
    followers = _power_law_int(200, 150000, exponent=3)

    is_ev_query = any(w in query.lower() for w in ["ev", "electric", "charging", "tesla"])
    posts_pool = EV_POSTS if is_ev_query else MIGRAINE_POSTS
    body = _seeded_choice(seed + "body", posts_pool) + " ✨"

    hashtags = []
    if is_ev_query:
        hashtags = random.sample(["#electricvehicle", "#evcharging", "#cleanenergy",
                                   "#sustainableliving", "#evlife", "#zeroemissions",
                                   "#greentransport", "#plugineverywhere"], k=random.randint(3, 7))
    else:
        hashtags = random.sample(["#migraine", "#chronicpain", "#invisibleillness",
                                   "#healthadvocate", "#migrainewarrior", "#brainhealth",
                                   "#patientadvocate", "#chronicillness"], k=random.randint(3, 6))

    likes = _power_law_int(10, 8000, exponent=3)
    comments = _power_law_int(0, int(likes * 0.08) + 1, exponent=2)
    engagement = round((likes + comments * 2) / max(followers, 1) * 100, 4)
    sentiment, score = _pick_sentiment()
    published_at = _random_timestamp(date_from, date_to)

    return {
        "external_id": f"ig_{idx}_{hashlib.md5(seed.encode()).hexdigest()[:8]}",
        "platform": "instagram",
        "vendor": "xpoz",
        "author_username": username,
        "author_display_name": display,
        "author_followers": followers,
        "bio": bio,
        "body": body,
        "url": f"https://www.instagram.com/p/{hashlib.md5(seed.encode()).hexdigest()[:11]}/",
        "published_at": published_at,
        "likes": likes,
        "shares": 0,
        "comments": comments,
        "views": _power_law_int(likes * 2, likes * 15, exponent=1.2),
        "engagement_score": engagement,
        "sentiment": sentiment,
        "sentiment_score": score,
        "hashtags": hashtags,
        "mentions": [],
        "media_urls": [f"https://cdn.instagram.com/img/{hashlib.md5(seed.encode()).hexdigest()}.jpg"],
        "language": "en",
        "extra_metadata": {"bio": bio},
    }


SUBREDDITS_MIGRAINE = ["r/migraine", "r/ChronicPain", "r/AskDocs", "r/pharmacy", "r/neurology"]
SUBREDDITS_EV = ["r/electricvehicles", "r/teslamotors", "r/leaf", "r/ChargingStations", "r/evcharging"]


def _generate_reddit_post(query: str, idx: int, date_from, date_to) -> dict:
    seed = f"reddit_{query}_{idx}"
    username = _seeded_choice(seed + "u", REDDIT_USERS)
    followers = _power_law_int(0, 50000, exponent=4)

    is_ev_query = any(w in query.lower() for w in ["ev", "electric", "charging", "tesla"])
    posts_pool = EV_POSTS if is_ev_query else MIGRAINE_POSTS
    subreddits = SUBREDDITS_EV if is_ev_query else SUBREDDITS_MIGRAINE
    body = _seeded_choice(seed + "body", posts_pool)
    subreddit = _seeded_choice(seed + "sub", subreddits)

    upvotes = _power_law_int(1, 3000, exponent=3)
    comments = _power_law_int(0, int(upvotes * 0.4) + 1, exponent=2)
    shares = _power_law_int(0, int(comments * 0.3) + 1, exponent=2)
    engagement = round((upvotes + comments * 2) / max(followers + 1, 1) * 100, 4)
    sentiment, score = _pick_sentiment()
    published_at = _random_timestamp(date_from, date_to)
    post_hash = hashlib.md5(seed.encode()).hexdigest()[:6]

    return {
        "external_id": f"rd_{idx}_{post_hash}",
        "platform": "reddit",
        "vendor": "xpoz",
        "author_username": username,
        "author_display_name": username,
        "author_followers": followers,
        "bio": None,
        "body": body,
        "url": f"https://www.reddit.com/{subreddit}/comments/{post_hash}/",
        "published_at": published_at,
        "likes": upvotes,
        "shares": shares,
        "comments": comments,
        "views": _power_law_int(upvotes * 5, upvotes * 50, exponent=1.2),
        "engagement_score": engagement,
        "sentiment": sentiment,
        "sentiment_score": score,
        "hashtags": [],
        "mentions": [],
        "media_urls": [],
        "language": "en",
        "extra_metadata": {"subreddit": subreddit, "upvote_ratio": round(random.uniform(0.6, 0.99), 2)},
    }


class MockXpozAdapter(VendorAdapter):
    """Generates realistic synthetic data for Twitter, Instagram, Reddit."""

    def get_supported_platforms(self) -> List[str]:
        return ["twitter", "instagram", "reddit"]

    async def search(
        self,
        query: str,
        platform: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int = 500,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        if cancellation:
            cancellation.raise_if_cancelled()
        count = min(max_results, random.randint(50, 200))
        results = []
        generators = {
            "twitter": _generate_twitter_post,
            "instagram": _generate_instagram_post,
            "reddit": _generate_reddit_post,
        }
        gen = generators.get(platform, _generate_twitter_post)
        for i in range(count):
            results.append(gen(query, i, date_from, date_to))
        if progress:
            await progress.before_request()
            await progress.page_received(new_posts=len(results))
        return results


class XpozAdapter(VendorAdapter):
    """Real Xpoz API adapter."""

    BASE_URL = "https://api.xpoz.io/v1"

    def __init__(self):
        self.api_key = settings.XPOZ_API_KEY
        self._mock = MockXpozAdapter()

    async def _before_provider_request(
        self,
        progress: Optional[ProviderProgressTracker],
    ) -> bool:
        if not progress:
            return True
        try:
            await progress.before_request()
            return True
        except PaginationSafeguardReached as exc:
            logger.warning(
                "Stopping Xpoz pagination (%s)",
                type(exc).__name__,
            )
            return False

    async def _record_provider_page(
        self,
        progress: Optional[ProviderProgressTracker],
        *,
        new_posts: int,
        cursor: object = None,
    ) -> bool:
        if not progress:
            return True
        try:
            await progress.page_received(
                new_posts=new_posts,
                cursor=cursor,
            )
            return True
        except PaginationSafeguardReached as exc:
            logger.warning(
                "Stopping Xpoz pagination (%s)",
                type(exc).__name__,
            )
            return False

    def _get_client(self):
        try:
            from xpoz import AsyncXpozClient
        except ImportError as exc:
            try:
                from xpoz import XpozClient
            except ImportError:
                logger.error("Xpoz SDK not installed: %s", exc)
                raise
            logger.warning(
                "Installed Xpoz SDK has no async client; falling back to a "
                "bounded background thread"
            )
            return XpozClient(
                self.api_key,
                timeout=settings.XPOZ_OPERATION_TIMEOUT_SECONDS,
            )
        return AsyncXpozClient(
            self.api_key,
            timeout=settings.XPOZ_OPERATION_TIMEOUT_SECONDS,
        )

    async def _close_client(self, client) -> None:
        close = getattr(client, "aclose", None) or getattr(client, "close", None)
        if not close:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    async def _connect_client(
        self,
        client,
        cancellation: Optional[CancellationSignal] = None,
    ) -> None:
        connect = getattr(client, "connect", None)
        if not connect:
            return
        await self._run_sdk_call(
            connect,
            cancellation=cancellation,
        )

    async def _run_sdk_call(
        self,
        operation,
        *args,
        cancellation: Optional[CancellationSignal] = None,
        **kwargs,
    ):
        if inspect.iscoroutinefunction(operation):
            request = lambda: operation(*args, **kwargs)
            if cancellation is None:
                return await xpoz_request_controller.run_async(request)
            return await xpoz_request_controller.run_async(
                request,
                cancellation=cancellation,
            )
        request = lambda: operation(*args, **kwargs)
        if cancellation is None:
            return await xpoz_request_controller.run_sync(request)
        return await xpoz_request_controller.run_sync(
            request,
            cancellation=cancellation,
        )

    def _get_response_type(self):
        try:
            from xpoz import ResponseType
            return ResponseType
        except ImportError:
            try:
                from xpoz.models import ResponseType
                return ResponseType
            except ImportError as exc:
                logger.error("Xpoz ResponseType is unavailable: %s", exc)
                raise

    def _normalize_twitter_post(self, tweet) -> dict:
        tweet_id = str(getattr(tweet, "id"))
        author_username = getattr(tweet, "author_username", None) or "anyuser"
        created_at = (
            _parse_xpoz_datetime(getattr(tweet, "created_at_date", None))
            or _parse_xpoz_unix_timestamp(getattr(tweet, "created_at", None))
        )
        media_urls = list(getattr(tweet, "media_urls", None) or [])
        urls = _normalize_twitter_urls(getattr(tweet, "urls", None))
        hashtags = _normalize_sequence(getattr(tweet, "hashtags", None))
        mentions = _normalize_sequence(getattr(tweet, "mentions", None))

        return {
            "external_id": tweet_id,
            "platform": "twitter",
            "vendor": "xpoz",
            "author_username": author_username,
            "author_display_name": author_username,
            "author_followers": 0,
            "bio": None,
            "body": getattr(tweet, "text", "") or "",
            "url": f"https://x.com/{author_username}/status/{tweet_id}",
            "published_at": created_at,
            "likes": int(getattr(tweet, "like_count", 0) or 0),
            "shares": int(getattr(tweet, "retweet_count", 0) or 0),
            "comments": int(getattr(tweet, "reply_count", 0) or 0),
            "views": int(getattr(tweet, "impression_count", 0) or 0),
            "engagement_score": 0.0,
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "hashtags": hashtags,
            "mentions": mentions,
            "media_urls": media_urls,
            "language": getattr(tweet, "lang", None) or "en",
            "extra_metadata": {
                "author_id": getattr(tweet, "author_id", None),
                "conversation_id": getattr(tweet, "conversation_id", None),
                "reply_to_tweet_id": getattr(tweet, "reply_to_tweet_id", None),
                "quote_count": int(getattr(tweet, "quote_count", 0) or 0),
                "urls": urls,
            },
        }

    def _normalize_instagram_post(self, post) -> dict:
        post_id = str(getattr(post, "id"))
        username = getattr(post, "username", None) or "unknown"
        created_at = (
            _parse_xpoz_datetime(getattr(post, "created_at_date", None))
            or _parse_xpoz_unix_timestamp(getattr(post, "created_at_timestamp", None))
            or _parse_xpoz_unix_timestamp(getattr(post, "created_at", None))
        )
        image_url = getattr(post, "image_url", None)
        video_url = getattr(post, "video_url", None)
        audio_only_url = getattr(post, "audio_only_url", None)
        media_urls = [url for url in [image_url, video_url, audio_only_url] if url]
        url = getattr(post, "code_url", None) or _get_instagram_url(post_id)

        return {
            "external_id": post_id,
            "platform": "instagram",
            "vendor": "xpoz",
            "author_username": username,
            "author_display_name": getattr(post, "full_name", None) or username,
            "author_followers": 0,
            "bio": None,
            "body": getattr(post, "caption", None) or "",
            "url": url,
            "published_at": created_at,
            "likes": int(getattr(post, "like_count", 0) or 0),
            "shares": int(getattr(post, "reshare_count", 0) or 0),
            "comments": int(getattr(post, "comment_count", 0) or 0),
            "views": int(getattr(post, "video_play_count", 0) or 0),
            "engagement_score": 0.0,
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "hashtags": [],
            "mentions": [],
            "media_urls": media_urls,
            "language": "en",
            "extra_metadata": {
                "user_id": getattr(post, "user_id", None),
                "post_type": getattr(post, "post_type", None),
                "media_type": getattr(post, "media_type", None),
                "location": getattr(post, "location", None),
                "profile_pic_url": getattr(post, "profile_pic_url", None),
                "video_duration": getattr(post, "video_duration", None),
                "video_subtitles_uri": getattr(post, "video_subtitles_uri", None),
                "subtitles": getattr(post, "subtitles", None),
            },
        }

    def _normalize_reddit_post(self, post) -> dict:
        post_id = str(getattr(post, "id"))
        author_username = getattr(post, "author_username", None) or "unknown"
        title = getattr(post, "title", None) or ""
        selftext = getattr(post, "selftext", None) or ""
        body = f"{title}\n\n{selftext}".strip() if selftext else title
        created_at = (
            _parse_xpoz_datetime(getattr(post, "created_at_date", None))
            or _parse_xpoz_unix_timestamp(getattr(post, "created_at", None))
        )

        return {
            "external_id": post_id,
            "platform": "reddit",
            "vendor": "xpoz",
            "author_username": author_username,
            "author_display_name": author_username,
            "author_followers": 0,
            "bio": None,
            "body": body,
            "url": f"https://redd.it/{post_id}",
            "published_at": created_at,
            "likes": int(getattr(post, "upvotes", 0) or getattr(post, "score", 0) or 0),
            "shares": 0,
            "comments": int(getattr(post, "comments_count", 0) or 0),
            "views": 0,
            "engagement_score": 0.0,
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "hashtags": [],
            "mentions": [],
            "media_urls": [],
            "language": "en",
            "extra_metadata": {
                "title": title,
                "subreddit_name": getattr(post, "subreddit_name", None),
                "score": int(getattr(post, "score", 0) or 0),
                "permalink": getattr(post, "permalink", None),
                "post_url": getattr(post, "post_url", None),
                "source_url": getattr(post, "url", None),
            },
        }

    def _in_date_range(
        self,
        published_at: Optional[datetime],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> bool:
        if not published_at:
            return True
        if date_from and published_at < date_from:
            return False
        if date_to and published_at > date_to:
            return False
        return True

    async def _search_twitter(
        self,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int,
        cancellation: Optional[CancellationSignal] = None,
        client=None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        client = client or self._get_client()
        if cancellation:
            cancellation.raise_if_cancelled()
        ResponseType = self._get_response_type()
        date_kwargs = _build_xpoz_date_kwargs(date_from, date_to)
    
        logger.info(
            "Xpoz Twitter paged search: query=%s limit=%s start_date=%s date_to=%s",
            query,
            max_results,
            date_kwargs.get("start_date"),
            date_kwargs.get("end_date"),
        )
        
        if max_results <= 300:
            response_type = getattr(ResponseType, "FAST", ResponseType.PAGING)
        else:
            response_type = ResponseType.PAGING

        if not await self._before_provider_request(progress):
            return []
        first_page = await self._call_twitter_search_posts(
            client=client,
            query=query,
            response_type=response_type,
            date_kwargs=date_kwargs,
            cancellation=cancellation,
        )

        normalized = []
        seen_external_ids = set()
        page = first_page
        page_count = 0
        consecutive_no_progress_pages = 0
        max_pages = settings.XPOZ_MAX_PAGES

        while page and len(normalized) < max_results and page_count < max_pages:
            page_count += 1
            collected_before_page = len(normalized)
            page_data = getattr(page, "data", []) or []
            pagination = getattr(page, "pagination", None)
            page_number = getattr(pagination, "page_number", page_count)
            total_rows = getattr(pagination, "total_rows", None)
            total_pages = getattr(pagination, "total_pages", None)
            logger.info(
                "Xpoz Twitter page received: query=%s page=%s items=%s collected=%s limit=%s total_rows=%s total_pages=%s",
                query,
                page_number,
                len(page_data),
                len(normalized),
                max_results,
                total_rows,
                total_pages,
            )

            for tweet in page_data:
                try:
                    post = self._normalize_twitter_post(tweet)
                except Exception as exc:
                    logger.warning("Skipping Xpoz Twitter post that failed normalization: %s", exc)
                    continue
                external_id = post.get("external_id")
                if external_id in seen_external_ids:
                    continue
                if not self._in_date_range(post["published_at"], date_from, date_to):
                    continue
                seen_external_ids.add(external_id)
                normalized.append(post)
                if len(normalized) >= max_results:
                    break

            if cancellation and cancellation.is_cancelled:
                break
            new_posts_this_page = len(normalized) - collected_before_page
            if not await self._record_provider_page(
                progress,
                new_posts=new_posts_this_page,
                cursor=page_number,
            ):
                break
            if new_posts_this_page == 0:
                consecutive_no_progress_pages += 1
                logger.warning(
                    "Xpoz Twitter page added no new posts: query=%s page=%s repeated_no_progress_pages=%s collected=%s limit=%s",
                    query,
                    page_number,
                    consecutive_no_progress_pages,
                    len(normalized),
                    max_results,
                )
            else:
                consecutive_no_progress_pages = 0

            if len(normalized) >= max_results:
                break
            if consecutive_no_progress_pages >= 3:
                logger.warning(
                    "Stopping Xpoz Twitter paging after %s consecutive pages with no new posts; returning %s collected posts",
                    consecutive_no_progress_pages,
                    len(normalized),
                )
                break
            if not getattr(page, "has_next_page", lambda: False)():
                break
            if not await self._before_provider_request(progress):
                break
            try:
                page = await self._run_sdk_call(
                    page.next_page,
                    cancellation=cancellation,
                )
            except CollectionCancelled:
                break
            except (ProviderRepeated502Error, ProviderRetryBudgetExceeded):
                raise
            except Exception as exc:
                logger.warning(
                    "Stopping Xpoz Twitter paging after page %s because next_page failed; returning %s collected posts (%s)",
                    page_number,
                    len(normalized),
                    type(exc).__name__,
                )
                break

        logger.info(
            "Xpoz Twitter paged search succeeded: query=%s count=%s pages=%s total_rows=%s total_pages=%s",
            query,
            len(normalized),
            page_count,
            getattr(getattr(first_page, "pagination", None), "total_rows", None),
            getattr(getattr(first_page, "pagination", None), "total_pages", None),
        )
        return normalized

    async def _call_twitter_search_posts(
        self,
        client,
        query: str,
        response_type,
        date_kwargs: dict,
        cancellation: Optional[CancellationSignal] = None,
    ):
        kwargs = {
            "response_type": response_type,
            **date_kwargs,
        }
        kwargs = {key: value for key, value in kwargs.items() if value is not None}
        return await self._call_search_posts_with_date_fallback(
            client.twitter.search_posts,
            query,
            kwargs,
            cancellation,
        )

    async def _call_search_posts_with_date_fallback(
        self,
        search_fn,
        query: str,
        kwargs: dict,
        cancellation: Optional[CancellationSignal] = None,
    ):
        try:
            return await self._run_sdk_call(
                search_fn,
                query,
                cancellation=cancellation,
                **kwargs,
            )
        except TypeError:
            if "end_date" in kwargs:
                logger.warning("Xpoz search rejected end_date; retrying without it")
                retry_kwargs = {key: value for key, value in kwargs.items() if key != "end_date"}
                return await self._run_sdk_call(
                    search_fn,
                    query,
                    cancellation=cancellation,
                    **retry_kwargs,
                )
            if "start_date" in kwargs:
                logger.warning("Xpoz search rejected start_date; retrying without date kwargs")
                retry_kwargs = {key: value for key, value in kwargs.items() if key != "start_date"}
                return await self._run_sdk_call(
                    search_fn,
                    query,
                    cancellation=cancellation,
                    **retry_kwargs,
                )
            raise

    async def _search_instagram(
        self,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int,
        cancellation: Optional[CancellationSignal] = None,
        client=None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        client = client or self._get_client()
        if cancellation:
            cancellation.raise_if_cancelled()
        date_kwargs = _build_xpoz_date_kwargs(date_from, date_to)
        # FOR TESTING
        test_limit = min(max_results, 300)

        logger.info(
            "Xpoz Instagram search: query=%s limit=%s date_from=%s date_to=%s",
            query,
            test_limit,
            date_from,
            date_to,
        )
        if not await self._before_provider_request(progress):
            return []
        try:
            results = await self._call_search_posts_with_date_fallback(
                client.instagram.search_posts,
                query,
                {
                    **date_kwargs,
                    "limit": test_limit,
                    "fields": XPOZ_INSTAGRAM_POST_FIELDS,
                },
                cancellation,
            )
        except CollectionCancelled:
            raise
        except Exception as exc:
            _log_xpoz_failure("Xpoz Instagram SDK call failed", exc, self.api_key)
            raise

        normalized = []
        for post in getattr(results, "data", []) or []:
            item = self._normalize_instagram_post(post)
            if self._in_date_range(item["published_at"], date_from, date_to):
                normalized.append(item)
        await self._record_provider_page(
            progress,
            new_posts=len(normalized),
        )
        logger.info("Xpoz Instagram search succeeded: query=%s count=%s", query, len(normalized))
        return normalized

    async def _search_reddit(
        self,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int,
        cancellation: Optional[CancellationSignal] = None,
        client=None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        client = client or self._get_client()
        if cancellation:
            cancellation.raise_if_cancelled()
        date_kwargs = _build_xpoz_date_kwargs(date_from, date_to)
        test_limit = min(max_results, 300)
        
        logger.info(
            "Xpoz Reddit search: query=%s limit=%s date_from=%s date_to=%s",
            query,
            test_limit,
            date_from,
            date_to,
        )
        if not await self._before_provider_request(progress):
            return []
        results = await self._call_search_posts_with_date_fallback(
            client.reddit.search_posts,
            query,
            {
                **date_kwargs,
                "limit": test_limit,
                "sort": "relevance",
                "fields": XPOZ_REDDIT_POST_FIELDS,
            },
            cancellation,
        )
        normalized = []
        for post in getattr(results, "data", []) or []:
            item = self._normalize_reddit_post(post)
            if self._in_date_range(item["published_at"], date_from, date_to):
                normalized.append(item)
        await self._record_provider_page(
            progress,
            new_posts=len(normalized),
        )
        logger.info("Xpoz Reddit search succeeded: query=%s count=%s", query, len(normalized))
        return normalized

    def get_supported_platforms(self) -> List[str]:
        return ["twitter", "instagram", "reddit"]

    async def search(
        self,
        query: str,
        platform: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int = 500,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        if cancellation:
            cancellation.raise_if_cancelled()
        if not self.api_key:
            return []

        normalized_platform = platform.lower()
        if normalized_platform in {"twitter", "instagram", "reddit"}:
            client = self._get_client()
            try:
                try:
                    await self._connect_client(client, cancellation)
                except CollectionCancelled:
                    raise
                except Exception as exc:
                    _log_xpoz_failure(
                        "Xpoz SDK client connect failed",
                        exc,
                        self.api_key,
                    )
                    raise
                if normalized_platform == "twitter":
                    return await self._search_twitter(
                        query,
                        date_from,
                        date_to,
                        max_results,
                        cancellation,
                        client,
                        progress,
                    )
                if normalized_platform == "instagram":
                    return await self._search_instagram(
                        query,
                        date_from,
                        date_to,
                        max_results,
                        cancellation,
                        client,
                        progress,
                    )
                return await self._search_reddit(
                    query,
                    date_from,
                    date_to,
                    max_results,
                    cancellation,
                    client,
                    progress,
                )
            finally:
                await self._close_client(client)

        async with httpx.AsyncClient() as client:
            if not await self._before_provider_request(progress):
                return []
            async def request():
                response = await client.post(
                    f"{self.BASE_URL}/search",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "query": query,
                        "platform": platform,
                        "date_from": date_from.isoformat() if date_from else None,
                        "date_to": date_to.isoformat() if date_to else None,
                        "max_results": max_results,
                    },
                    timeout=settings.XPOZ_OPERATION_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                return response

            if cancellation is None:
                response = await xpoz_request_controller.run_async(request)
            else:
                response = await xpoz_request_controller.run_async(
                    request,
                    cancellation=cancellation,
                )
            results = response.json().get("results", [])
            await self._record_provider_page(
                progress,
                new_posts=len(results),
            )
            return results
