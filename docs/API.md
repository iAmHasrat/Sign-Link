# Sign Link API

Base URL: `http://localhost:5000/api`

Protected endpoints require `Authorization: Bearer <jwt>`.

## Health

`GET /health`

Returns API status.

## Authentication

`POST /auth/register`

```json
{
  "fullName": "Asha Singh",
  "username": "asha",
  "email": "asha@example.com",
  "password": "password123",
  "confirmPassword": "password123",
  "role": "Deaf",
  "preferredLanguage": "en"
}
```

`POST /auth/login`

```json
{
  "email": "asha@example.com",
  "password": "password123"
}
```

`GET /auth/me`

Refreshes the current authenticated session.

## Users

`GET /users/profile`

Returns the signed-in user.

`PUT /users/profile`

```json
{
  "fullName": "Asha Kaur",
  "role": "Deaf",
  "preferredLanguage": "pa",
  "profilePicture": "https://example.com/avatar.png"
}
```

`GET /users/search?q=asha`

Searches users by full name, username, or email.

## Messages

`GET /messages/:peerId`

Returns the latest conversation messages with a peer.

`PATCH /messages/:peerId/seen`

Marks messages from that peer as seen by the current user and emits a `messages-seen` Socket.IO event to the peer.

`POST /messages`

```json
{
  "receiverId": 2,
  "messageText": "Hello"
}
```

## Calls

`GET /calls/history`

Returns the signed-in user's call history.

## AI-Ready Placeholders

`POST /sign/predict`

Returns:

```json
{
  "sign": "HELP",
  "confidence": 0.95,
  "provider": "placeholder"
}
```

`POST /translate`

`POST /speech-to-text`

`POST /text-to-speech`

These endpoints are intentionally isolated so a future MediaPipe, TensorFlow, OpenCV, or FastAPI service can be introduced behind the controller layer without changing frontend routes.

## Socket.IO Events

Client authenticates with:

```js
io(SOCKET_URL, { auth: { token } })
```

Events:

- `user-online`: `{ userId, online }`
- `presence-snapshot`: `[{ userId, online }]`
- `send-message`: `{ receiverId, messageText }`
- `message-received`: message row
- `typing`: `{ receiverId, isTyping }`
- `messages-seen`: `{ peerId }` from client, `{ byUserId, messageIds, seenAt }` from server
- `incoming-call`: `{ receiverId, offer }`
- `call-accepted`: `{ callerId, callId, answer }`
- `call-rejected`: `{ callerId, callId }`
- `offer`: `{ receiverId, callId, offer }`
- `answer`: `{ receiverId, callId, answer }`
- `ice-candidate`: `{ receiverId, callId, candidate }`
- `call-ended`: `{ receiverId, callId }`

## Landmark Microservice

Run from `ai-service/`:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Endpoints:

- `GET http://localhost:8000/health`
- `POST http://localhost:8000/api/landmarks`

Request:

```json
{
  "image": "data:image/jpeg;base64,..."
}
```

Response includes normalized MediaPipe hand and face landmark coordinates. It does not classify signs or predict gestures.
