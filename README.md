# ResumeSpark Flask App

ResumeSpark is a Flask application with authentication, resume generation, career planning, and interview preparation.

## Features

- Email/password sign up and sign in
- Google login route wiring
- Forgot password flow with reset token link generation
- Dashboard tools:
  - Create New Resume
  - Career Lab
  - Cover Letter Generator
  - Resume Score
  - Interview Prep
- Resume PDF download
- Custom target role support such as AI Engineer
- Flexible roadmap duration from 1 month to 10 years
- SQLite database for local development

## Setup

1. Open PowerShell and go to the project:

```powershell
cd E:\ResumeSpark
```

2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Run the app:

```powershell
python app.py
```

5. Open `http://127.0.0.1:5000`

## Google Login Setup

Google login is wired into the app, but it needs environment variables before it will work:

```powershell
$env:GOOGLE_CLIENT_ID="your-client-id"
$env:GOOGLE_CLIENT_SECRET="your-client-secret"
$env:SECRET_KEY="a-strong-secret"
```

## Forgot Password Note

The forgot-password flow currently generates a reset link on-screen for local development. The next step is connecting an email provider.

## New Input Features

- Users can select `Other` in target role and type a custom professional role.
- Resume Builder asks additional questions like phone, city, LinkedIn, GitHub, summary, internship, certifications, and achievements.
- Career Lab asks for roadmap time so the roadmap can be planned for 1 month, 3 months, 6 months, 1 year, 2 years, 5 years, 7 years, 8 years, or 10 years.
- Required skills now include direct search links to company career sources when available.
