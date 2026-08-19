from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Config
JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'tti_secret_key_2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Stripe Config
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')

# Admin account — logging in as this user bypasses the payment gateway entirely
# so courses/modules can be reviewed without a real Stripe charge.
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'ttl@admin.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '1234')
ADMIN_NAME = "TTI Admin"

# Create the main app
app = FastAPI(title="Trauma Transformation Institute API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# ============ MODELS ============

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: str
    is_admin: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ContentSource(BaseModel):
    label: str
    url: str

class ContentCard(BaseModel):
    title: str
    points: List[str] = []
    insight: str = ""
    sources: List[ContentSource] = []

class SlideItem(BaseModel):
    type: str = "content"  # "title" | "content" | "closing"
    eyebrow: str = ""
    title: str = ""
    subtitle: str = ""
    points: List[str] = []
    quote: str = ""

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_index: int
    explanation: str = ""

QUIZ_PASS_THRESHOLD = 0.9  # 90% required to pass
QUIZ_MAX_ATTEMPTS = 3      # attempts allowed per lockout cycle
QUIZ_LOCKOUT_HOURS = 1     # cooldown after exhausting attempts without passing

class QuizResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    course_id: str
    best_score: int
    best_total: int
    passed: bool
    attempts: int = 0                    # attempts used in the current (unpassed) cycle
    locked_until: Optional[str] = None   # set once attempts are exhausted without passing
    last_attempt_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class QuizResultSubmit(BaseModel):
    course_id: str
    score: int
    total: int

class Certificate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    track: str  # "prerequisite" or "clinical"
    title: str
    certificate_number: str
    recipient_name: str
    issued_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Course(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    track: str  # "wellness" or "clinical"
    level: str  # "prerequisite", "level1", "level2", "advanced"
    description: str
    detailed_description: str = ""
    price: float
    equipment_fee: float = 0.0
    duration: str
    location: str
    schedule: str
    instructor: str = "ETT Certified Trainer"
    max_participants: int = 20
    features: List[str] = []
    content_cards: List[ContentCard] = []
    quiz: List[QuizQuestion] = []
    slides: List[SlideItem] = []
    is_coming_soon: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class CourseCreate(BaseModel):
    title: str
    track: str
    level: str
    description: str
    detailed_description: str = ""
    price: float
    equipment_fee: float = 0.0
    duration: str
    location: str
    schedule: str
    instructor: str = "ETT Certified Trainer"
    max_participants: int = 20
    features: List[str] = []
    content_cards: List[ContentCard] = []
    quiz: List[QuizQuestion] = []
    slides: List[SlideItem] = []
    is_coming_soon: bool = False

class Enrollment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    course_id: str
    payment_status: str = "pending"
    session_id: Optional[str] = None
    enrolled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: str
    user_email: str
    course_id: str
    amount: float
    currency: str = "inr"
    payment_status: str = "initiated"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class CheckoutRequest(BaseModel):
    course_id: str
    origin_url: str

# ============ AUTH HELPERS ============

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============ AUTH ROUTES ============

@api_router.post("/auth/signup", response_model=TokenResponse)
async def signup(user_data: UserCreate):
    # Check if user exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "name": user_data.name,
        "password_hash": hash_password(user_data.password),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    token = create_token(user_id, user_data.email)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user_data.email,
            name=user_data.name,
            created_at=user_doc["created_at"],
            is_admin=(user_data.email == ADMIN_EMAIL)
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user["id"], user["email"])

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            created_at=user["created_at"],
            is_admin=(user["email"] == ADMIN_EMAIL)
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        created_at=user["created_at"],
        is_admin=(user["email"] == ADMIN_EMAIL)
    )

# ============ COURSE ROUTES ============

@api_router.get("/courses", response_model=List[Course])
async def get_courses(track: Optional[str] = None):
    query = {}
    if track:
        query["track"] = track
    courses = await db.courses.find(query, {"_id": 0}).to_list(100)
    return courses

@api_router.get("/courses/{course_id}", response_model=Course)
async def get_course(course_id: str):
    course = await db.courses.find_one({"id": course_id}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

@api_router.post("/courses", response_model=Course)
async def create_course(course_data: CourseCreate):
    course = Course(**course_data.model_dump())
    await db.courses.insert_one(course.model_dump())
    return course

# ============ ENROLLMENT & PAYMENT ROUTES ============

@api_router.post("/enrollments/checkout")
async def create_checkout(request: Request, checkout_data: CheckoutRequest, user: dict = Depends(get_current_user)):
    # Get course details
    course = await db.courses.find_one({"id": checkout_data.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    if course.get("is_coming_soon"):
        raise HTTPException(status_code=400, detail="This course is not yet available for enrollment")
    
    # Check if already enrolled
    existing = await db.enrollments.find_one({
        "user_id": user["id"],
        "course_id": checkout_data.course_id,
        "payment_status": "paid"
    })
    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled in this course")
    
    # Calculate total amount (course price + equipment fee)
    total_amount = float(course["price"]) + float(course.get("equipment_fee", 0))

    # Admin bypass: skip Stripe entirely and grant instant access so the
    # admin account can review every module/course without a real charge.
    if user["email"] == ADMIN_EMAIL:
        bypass_session_id = f"admin-bypass-{uuid.uuid4()}"

        transaction = PaymentTransaction(
            session_id=bypass_session_id,
            user_id=user["id"],
            user_email=user["email"],
            course_id=checkout_data.course_id,
            amount=total_amount,
            currency="inr",
            payment_status="paid"
        )
        await db.payment_transactions.insert_one(transaction.model_dump())

        enrollment = Enrollment(
            user_id=user["id"],
            course_id=checkout_data.course_id,
            payment_status="paid",
            session_id=bypass_session_id
        )
        await db.enrollments.insert_one(enrollment.model_dump())

        return {
            "bypass": True,
            "checkout_url": None,
            "session_id": bypass_session_id,
            "message": "Admin access — enrolled without payment"
        }

    # Build URLs from frontend origin
    success_url = f"{checkout_data.origin_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{checkout_data.origin_url}/courses/{checkout_data.course_id}"
    
    # Create Stripe checkout
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    checkout_request = CheckoutSessionRequest(
        amount=total_amount,
        currency="inr",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user["id"],
            "user_email": user["email"],
            "course_id": checkout_data.course_id,
            "course_title": course["title"]
        }
    )
    
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    
    # Create payment transaction record
    transaction = PaymentTransaction(
        session_id=session.session_id,
        user_id=user["id"],
        user_email=user["email"],
        course_id=checkout_data.course_id,
        amount=total_amount,
        currency="inr",
        payment_status="initiated"
    )
    await db.payment_transactions.insert_one(transaction.model_dump())
    
    # Create pending enrollment
    enrollment = Enrollment(
        user_id=user["id"],
        course_id=checkout_data.course_id,
        payment_status="pending",
        session_id=session.session_id
    )
    await db.enrollments.insert_one(enrollment.model_dump())
    
    return {"checkout_url": session.url, "session_id": session.session_id}

@api_router.get("/payments/status/{session_id}")
async def get_payment_status(request: Request, session_id: str, user: dict = Depends(get_current_user)):
    # Get transaction
    transaction = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # If already processed as paid, return immediately
    if transaction["payment_status"] == "paid":
        return {"status": "complete", "payment_status": "paid"}
    
    # Check with Stripe
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    try:
        status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
        
        # Update transaction and enrollment based on status
        if status.payment_status == "paid" and transaction["payment_status"] != "paid":
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "payment_status": "paid",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            await db.enrollments.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "paid"}}
            )
        elif status.status == "expired":
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "payment_status": "expired",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            await db.enrollments.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "expired"}}
            )
        
        return {
            "status": status.status,
            "payment_status": status.payment_status,
            "amount_total": status.amount_total,
            "currency": status.currency
        }
    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        return {"status": "pending", "payment_status": transaction["payment_status"]}

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    try:
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        if webhook_response.payment_status == "paid":
            # Update transaction
            await db.payment_transactions.update_one(
                {"session_id": webhook_response.session_id},
                {"$set": {
                    "payment_status": "paid",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            # Update enrollment
            await db.enrollments.update_one(
                {"session_id": webhook_response.session_id},
                {"$set": {"payment_status": "paid"}}
            )
        
        return {"received": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"received": True}

# ============ USER DASHBOARD ROUTES ============

@api_router.get("/enrollments/my")
async def get_my_enrollments(user: dict = Depends(get_current_user)):
    enrollments = await db.enrollments.find(
        {"user_id": user["id"], "payment_status": "paid"},
        {"_id": 0}
    ).to_list(100)
    
    # Get course details for each enrollment
    result = []
    for enrollment in enrollments:
        course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0})
        if course:
            result.append({
                "enrollment": enrollment,
                "course": course
            })
    
    return result

# ============ QUIZ ROUTES ============

@api_router.post("/quiz-results", response_model=QuizResult)
async def submit_quiz_result(data: QuizResultSubmit, user: dict = Depends(get_current_user)):
    if data.total <= 0 or data.score < 0 or data.score > data.total:
        raise HTTPException(status_code=400, detail="Invalid score")

    now = datetime.now(timezone.utc)
    existing = await db.quiz_results.find_one(
        {"user_id": user["id"], "course_id": data.course_id}, {"_id": 0}
    )

    attempts_used = existing["attempts"] if existing else 0
    already_passed = existing["passed"] if existing else False

    # If a lockout is active, only let the attempt through once it has expired
    if existing and existing.get("locked_until"):
        locked_until_dt = datetime.fromisoformat(existing["locked_until"])
        if now < locked_until_dt:
            raise HTTPException(
                status_code=403,
                detail=f"Maximum attempts reached. You can try again after {existing['locked_until']}."
            )
        attempts_used = 0  # cooldown elapsed — fresh cycle

    if not already_passed and attempts_used >= QUIZ_MAX_ATTEMPTS:
        raise HTTPException(status_code=403, detail="Maximum attempts reached. Please try again later.")

    passed_this_attempt = (data.score / data.total) >= QUIZ_PASS_THRESHOLD
    overall_passed = already_passed or passed_this_attempt
    new_attempts = 0 if overall_passed else attempts_used + 1

    locked_until_val = None
    if not overall_passed and new_attempts >= QUIZ_MAX_ATTEMPTS:
        locked_until_val = (now + timedelta(hours=QUIZ_LOCKOUT_HOURS)).isoformat()

    best_score = max(existing["best_score"], data.score) if existing else data.score

    result = QuizResult(
        id=existing["id"] if existing else str(uuid.uuid4()),
        user_id=user["id"],
        course_id=data.course_id,
        best_score=best_score,
        best_total=data.total,
        passed=overall_passed,
        attempts=new_attempts,
        locked_until=locked_until_val,
        last_attempt_at=now.isoformat()
    )
    await db.quiz_results.update_one(
        {"user_id": user["id"], "course_id": data.course_id},
        {"$set": result.model_dump()},
        upsert=True
    )
    return result

@api_router.get("/quiz-results/my")
async def get_my_quiz_results(user: dict = Depends(get_current_user)):
    results = await db.quiz_results.find({"user_id": user["id"]}, {"_id": 0}).to_list(200)
    return results

# ============ CERTIFICATE ROUTES ============

# A track's certificate requires every matching course to be both paid-enrolled
# and quiz-passed (>=90%). Certificates are auto-issued (and persisted) the
# first time a user is found eligible.
CERTIFICATE_TRACKS = {
    "prerequisite": {
        "title": "ETT Prerequisite Foundation Certificate",
        "match": lambda c: c["track"] == "wellness" and c["level"] == "module",
    },
    "clinical": {
        "title": "ETT Clinical Practitioner Certificate",
        "match": lambda c: c["track"] == "clinical" and c["level"] in ("level1", "level2"),
    },
}

@api_router.get("/certificates/my")
async def get_my_certificates(user: dict = Depends(get_current_user)):
    all_courses = await db.courses.find({}, {"_id": 0}).to_list(200)
    enrollments = await db.enrollments.find(
        {"user_id": user["id"], "payment_status": "paid"}, {"_id": 0}
    ).to_list(200)
    enrolled_ids = {e["course_id"] for e in enrollments}
    quiz_results = await db.quiz_results.find({"user_id": user["id"]}, {"_id": 0}).to_list(200)
    passed_ids = {q["course_id"] for q in quiz_results if q["passed"]}

    certificates = []
    for track_key, meta in CERTIFICATE_TRACKS.items():
        track_courses = [c for c in all_courses if meta["match"](c)]
        if not track_courses:
            continue

        done = sum(1 for c in track_courses if c["id"] in enrolled_ids and c["id"] in passed_ids)
        total = len(track_courses)
        completed = done == total

        existing = await db.certificates.find_one(
            {"user_id": user["id"], "track": track_key}, {"_id": 0}
        )
        if completed and not existing:
            cert = Certificate(
                user_id=user["id"],
                track=track_key,
                title=meta["title"],
                certificate_number=f"TTI-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:8].upper()}",
                recipient_name=user["name"],
            )
            await db.certificates.insert_one(cert.model_dump())
            existing = cert.model_dump()

        certificates.append({
            "track": track_key,
            "title": meta["title"],
            "completed": completed,
            "progress": {"done": done, "total": total},
            "certificate": existing,
        })

    return certificates

# ============ SEED DATA ============

# Researched via a 10-agent multi-agent workflow (each agent used WebSearch to pull
# current, credible, real sources for its module) on 2026-08-19. Keyed by course title.
MODULE_CONTENT = {
    "Module 1 — Understanding Trauma": [{
        "title": "Key Concepts",
        "points": [
            "Trauma is classified as acute (single event), chronic (repeated/prolonged), or developmental (occurring during childhood development).",
            "Chronic stress can affect the hippocampus and elevate cortisol, which is linked to how traumatic memories are formed and recalled.",
            "Polyvagal theory describes fight, flight, freeze, and fawn as automatic nervous-system defense responses, not conscious choices.",
            "Intergenerational trauma can be passed through caregiving patterns, attachment styles, and possibly epigenetic changes in stress-response genes.",
        ],
        "insight": "A 2025 study of three generations of Syrian refugees found distinct DNA methylation signatures tied to violence exposure, with some changes appearing in the germline and others from direct trauma exposure, offering new evidence for biological pathways in intergenerational trauma transmission.",
        "sources": [
            {"label": "NCBI Bookshelf — Acute and Chronic Mental Health Trauma (StatPearls)", "url": "https://www.ncbi.nlm.nih.gov/books/NBK594231/"},
            {"label": "Scientific Reports — Epigenetic signatures of intergenerational violence exposure", "url": "https://www.nature.com/articles/s41598-025-89818-z"},
            {"label": "PMC — Polyvagal theory in trauma and emotion regulation", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11150850/"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Screen for trauma history using brief validated tools (e.g., ACE-style questions) before assuming readiness for depth work.",
            "Use titration and pendulation: introduce traumatic material in small doses, alternating with regulation, not full exposure at once.",
            "Track the client's 'window of tolerance' moment-to-moment; pace toward stabilization first with chronic/developmental trauma before processing memories.",
            "Prioritize safety, choice, and collaboration in session structure per trauma-informed care principles, not just technique selection.",
        ],
        "insight": "In August 2024 the APA approved new professional practice guidelines for working with adults with complex trauma histories and PTSD/traumatic stress disorders, formalizing evidence-based pacing recommendations for practitioners.",
        "sources": [
            {"label": "APA Monitor — New APA guidelines on PTSD and trauma (2025)", "url": "https://www.apa.org/monitor/2025/07-08/guidelines-treating-ptsd-trauma"},
            {"label": "SAMHSA/NCBI Bookshelf — Screening and Assessment in Trauma-Informed Care", "url": "https://www.ncbi.nlm.nih.gov/books/NBK207188/"},
        ],
    }],
    "Module 2 — Brain Waves & Nervous System States": [{
        "title": "Key Concepts",
        "points": [
            "Brain waves are grouped by EEG frequency: delta (deep sleep), theta (internal focus/emotion), alpha (calm relaxation), beta (active thinking), and gamma (fast neural binding).",
            "Theta wave activity is linked to emotional regulation, with research showing theta oscillations rise during cognitive reappraisal of feelings.",
            "The 'window of tolerance,' a widely used clinical concept, describes the arousal zone where a person can process emotion without shutting down or becoming overwhelmed.",
            "Trauma-related shifts in brain wave patterns are associated with changes in emotional regulation, sensory processing, and cognitive control.",
        ],
        "insight": "A 2024 study on panic disorder found reduced theta power and weaker theta-gamma coupling correlated with working-memory interference and anxiety symptoms, pointing to specific oscillatory markers relevant to regulation-focused therapy.",
        "sources": [
            {"label": "EEG Frequency Bands Explained (Delta–Gamma overview)", "url": "https://neurosity.co/guides/eeg-frequency-bands-explained"},
            {"label": "Theta power/theta-gamma coupling in panic disorder (PMC, 2024)", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11613674/"},
            {"label": "Polyvagal theory: from physiological observation to clinical insight (PMC)", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12479538/"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Before deeper trauma work, assess whether the client is within their 'window of tolerance' — calm and engaged, not hyper- or hypo-aroused.",
            "Use brief grounding first: paced breathing, orienting to sights/sounds in the room, or naming 5 things seen, to widen regulation capacity.",
            "Titrate pacing — introduce stabilization/resourcing skills before processing distressing material, and pause if signs of shutdown or flooding appear.",
            "Track visible cues (tone of voice, breathing, eye contact, stillness vs. agitation) in real time to judge readiness, not just verbal self-report.",
        ],
        "insight": "A 2025 peer-reviewed review reaffirms polyvagal theory's clinical utility for framing regulation work while flagging real methodological critiques, so practitioners increasingly use it as a practical, client-friendly framework rather than a fully proven neurophysiological model.",
        "sources": [
            {"label": "NICABM — How to Expand a Client's Window of Tolerance", "url": "https://www.nicabm.com/topic/window-of-tolerance/"},
            {"label": "Frontiers in Behavioral Neuroscience (2025) — Polyvagal theory: clinical insight and critiques", "url": "https://www.frontiersin.org/journals/behavioral-neuroscience/articles/10.3389/fnbeh.2025.1659083/full"},
        ],
    }, {
        "title": "The Healing Sequence",
        "points": [
            "Brain waves are rhythmic electrical patterns created by groups of neurons — temporary states of the nervous system, not fixed traits or identities.",
            "In 1924, Hans Berger recorded the first human EEG, identifying distinct brain rhythms tied to alertness, relaxation, and sleep.",
            "Healing typically moves through a sequence — safety, then emotional access, then rest and integration — insight alone is rarely sufficient.",
            "Trauma narrows brain-wave flexibility; healing restores the nervous system's ability to move between states with ease.",
            "Sleep supports Delta and REM states, where much of the deep emotional and physical healing actually occurs.",
        ],
        "insight": "Because brain-wave work increases client suggestibility, consent, pacing, and safety are treated as essential ethical guardrails throughout this kind of practice — regulation precedes revelation, and the nervous system leads.",
        "sources": [
            {"label": "Wikipedia — Hans Berger and the invention of human EEG (1924)", "url": "https://en.wikipedia.org/wiki/Hans_Berger"},
            {"label": "NICABM — How to Expand a Client's Window of Tolerance", "url": "https://www.nicabm.com/topic/window-of-tolerance/"},
        ],
    }],
    "Module 3 — The Role of Eyes in Healing": [{
        "title": "Key Concepts",
        "points": [
            "Guided eye movements are thought to tax working memory, which can make recalled traumatic images feel less vivid and less emotionally intense.",
            "Brain imaging studies link eye movements during memory recall to reduced amygdala (fear-center) activity and increased prefrontal activity.",
            "EMDR-adjacent techniques use the eyes' neural connections to memory and emotion networks, not just visual focus alone.",
            "Frameworks that treat the eyes as 'energy centers' are traditional/experiential lenses, not neuroscientifically validated mechanisms, and are presented as such.",
        ],
        "insight": "A May 2024 Cerebral Cortex study proposed that bilateral eye movements may actively facilitate memory and perceptual processing, not just interfere with it, complicating the older 'working memory taxation' theory.",
        "sources": [
            {"label": "Cerebral Cortex (2024) — Eye movement intervention facilitates memory processing", "url": "https://academic.oup.com/cercor/article/34/5/bhae190/7667563"},
            {"label": "PMC — Degrading traumatic memories with eye movements (pilot fMRI study in PTSD)", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5131454/"},
            {"label": "EMDRIA — A Working Memory Explanation for the Effects of Eye Movements", "url": "https://www.emdria.org/resource/a-working-memory-explanation-for-the-effects-of-eye-movements-in-emdr/"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Always complete history-taking, safe-place resourcing, and stabilization skills before introducing eye-movement or bilateral stimulation sets.",
            "Titrate pacing: start with short, slower bilateral stimulation sets, checking distress ratings between sets and adjusting to client tolerance.",
            "Eye movements are one delivery option only; tapping, alternating tones, or handheld buzzers substitute when eye tracking causes discomfort.",
            "Never end a session mid-reprocessing; use a containment/grounding close if a target isn't fully resolved before time runs out.",
        ],
        "insight": "Since 2021–2023, systematic reviews show remote/telehealth-delivered bilateral stimulation — via screen-guided eye movements, lightbars, or self-tapping — produces symptom reduction comparable to in-person sessions, expanding practical access.",
        "sources": [
            {"label": "EMDRIA — The Eight Phases of EMDR Therapy", "url": "https://www.emdria.org/blog/the-eight-phases-of-emdr-therapy/"},
            {"label": "Frontiers in Psychiatry — Systematic Review of Remote EMDR Therapy Studies (2023)", "url": "https://www.frontiersin.org/journals/psychiatry/articles/10.3389/fpsyt.2023.1336569/full"},
        ],
    }],
    "Module 4 — Attachment Styles and Relationships": [{
        "title": "Key Concepts",
        "points": [
            "Adult attachment is commonly described using four patterns: secure, anxious-preoccupied, dismissive-avoidant, and fearful-avoidant (disorganized).",
            "Higher numbers of adverse childhood experiences are linked to more insecure attachment, including fear of abandonment and difficulty trusting others.",
            "Disorganized attachment often involves both wanting and fearing closeness, and is linked to heightened dissociation after trauma.",
            "Consistent, attuned therapeutic relationships can help clients build 'earned secure attachment' even after insecure early experiences.",
        ],
        "insight": "A 2025 Scientific Reports study found that adult attachment style mediates the relationship between early childhood trauma and later suicidal behavior, underscoring attachment patterns as a key treatment target.",
        "sources": [
            {"label": "Scientific Reports (2025) — Adult attachment mediates trauma and suicidal behavior", "url": "https://www.nature.com/articles/s41598-025-00831-8"},
            {"label": "PMC — Disorganized Attachment and Personality Functioning in Adults", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5026862/"},
            {"label": "PMC — Adult attachment mediating early trauma and suicidal behaviour", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12056111/"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Assess via intake interview (relationship history, stress coping) plus validated self-report tools like the ECR-R, not from theory alone.",
            "Watch in-session cues: eye contact, disclosure pace, and reaction to therapist warmth or limits reveal attachment style in real time.",
            "Adapt stance per style: give avoidant clients pacing and autonomy; give anxious clients consistency, predictability, and explicit reassurance.",
            "Treat alliance ruptures as core clinical work, since insecure attachment predicts dropout and rupture-repair rebuilds the relational template.",
        ],
        "insight": "Since 2024–2025, attachment-informed practice has shifted toward integrating attachment assessment with somatic and relational interventions, using tools like the Adult Attachment Interview as a clinical adjunct alongside CBT or psychodynamic work.",
        "sources": [
            {"label": "PubMed — Attachment-informed therapy for adults: a unifying perspective on practice", "url": "https://pubmed.ncbi.nlm.nih.gov/26179192/"},
            {"label": "ScienceDirect — Adult attachment patterns and the therapeutic alliance: a systematic review", "url": "https://www.sciencedirect.com/science/article/abs/pii/S0272735809001883"},
        ],
    }],
    "Module 5 — Chakras and Levels of Consciousness": [{
        "title": "Key Concepts",
        "points": [
            "Chakras are a framework from Indian yogic and tantric traditions, not an anatomical structure recognized in Western medicine.",
            "Many practitioners use the chakra sequence informally to parallel a progression from basic survival needs toward meaning and self-realization, echoed by Maslow's hierarchy of needs.",
            "The American Psychological Association has no official position endorsing chakra or energy-based techniques, citing insufficient outcome evidence.",
            "Body-awareness (interoceptive) skills, which chakra practice trains informally, are supported by real trauma research as relevant to emotion regulation.",
        ],
        "insight": "A 2024 Frontiers in Psychiatry scoping review of 43 studies found decreased interoceptive (body-signal) awareness is consistently linked to PTSD and reduced emotion regulation — an evidence-based rationale for why body-awareness practices like chakra work may support, but not replace, trauma therapy.",
        "sources": [
            {"label": "Frontiers in Psychiatry (2024) — Interoceptive awareness and PTSD: a scoping review", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11150711/"},
            {"label": "Psychology Today — Maslow's Hierarchy vs. the 7 Chakras", "url": "https://www.psychologytoday.com/us/blog/the-resilient-brain/201804/maslows-hierarchy-vs-the-7-chakras-interestingly-similar"},
            {"label": "Center for Inquiry — Energy Psychology and evidence standards", "url": "https://centerforinquiry.org/blog/energy-psychology-an-apa-endorsed-pseudoscience/"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Frame chakra/energy-body language as a complementary wellness lens, not a diagnosis, prognosis, or standalone trauma treatment.",
            "Anchor sessions in observable nervous-system regulation (breath, grounding, titrated movement) rather than unverifiable energetic claims.",
            "Screen for active PTSD/dissociation and refer to a licensed trauma clinician when symptoms exceed a wellness scope of practice.",
            "Seek supervision or consult a client's therapist when layering chakra-informed bodywork alongside clinical mental-health care.",
        ],
        "insight": "A 2024 systematic review of nearly 1,000 studies ranked trauma-sensitive yoga among the top PTSD interventions, while a 2025 biofield-therapies evidence map still finds no validated physiological basis for chakra-specific effects — the regulation practice is the active ingredient, not the energy metaphysics.",
        "sources": [
            {"label": "Woven Wholeness — Using Chakras in Trauma Therapy (boundaries, supervision, scope)", "url": "https://www.wovenwholeness.com/post/using-chakras-in-trauma-therapy"},
            {"label": "J. Integrative & Complementary Medicine (2025) — Biofield Therapies Evidence Map", "url": "https://journals.sagepub.com/doi/10.1089/jicm.2024.0773"},
        ],
    }],
    "Module 6 — Introduction to ETT": [{
        "title": "Key Concepts",
        "points": [
            "ETT combines standard talk therapy with structured visual input (colored light and guided eye movements) to speed emotional processing.",
            "It was developed by psychologist Steven Vazquez, who trademarked the approach in 1991.",
            "Proponents describe ETT as engaging visual pathways linked to subcortical brain regions (like the thalamus) that regulate arousal, alongside cognitive processing.",
            "Independent, peer-reviewed research on ETT remains limited; most existing studies were conducted by its own developer, so effectiveness claims are still preliminary.",
        ],
        "insight": "Emerging theoretical work has proposed a 'Sensory-Salience Regulation' framework for how ETT's visual techniques might work, while cautioning that ETT's evidence base remains preliminary and observed improvements could reflect therapeutic alliance or expectancy rather than the light/color mechanism itself.",
        "sources": [
            {"label": "GoodTherapy — Emotional Transformation Therapy overview", "url": "https://www.goodtherapy.org/learn-about-therapy/types/emotional-transformation-therapy"},
            {"label": "Taproot Therapy Collective — ETT and Dr. Steven Vazquez", "url": "https://gettherapybirmingham.com/emotional-transformation-therapy-ett-dr-steven-vazquez/"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Sessions open with brief distress screening, then anchor the client on one specific feeling/body sensation before introducing a visual technique.",
            "The therapist stays in verbal contact throughout light/eye-movement work, checking in on shifts and adjusting wavelength or eye-position in real time.",
            "Colored-light and eye-movement techniques are used as adjuncts within an attachment-based talk framework, not as standalone treatment.",
            "Sessions close with verbal integration and a grounding/stabilization plan; light and color effects are framed as a wellness adjunct, not a proven standalone treatment.",
        ],
        "insight": "As of 2023–2025 literature searches, ETT still has no published peer-reviewed RCTs and remains grouped with other 'power therapies' that reviewers flag as lacking a robust independent evidence base — trainees are taught to present it as complementary to established talk therapy, not a validated protocol on its own.",
        "sources": [
            {"label": "ETT Level 1 training overview (etttraining.com)", "url": "https://www.etttraining.com/ett-level-1"},
            {"label": "GoodTherapy — Emotional Transformation Therapy explainer", "url": "https://www.goodtherapy.org/learn-about-therapy/types/emotional-transformation-therapy"},
        ],
    }],
    "Module 7 — Epigenetics and Neuroplasticity": [{
        "title": "Key Concepts",
        "points": [
            "Experiences like chronic stress can chemically tag genes (e.g., via DNA methylation) without altering the DNA sequence itself.",
            "The brain retains lifelong neuroplasticity, meaning it can form new neural connections in response to safe, repeated experiences.",
            "Trauma-linked epigenetic changes often affect stress-response genes and brain regions like the hippocampus, amygdala, and prefrontal cortex.",
            "Consistent therapeutic practices (e.g., EMDR, mindfulness) are associated with measurable shifts in brain activity patterns over weeks to months.",
        ],
        "insight": "Recent research (2023–2025) is investigating methylation of the BDNF gene, which supports neuron growth and plasticity, as a potential epigenetic biomarker linking childhood adversity to later brain recovery and vulnerability.",
        "sources": [
            {"label": "NIH/NCBI StatPearls — Neuroplasticity", "url": "https://www.ncbi.nlm.nih.gov/books/NBK557811/"},
            {"label": "PMC — Epigenetic Modifications in Stress Response Genes and Childhood Trauma", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6857662/"},
            {"label": "Frontiers in Psychiatry (2025) — From trauma to depression: epigenetic pathways", "url": "https://www.frontiersin.org/journals/psychiatry/articles/10.3389/fpsyt.2025.1666599/full"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Establish physiological safety and regulation first (grounding, breath) before introducing new cognitive or narrative work, since plastic change is state-dependent.",
            "Assign small, specific between-session practice reps rather than one-off insight — consistent low-dose repetition builds durable neural pathways faster than intensity.",
            "Titrate exposure to distressing material in manageable increments to avoid overwhelm, which can reinforce old threat pathways instead of new ones.",
            "Collaboratively design homework with the client, not just prescribe it — engagement and follow-through directly predict whether new pathways strengthen.",
        ],
        "insight": "A 2024 peer-reviewed synthesis reframes between-session homework as a core transtheoretical clinical skill, and 2025 pilot work is exploring AI-assisted weekly tracking of client practice trajectories to make neuroplastic homework adherence more structured and measurable.",
        "sources": [
            {"label": "PMC (2024) — Between-Session Homework in Clinical Training and Practice", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11303922/"},
            {"label": "Trauma Therapist Institute — Neuroplasticity in Practice", "url": "https://www.traumatherapistinstitute.com/neuroplasticity-in-practice-supporting-lasting-change-in-trauma"},
        ],
    }],
    "Module 8 — Ethics in Healing and Wellness": [{
        "title": "Key Concepts",
        "points": [
            "Informed consent is an ongoing process, not a one-time form — clients can revoke consent at any point, including mid-session.",
            "APA ethics standards require therapists to maintain clear professional boundaries, since trauma disclosures can blur clinician-client roles.",
            "Energy-based practices like chakras are a cultural/wellness framework, not an empirically validated medical treatment, and should be presented that way.",
            "Touch-based somatic work carries added consent risk due to power imbalances, so practitioners need explicit, revocable, moment-to-moment consent protocols.",
        ],
        "insight": "A 2025 qualitative study on therapeutic touch in supportive/psychedelic-assisted therapy found reduced client capacity to consent and recommended clear touch protocols and boundary-transgression training — a caution directly relevant to somatic and energy-based modalities.",
        "sources": [
            {"label": "APA — Ethical Principles of Psychologists and Code of Conduct", "url": "https://www.apa.org/ethics/code"},
            {"label": "PMC (2025) — Ethical use of therapeutic touch in supportive/psychedelic-assisted therapy", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12618852/"},
            {"label": "Ethical guidelines for treating trauma survivors (overview)", "url": "https://en.wikipedia.org/wiki/Ethical_guidelines_for_treating_trauma_survivors"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Treat informed consent as ongoing, not one-time: revisit before trauma-focused work and explicitly honor a client's right to pause or withdraw.",
            "Use verbal 'choice points' before charged material, e.g. 'Is it okay if we go there now?', to keep consent active in-session.",
            "Set session-frame boundaries early — contact policy, dual-relationship limits, confidentiality scope — to protect both parties and model healthy relating.",
            "For non-clinical wellness modalities (energy work, chakras), disclose plainly that they are not a medical treatment and stay within your actual scope of practice.",
        ],
        "insight": "Since 2024, states including Illinois, California, New York, and Colorado have begun requiring explicit written client consent for AI-assisted notetaking and sentiment-analysis tools in session, with a 2025 APA survey finding 41% of licensed therapists now using AI tools, up from 12% in 2023.",
        "sources": [
            {"label": "APA — The Benefits of Better Boundaries in Clinical Practice", "url": "https://www.apa.org/topics/psychotherapy/better-boundaries-clinical-practice"},
            {"label": "Family Therapy Magazine — AI, Consent, and Control in Teletherapy Documentation", "url": "https://ftm.aamft.org/when-the-chart-is-watching-back-ai-consent-and-control-in-teletherapy-documentation/"},
        ],
    }],
    "Module 9 — Light and Color in Healing": [{
        "title": "Key Concepts",
        "points": [
            "Light affects mood partly through melanopsin-containing retinal cells that are most sensitive to blue wavelengths, separate from vision itself.",
            "Warmer, lower color-temperature lighting (around 2700K) is linked to lower negative emotional bias than cooler, bluer light.",
            "Studies find red light produces the strongest emotional arousal response, while blue and green light tend to have calming effects.",
            "Color/chromotherapy is a wellness framework rather than a proven standalone clinical treatment, and works best alongside evidence-based therapy.",
        ],
        "insight": "A Department of Defense-funded 300-participant randomized controlled trial (2024–2025) is testing red/near-infrared photobiomodulation combined with cognitive rehabilitation for chronic traumatic brain injury, with evidence so far described as promising but still preliminary.",
        "sources": [
            {"label": "PMC — Warm/cool light effects on mood", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8481791/"},
            {"label": "PMC — Colored lights and affective impressions", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9752890/"},
            {"label": "PMC — Photobiomodulation for traumatic brain injury: evidence review", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10931349/"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Morning light exposure (500–10,000 lux) is dosed by minutes per day (15–60 min), not just by wavelength or color.",
            "EMDR-style light bars use 1–3 flashes/second bilateral stimulation and require formal certification plus informed consent.",
            "Screen for seizure disorders, migraines, bipolar disorder, and retinal/eye conditions before any light protocol — light can trigger mania or seizures.",
            "Frame chakra/color-based light work as a wellness adjunct, not a proven PTSD treatment, unlike dosed light-box or EMDR protocols.",
        ],
        "insight": "A 2022 pilot RCT tested manualized morning light dosing (15 vs 30 vs 60 min/day for 4 weeks) for probable PTSD and found the 60-minute arm produced large symptom improvements versus placebo, pushing the field toward structured, measurable dosing protocols.",
        "sources": [
            {"label": "PMC — Morning Light Treatment for Traumatic Stress (Study Protocol)", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9176814/"},
            {"label": "PMC — Morning Blue Light Treatment & Fear-Extinction Memory in PTSD", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9510714/"},
        ],
    }],
    "Module 10 — Cultural Considerations in Therapy": [{
        "title": "Key Concepts",
        "points": [
            "Cultural humility, an ongoing openness to a client's identity, predicts stronger therapy outcomes better than one-time competence training.",
            "Racial and historical trauma can pass across generations through family communication and coping patterns, not only genetics.",
            "Actively naming ('broaching') race, ethnicity, and culture in sessions helps clients feel safer discussing related distress.",
            "Few standardized, evidence-based treatments exist specifically for racial trauma, though new protocols are now being tested in trials.",
        ],
        "insight": "A 2024–2025 randomized controlled trial is formally testing the 'Healing Racial Trauma' protocol (combining CBT, FAP, and ACT techniques), while a related 2024 UK clinician survey found only about a third of mental health staff felt confident addressing racial trauma with clients.",
        "sources": [
            {"label": "PMC — Healing Racial Trauma Protocol (RCT)", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12292441/"},
            {"label": "PMC — Framework for broaching race/ethnicity/culture in therapy", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10951024/"},
            {"label": "Psychiatry Focus — Trauma-Informed Care and Cultural Humility", "url": "https://psychiatryonline.org/doi/10.1176/appi.focus.20190027"},
        ],
    }, {
        "title": "Practical Application",
        "points": [
            "Use 'broaching': proactively invite discussion of culture, identity, and power early and throughout treatment, at the client's own pace.",
            "Practice cultural humility over competence: ask open, curious questions instead of assuming meaning from a client's group membership.",
            "Adapt evidence-based protocols (e.g. TF-CBT) by weaving in a client's religious/folk healing practices and family structures, not replacing the core model.",
            "Name racial or cultural trauma explicitly in session (e.g. racial socialization work) rather than treating it as a side issue.",
        ],
        "insight": "A 2024–2025 mixed-methods protocol applied the ADAPT-ITT implementation model to build racial-trauma and racial-socialization content directly into TF-CBT, reflecting a shift toward structured, evidence-based cultural adaptation rather than ad hoc sensitivity training.",
        "sources": [
            {"label": "Blueprint — Broaching in Counseling: A Practical Guide", "url": "https://www.blueprint.ai/blog/broaching-in-counseling-a-practical-guide-for-culturally-responsive-clinical-practice"},
            {"label": "PMC — ADAPT-ITT Model for TF-CBT and Racial Trauma", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12491897/"},
        ],
    }],
    "ETT Clinical Level 1": [
        {
            "title": "Clinical Assessment & Case Work",
            "points": [
                "Case conceptualization turns assessment data into a working model of a client's problems, treatment targets, and likely obstacles.",
                "Evidence-based assessment pairs standardized measures with clinical judgment to improve diagnostic accuracy and treatment planning.",
                "Structured case conceptualization is considered a core, career-long clinical competency, not something mastered once and set aside.",
                "Clear clinical documentation supports continuity of care, progress tracking, and legal/ethical accountability.",
            ],
            "insight": "A 2024 review in Clinical Psychology Review found integrative case-conceptualization research still lags behind research on specific therapy techniques, with newer evidence-based conceptualization models proposed to close that gap.",
            "sources": [
                {"label": "PMC — Case Conceptualization in Clinical Practice and Training", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11303933/"},
                {"label": "PMC — What Motivates Clinicians-in-Training to Use Evidence-Based Assessment", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6600084/"},
            ],
        },
        {
            "title": "Attachment-Based Intervention",
            "points": [
                "Attachment-based interventions target the caregiver-child or relational bond itself, not just symptoms, to build emotional security.",
                "Attachment-Based Family Therapy (ABFT) is a guideline-listed treatment used for adolescent depression and suicidality.",
                "Evidence is strongest for improving parenting behavior and caregiver-child relationship quality, per systematic reviews.",
                "As with most relational approaches, effect sizes vary by population, so outcomes should be tracked individually, not assumed.",
            ],
            "insight": "A meta-analysis published in December 2024, reviewing ABFT trials through November 2023, found meaningful reductions in suicidal ideation among adolescents and young adults compared to control conditions.",
            "sources": [
                {"label": "PMC — Effectiveness of Attachment-Based Family Therapy for Suicidal Adolescents", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11960573/"},
                {"label": "Springer — Effectiveness of Attachment-Based Interventions for Maltreated Children", "url": "https://link.springer.com/article/10.1007/s10567-026-00556-8"},
            ],
        },
    ],
    "ETT Clinical Level 2": [
        {
            "title": "Addiction, Trauma & Diagnostic Integration",
            "points": [
                "DSM-5-TR requires separately assessing trauma exposure and substance use patterns, since PTSD and addiction frequently co-occur.",
                "Untreated trauma symptoms raise relapse risk, while active substance use can worsen PTSD, so effective care treats both together.",
                "Combined approaches, such as Cognitive Processing Therapy paired with Relapse Prevention, have shown reductions in both PTSD symptoms and alcohol use.",
                "A documented trauma history is linked to poorer treatment retention, making trauma-informed screening a core addiction-counseling skill.",
            ],
            "insight": "A 2024 study in the Journal of Substance Use & Addiction Treatment found trauma-informed residential substance use care produced significant reductions in substance involvement, depression, anxiety, and PTSD symptoms.",
            "sources": [
                {"label": "JSAT — Trauma-informed model in residential SUD treatment (2024)", "url": "https://www.jsatjournal.com/article/S2949-8759(24)00283-2/fulltext"},
                {"label": "PMC — Integrated CPT + Relapse Prevention for co-occurring PTSD/AUD", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12383005/"},
            ],
        },
        {
            "title": "Spiritual Integration & Ongoing Certification",
            "points": [
                "APA's 2023 Handbook of Spiritually Integrated Psychotherapies frames spirituality as a cultural factor to integrate ethically, not a standalone proven treatment.",
                "Surveys show many clients want to discuss religion or spirituality in therapy, yet formal graduate training on this remains limited.",
                "Licensing and certification bodies commonly require ongoing consultation calls or supervision alongside continuing education hours to maintain competency.",
                "Because outcome evidence is still developing compared to established therapies, spiritual integration is best described as a values-affirming clinical framework, not a validated protocol.",
            ],
            "insight": "In 2023, APA leadership publicly called for religious and spiritual competency training to become a standard part of graduate psychology programs, reflecting a recognized training gap.",
            "sources": [
                {"label": "BU Danielsen Institute — APA Handbook of Spiritually Integrated Psychotherapies", "url": "https://www.bu.edu/danielsen/2023/04/05/di-research-in-recent-apa-handbook-of-spiritually-integrated-psychotherapies/"},
                {"label": "Society for the Advancement of Psychotherapy — Religion & Spirituality in Graduate Training", "url": "https://www.societyforpsychotherapy.org/addressing-religion-and-spirituality-in-psychotherapy-why-it-should-be-in-graduate-training-programs/"},
            ],
        },
    ],
    "Trauma-Informed Hospitality Training": [
        {
            "title": "Workplace Trauma & De-escalation",
            "points": [
                "Trauma-informed care rests on six SAMHSA principles: safety, trustworthiness, peer support, collaboration, empowerment, and cultural awareness.",
                "Roughly 75% of customer-facing employees report encountering customer aggression regularly, with about 1 in 4 facing it weekly.",
                "Core de-escalation habits include staying calm, keeping a safe distance, using open body language, and listening without interrupting.",
                "Research reviews note the evidence base for specific de-escalation techniques is still limited, so training should pair skills with clear safety protocols, not replace them.",
            ],
            "insight": "A 2025 hospitality risk-management analysis found severe customer-aggression incidents requiring intervention rose sharply year-over-year, reinforcing why frontline de-escalation training is increasingly treated as a core safety competency rather than optional soft-skills coaching.",
            "sources": [
                {"label": "SAMHSA — Six Guiding Principles to a Trauma-Informed Approach", "url": "https://www.samhsa.gov/resource/dbhis/infographic-6-guiding-principles-trauma-informed-approach"},
                {"label": "McGriff — De-Escalation in Hospitality (Safety & Risk Management)", "url": "https://mcgriff.com/resources/articles/hospitality-de-escalation-liability-risk-management/"},
            ],
        },
        {
            "title": "Staff Wellbeing & Team Support",
            "points": [
                "Guest-facing hospitality roles are nearly twice as likely to experience depression and about a third more likely to experience anxiety than other workers.",
                "Secondary traumatic stress can affect staff who repeatedly witness or respond to guests' or coworkers' distress, even without direct personal harm.",
                "Organizational culture and manager support are stronger protective factors against burnout than individual self-care alone.",
                "High hospitality turnover (often cited near 70%+ annually) is closely linked to unaddressed burnout and inadequate mental health support.",
            ],
            "insight": "A 2025 industry survey found 47% of U.S. hospitality frontline managers reported personal burnout and 68% saw it in their teams, with understaffing cited as the top driver — a 21% jump from the prior year.",
            "sources": [
                {"label": "Axonify — 2025 Hospitality Industry Survey on Burnout & Training", "url": "https://axonify.com/news/hospitality-survey-2024/"},
                {"label": "PMC — Self-Compassion Interventions to Target Secondary Traumatic Stress", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10298083/"},
            ],
        },
    ],
    "Wellness Retreat Program": [
        {
            "title": "Immersive Healing Practices",
            "points": [
                "Combining time in nature with mindfulness practice improves mood more than either approach used alone.",
                "Multi-day mindfulness and yoga retreats have been shown to lower stress hormones and inflammation markers within days.",
                "A meta-analysis of nine randomized trials found mindfulness-based yoga significantly reduced depression symptoms.",
                "Structured nature-based therapy programs are linked to measurable gains in mood, stress reduction, and life satisfaction.",
            ],
            "insight": "A 2023 multi-site trial of 291 adults found structured nature-based therapy produced large effect sizes for reducing depression, anxiety, and stress, and improving daily functioning.",
            "sources": [
                {"label": "Scientific Reports (2023) — Nature-based therapy multi-site trial", "url": "https://www.nature.com/articles/s41598-023-49702-0"},
                {"label": "PMC — Mindfulness yoga and depression meta-analysis", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10492419/"},
            ],
        },
        {
            "title": "Personal Transformation & Integration",
            "points": [
                "Structured practices like journaling and continued mindfulness help translate retreat insights into lasting daily habits.",
                "Research describes personal transformation as a gradual, evolving process rather than a single peak moment.",
                "Self-transcendence, a shift toward less ego-focused concerns, is a theme common to many transformative experiences.",
                "Approaches like transpersonal coaching are used to support integration but remain frameworks, not clinically validated treatments.",
            ],
            "insight": "A 2024 study described personal transformation as a 'self-processing competence' that develops in distinct phases before, during, and after a guided experience, reinforcing why structured post-retreat integration support matters as much as the retreat itself.",
            "sources": [
                {"label": "ResearchGate (2024) — Personal Transformation: Developing Self-Processing Competence", "url": "https://www.researchgate.net/publication/377969931_Personal_Transformation_Developing_Self-Processing_Competence_Through_Coaching"},
                {"label": "SA J. Human Resource Mgmt — Transformational value of coaching", "url": "https://sajhrm.co.za/index.php/sajhrm/article/view/3468/5518"},
            ],
        },
    ],
    "Rehabilitation Support Program": [
        {
            "title": "Compliance-Focused Rehabilitation Protocols",
            "points": [
                "Court-mandated treatment plans typically combine drug testing, counseling, and coordination between courts, probation, and treatment staff.",
                "NIH/NIDA-funded research networks study how to deliver evidence-based addiction treatment inside justice-system settings.",
                "More than 90% of U.S. drug courts now permit medication-assisted treatments such as buprenorphine, reversing past restrictions.",
                "Routine urine or other drug testing remains a standard tool for monitoring compliance during supervised treatment.",
            ],
            "insight": "A recent national survey found about 90% of U.S. drug courts no longer prohibit medications for opioid use disorder, up sharply from roughly half a decade earlier, though only about one-quarter of states require staff training on them.",
            "sources": [
                {"label": "NIH/PMC — CJ-DATS Study Protocol Series", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3975625/"},
                {"label": "PMC — Medication-Assisted Treatment in Problem-Solving Courts: National Survey", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10766435/"},
            ],
        },
        {
            "title": "Reintegration & Long-Term Support",
            "points": [
                "Researchers now argue reentry success should be measured by employment, housing stability, and health, not recidivism alone.",
                "Peer recovery specialists use lived experience to build trust, offer emotional support, and connect people to resources.",
                "Second Chance Act program participants showed better long-term employment and earnings, though rearrest rates stayed similar.",
                "Throughcare programs that bridge incarceration and community life have been shown to help reduce reoffending.",
            ],
            "insight": "A 2024 study tracking Missouri's Community Reentry Initiative over five years found 52.4% of participants returned to prison, highlighting why reintegration support needs to be sustained well beyond initial release.",
            "sources": [
                {"label": "Taylor & Francis (2024) — Community Reentry Program Outcomes Over Five Years", "url": "https://www.tandfonline.com/doi/full/10.1080/10509674.2024.2443899"},
                {"label": "CSG Justice Center — Beyond Recidivism: Redefining Reentry Success", "url": "https://csgjusticecenter.org/publications/beyond-recidivism-redefining-reentry-data-health-housing-employment/"},
            ],
        },
    ],
}

# Quiz questions per course — authored from the researched content above so every
# fact tested is already source-backed. correct_index is 0-based into "options".
QUIZ_CONTENT = {
    "Module 1 — Understanding Trauma": [
        {"question": "How is trauma classified based on duration and timing?", "options": ["Only as PTSD or non-PTSD", "Acute, chronic, or developmental", "Mild, moderate, or severe", "Type 1 and Type 2"], "correct_index": 1, "explanation": "Trauma is classified as acute (single event), chronic (repeated/prolonged), or developmental (occurring during childhood)."},
        {"question": "What does polyvagal theory describe as automatic nervous-system defense responses?", "options": ["Fight, flight, freeze, and fawn", "Attack, retreat, negotiate", "Anger, sadness, fear, joy", "Sympathetic activation only"], "correct_index": 0, "explanation": "Polyvagal theory frames fight, flight, freeze, and fawn as automatic responses, not conscious choices."},
        {"question": "What pacing approach should be used when introducing traumatic material in session?", "options": ["Full exposure immediately", "Titration — small doses alternating with regulation", "Avoid the topic entirely", "Let the client set zero structure"], "correct_index": 1, "explanation": "Titration and pendulation introduce material in small doses, alternating with regulation, rather than full exposure at once."},
        {"question": "What recent (2025) research offers biological evidence for intergenerational trauma transmission?", "options": ["Blood type studies", "DNA methylation / epigenetic signatures", "IQ testing", "Muscle memory studies"], "correct_index": 1, "explanation": "A 2025 study of Syrian refugee families found distinct DNA methylation signatures tied to violence exposure across generations."},
    ],
    "Module 2 — Brain Waves & Nervous System States": [
        {"question": "Who recorded the first human EEG in 1924, identifying distinct brain rhythms tied to alertness, relaxation, and sleep?", "options": ["Sigmund Freud", "Hans Berger", "Ivan Pavlov", "William James"], "correct_index": 1, "explanation": "Hans Berger recorded the first EEG in 1924, founding the field of clinical electroencephalography."},
        {"question": "Which brain-wave state is most associated with deep sleep?", "options": ["Beta", "Gamma", "Delta", "Alpha"], "correct_index": 2, "explanation": "Delta waves are the slowest frequency and are associated with deep, restorative sleep."},
        {"question": "What is the typical sequence healing moves through, according to this framework?", "options": ["Insight, then action, then closure", "Safety, then emotional access, then rest and integration", "Diagnosis, then medication, then discharge", "Confrontation, then avoidance"], "correct_index": 1, "explanation": "Healing tends to move from safety to emotional access, then rest and integration — insight alone is rarely sufficient."},
        {"question": "What effect does trauma have on brain-wave flexibility?", "options": ["No effect", "It narrows the ability to move between states", "It permanently locks the brain in gamma", "It only affects delta sleep"], "correct_index": 1, "explanation": "Trauma narrows brain-wave flexibility; healing restores the nervous system's ability to move between states with ease."},
        {"question": "Why are consent, pacing, and safety especially essential in brain-wave-based work?", "options": ["It's required for insurance billing", "Brain-wave work increases suggestibility", "It's a legal formality only", "Clients get bored easily"], "correct_index": 1, "explanation": "Brain-wave work increases suggestibility, so consent, pacing, and safety are essential ethical guardrails."},
    ],
    "Module 3 — The Role of Eyes in Healing": [
        {"question": "What is the primary theorized mechanism behind why guided eye movements may reduce distress of traumatic memories?", "options": ["They improve eyesight", "They tax working memory, making images feel less vivid", "They increase heart rate", "They induce sleep"], "correct_index": 1, "explanation": "Guided eye movements are thought to tax working memory, making recalled images feel less vivid and intense."},
        {"question": "What must practitioners complete before introducing eye-movement techniques?", "options": ["Nothing — start immediately", "History-taking, safe-place resourcing, and stabilization skills", "A physical eye exam", "A written contract only"], "correct_index": 1, "explanation": "Safety and stabilization work always comes before introducing eye-movement or bilateral stimulation sets."},
        {"question": "What is an alternative delivery method when eye tracking causes discomfort?", "options": ["Tapping or alternating tones", "Skipping with no substitute", "Loud music", "Bright flashing lights"], "correct_index": 0, "explanation": "Tapping, alternating tones, or handheld buzzers substitute when eye tracking causes discomfort or dissociation."},
        {"question": "What did a 2024 Cerebral Cortex study suggest about bilateral eye movements?", "options": ["They have no effect on memory", "They may actively facilitate memory and perceptual processing", "They cause permanent memory loss", "They only work on children"], "correct_index": 1, "explanation": "The study proposed bilateral eye movements may actively facilitate processing, not just interfere with it."},
    ],
    "Module 4 — Attachment Styles and Relationships": [
        {"question": "Which of the following is NOT one of the four commonly described adult attachment patterns?", "options": ["Secure", "Anxious-preoccupied", "Dismissive-avoidant", "Hyperactive"], "correct_index": 3, "explanation": "The four patterns are secure, anxious-preoccupied, dismissive-avoidant, and fearful-avoidant (disorganized)."},
        {"question": "How should a therapist typically adapt their stance for an avoidant client?", "options": ["Push for immediate emotional disclosure", "Give pacing and autonomy", "Ignore their boundaries", "Demand constant contact"], "correct_index": 1, "explanation": "Avoidant clients respond better to pacing and autonomy, while anxious clients need consistency and reassurance."},
        {"question": "What predicts client dropout and requires active clinical attention?", "options": ["Session length", "Alliance ruptures", "Room temperature", "Billing cycle"], "correct_index": 1, "explanation": "Insecure attachment predicts dropout, and treating alliance ruptures as core clinical work rebuilds the relational template."},
        {"question": "What is 'earned secure attachment'?", "options": ["An attachment style you're born with permanently", "Security built through consistent, attuned therapeutic relationships", "A type of insurance policy", "A diagnostic label in the DSM-5"], "correct_index": 1, "explanation": "Consistent, attuned therapeutic relationships can help clients build earned secure attachment even after insecure early experiences."},
    ],
    "Module 5 — Chakras and Levels of Consciousness": [
        {"question": "How should chakra/energy-body concepts be framed in a wellness session?", "options": ["As a proven medical diagnosis", "As a complementary wellness lens, not a standalone trauma treatment", "As a replacement for all clinical therapy", "As a certification requirement for MDs"], "correct_index": 1, "explanation": "Chakra language should be framed as a complementary wellness lens, not a diagnosis or standalone treatment."},
        {"question": "What is the APA's official stance on chakra/energy-based techniques?", "options": ["Fully endorsed with CE credit", "No official endorsing position, citing insufficient outcome evidence", "Banned outright", "Required for all licensed therapists"], "correct_index": 1, "explanation": "The APA has no official position endorsing chakra or energy-based techniques."},
        {"question": "What should practitioners anchor sessions in, rather than unverifiable energetic claims?", "options": ["Observable nervous-system regulation (breath, grounding, movement)", "Astrology charts", "Random guessing", "A client's zodiac sign"], "correct_index": 0, "explanation": "Sessions should be anchored in observable nervous-system regulation, not unverifiable energetic claims."},
        {"question": "What did a 2024 review find about interoceptive (body-signal) awareness and PTSD?", "options": ["No relationship exists", "Decreased interoceptive awareness is consistently linked to PTSD", "Interoception cures PTSD instantly", "Only children experience this"], "correct_index": 1, "explanation": "A scoping review of 43 studies found decreased interoceptive awareness is consistently linked to PTSD."},
    ],
    "Module 6 — Introduction to ETT": [
        {"question": "Who developed Emotional Transformation Therapy (ETT) and trademarked it in 1991?", "options": ["Sigmund Freud", "Steven Vazquez", "Carl Jung", "Francine Shapiro"], "correct_index": 1, "explanation": "ETT was developed by psychologist Steven Vazquez, who trademarked the approach in 1991."},
        {"question": "What does ETT combine with structured visual input like colored light and eye movements?", "options": ["Standard talk therapy", "Only medication", "Physical exercise only", "Nothing else"], "correct_index": 0, "explanation": "ETT combines standard talk therapy with structured visual input to speed emotional processing."},
        {"question": "What is the current state of independent, peer-reviewed research on ETT?", "options": ["Extremely robust with hundreds of independent RCTs", "Limited — most existing studies were conducted by its own developer", "Banned from being studied", "Fully validated by the FDA"], "correct_index": 1, "explanation": "Independent research remains limited, so effectiveness claims are still considered preliminary."},
        {"question": "How should ETT be presented to trainees, given its evidence base?", "options": ["As a fully validated standalone trauma protocol", "As a complementary technique layered onto established talk therapy", "As a replacement for all other therapies", "As having no clinical value whatsoever"], "correct_index": 1, "explanation": "ETT is best presented as complementary to established talk therapy, not a validated protocol on its own."},
    ],
    "Module 7 — Epigenetics and Neuroplasticity": [
        {"question": "What is DNA methylation an example of?", "options": ["A permanent change to the DNA sequence", "A way experiences chemically tag genes without altering the DNA sequence", "A type of surgery", "A vitamin"], "correct_index": 1, "explanation": "DNA methylation chemically tags genes in response to experience, without altering the underlying DNA sequence."},
        {"question": "What does 'neuroplasticity' refer to?", "options": ["The brain's fixed, unchangeable structure", "The brain's lifelong capacity to form new neural connections", "A type of plastic surgery", "Memory loss"], "correct_index": 1, "explanation": "Neuroplasticity is the brain's lifelong capacity to form new neural connections in response to safe, repeated experience."},
        {"question": "What practice builds durable neural pathways most effectively, per current research?", "options": ["One-off insight sessions with no follow-up", "Small, specific, repeated between-session practice reps", "High-intensity single exposure only", "Avoiding all practice"], "correct_index": 1, "explanation": "Consistent low-dose repetition between sessions builds durable neural pathways faster than one-off intensity."},
        {"question": "Which gene has recent research investigated as a biomarker linking childhood adversity to brain recovery?", "options": ["BDNF", "BRCA1", "MTHFR", "APOE"], "correct_index": 0, "explanation": "Recent research is investigating methylation of the BDNF gene, which supports neuron growth and plasticity."},
    ],
    "Module 8 — Ethics in Healing and Wellness": [
        {"question": "How should informed consent be treated in trauma-focused work?", "options": ["As a one-time form signed at intake", "As an ongoing process that can be revoked at any point", "As unnecessary paperwork", "As the client's sole responsibility"], "correct_index": 1, "explanation": "Informed consent is ongoing — clients can revoke consent at any point, including mid-session."},
        {"question": "What is a 'choice point' in session?", "options": ["A billing decision", "A verbal check-in like 'Is it okay if we go there now?'", "The end of a session", "A legal document"], "correct_index": 1, "explanation": "Choice points are verbal check-ins used before charged material to keep consent active in-session."},
        {"question": "For non-clinical wellness modalities like energy work, what must practitioners disclose?", "options": ["Nothing is required", "Plainly that it is not a medical treatment", "That it cures all conditions", "Their personal religious views"], "correct_index": 1, "explanation": "Practitioners must plainly disclose that non-clinical modalities are not medical treatment and stay within scope of practice."},
        {"question": "What ethical shift has emerged since 2024 regarding AI tools in therapy?", "options": ["AI tools are banned entirely", "States now require explicit client consent for AI-assisted notetaking", "AI has replaced all therapists", "No changes have occurred"], "correct_index": 1, "explanation": "Since 2024, several states require explicit written client consent for AI-assisted notetaking and analysis tools."},
    ],
    "Module 9 — Light and Color in Healing": [
        {"question": "Which retinal cells are primarily responsible for light's mood effects, separate from vision?", "options": ["Rod cells", "Cone cells", "Melanopsin-containing retinal cells", "Optic nerve fibers"], "correct_index": 2, "explanation": "Melanopsin-containing retinal cells, most sensitive to blue wavelengths, drive light's mood effects separate from vision."},
        {"question": "How is morning light exposure typically dosed in structured protocols?", "options": ["By color only, regardless of duration", "By minutes per day (e.g. 15–60 min)", "Randomly with no structure", "Only once per year"], "correct_index": 1, "explanation": "Morning light exposure is dosed by minutes per day, not just by wavelength or color."},
        {"question": "What conditions must practitioners screen for before any light protocol?", "options": ["Allergies only", "Seizure disorders, migraines, bipolar disorder, retinal/eye conditions", "Food preferences", "Handedness"], "correct_index": 1, "explanation": "Light can trigger mania or seizures, so these conditions must be screened for before any light protocol."},
        {"question": "How should chakra/color-based light work be framed, unlike dosed light-box or EMDR protocols?", "options": ["As a proven PTSD treatment", "As a wellness adjunct, not a proven PTSD treatment", "As dangerous and forbidden", "As a replacement for medication"], "correct_index": 1, "explanation": "Chakra/color-based light work should be framed as a wellness adjunct, unlike clinically dosed protocols."},
    ],
    "Module 10 — Cultural Considerations in Therapy": [
        {"question": "What does 'broaching' mean in a therapeutic context?", "options": ["Avoiding all discussion of race and culture", "Proactively inviting discussion of culture, identity, and power at the client's pace", "Breaking client confidentiality", "A billing term"], "correct_index": 1, "explanation": "Broaching means proactively inviting discussion of culture, identity, and power, at the client's own pace."},
        {"question": "What predicts stronger therapy outcomes better than one-time competence training?", "options": ["Cultural humility — an ongoing openness to a client's identity", "Memorizing cultural facts", "Avoiding the topic entirely", "Strict adherence to a single manual"], "correct_index": 0, "explanation": "Cultural humility, an ongoing openness to identity, outperforms one-time competence training."},
        {"question": "How can evidence-based protocols like TF-CBT be culturally adapted?", "options": ["By replacing the core model entirely", "By weaving in religious/folk practices and family structures without replacing the core model", "By ignoring cultural factors", "By using a different protocol per culture"], "correct_index": 1, "explanation": "Cultural adaptation weaves in client practices and structures while keeping the evidence-based core model intact."},
        {"question": "How can racial or historical trauma pass across generations?", "options": ["Only through genetics", "Through family communication and coping patterns, not only genetics", "It cannot pass across generations", "Only through inherited wealth"], "correct_index": 1, "explanation": "Racial and historical trauma can pass through family communication and coping patterns, not only genetics."},
    ],
    "ETT Clinical Level 1": [
        {"question": "What does case conceptualization turn assessment data into?", "options": ["A billing code", "A working model of the client's problems, targets, and obstacles", "A diagnosis only", "A legal document"], "correct_index": 1, "explanation": "Case conceptualization turns assessment data into a working model guiding treatment."},
        {"question": "What is Attachment-Based Family Therapy (ABFT) a guideline-listed treatment for?", "options": ["Adolescent depression and suicidality", "The common cold", "Diabetes", "None of the above"], "correct_index": 0, "explanation": "ABFT is a guideline-listed treatment for adolescent depression and suicidality."},
        {"question": "What does evidence-based assessment pair standardized measures with?", "options": ["Guesswork", "Clinical judgment", "Astrology", "Random selection"], "correct_index": 1, "explanation": "Evidence-based assessment pairs standardized measures with clinical judgment for accuracy."},
    ],
    "ETT Clinical Level 2": [
        {"question": "Why does DSM-5-TR require separately assessing trauma exposure and substance use patterns?", "options": ["They are unrelated", "PTSD and addiction frequently co-occur", "It's a legal requirement only", "Insurance mandates it"], "correct_index": 1, "explanation": "PTSD and addiction frequently co-occur, so both must be separately assessed for effective care."},
        {"question": "How is spirituality framed in APA's 2023 Handbook of Spiritually Integrated Psychotherapies?", "options": ["As a standalone proven treatment", "As a cultural factor to integrate ethically, not a standalone treatment", "As irrelevant to therapy", "As a diagnostic category"], "correct_index": 1, "explanation": "Spirituality is framed as a cultural factor to integrate ethically, not a proven standalone treatment."},
        {"question": "What combined approach has shown reductions in both PTSD symptoms and alcohol use?", "options": ["Cognitive Processing Therapy paired with Relapse Prevention", "Medication alone", "No treatment", "Isolation therapy"], "correct_index": 0, "explanation": "Combining CPT with Relapse Prevention has shown reductions in both PTSD symptoms and alcohol use."},
    ],
    "Trauma-Informed Hospitality Training": [
        {"question": "How many SAMHSA guiding principles underpin trauma-informed care?", "options": ["Three", "Six", "Ten", "Two"], "correct_index": 1, "explanation": "SAMHSA's trauma-informed approach rests on six guiding principles."},
        {"question": "What percentage of customer-facing employees report encountering customer aggression regularly?", "options": ["Roughly 10%", "Roughly 75%", "Roughly 25%", "Nearly 100%"], "correct_index": 1, "explanation": "Roughly 75% of customer-facing employees report encountering customer aggression regularly."},
        {"question": "What is a stronger protective factor against burnout than individual self-care alone?", "options": ["Organizational culture and manager support", "Higher pay only", "Longer shifts", "Isolation from coworkers"], "correct_index": 0, "explanation": "Organizational culture and manager support are stronger protective factors against burnout than self-care alone."},
    ],
    "Wellness Retreat Program": [
        {"question": "What combination improves mood more than either approach alone?", "options": ["Time in nature combined with mindfulness practice", "Sleep alone", "Caffeine and exercise", "Isolation and silence"], "correct_index": 0, "explanation": "Combining time in nature with mindfulness practice improves mood more than either alone."},
        {"question": "How is personal transformation best described according to research?", "options": ["A single peak moment", "A gradual, evolving process", "An instant fix", "Something only possible in childhood"], "correct_index": 1, "explanation": "Personal transformation is described as a gradual, evolving process rather than a single peak moment."},
        {"question": "What theme is common to many transformative experiences?", "options": ["Increased ego-focus", "Self-transcendence — a shift toward less ego-focused concerns", "Total isolation", "Financial gain"], "correct_index": 1, "explanation": "Self-transcendence, a shift toward less ego-focused concerns, is a common theme in transformative experiences."},
    ],
    "Rehabilitation Support Program": [
        {"question": "What percentage of U.S. drug courts now permit medication-assisted treatments like buprenorphine?", "options": ["Less than 10%", "More than 90%", "Exactly 50%", "None"], "correct_index": 1, "explanation": "More than 90% of U.S. drug courts now permit medication-assisted treatments, reversing past restrictions."},
        {"question": "What should reentry success be measured by, rather than recidivism alone?", "options": ["Employment, housing stability, and health", "Number of arrests only", "Nothing else matters", "Media coverage"], "correct_index": 0, "explanation": "Researchers argue reentry success should be measured by employment, housing stability, and health."},
        {"question": "Who uses lived experience to build trust and connect people to resources in rehabilitation programs?", "options": ["Peer recovery specialists", "Random volunteers", "Only judges", "Insurance agents"], "correct_index": 0, "explanation": "Peer recovery specialists use their own lived experience to build trust and connect clients to resources."},
    ],
}

# Hand-authored interactive slide deck for Module 7 — supplied directly as
# structured presentation content (title / content / closing slide types).
MODULE_7_SLIDES = [
    {"type": "title", "eyebrow": "Module 7", "title": "Neuroplasticity, Epigenetics & Post-Traumatic Growth", "subtitle": "How the brain and body adapt, heal, and grow after trauma"},
    {"type": "content", "eyebrow": "Why This Matters", "title": "Why This Matters", "points": [
        "Trauma doesn't just affect emotions — it reshapes the brain, influences gene expression, and alters how we relate to the world.",
        "The good news: the same systems impacted by trauma are also the systems that allow healing and growth.",
        "This module explores how the brain changes (neuroplasticity), how experience influences biology (epigenetics), and how resilience and growth can emerge after trauma (PTG).",
    ]},
    {"type": "content", "eyebrow": "Reframe", "title": "Trauma: A Quick Reframe", "points": [
        "Trauma is not the event — it's the body and nervous system's response to an overwhelming experience.",
        "Trauma lives in the brain and body.",
        "It prioritizes survival over connection and learning.",
        "Healing is about restoring safety and flexibility — not 'forgetting'.",
    ]},
    {"type": "content", "eyebrow": "Neuroplasticity", "title": "What Is Neuroplasticity?", "points": [
        "The brain's ability to change its structure and function based on experience.",
        "Neurons that fire together, wire together.",
        "Repeated experiences strengthen certain pathways.",
        "The brain remains changeable throughout life.",
        "This applies to habits, emotional responses, trauma patterns, and healing patterns.",
    ]},
    {"type": "content", "eyebrow": "Neuroplasticity", "title": "Neuroplasticity & Trauma", "points": [
        "Trauma creates strong survival pathways: hypervigilance, emotional shutdown, fight/flight/freeze/fawn responses.",
        "These patterns are adaptive, not pathological — they kept the person safe at one point in time.",
        "Healing works by creating new experiences of safety, repeating regulation and connection, and gently weakening survival-only pathways.",
    ]},
    {"type": "content", "eyebrow": "Neuroplasticity", "title": "Neuroplasticity & Healing", "points": [
        "The brain changes through experience, not insight alone.",
        "Practices that support healing plasticity: nervous system regulation, mindfulness and body awareness, EMDR/somatic therapies/breathwork, safe relationships and co-regulation, repetition over intensity.",
        "Small, consistent inputs matter more than dramatic breakthroughs.",
    ]},
    {"type": "content", "eyebrow": "Epigenetics", "title": "What Is Epigenetics?", "points": [
        "How experiences influence whether certain genes are turned 'on' or 'off'.",
        "Genes do not change — gene expression changes.",
        "Think of genes as a piano: the keys are fixed, but the music played depends on the environment.",
    ]},
    {"type": "content", "eyebrow": "Epigenetics", "title": "Epigenetics & Trauma", "points": [
        "Trauma, especially early or chronic trauma, can influence stress hormone regulation, immune responses, and emotional sensitivity.",
        "It can also affect vulnerability to anxiety or depression.",
        "These changes can sometimes be passed across generations — not as destiny, but as sensitivity.",
        "This helps explain intergenerational trauma without blame.",
    ]},
    {"type": "content", "eyebrow": "Epigenetics", "title": "Epigenetics & Healing", "points": [
        "Just as stress can influence gene expression, healing experiences can too.",
        "Supportive factors: safe attachment, emotional regulation, nutrition/sleep/movement, reduced chronic stress, meaningful connection.",
        "Biology is responsive, not fixed.",
    ]},
    {"type": "content", "eyebrow": "Resilience", "title": "Trauma Resilience: What It Really Means", "points": [
        "Resilience does not mean being unaffected, 'bouncing back' quickly, or staying positive.",
        "True resilience means adaptability, recovery after disruption, capacity to feel and regulate, and the ability to re-engage with life.",
    ]},
    {"type": "content", "eyebrow": "Resilience", "title": "Building Trauma Resilience", "points": [
        "Resilience develops through nervous system flexibility, emotional literacy, safe relationships, meaning-making, and self-compassion.",
        "It is relational, not individual willpower.",
    ]},
    {"type": "content", "eyebrow": "Post-Traumatic Growth", "title": "What Is Post-Traumatic Growth (PTG)?", "points": [
        "Positive psychological changes that can occur after trauma.",
        "Growth does not cancel pain.",
        "Growth does not mean trauma was 'good'.",
        "Growth happens alongside grief and loss.",
    ]},
    {"type": "content", "eyebrow": "Post-Traumatic Growth", "title": "Areas of Post-Traumatic Growth", "points": [
        "Deeper relationships",
        "Greater appreciation for life",
        "Increased personal strength",
        "New priorities and meaning",
        "Spiritual or existential shifts",
        "PTG is not forced — it emerges when safety and integration are present.",
    ]},
    {"type": "content", "eyebrow": "Post-Traumatic Growth", "title": "How PTG Develops", "points": [
        "Processing, not bypassing, trauma",
        "Emotional expression",
        "Coherent storytelling",
        "Supportive communities",
        "A sense of agency",
        "Growth follows integration, not suppression.",
    ]},
    {"type": "content", "eyebrow": "Synthesis", "title": "Bringing It All Together", "points": [
        "Trauma impacts brain pathways (neuroplasticity), biological expression (epigenetics), and sense of self and meaning.",
        "Healing involves creating safety, rewiring patterns through experience, supporting the body as much as the mind, and allowing space for resilience and growth.",
    ]},
    {"type": "content", "eyebrow": "Summary", "title": "Key Takeaways", "points": [
        "The brain is changeable.",
        "Biology is responsive.",
        "Trauma responses are intelligent adaptations.",
        "Healing is experiential and relational.",
        "Growth is possible, but never rushed.",
    ]},
    {"type": "closing", "eyebrow": "Closing Reflection", "title": "Closing Reflection", "quote": "Healing is not about becoming who you were before. It's about becoming more integrated, more flexible, and more alive than survival allowed."},
]


def auto_slides_from_course(course: "Course") -> list:
    """Build a slide deck from a course's existing content cards, so every
    course gets an interactive presentation even without hand-authored slides."""
    slides = [{
        "type": "title",
        "eyebrow": f"{course.track.capitalize()} Track",
        "title": course.title,
        "subtitle": course.description,
    }]
    for card in course.content_cards:
        slides.append({
            "type": "content",
            "eyebrow": card.title,
            "title": card.title,
            "points": card.points,
        })
        if card.insight:
            slides.append({
                "type": "content",
                "eyebrow": "Latest Research",
                "title": "Latest Research",
                "points": [card.insight],
            })
    if course.features:
        slides.append({
            "type": "closing",
            "eyebrow": "Key Takeaways",
            "title": "Key Takeaways",
            "points": course.features[:6],
        })
    return slides


@api_router.post("/seed")
async def seed_data():
    # Clear existing courses
    await db.courses.delete_many({})
    
    courses = [
        # ETT Prerequisite Foundation Course Modules (Wellness Track)
        Course(
            title="Module 1 — Understanding Trauma",
            track="wellness",
            level="module",
            description="Acute, chronic, and developmental trauma fundamentals",
            detailed_description="This module covers how trauma lives in the nervous system and body. Learn about acute, chronic, and developmental trauma, trauma stored in the nervous system and body memory, intergenerational patterns and defense mechanisms, and the 'inner thorn' approach to safe trauma work.",
            price=15000.00,
            equipment_fee=0.0,
            duration="1 day",
            location="Mumbai, India",
            schedule="March 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "Acute, chronic, and developmental trauma",
                "Trauma stored in nervous system and body memory",
                "Intergenerational patterns and defense mechanisms",
                "The 'inner thorn' approach to safe trauma work"
            ]
        ),
        Course(
            title="Module 2 — Brain Waves & Nervous System States",
            track="wellness",
            level="module",
            description="Delta, theta, alpha, beta, and gamma brain states",
            detailed_description="Understand why brain states matter more than insight in healing. Explore delta, theta, alpha, beta, and gamma brain states, emotional regulation and cognitive function, and why timing and brain state determine therapeutic success.",
            price=15000.00,
            equipment_fee=0.0,
            duration="1 day",
            location="Mumbai, India",
            schedule="March 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "Delta, theta, alpha, beta, gamma states",
                "Emotional regulation and cognitive function",
                "Timing and brain state in therapy",
                "Nervous system readiness for healing"
            ]
        ),
        Course(
            title="Module 3 — The Role of Eyes in Healing",
            track="wellness",
            level="module",
            description="Neurological pathways connected to eye movement",
            detailed_description="Learn how eye movement, perception, and visual input affect emotional processing. Cover neurological pathways connected to eye movement, visual input, memory access, emotional regulation, and how guided eye movement supports processing in ETT.",
            price=15000.00,
            equipment_fee=0.0,
            duration="1 day",
            location="Delhi, India",
            schedule="April 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "Neurological pathways and eye movement",
                "Visual input, memory access, emotional regulation",
                "Guided eye movement in ETT",
                "Perception and emotional processing"
            ]
        ),
        Course(
            title="Module 4 — Attachment Styles and Relationships",
            track="wellness",
            level="module",
            description="Secure, anxious, avoidant, and disorganized attachment",
            detailed_description="Understand the relevance of attachment styles in therapeutic readiness. Learn about secure, anxious, avoidant, and disorganized attachment, how attachment patterns influence healing capacity, and working with relational patterns in ETT practice.",
            price=15000.00,
            equipment_fee=0.0,
            duration="1 day",
            location="Delhi, India",
            schedule="April 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "Secure, anxious, avoidant, disorganized attachment",
                "Attachment patterns and healing capacity",
                "Working with relational patterns",
                "Therapeutic readiness assessment"
            ]
        ),
        Course(
            title="Module 5 — Chakras and Levels of Consciousness",
            track="wellness",
            level="module",
            description="Chakras as psychological and energetic centers",
            detailed_description="Explore the relationship between chakras, consciousness, and psychological states. Learn about chakras as psychological and energetic centers, progression from survival to self-realization, and integrating chakra awareness into therapeutic work.",
            price=15000.00,
            equipment_fee=0.0,
            duration="1 day",
            location="Bangalore, India",
            schedule="May 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "Chakras as psychological centers",
                "Progression from survival to self-realization",
                "Integrating chakra awareness in therapy",
                "Consciousness levels and healing"
            ]
        ),
        Course(
            title="Module 6 — Introduction to ETT",
            track="wellness",
            level="module",
            description="Foundations and principles of Emotional Transformation Therapy",
            detailed_description="Learn the foundations and principles of ETT, how ETT works beyond talk therapy, and the integration of perception, memory, and nervous system in the healing process.",
            price=18000.00,
            equipment_fee=0.0,
            duration="1.5 days",
            location="Bangalore, India",
            schedule="May 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "Foundations and principles of ETT",
                "How ETT works beyond talk therapy",
                "Perception, memory, nervous system integration",
                "Introduction to ETT techniques"
            ]
        ),
        Course(
            title="Module 7 — Epigenetics and Neuroplasticity",
            track="wellness",
            level="module",
            description="How experiences influence gene expression and brain rewiring",
            detailed_description="Understand the science of neuroplasticity and epigenetics behind lasting change. Learn how experiences influence gene expression, the brain's capacity to rewire, and supporting permanent change through neurological pathways.",
            price=15000.00,
            equipment_fee=0.0,
            duration="1 day",
            location="Chennai, India",
            schedule="June 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "How experiences influence gene expression",
                "Brain's capacity to rewire",
                "Supporting permanent change",
                "Neurological pathways of transformation"
            ]
        ),
        Course(
            title="Module 8 — Ethics in Healing and Wellness",
            track="wellness",
            level="module",
            description="Boundaries, consent, and client safety in trauma work",
            detailed_description="Learn ethical responsibility in healing work including boundaries, consent, and client safety, professional responsibility in trauma work, and ETT-specific ethical considerations.",
            price=12000.00,
            equipment_fee=0.0,
            duration="1 day",
            location="Chennai, India",
            schedule="June 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "Boundaries, consent, client safety",
                "Professional responsibility",
                "ETT-specific ethical considerations",
                "Annual ethics certification"
            ]
        ),
        Course(
            title="Module 9 — Light and Color in Healing",
            track="wellness",
            level="module",
            description="Physiological and psychological effects of light and color",
            detailed_description="Learn how light and color directly influence physiology and emotion. Cover physiological and psychological effects of light and color, wavelengths, perception, and emotional states, and practical applications in ETT and wellness settings.",
            price=18000.00,
            equipment_fee=5000.00,
            duration="1.5 days",
            location="Hyderabad, India",
            schedule="July 2025",
            instructor="ETT Certified Trainer",
            max_participants=20,
            features=[
                "Physiological effects of light and color",
                "Wavelengths and emotional states",
                "Practical applications in ETT",
                "Light therapy equipment training"
            ]
        ),
        Course(
            title="Module 10 — Cultural Considerations in Therapy",
            track="wellness",
            level="module",
            description="Cultural identity, racial, and intergenerational dynamics",
            detailed_description="Learn the importance of cultural awareness in therapy and wellness practice. Cover cultural identity and healing, racial, ethnic, and intergenerational dynamics, and practicing ETT with cultural sensitivity and awareness.",
            price=12000.00,
            equipment_fee=0.0,
            duration="1 day",
            location="Hyderabad, India",
            schedule="July 2025",
            instructor="ETT Certified Trainer",
            max_participants=25,
            features=[
                "Cultural identity and healing",
                "Racial, ethnic, intergenerational dynamics",
                "ETT with cultural sensitivity",
                "Inclusive practice guidelines"
            ]
        ),
        # Clinical Track Courses
        Course(
            title="ETT Clinical Level 1",
            track="clinical",
            level="level1",
            description="Core ETT techniques & attachment work for mental health professionals",
            detailed_description="Comprehensive clinical training covering all wellness content plus advanced clinical protocols. Learn core ETT techniques, attachment work methodologies, and evidence-based approaches for licensed mental health practitioners.",
            price=65000.00,
            equipment_fee=15000.00,
            duration="4 days",
            location="Mumbai, India",
            schedule="April 20-23, 2025",
            instructor="Dr. Rajesh Kumar",
            max_participants=18,
            features=[
                "All prerequisite modules content",
                "Clinical assessment protocols",
                "Attachment-based interventions",
                "Case conceptualization",
                "Supervised practice",
                "Clinical documentation"
            ]
        ),
        Course(
            title="ETT Clinical Level 2",
            track="clinical",
            level="level2",
            description="Addiction, trauma, spirituality, and DSM-5 diagnostic integration",
            detailed_description="Advanced clinical certification covering complex presentations including addiction, somatic conditions, trauma, spirituality/religion integration, and DSM-5 diagnostic frameworks. Includes monthly consultation calls and certification requirements.",
            price=85000.00,
            equipment_fee=25000.00,
            duration="4 days",
            location="Delhi, India",
            schedule="June 15-18, 2025",
            instructor="Dr. Sunita Reddy",
            max_participants=15,
            features=[
                "Addiction treatment protocols",
                "Trauma-informed interventions",
                "Somatic condition management",
                "Spiritual integration approaches",
                "DSM-5 diagnostic integration",
                "Monthly consultation calls",
                "Certification pathway"
            ]
        ),
        # Coming Soon Programs
        Course(
            title="Trauma-Informed Hospitality Training",
            track="wellness",
            level="advanced",
            description="Specialized training for hospitality staff and corporate teams",
            detailed_description="Coming soon: A specialized program designed for hospitality industry professionals and corporate teams to understand and respond to trauma-informed practices in workplace settings.",
            price=35000.00,
            duration="2 days",
            location="Multiple Locations",
            schedule="Coming Soon",
            is_coming_soon=True,
            features=[
                "Understanding workplace trauma",
                "De-escalation techniques",
                "Self-care strategies",
                "Team support protocols"
            ]
        ),
        Course(
            title="Wellness Retreat Program",
            track="wellness",
            level="advanced",
            description="Immersive wellness retreat experience at holistic centers",
            detailed_description="Coming soon: An immersive retreat program combining ETT practices with holistic wellness approaches at certified retreat centers across India.",
            price=75000.00,
            duration="5 days",
            location="Rishikesh, India",
            schedule="Coming Soon",
            is_coming_soon=True,
            features=[
                "Immersive ETT experience",
                "Meditation & yoga integration",
                "Nature therapy",
                "Personal transformation journey"
            ]
        ),
        Course(
            title="Rehabilitation Support Program",
            track="clinical",
            level="advanced",
            description="Specialized program for people on probation and rehabilitation",
            detailed_description="Coming soon: A specialized rehabilitation program designed in compliance with requirements for addiction and rehabilitation centers, supporting individuals on probation.",
            price=45000.00,
            duration="3 days",
            location="Various Centers",
            schedule="Coming Soon",
            is_coming_soon=True,
            features=[
                "Compliance-focused curriculum",
                "Rehabilitation protocols",
                "Reintegration support",
                "Follow-up resources"
            ]
        )
    ]

    # Attach content cards: web-researched cards for the 10 prerequisite modules,
    # auto-generated "highlights" cards (from features) for every other course.
    for course in courses:
        if course.title in MODULE_CONTENT:
            course.content_cards = [ContentCard(**card) for card in MODULE_CONTENT[course.title]]
        elif course.features:
            course.content_cards = [ContentCard(title="Program Highlights", points=course.features)]
        if course.title in QUIZ_CONTENT:
            course.quiz = [QuizQuestion(**q) for q in QUIZ_CONTENT[course.title]]
        if course.title == "Module 7 — Epigenetics and Neuroplasticity":
            course.slides = [SlideItem(**s) for s in MODULE_7_SLIDES]
        else:
            course.slides = [SlideItem(**s) for s in auto_slides_from_course(course)]

    for course in courses:
        await db.courses.insert_one(course.model_dump())

    return {"message": f"Seeded {len(courses)} courses"}

# ============ HEALTH CHECK ============

@api_router.get("/")
async def root():
    return {"message": "Trauma Transformation Institute API", "status": "healthy"}

@api_router.get("/health")
async def health():
    return {"status": "ok"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def ensure_admin_user():
    """Provision the admin account (bypasses Stripe on checkout) if it doesn't exist yet."""
    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    if existing:
        return
    await db.users.insert_one({
        "id": str(uuid.uuid4()),
        "email": ADMIN_EMAIL,
        "name": ADMIN_NAME,
        "password_hash": hash_password(ADMIN_PASSWORD),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    logger.info(f"Provisioned admin account: {ADMIN_EMAIL}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
