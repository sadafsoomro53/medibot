"""Safety checks: emergency detection and content moderation."""
import logging
import re

log = logging.getLogger(__name__)

# Phrases that suggest a medical or mental-health emergency (English, Roman Urdu, Urdu).
_EMERGENCY_PATTERNS = [
    r"\bchest pain\b", r"\bheart attack\b", r"\bcan'?t breathe\b", r"\bcannot breathe\b",
    r"\b(difficulty|trouble) breathing\b", r"\bnot breathing\b", r"\bstroke\b.*\b(now|happening|symptoms)\b",
    r"\bface (is )?drooping\b", r"\bslurred speech\b", r"\bunconscious\b", r"\bpassed out\b",
    r"\bseizure\b", r"\bsevere bleeding\b", r"\bbleeding (heavily|a lot|won'?t stop)\b",
    r"\boverdose\b", r"\bpoison(ed|ing)\b", r"\bsuicid", r"\bkill (myself|me)\b",
    r"\bend my life\b", r"\bwant to die\b", r"\bself[- ]harm\b", r"\bhurt myself\b",
    r"\banaphyla", r"\bthroat (is )?(closing|swelling)\b",
    # Roman Urdu
    r"\bseene (mein|me) dard\b", r"\bsaans nahi\b", r"\bsaans (lene )?(mein|me) (dikkat|mushkil)\b",
    r"\bbehosh\b", r"\bkhudkushi\b", r"\bmarna chahta\b", r"\bmarna chahti\b", r"\bkhoon (bohat|bahut) beh\b",
    # Urdu script
    "سینے میں درد", "سانس نہیں", "بے ہوش", "خودکشی", "مرنا چاہتا", "مرنا چاہتی",
]
_EMERGENCY_RE = re.compile("|".join(_EMERGENCY_PATTERNS), re.IGNORECASE)

# Moderation categories that block a request outright.
_BLOCK_CATEGORIES = {
    "sexual/minors", "hate/threatening", "violence/graphic", "illicit/violent", "harassment/threatening",
}
# Categories that should trigger the emergency/support banner (but still get an answer).
_SUPPORT_CATEGORIES = {"self-harm", "self-harm/intent", "self-harm/instructions"}

BLOCKED_REPLY = (
    "I'm sorry, but I can't help with that request. I'm here to answer general medical and health "
    "questions. Is there something health-related I can help you with?"
)


def looks_like_emergency(text: str) -> bool:
    return bool(_EMERGENCY_RE.search(text or ""))


def moderate(text: str, api_key: str | None) -> dict:
    """Return {"blocked": bool, "support": bool}. Fails open (never blocks) if the API is unreachable."""
    result = {"blocked": False, "support": False}
    if not api_key:
        return result
    try:
        from openai import OpenAI

        resp = OpenAI(api_key=api_key, timeout=8).moderations.create(
            model="omni-moderation-latest", input=text
        )
        r = resp.results[0]
        cats = {k for k, v in r.categories.model_dump(by_alias=True).items() if v}
        result["blocked"] = bool(cats & _BLOCK_CATEGORIES)
        result["support"] = bool(cats & _SUPPORT_CATEGORIES)
        if cats:
            log.info("Moderation flagged categories: %s", sorted(cats))
    except Exception:
        log.warning("Moderation check failed; continuing without it", exc_info=True)
    return result
