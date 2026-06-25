# Sign Link

Sign Link is a full-stack communication platform for Deaf and Hearing users. It includes JWT authentication, profiles, user search, realtime chat, one-to-one WebRTC calling, call history, multilingual UI support, dark mode, MySQL persistence, and placeholder AI endpoints for future sign-language recognition and speech workflows.

## Stack

- Frontend: React, Vite, React Router, Tailwind CSS, Axios, Socket.IO Client
- Backend: Node.js, Express, Socket.IO, JWT, bcrypt, Helmet, CORS, express-validator
- Database: MySQL
- Calling: WebRTC with Socket.IO signaling
- Landmark service: Python FastAPI, OpenCV, MediaPipe Hands, MediaPipe Face Mesh

## Project Structure

```text
frontend/   React client
backend/    Express API and Socket.IO server
database/   MySQL schema
docs/       API and deployment documentation
ai-service/ FastAPI landmark extraction service
```

## Setup

1. Install dependencies:

```bash
npm run install:all
```

2. Create environment files:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

3. Create the database:

```bash
mysql -u root -p < database/schema.sql
```

4. Start the backend:

```bash
npm run dev:backend
```

5. Start the frontend:

```bash
npm run dev:frontend
```

Frontend runs on `http://localhost:5173` and backend runs on `http://localhost:5000` by default.

6. Start the landmark service:

```bash
cd ai-service
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Key Features

- Register and login with email validation, bcrypt password hashing, and JWT sessions
- Protected React routes and session refresh via `/api/auth/me`
- Update profile role, language, and profile picture URL
- Search users and launch chat or video calls
- Realtime messages, typing indicator, and Socket.IO online events
- Seen receipts for messages
- WebRTC call flow with incoming call, accept, reject, ICE, end call, audio/video toggles, fullscreen, and duration timer
- Call history stored in MySQL
- Browser speech-to-text through Web Speech API
- Browser text-to-speech through `speechSynthesis`
- Periodic video frame landmark detection through the FastAPI MediaPipe service
- English, Hindi, and Punjabi translation JSON files
- Dark and light theme support
- AI-ready API placeholders for sign prediction, translation, speech-to-text, and text-to-speech

## API

See [docs/API.md](docs/API.md).

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
