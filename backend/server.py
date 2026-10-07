from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import re
import json
import uuid
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Annotated

import bcrypt
import jwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, EmailStr, Field, ConfigDict

# NLP resources are optional at import time: if a package is missing, the
# server must still boot (and fall back to the built-in word bank) rather
# than crash and take every endpoint down with it.
try:
    import nltk
    from nltk.corpus import wordnet as wn
except ImportError:  # pragma: no cover
    nltk = None
    wn = None
try:
    import pronouncing
except ImportError:  # pragma: no cover
    pronouncing = None

# ---------------- MongoDB ----------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# ---------------- App ----------------
app = FastAPI()
api_router = APIRouter(prefix="/api")

JWT_ALGO = "HS256"
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

GUEST_WORD_LIMIT = 350

# ---------------- Models ----------------
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x) if isinstance(x, ObjectId) else x)]


class UserPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    email: EmailStr
    name: str
    created_at: Optional[str] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RephraseRequest(BaseModel):
    text: str
    mode: str = "synonym"  # synonym, antonym, rhyme, syllable, academic, conversational


class WordAlternativesRequest(BaseModel):
    word: str
    mode: str = "synonym"
    context: Optional[str] = ""


class DetectRequest(BaseModel):
    text: str


# ---------------- Password / JWT ----------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["id"] = str(user["_id"])
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_optional_user(request: Request) -> Optional[dict]:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )


# ---------------- POS heuristic ----------------
COMMON_PREPOSITIONS = {"in", "on", "at", "of", "for", "with", "to", "from", "by", "about",
                       "as", "into", "through", "during", "before", "after", "above", "below",
                       "between", "under", "over", "against", "among", "along", "across",
                       "behind", "beside", "beyond", "near", "off", "onto", "upon", "within",
                       "without", "toward", "towards"}
COMMON_ADVERBS_ENDINGS = ("ly",)
COMMON_ADJ_ENDINGS = ("ous", "ful", "ive", "able", "ible", "ical", "less", "ish", "al")
COMMON_VERB_ENDINGS = ("ing", "ed", "ate", "ize", "ise", "fy")
COMMON_NOUN_ENDINGS = ("tion", "sion", "ment", "ness", "ity", "ship", "hood", "ance", "ence")
COMMON_VERBS = {"is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
                "do", "does", "did", "will", "would", "shall", "should", "can", "could",
                "may", "might", "must", "make", "made", "get", "got", "go", "went", "gone",
                "come", "came", "see", "saw", "know", "knew", "think", "thought", "take",
                "took", "give", "gave", "find", "found", "want", "need", "use", "used"}
STOPWORDS = {"the", "a", "an", "and", "or", "but", "if", "then", "so", "not", "no", "yes",
             "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
             "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their"}


def classify_word(word: str) -> str:
    w = word.lower().strip(".,!?;:\"'()[]")
    if not w or not w.isalpha():
        return "other"
    if w in COMMON_PREPOSITIONS:
        return "prepositions"
    if w in COMMON_VERBS:
        return "verbs"
    if w in STOPWORDS:
        return "other"
    if w.endswith(COMMON_ADVERBS_ENDINGS) and len(w) > 3:
        return "adverbs"
    if w.endswith(COMMON_ADJ_ENDINGS):
        return "adjectives"
    if w.endswith(COMMON_VERB_ENDINGS):
        return "verbs"
    if w.endswith(COMMON_NOUN_ENDINGS):
        return "nouns"
    if w[0].isupper() and len(w) > 2:
        return "nouns"
    return "nouns"


def analyze_pos(text: str) -> dict:
    words = re.findall(r"[A-Za-z]+", text)
    buckets = {"nouns": [], "verbs": [], "adjectives": [], "adverbs": [], "prepositions": []}
    seen = {k: set() for k in buckets}
    for w in words:
        cat = classify_word(w)
        if cat in buckets and w.lower() not in seen[cat]:
            buckets[cat].append(w)
            seen[cat].add(w.lower())
    return buckets


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


# ---------------- LLM (OpenAI) ----------------
def _openai_client():
    if not OPENAI_API_KEY:
        return None
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY)


def llm_json(system: str, user: str) -> Optional[dict]:
    cli = _openai_client()
    if cli is None:
        return None
    try:
        resp = cli.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logging.warning(f"LLM error: {e}")
        return None


# ---------------- Rephrase logic ----------------
MODE_INSTRUCTIONS = {
    "synonym": "Replace 30-50% of the significant words with close synonyms while preserving meaning.",
    "antonym": "Rephrase using antonym-based inversions (double-negatives etc.) that preserve overall meaning.",
    "rhyme": "Rephrase substituting select words with rhyming alternatives that still fit context.",
    "syllable": "Rephrase swapping select words for syllable-flipped or reordered-syllable variants that read naturally.",
    "academic": "Rewrite in a formal academic register while preserving meaning; vary sentence structure.",
    "conversational": "Rewrite in a natural conversational human tone that bypasses AI detection; use varied sentence rhythm.",
}

# Small offline synonym bank as a fallback
FALLBACK_SYNONYMS = {
    "important": ["crucial", "vital", "essential", "significant"],
    "good": ["excellent", "fine", "solid", "great"],
    "bad": ["poor", "awful", "subpar", "lousy"],
    "big": ["large", "huge", "massive", "sizable"],
    "small": ["tiny", "little", "compact", "modest"],
    "make": ["create", "produce", "craft", "build"],
    "use": ["utilize", "employ", "leverage", "apply"],
    "help": ["assist", "aid", "support", "facilitate"],
    "show": ["display", "demonstrate", "reveal", "present"],
    "think": ["consider", "believe", "reckon", "reason"],
    "many": ["numerous", "several", "countless", "various"],
    "problem": ["issue", "challenge", "obstacle", "difficulty"],
    "start": ["begin", "commence", "initiate", "launch"],
    "end": ["conclude", "finish", "terminate", "wrap up"],
    "great": ["excellent", "superb", "outstanding", "remarkable"],
    "quickly": ["swiftly", "rapidly", "promptly", "speedily"],
    "however": ["nevertheless", "nonetheless", "yet", "though"],
    "therefore": ["consequently", "hence", "thus", "accordingly"],
    "because": ["since", "as", "given that", "owing to"],
    "very": ["extremely", "highly", "particularly", "notably"],
    "people": ["individuals", "folks", "persons", "populace"],
    "world": ["realm", "sphere", "domain", "planet"],
    "life": ["existence", "living", "experience", "journey"],
    "time": ["period", "moment", "span", "era"],
    "way": ["manner", "method", "approach", "route"],
    "work": ["labor", "toil", "task", "effort"],
    "new": ["fresh", "novel", "recent", "modern"],
    "old": ["aged", "vintage", "ancient", "seasoned"],
    "different": ["distinct", "varied", "diverse", "unlike"],
    "same": ["identical", "equivalent", "matching", "similar"],
}


# ---------------- WordNet (synonym / antonym source of truth) ----------------
# WordNet is used for "synonym" and "antonym" modes always, even when an LLM
# key is configured — it's free, deterministic, and WordNet's lemma/antonym
# relations are exactly what those two modes need. The LLM is reserved for
# the modes that aren't lexical-database problems (rhyme, syllable-flip,
# academic, conversational).
_WORDNET_READY = False

# Literal WordNet POS tags (n/v/a/r). Do NOT use wn.NOUN etc. here: reading
# them at import time forces the corpus to load and crashes the server on a
# machine that hasn't downloaded it yet.
_POS_TO_WORDNET = {
    "nouns": "n",
    "verbs": "v",
    "adjectives": "a",
    "adverbs": "r",
}


def ensure_wordnet() -> bool:
    """Make sure the NLTK WordNet corpus is downloaded and loadable.

    Self-healing: tries a cheap lookup first: if the corpus is already
    present (or was already confirmed this process), this is a no-op. If
    it's missing, attempts a one-time download. On any failure (e.g. no
    network access at this moment) it logs a warning and returns False;
    callers fall back to the small hardcoded FALLBACK_SYNONYMS bank so a
    missing corpus degrades the feature instead of crashing requests.
    """
    global _WORDNET_READY
    if _WORDNET_READY:
        return True
    if nltk is None or wn is None:
        return False
    try:
        wn.synsets("test")
        _WORDNET_READY = True
        return True
    except LookupError:
        try:
            nltk.download("wordnet", quiet=True)
            nltk.download("omw-1.4", quiet=True)
            wn.synsets("test")
            _WORDNET_READY = True
            return True
        except Exception as e:
            logging.warning(f"WordNet corpus unavailable, using fallback word bank: {e}")
            return False
    except Exception as e:
        logging.warning(f"WordNet check failed, using fallback word bank: {e}")
        return False


def _wordnet_pos(word: str):
    """Map our POS heuristic onto WordNet's POS tags, or None to search all."""
    return _POS_TO_WORDNET.get(classify_word(word))


def _wordnet_synsets(word: str, pos) -> list:
    """Synsets for word, preferring the guessed POS but never trusting a
    wrong guess to hide real results: our suffix-based classify_word()
    heuristic (built for the POS sidebar, not lexical lookup) defaults to
    "nouns" for anything it doesn't recognize, which misclassifies plenty of
    common adjectives ("happy", "important", "big", "fast", ...). A
    POS-restricted search for those returns nothing even though WordNet has
    entries, so an empty restricted result always falls back to an
    unrestricted search rather than being treated as "no synonyms"."""
    try:
        if pos:
            restricted = wn.synsets(word, pos=pos)
            if restricted:
                return restricted
        return wn.synsets(word)
    except Exception:
        return []


def wordnet_synonyms(word: str, limit: int = 8) -> List[str]:
    if not ensure_wordnet():
        return []
    pos = _wordnet_pos(word)
    key = word.lower()
    seen = {key}
    results = []
    synsets = _wordnet_synsets(word, pos)
    for syn in synsets:
        for lemma in syn.lemmas():
            name = lemma.name().replace("_", " ")
            lname = name.lower()
            if lname in seen:
                continue
            seen.add(lname)
            results.append(name)
            if len(results) >= limit:
                return results
    return results


def wordnet_antonyms(word: str, limit: int = 8) -> List[str]:
    if not ensure_wordnet():
        return []
    pos = _wordnet_pos(word)
    key = word.lower()
    seen = {key}
    results = []
    synsets = _wordnet_synsets(word, pos)

    def collect_from(lemma_name: str, syns) -> None:
        for syn in syns:
            for lemma in syn.lemmas():
                if lemma.name().lower() != lemma_name:
                    continue
                for ant in lemma.antonyms():
                    name = ant.name().replace("_", " ")
                    lname = name.lower()
                    if lname not in seen:
                        seen.add(lname)
                        results.append(name)

    # Direct antonyms of the word itself.
    collect_from(key, synsets)

    # WordNet's direct antonym links are sparse, so when that comes up short,
    # also check antonyms of the word's own synonyms (a synonym of "happy" is
    # "glad"; "glad" may carry an antonym link that "happy" itself lacks).
    if len(results) < limit:
        for syn_word in wordnet_synonyms(word, limit=10):
            if len(results) >= limit:
                break
            syn_key = syn_word.lower()
            inner_synsets = _wordnet_synsets(syn_word, pos)
            collect_from(syn_key, inner_synsets)

    return results[:limit]


def wordnet_alternatives(word: str, mode: str, limit: int = 8) -> List[str]:
    if mode == "antonym":
        return wordnet_antonyms(word, limit=limit)
    return wordnet_synonyms(word, limit=limit)


def wordnet_rephrase(text: str, mode: str) -> dict:
    """Bulk rephrase for synonym/antonym modes, sourced entirely from WordNet."""
    tokens = re.findall(r"\S+|\s+", text)
    changes = []
    out_tokens = []
    idx = 0
    for tok in tokens:
        if tok.isspace():
            out_tokens.append(tok)
            continue
        clean = re.sub(r"[^A-Za-z]", "", tok)
        if not clean:
            out_tokens.append(tok)
            continue
        prefix = re.match(r"^[^A-Za-z]*", tok).group(0)
        suffix = re.search(r"[^A-Za-z]*$", tok).group(0)
        lower = clean.lower()
        category = classify_word(clean)
        eligible = (
            len(clean) > 3
            and lower not in STOPWORDS
            and category in ("nouns", "verbs", "adjectives", "adverbs")
        )
        alts = wordnet_alternatives(clean, mode, limit=6) if eligible else []
        if alts and random.random() < 0.55:
            new_word = random.choice(alts)
            if tok[len(prefix)].isupper():
                new_word = new_word.capitalize()
            replaced = f"{prefix}{new_word}{suffix}"
            changes.append({
                "id": f"c{idx}",
                "original": tok.strip(),
                "replacement": new_word,
                "alternatives": alts,
                "position": len("".join(out_tokens)),
            })
            out_tokens.append(replaced)
            idx += 1
        else:
            out_tokens.append(tok)
    rebuilt = "".join(out_tokens)
    return {"output": rebuilt, "changes": changes}


# ---------------- Rhyme (CMU Pronouncing Dictionary via `pronouncing`) ----------------
# Same philosophy as WordNet above: a free, deterministic, fully-offline
# lexical resource (bundled CMU dict, no network/download needed) stands in
# for the LLM wherever it can actually answer the question. Rhyme matching is
# exactly that kind of lookup, so "rhyme" mode tries this first and only
# falls back to the LLM/hardcoded bank when the dictionary has nothing for a
# given word (proper nouns, typos, very rare words, etc.).
def rhyme_alternatives(word: str, limit: int = 8) -> List[str]:
    clean = re.sub(r"[^A-Za-z']", "", word).lower()
    if not clean or pronouncing is None:
        return []
    try:
        if not pronouncing.phones_for_word(clean):
            return []
        candidates = pronouncing.rhymes(clean)
    except Exception as e:
        logging.warning(f"Rhyme lookup failed for {word!r}: {e}")
        return []
    # The CMU dict is a pronunciation list, not a curated vocabulary — it's
    # full of surnames and proper nouns (e.g. "deneuve", "labov", "ankeney")
    # that happen to rhyme but read as nonsense mid-sentence. WordNet makes a
    # reasonable "is this a real, known English word" filter, so lean on it
    # when it's available; if the corpus isn't loaded, fall back to the
    # unfiltered list rather than returning nothing.
    wordnet_ready = ensure_wordnet()
    seen = {clean}
    results = []
    for w in candidates:
        lw = w.lower()
        if lw in seen or not lw.isalpha():
            continue
        if wordnet_ready and not wn.synsets(lw):
            continue
        seen.add(lw)
        results.append(w)
        if len(results) >= limit:
            break
    return results


def rhyme_rephrase(text: str) -> dict:
    """Bulk rephrase for rhyme mode, sourced from the CMU pronouncing dict."""
    tokens = re.findall(r"\S+|\s+", text)
    changes = []
    out_tokens = []
    idx = 0
    for tok in tokens:
        if tok.isspace():
            out_tokens.append(tok)
            continue
        clean = re.sub(r"[^A-Za-z]", "", tok)
        if not clean:
            out_tokens.append(tok)
            continue
        prefix = re.match(r"^[^A-Za-z]*", tok).group(0)
        suffix = re.search(r"[^A-Za-z]*$", tok).group(0)
        lower = clean.lower()
        eligible = len(clean) > 3 and lower not in STOPWORDS
        alts = rhyme_alternatives(clean, limit=6) if eligible else []
        if alts and random.random() < 0.55:
            new_word = random.choice(alts)
            if tok[len(prefix)].isupper():
                new_word = new_word.capitalize()
            replaced = f"{prefix}{new_word}{suffix}"
            changes.append({
                "id": f"c{idx}",
                "original": tok.strip(),
                "replacement": new_word,
                "alternatives": alts,
                "position": len("".join(out_tokens)),
            })
            out_tokens.append(replaced)
            idx += 1
        else:
            out_tokens.append(tok)
    rebuilt = "".join(out_tokens)
    return {"output": rebuilt, "changes": changes}


def fallback_rephrase(text: str, mode: str) -> dict:
    words = re.findall(r"\S+|\s+", text)
    changes = []
    out_tokens = []
    idx = 0
    for tok in words:
        if tok.isspace():
            out_tokens.append(tok)
            continue
        clean = re.sub(r"[^A-Za-z]", "", tok).lower()
        prefix = re.match(r"^[^A-Za-z]*", tok).group(0)
        suffix = re.search(r"[^A-Za-z]*$", tok).group(0)
        if clean and clean in FALLBACK_SYNONYMS and random.random() < 0.55:
            alts = FALLBACK_SYNONYMS[clean]
            new_word = random.choice(alts)
            if tok[len(prefix)].isupper():
                new_word = new_word.capitalize()
            replaced = f"{prefix}{new_word}{suffix}"
            changes.append({
                "id": f"c{idx}",
                "original": tok.strip(),
                "replacement": new_word,
                "alternatives": alts,
                "position": len("".join(out_tokens)),
            })
            out_tokens.append(replaced)
            idx += 1
        else:
            out_tokens.append(tok)
    rebuilt = "".join(out_tokens)
    # Recompute positions in output text by locating replacements
    return {"output": rebuilt, "changes": changes}


def llm_rephrase(text: str, mode: str) -> Optional[dict]:
    system = (
        "You are a rephrasing assistant. Rephrase the user's text following the instruction. "
        "Return strict JSON with keys: output (string, rephrased text) and changes (array of "
        "objects with keys id, original, replacement, alternatives (array of 3-4 strings)). "
        "Only include words/phrases you actually changed. Preserve punctuation and paragraph breaks."
    )
    instr = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["synonym"])
    user = f"Instruction: {instr}\n\nText:\n{text}\n\nReturn JSON only."
    result = llm_json(system, user)
    if not result or "output" not in result:
        return None
    changes = result.get("changes") or []
    # Ensure ids
    for i, c in enumerate(changes):
        c.setdefault("id", f"c{i}")
        c.setdefault("alternatives", [])
    return {"output": result["output"], "changes": changes}


def llm_alternatives(word: str, mode: str, context: str) -> Optional[List[str]]:
    system = (
        "You suggest alternative words. Return strict JSON: {\"alternatives\": [\"w1\",\"w2\",...]}. "
        "Provide 5 alternatives suitable to the mode."
    )
    instr = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["synonym"])
    user = f"Mode: {mode}. Instruction: {instr}\nContext: {context}\nWord: {word}\nReturn JSON only."
    result = llm_json(system, user)
    if not result:
        return None
    return result.get("alternatives") or None


def llm_detect(text: str) -> Optional[dict]:
    system = (
        "You are an AI-text and plagiarism detector. Analyze the text and return strict JSON: "
        "{\"ai_score\": 0-100, \"plagiarism_score\": 0-100, \"ai_reasoning\": \"...\", "
        "\"plagiarism_reasoning\": \"...\", \"risk_sentences\": [\"...\"]}. Higher = more risky."
    )
    result = llm_json(system, f"Text:\n{text}\nReturn JSON only.")
    return result


def heuristic_detect(text: str) -> dict:
    words = re.findall(r"[A-Za-z]+", text)
    if not words:
        return {"ai_score": 0, "plagiarism_score": 0,
                "ai_reasoning": "No text provided.",
                "plagiarism_reasoning": "No text provided.",
                "risk_sentences": []}
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    lens = [len(re.findall(r"\w+", s)) for s in sents if s.strip()]
    if not lens:
        lens = [len(words)]
    avg = sum(lens) / len(lens)
    var = sum((l - avg) ** 2 for l in lens) / len(lens)
    # Uniform sentence length => higher AI likelihood
    ai_score = max(5, min(95, int(80 - var * 2 + max(0, 20 - abs(avg - 18)))))
    # Rare words fraction => lower plagiarism
    unique = len(set(w.lower() for w in words)) / len(words)
    plagiarism_score = max(5, min(95, int(90 - unique * 100 + random.randint(-10, 10))))
    risk = sents[:2] if len(sents) > 1 else sents
    return {
        "ai_score": ai_score,
        "plagiarism_score": plagiarism_score,
        "ai_reasoning": "Heuristic analysis based on sentence-length variance and lexical patterns.",
        "plagiarism_reasoning": "Heuristic analysis based on lexical uniqueness and common-phrase density.",
        "risk_sentences": [s for s in risk if s.strip()],
    }


# ---------------- Routes ----------------
@api_router.get("/")
async def root():
    return {
        "message": "VerbaHumanize API",
        "llm": bool(OPENAI_API_KEY),
        # Diagnostics: fan mode / synonym / antonym need wordnet=true, rhyme
        # needs pronouncing=true. If wordnet is false, the corpus is missing
        # or failed to download (see the server log for the reason).
        "wordnet": ensure_wordnet(),
        "pronouncing": pronouncing is not None,
    }


# Auth
@api_router.post("/auth/register")
async def register(body: RegisterRequest, response: Response):
    email = body.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email,
        "name": body.name.strip(),
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    token = create_access_token(str(res.inserted_id), email)
    set_auth_cookie(response, token)
    return {"id": str(res.inserted_id), "email": email, "name": body.name, "token": token}


@api_router.post("/auth/login")
async def login(body: LoginRequest, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(user["_id"]), email)
    set_auth_cookie(response, token)
    return {"id": str(user["_id"]), "email": email, "name": user["name"], "token": token}


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# POS analyze
@api_router.post("/analyze/pos")
async def pos(body: DetectRequest):
    return {"pos": analyze_pos(body.text), "word_count": word_count(body.text)}


# Rephrase
@api_router.post("/rephrase")
async def rephrase(body: RephraseRequest, request: Request):
    text = body.text or ""
    user = await get_optional_user(request)
    wc = word_count(text)
    if wc == 0:
        raise HTTPException(status_code=400, detail="Please provide text to rephrase.")
    if not user and wc > GUEST_WORD_LIMIT:
        raise HTTPException(
            status_code=403,
            detail=f"Guest limit is {GUEST_WORD_LIMIT} words. Please sign up to rephrase longer texts.",
        )
    if body.mode in ("synonym", "antonym"):
        # Always WordNet-driven for these two modes, LLM key or not: lexical
        # relations (synsets, antonyms) are WordNet's job, not the LLM's.
        result = wordnet_rephrase(text, body.mode)
        result["source"] = "wordnet"
        result["llm_used"] = False
    elif body.mode == "rhyme":
        # Try the pronunciation dictionary first (free, deterministic,
        # offline); only reach for the LLM/hardcoded bank if it couldn't
        # find a rhyme for anything in the text.
        result = rhyme_rephrase(text)
        if result["changes"]:
            result["source"] = "pronouncing"
            result["llm_used"] = False
        else:
            result = llm_rephrase(text, body.mode) or fallback_rephrase(text, body.mode)
            result["source"] = "llm" if bool(OPENAI_API_KEY) else "fallback"
            result["llm_used"] = bool(OPENAI_API_KEY)
    else:
        result = llm_rephrase(text, body.mode) or fallback_rephrase(text, body.mode)
        result["source"] = "llm" if bool(OPENAI_API_KEY) else "fallback"
        result["llm_used"] = bool(OPENAI_API_KEY)
    result["input_word_count"] = wc
    result["output_word_count"] = word_count(result["output"])
    result["mode"] = body.mode
    return result


@api_router.post("/rephrase/alternatives")
async def alternatives(body: WordAlternativesRequest):
    if body.mode in ("synonym", "antonym"):
        alts = wordnet_alternatives(body.word, body.mode)
        if alts:
            return {"alternatives": alts, "llm_used": False, "source": "wordnet"}
        # WordNet has nothing (corpus unavailable, or an unknown word). The
        # built-in bank only holds synonyms, so it's valid for synonym mode
        # only — never serve synonyms as "antonyms".
        fb = FALLBACK_SYNONYMS.get(body.word.lower().strip(), []) if body.mode == "synonym" else []
        return {"alternatives": fb, "llm_used": False, "source": "fallback" if fb else "none"}

    if body.mode == "rhyme":
        alts = rhyme_alternatives(body.word)
        if alts:
            return {"alternatives": alts, "llm_used": False, "source": "pronouncing"}
        # No dictionary rhyme for this word — fall through to LLM/fallback below.

    alts = llm_alternatives(body.word, body.mode, body.context or "")
    if alts is None:
        key = body.word.lower().strip()
        alts = FALLBACK_SYNONYMS.get(key, [])
        if not alts:
            alts = [body.word + "-alt1", body.word + "-alt2", body.word + "-alt3"]
    return {
        "alternatives": alts,
        "llm_used": bool(OPENAI_API_KEY) and alts is not None,
        "source": "llm" if bool(OPENAI_API_KEY) else "fallback",
    }


# AI detection & plagiarism
@api_router.post("/detect")
async def detect(body: DetectRequest, request: Request):
    user = await get_optional_user(request)
    if not user:
        raise HTTPException(status_code=403, detail="Please sign in to run AI and plagiarism checks.")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="No text provided.")
    result = llm_detect(body.text) or heuristic_detect(body.text)
    result["llm_used"] = bool(OPENAI_API_KEY)
    return result


# ---------------- Wire up ----------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
    except Exception as e:
        logger.warning(f"index error: {e}")
    ensure_wordnet()


@app.on_event("shutdown")
async def shutdown():
    client.close()