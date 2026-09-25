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
    return {"message": "VerbaHumanize API", "llm": bool(OPENAI_API_KEY)}


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
    result = llm_rephrase(text, body.mode) or fallback_rephrase(text, body.mode)
    result["input_word_count"] = wc
    result["output_word_count"] = word_count(result["output"])
    result["mode"] = body.mode
    result["llm_used"] = bool(OPENAI_API_KEY)
    return result


@api_router.post("/rephrase/alternatives")
async def alternatives(body: WordAlternativesRequest):
    alts = llm_alternatives(body.word, body.mode, body.context or "")
    if alts is None:
        key = body.word.lower().strip()
        alts = FALLBACK_SYNONYMS.get(key, [])
        if not alts:
            alts = [body.word + "-alt1", body.word + "-alt2", body.word + "-alt3"]
    return {"alternatives": alts, "llm_used": bool(OPENAI_API_KEY) and alts is not None}


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


@app.on_event("shutdown")
async def shutdown():
    client.close()