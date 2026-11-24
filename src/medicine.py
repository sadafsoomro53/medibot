"""Medicine lookup using the free openFDA drug label API (https://open.fda.gov/apis/drug/label/).

Returns uses, warnings and side effects only. Dosage sections are deliberately left out.
openFDA covers US-labelled medicines; for local brand names, search by the generic name
(e.g. "paracetamol" -> try "acetaminophen").
"""
import difflib
import logging
import re
import threading
import time

import requests

log = logging.getLogger(__name__)

_API = "https://api.fda.gov/drug/label.json"
_SECTIONS = [
    ("purpose", "Purpose"),
    ("indications_and_usage", "Uses"),
    ("warnings", "Warnings"),
    ("boxed_warning", "Boxed warning"),
    ("do_not_use", "Do not use if"),
    ("ask_doctor", "Ask a doctor before use if"),
    ("stop_use", "Stop use and ask a doctor if"),
    ("adverse_reactions", "Side effects"),
    ("pregnancy_or_breast_feeding", "Pregnancy / breast-feeding"),
]
# Common names outside the US (incl. Pakistani brands) -> US generic name
_ALIASES = {
    "paracetamol": "acetaminophen", "panadol": "acetaminophen", "calpol": "acetaminophen",
    "tylenol": "acetaminophen", "salbutamol": "albuterol", "ventolin": "albuterol",
    "adrenaline": "epinephrine", "brufen": "ibuprofen", "advil": "ibuprofen", "motrin": "ibuprofen",
    "disprin": "aspirin", "loprin": "aspirin", "ponstan": "mefenamic acid", "flagyl": "metronidazole",
    "augmentin": "amoxicillin and clavulanate potassium", "amoxil": "amoxicillin",
    "glucophage": "metformin", "risek": "omeprazole", "nexium": "esomeprazole", "zantac": "ranitidine",
    "softin": "loratadine", "claritin": "loratadine", "zyrtec": "cetirizine", "rigix": "cetirizine",
    "arinac": "ibuprofen and pseudoephedrine", "telfast": "fexofenadine", "allegra": "fexofenadine",
    "voltaren": "diclofenac", "voltral": "diclofenac", "dicloran": "diclofenac", "caflam": "diclofenac",
    "ciproxin": "ciprofloxacin", "cipro": "ciprofloxacin", "leflox": "levofloxacin", "tavanic": "levofloxacin",
    "klaricid": "clarithromycin", "vibramycin": "doxycycline", "ceclor": "cefaclor", "keflex": "cephalexin",
    "lipitor": "atorvastatin", "lipiget": "atorvastatin", "crestor": "rosuvastatin", "zocor": "simvastatin",
    "norvasc": "amlodipine", "cozaar": "losartan", "concor": "bisoprolol", "tenormin": "atenolol",
    "inderal": "propranolol", "lasix": "furosemide", "aldactone": "spironolactone", "zestril": "lisinopril",
    "coumadin": "warfarin", "plavix": "clopidogrel", "ecosprin": "aspirin", "xarelto": "rivaroxaban",
    "eliquis": "apixaban", "zithromax": "azithromycin", "azomax": "azithromycin",
    "imodium": "loperamide", "gravinate": "dimenhydrinate", "zofran": "ondansetron",
    "maxolon": "metoclopramide", "duphalac": "lactulose", "dulcolax": "bisacodyl", "losec": "omeprazole",
    "nexum": "esomeprazole", "protonix": "pantoprazole", "pepcid": "famotidine",
    "amaryl": "glimepiride", "januvia": "sitagliptin", "jardiance": "empagliflozin", "forxiga": "dapagliflozin",
    "lantus": "insulin glargine", "euthyrox": "levothyroxine", "synthroid": "levothyroxine",
    "thyroxine": "levothyroxine", "deltacortril": "prednisolone", "decadron": "dexamethasone",
    "singulair": "montelukast", "myteka": "montelukast", "seretide": "fluticasone propionate and salmeterol",
    "pulmicort": "budesonide", "benadryl": "diphenhydramine", "piriton": "chlorpheniramine",
    "mucinex": "guaifenesin", "xanax": "alprazolam", "valium": "diazepam", "prozac": "fluoxetine",
    "zoloft": "sertraline", "cipralex": "escitalopram", "lexapro": "escitalopram", "cymbalta": "duloxetine",
    "tryptanol": "amitriptyline", "seroquel": "quetiapine", "risperdal": "risperidone", "ambien": "zolpidem",
    "neurontin": "gabapentin", "lyrica": "pregabalin", "tramal": "tramadol", "tegral": "carbamazepine",
    "tegretol": "carbamazepine", "keppra": "levetiracetam", "depakote": "divalproex sodium",
    "zyloric": "allopurinol", "mobic": "meloxicam", "celebrex": "celecoxib", "naprosyn": "naproxen",
    "diflucan": "fluconazole", "zovirax": "acyclovir", "valtrex": "valacyclovir", "tamiflu": "oseltamivir",
    "zentel": "albendazole", "vermox": "mebendazole", "septran": "sulfamethoxazole and trimethoprim",
    "bactrim": "sulfamethoxazole and trimethoprim", "dalacin": "clindamycin", "macrobid": "nitrofurantoin",
    "lamisil": "terbinafine", "canesten": "clotrimazole", "bactroban": "mupirocin", "flomax": "tamsulosin",
    "viagra": "sildenafil", "cialis": "tadalafil", "cyklokapron": "tranexamic acid", "transamin": "tranexamic acid",
    "plaquenil": "hydroxychloroquine", "aldomet": "methyldopa", "lanoxin": "digoxin",
}
# Generic names we can correct spelling towards
_GENERICS = [
    "acetaminophen", "ibuprofen", "aspirin", "naproxen", "diclofenac", "mefenamic acid", "albuterol",
    "epinephrine", "amoxicillin", "azithromycin", "ciprofloxacin", "metronidazole", "doxycycline",
    "cephalexin", "clarithromycin", "levofloxacin", "metformin", "insulin", "glimepiride", "omeprazole",
    "esomeprazole", "pantoprazole", "ranitidine", "famotidine", "loratadine", "cetirizine",
    "fexofenadine", "diphenhydramine", "chlorpheniramine", "atorvastatin", "rosuvastatin", "simvastatin",
    "amlodipine", "losartan", "lisinopril", "metoprolol", "atenolol", "furosemide", "hydrochlorothiazide",
    "warfarin", "clopidogrel", "levothyroxine", "prednisone", "prednisolone", "dexamethasone",
    "montelukast", "loperamide", "ondansetron", "dimenhydrinate", "sertraline",
    "fluoxetine", "escitalopram", "alprazolam", "diazepam", "gabapentin", "tramadol", "codeine",
    "fluconazole", "acyclovir", "ivermectin", "albendazole", "folic acid", "ferrous sulfate",
    # pain & inflammation
    "meloxicam", "celecoxib", "ketorolac", "indomethacin", "cyclobenzaprine", "baclofen", "morphine",
    "oxycodone", "naloxone", "colchicine", "allopurinol",
    # antibiotics, antivirals, antifungals, antiparasitics
    "cefaclor", "cefixime", "ceftriaxone", "cefuroxime", "clindamycin", "nitrofurantoin", "trimethoprim",
    "sulfamethoxazole and trimethoprim", "linezolid", "vancomycin", "gentamicin", "penicillin",
    "isoniazid", "rifampin", "ethambutol", "pyrazinamide", "valacyclovir", "oseltamivir", "mebendazole",
    "ketoconazole", "clotrimazole", "terbinafine", "mupirocin", "permethrin", "hydroxychloroquine",
    # heart & blood
    "bisoprolol", "propranolol", "carvedilol", "valsartan", "telmisartan", "candesartan", "enalapril",
    "spironolactone", "digoxin", "nitroglycerin", "isosorbide mononitrate", "methyldopa", "rivaroxaban",
    "apixaban", "heparin", "tranexamic acid",
    # diabetes & hormones
    "glipizide", "glyburide", "pioglitazone", "sitagliptin", "empagliflozin", "dapagliflozin",
    "insulin glargine", "medroxyprogesterone", "levonorgestrel", "misoprostol",
    # stomach & gut
    "metoclopramide", "lactulose", "bisacodyl", "calcium carbonate", "magnesium hydroxide",
    # allergy, cough & breathing
    "levocetirizine", "desloratadine", "dextromethorphan", "guaifenesin", "pseudoephedrine",
    "phenylephrine", "fluticasone", "budesonide", "salmeterol", "ipratropium",
    # brain & mental health
    "pregabalin", "carbamazepine", "levetiracetam", "divalproex sodium", "lamotrigine", "amitriptyline",
    "duloxetine", "venlafaxine", "bupropion", "quetiapine", "risperidone", "olanzapine", "lithium",
    "zolpidem",
    # urology & other
    "tamsulosin", "finasteride", "oxybutynin", "sildenafil", "tadalafil", "hydrocortisone",
]
_KNOWN = sorted(set(_ALIASES) | set(_GENERICS))

_cache: dict[str, tuple[float, dict | None]] = {}
_cache_lock = threading.Lock()
_TTL = 6 * 3600


def _clean(text: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _resolve(key: str) -> tuple[str, str | None]:
    """Map a typed name to the generic we search for. Returns (search_key, corrected_name or None)."""
    if key in _ALIASES:
        return _ALIASES[key], None
    if key in _GENERICS:
        return key, None
    match = difflib.get_close_matches(key, _KNOWN, n=1, cutoff=0.75)
    if match:
        return _ALIASES.get(match[0], match[0]), match[0]
    return key, None


def _get(params: dict) -> requests.Response:
    """GET openFDA, retrying briefly on timeouts and 5xx/429 (its API is sometimes flaky)."""
    for attempt in range(3):
        try:
            resp = requests.get(_API, params=params, timeout=8)
            if resp.status_code < 500 and resp.status_code != 429:
                return resp
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise
        time.sleep(0.6 * (attempt + 1))
    resp.raise_for_status()
    return resp


def lookup(name: str) -> dict | None:
    key = re.sub(r"[^a-z0-9 \-]", "", name.lower()).strip()
    if not key:
        return None
    key, corrected = _resolve(key)
    with _cache_lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        result = hit[1]
    else:
        result = _fetch(key)
        with _cache_lock:
            if len(_cache) > 500:
                _cache.clear()
            _cache[key] = (time.time(), result)
    # query/corrected depend on what this user typed, so they are added per request
    return {**result, "query": name, "corrected": corrected} if result else None


def _fetch(key: str) -> dict | None:

    q = f'openfda.generic_name:"{key}" OR openfda.brand_name:"{key}" OR openfda.substance_name:"{key}"'
    try:
        resp = _get({"search": q, "limit": 1})
        if resp.status_code == 404:
            result = None
        else:
            resp.raise_for_status()
            item = resp.json()["results"][0]
            fda = item.get("openfda", {})
            sections = []
            for field, label in _SECTIONS:
                if item.get(field):
                    sections.append({"label": label, "text": _clean(" ".join(item[field]))})
            result = {
                "brand": ", ".join(fda.get("brand_name", [])[:3]) or None,
                "generic": ", ".join(fda.get("generic_name", [])[:3]) or key,
                "route": ", ".join(fda.get("route", [])[:3]) or None,
                "manufacturer": ", ".join(fda.get("manufacturer_name", [])[:1]) or None,
                "sections": sections,
                "source": "U.S. FDA drug label (openFDA)",
            }
    except requests.RequestException:
        log.warning("openFDA lookup failed", exc_info=True)
        raise
    return result
