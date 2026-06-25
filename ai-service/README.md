# Sign Link Landmark Service

FastAPI service for frame-based MediaPipe landmark extraction.

It detects:

- Up to two hands with MediaPipe Hands
- One face with MediaPipe Face Mesh

It does not classify signs, load datasets, train ML models, or predict gestures.

## Run

```powershell
cd ai-service
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Health:

```text
http://localhost:8000/health
```

Landmarks:

```http
POST http://localhost:8000/api/landmarks
Content-Type: application/json

{
  "image": "data:image/jpeg;base64,..."
}
```
