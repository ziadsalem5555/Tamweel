# CrowdFund Egypt 🇪🇬 - Django Crowdfunding Platform

A full-stack, modern Crowdfunding web application built with **Django 6.1**, **Bootstrap 5**, and **SQLite/PostgreSQL**, tailored specifically for fundraising campaigns and social innovation in Egypt.

---

## 🌟 Key Features

### 1. 🔐 Authentication & Account Management
- **Registration**: Custom user model with First Name, Last Name, Email, Password, Confirm Password, Egyptian Mobile Phone validation, and Profile Picture.
- **Egyptian Mobile Validation**: Validates Egyptian phone prefixes (`010`, `011`, `012`, `015` and international format `+2010...`).
- **24-Hour Email Activation**: Secure signed cryptographic tokens with a strict 24-hour expiration window. Users cannot log in before email verification.
- **Login / Logout**: Authentication via Email & Password.
- **Password Reset**: Complete built-in Django password reset flow via email.
- **User Profile**:
  - View personal info, profile picture, birthdate, facebook profile, country.
  - View all created campaigns and personal donations.
  - Edit all profile info **except email** (immutable).
  - Account deletion with **password confirmation verification**.

### 2. 🚀 Campaigns & Projects
- **Campaign Creation**: Title, details/story, target amount (in EGP), start time, end time, category, tags, and multiple image uploads.
- **Multiple Pictures Slider**: Interactive image carousel on campaign details and cards.
- **Fundraising Progress**: Real-time calculation of total donations, progress percentage, and remaining amount in EGP.
- **25% Cancellation Business Rule**: Project creators can cancel a project **only if total donations are less than 25% of the target**.
- **Ratings**: 1 to 5 stars rating system with dynamically calculated average rating and ratings count.
- **Comments & 1-Level Nested Replies**: Authenticated discussions on campaigns.
- **Reporting System**: Users can submit inappropriate reports for campaigns or comments to admin moderators.
- **Similar Projects**: Dynamically recommends 4 similar projects based on shared tags (with fallback to category).

### 3. 🏠 Homepage & Discovery
- **Top Rated Running Projects Slider**: Top 5 highest rated running projects in an interactive carousel.
- **Latest 5 Projects**: Freshly launched campaigns.
- **Latest 5 Featured Projects**: Admin-selected featured campaigns.
- **Categories**: Visual category cards linking to filtered campaign listings.
- **Search**: Case-insensitive search by project title and `#tag`.
- **Pagination & Sorting**: Paginated campaign listings with sort by latest, oldest, target high/low.

### 4. 🛡️ Django Admin Management
- Custom Admin Dashboard at `/admin/` for managing Users, Categories, Projects, Project Images, Tags, Donations, Ratings, Comments, and Reports.
- Batch actions to mark projects as featured or review reports.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.14, Django 6.1
- **Database**: SQLite (default for development) / PostgreSQL ready
- **Image Processing**: Pillow
- **Frontend**: HTML5, CSS3, Bootstrap 5.3, FontAwesome 6, Vanilla JavaScript
- **Environment Management**: `python-dotenv`

---

## 🚀 Quick Start Guide

### 1. Clone the repository & Navigate to project directory:
```bash
cd "final project"
```

### 2. Set up virtual environment (optional but recommended):
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies:
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables:
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 5. Run Database Migrations:
```bash
python manage.py migrate
```

### 6. Load Realistic Egyptian Demo Data:
Run the built-in demo seeder:
```bash
python manage.py seed_data
```

This command automatically populates:
- **Admin Account**: `admin@crowdfundegypt.com` | `Admin123456!`
- **Demo Users**: `ahmed.hassan@example.com`, `sara.ibrahim@example.com`, etc. (Password: `Password123!`)
- 6 Egyptian categories, 13 tags, 7 funded projects with images, donations, ratings, comments, and replies.

### 7. Run the Development Server:
```bash
python manage.py runserver
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## 🧪 Running Automated Tests

Run the complete test suite covering authentication, Egyptian phone validation, activation expiration, project cancellation business rules, ratings, and donations:

```bash
python manage.py test
```

---

## 📧 Email Configuration

By default in development, emails (activation & password reset) are logged directly to the console (`django.core.mail.backends.console.EmailBackend`).

To configure real SMTP (e.g. Gmail), update `.env`:
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=CrowdFund Egypt <noreply@crowdfundegypt.com>
```

---

## 🌐 Meta / Facebook OAuth Login (Bonus Feature)

Tamweel supports single sign-on via Meta / Facebook OAuth 2.0.

### 1. Facebook App Setup:
1. Go to the [Meta for Developers Portal](https://developers.facebook.com/) and log in.
2. Click **Create App** and select **Authenticate and request data from users with Facebook Login** (or "Consumer" / "Business").
3. Add the **Facebook Login** product to your App.
4. Under **Facebook Login > Settings > Client OAuth Settings**, add the exact OAuth Redirect URI:
   ```text
   http://127.0.0.1:8000/accounts/facebook/callback/
   ```
   *(For production, add `https://yourdomain.com/accounts/facebook/callback/`)*
5. Under **App Settings > Basic**, copy your **App ID** and **App Secret**.

### 2. Configure Environment Variables (`.env`):
```env
FACEBOOK_APP_ID=your_actual_facebook_app_id
FACEBOOK_APP_SECRET=your_actual_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://127.0.0.1:8000/accounts/facebook/callback/
```

### 3. Local Testing Flow:
1. Open `http://127.0.0.1:8000/accounts/login/` in your browser.
2. Click **Continue with Facebook**.
3. Authenticate and authorize permissions on Facebook dialog.
4. Facebook redirects back to Django, automatically linking to your existing account or creating a verified Tamweel profile without passwords.

---


## 📁 Project Architecture

```
final project/
│
├── accounts/                  # Authentication, custom user, profile, activation
│   ├── models.py              # Custom User model (Email primary, Egyptian phone, etc.)
│   ├── validators.py          # Egyptian mobile phone validator
│   ├── tokens.py              # 24-hour timestamp signed activation tokens
│   ├── forms.py               # Registration, Login, Profile Edit, Account Deletion
│   ├── views.py               # Auth & profile views
│   ├── urls.py                # Accounts routing
│   ├── admin.py               # User Admin configuration
│   └── tests.py               # Account unit & integration tests
│
├── projects/                  # Campaigns, categories, donations, comments, ratings
│   ├── models.py              # Category, Tag, Project, ProjectImage, Donation, Rating, Comment, Reports
│   ├── forms.py               # Project creation, Donation, Comment, Rating, Report forms
│   ├── views.py               # Home, Project list/detail, Donation, Rating, Comment, Cancellation views
│   ├── urls.py                # Projects routing
│   ├── admin.py               # Projects Admin configuration
│   ├── context_processors.py  # Global categories context processor
│   ├── management/commands/   # seed_data command
│   └── tests.py               # Projects & business rules test suite
│
├── crowdfunding/              # Project core settings & root routing
│   ├── settings.py            # App settings, media, auth backends, messages
│   ├── urls.py                # Root URLs
│   ├── wsgi.py
│   └── asgi.py
│
├── templates/                 # Reusable UI templates
│   ├── base.html              # Base layout with Bootstrap 5 & FontAwesome
│   ├── home.html              # Homepage (Top 5 slider, latest 5, featured, categories, search)
│   ├── accounts/              # Auth & profile templates
│   ├── projects/              # Project list, detail, create, cancel, my projects/donations
│   └── includes/              # Navbar, footer, flash messages, project card components
│
├── static/                    # Custom CSS and JavaScript
│   ├── css/style.css
│   └── js/main.js
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🎓 Viva / Interview Summary

- **Why a Custom User Model?**: Inheriting from `AbstractUser` and setting `email` as `USERNAME_FIELD` allows modern, secure email-based authentication while retaining Django's built-in permission system.
- **How does the 24-hour activation link work?**: Uses Django's `TimestampSigner` with `max_age=86400`. When the user clicks the link, the signature timestamp is compared against current time. If expired, `SignatureExpired` is handled gracefully.
- **How is the 25% cancellation rule enforced?**: The backend checks `project.total_donations < (0.25 * project.total_target)` in both the model property and the view before modifying the status, preventing client-side tampering.
