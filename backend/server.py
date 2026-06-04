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

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

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
            created_at=user_doc["created_at"]
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
            created_at=user["created_at"]
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        created_at=user["created_at"]
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

# ============ SEED DATA ============

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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
