# Trauma Transformation Institute (TTI) - PRD

## Original Problem Statement
Build a website for Trauma Transformation Institute (TTI) / ETT India offering Emotional Transformation Therapy programs and courses in India. Two main tracks: ETT Wellness Model and ETT Clinical Model.

## User Personas
1. **Wellness Professionals** - Personal development seekers, yoga instructors, life coaches
2. **Mental Health Professionals** - Licensed therapists, psychologists seeking clinical certification
3. **Corporate Teams** - HR professionals, hospitality staff (Coming Soon)

## Core Requirements
- Landing page with two pathway options (Wellness vs Clinical)
- Course catalog with 10 prerequisite modules
- User authentication (signup/login)
- Stripe payment integration for enrollment
- User dashboard for enrolled courses
- Coming Soon badges for upcoming programs

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB
- **Payment**: Stripe Checkout
- **Auth**: JWT-based authentication

## What's Been Implemented (June 2025)

### Design & UI
- Custom TTI logo integration (teal brain icon)
- Wavy teal background design (matching reference website)
- Navy/white color scheme with teal accents
- Playfair Display + DM Sans fonts
- Responsive cards with shadow effects

### Backend APIs
- User authentication (signup/login/me)
- Courses CRUD with track filtering
- Stripe checkout integration
- Payment status polling
- Enrollments management
- Seed data for 15 courses

### Frontend Pages
- LandingPage - Two track selection cards
- WellnessHomePage - 12 courses (10 modules + 2 coming soon)
- ClinicalHomePage - 3 courses (2 levels + 1 coming soon)
- CourseDetailsPage - Full course info with enrollment
- LoginPage / SignupPage - Auth forms
- DashboardPage - User enrolled courses
- PaymentSuccessPage - Payment confirmation
- AboutPage - Institute information

### Course Modules (Wellness Track)
1. Module 1 — Understanding Trauma
2. Module 2 — Brain Waves & Nervous System States
3. Module 3 — The Role of Eyes in Healing
4. Module 4 — Attachment Styles and Relationships
5. Module 5 — Chakras and Levels of Consciousness
6. Module 6 — Introduction to ETT
7. Module 7 — Epigenetics and Neuroplasticity
8. Module 8 — Ethics in Healing and Wellness
9. Module 9 — Light and Color in Healing
10. Module 10 — Cultural Considerations in Therapy

## Prioritized Backlog

### P0 (Must Have) - DONE
- [x] Landing page with track selection
- [x] Course catalog display
- [x] User authentication
- [x] Stripe payment integration
- [x] User dashboard

### P1 (Should Have)
- [ ] Training materials download/access
- [ ] Monthly consultation call scheduling
- [ ] Email notifications for enrollment
- [ ] Admin dashboard for course management

### P2 (Nice to Have)
- [ ] Progress tracking per module
- [ ] Certificate generation
- [ ] Group cohort management
- [ ] Instructor profiles page
- [ ] Blog/resources section

## Next Tasks
1. Add training materials section for enrolled users
2. Implement email confirmation for enrollments
3. Add contact form functionality
4. Create admin panel for course management
5. Add certificate generation for completed courses
