# TissaTech Backend API Integration Guide (Frontend)

This guide explains how frontend developers should integrate with the backend APIs.

## 1. Base URLs

- Local backend: `http://localhost:8000`
- API prefix: `/api/v1`
- Swagger: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## 2. Authentication Modes

There are two supported auth modes:

1. Admin dashboard mode (JWT Bearer token)
- Use `Authorization: Bearer <access_token>`
- Tokens come from `/api/v1/auth/register` or `/api/v1/auth/login`

2. Embedded widget mode (API key)
- Use `X-API-Key: <raw_widget_api_key>`
- API key is generated from admin endpoint `/api/v1/admin/widget-api-key`

## 3. Common Response and Error Format

Most endpoints return JSON.

Typical error payload:

```json
{
  "detail": "Error message"
}
```

Unhandled server exceptions are returned as:

```json
{
  "detail": "Actual exception message",
  "type": "ExceptionType"
}
```

## 4. Auth APIs (`/api/v1/auth`)

### POST `/register`

Registers workspace + admin user, returns access and refresh tokens.

Request JSON:

```json
{
  "email": "admin@company.com",
  "password": "StrongPassword@123",
  "full_name": "Admin User",
  "workspace_slug": "company-slug",
  "company_name": "Company Name"
}
```

Response `201`:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<refresh>",
  "token_type": "bearer",
  "expires_in": 900
}
```

### POST `/login`

Important: this endpoint expects `application/x-www-form-urlencoded`, not JSON.

Required form fields:
- `username` (email)
- `password`

Response:
Same as `/register`.

### POST `/refresh`

Refresh token endpoint uses query parameter.

Example:
`POST /api/v1/auth/refresh?refresh_token=<token>`

Response:
Same as `/register`.

### POST `/logout`

Logout endpoint also uses query parameter.

Example:
`POST /api/v1/auth/logout?refresh_token=<token>`

Response:

```json
{ "message": "Logged out successfully" }
```

### GET `/me`

Requires `Authorization: Bearer`.

Response:

```json
{
  "id": "uuid",
  "email": "admin@company.com",
  "full_name": "Admin User",
  "role": "admin",
  "workspace_id": "uuid"
}
```

## 5. Admin APIs (`/api/v1/admin`) - Bearer admin required

### GET `/analytics/overview?days=30`

Returns analytics + KB status.

### GET `/conversations?page=1&page_size=50`

Returns paginated conversation summaries.

### POST `/documents`

Upload document for indexing pipeline.

Content type: `multipart/form-data`
- `file`: required
- `title`: optional query param

### GET `/documents`

List uploaded documents for workspace.

### DELETE `/documents/{document_id}`

Delete document by UUID.

### POST `/crawl`

Start website crawl and training.

Request JSON:

```json
{
  "url": "https://tissatech.com",
  "max_pages": 100
}
```

Response:

```json
{
  "task_id": "uuid-or-celery-id",
  "status": "queued",
  "url": "https://tissatech.com",
  "max_pages": 100,
  "message": "Crawl started. Poll /api/v1/admin/crawl-status/{task_id} for progress."
}
```

### GET `/crawl-status/{task_id}`

Frontend should poll every 2-5 seconds.

Response:

```json
{
  "task_id": "id",
  "celery_state": "PENDING",
  "celery_error": null,
  "kb_status": "queued",
  "kb_error": null,
  "kb_trained_url": "https://tissatech.com",
  "bedrock_kb_id": null,
  "bedrock_agent_id": null,
  "bedrock_agent_alias_id": null
}
```

`kb_status` values:
- `queued`
- `crawling`
- `uploading`
- `provisioning`
- `indexing`
- `ready`
- `failed`

### GET `/workspace-settings`

Returns workspace Bedrock and KB settings for admin UI.

### POST `/widget-api-key`

Generates raw API key for widget embed.

Response:

```json
{
  "api_key": "tst_...",
  "prefix": "tst_xxxxx"
}
```

### POST `/widget-config`

Save widget UI configuration.

Request JSON:

```json
{
  "bot_name": "Tissa",
  "greeting_message": "Hi! How can I help you today?",
  "primary_color": "#E65C5C",
  "secondary_color": "#c0392b",
  "placeholder_text": "Type a message...",
  "avatar_url": null,
  "position": "bottom-right",
  "allowed_domains": ["https://example.com"]
}
```

## 6. Widget Public APIs (`/api/v1/widget`) - API key required

Every request must include:
- `X-API-Key: <raw_widget_api_key>`

### GET `/config`

Returns active widget settings (or defaults if not configured).

### POST `/session`

Creates anonymous widget session.

Response:

```json
{
  "session_token": "random-token"
}
```

## 7. Chat APIs (`/api/v1/chat`)

### POST `/message` (SSE streaming)

Auth:
- Bearer token OR
- `X-API-Key`
- Optional latency headers:
  - `X-Bedrock-Region: ap-south-1` (preferred region for request)
  - `X-Country-Code: IN` (2-letter country code for smart region routing)
  - `CF-IPCountry: IN` is also honored automatically (Cloudflare setups)

Recommended frontend strategy:
- If your edge/CDN already provides country, pass `X-Country-Code`.
- Optionally map country to a nearest Bedrock region and pass `X-Bedrock-Region`.
- Backend will try preferred region first, then fall back to configured regions automatically.

Request JSON:

```json
{
  "message": "Explain your services",
  "conversation_id": null,
  "session_id": "optional-session-id",
  "user_profile": {
    "name": "John",
    "email": "john@example.com",
    "phone": "+1...",
    "organization": "Acme Inc",
    "industry": "Technology",
    "role": "CTO"
  }
}
```

Response content type:
- `text/event-stream`

SSE events:
- `event: message` with partial text chunks
- `event: end` with final metadata and `message_id` (`latency_ms`, `tokens_used`, `region`, `model_id`)

Frontend must stream and concatenate chunks.

### GET `/suggestions?role=<role>&limit=5`

Returns last user-question suggestions for same role in same workspace.

Auth:
- Bearer token OR `X-API-Key`

Response:

```json
{
  "role": "cto",
  "suggestions": [
    "What integrations do you support?",
    "How much does implementation take?"
  ]
}
```

### GET `/conversations`

Current behavior: returns an empty array (`[]`).
Use `/conversations/{conversation_id}/messages` for message history.

### GET `/conversations/{conversation_id}/messages`

Returns chat history for one conversation in workspace.

### POST `/messages/{message_id}/feedback`

Request JSON:

```json
{
  "feedback_type": "thumbs_up",
  "comment": "Helpful answer"
}
```

Valid `feedback_type`:
- `thumbs_up`
- `thumbs_down`

## 8. Health and Monitoring APIs

Public endpoints:
- `GET /health`
- `GET /health/ready`
- `GET /health/live`
- `GET /metrics` (Prometheus)

## 9. Debug APIs (Development Only)

These are enabled only in non-production:
- `GET /api/v1/debug/config`
- `GET /api/v1/debug/bedrock-test`
- `GET /api/v1/debug/db-test`
- `POST /api/v1/debug/test-crawl`
- `POST /api/v1/debug/test-s3-upload`
- `GET /api/v1/debug/test-celery-task`
- `GET /api/v1/debug/workspace-settings`

Do not consume debug endpoints in production frontend flows.

## 10. Frontend Integration Notes

1. Store both access and refresh token securely.
2. Use access token in `Authorization` for admin/dashboard APIs.
3. On `401`, call refresh endpoint then retry original request.
4. For widget site integration, use only `X-API-Key` and session token.
5. For crawl progress UI, poll `/admin/crawl-status/{task_id}` and map `kb_status` to step indicators.
6. For chat, implement SSE stream parser and render partial chunks progressively.

## 11. Minimal JS Snippets

### Login (form encoded)

```js
const body = new URLSearchParams({ username: email, password });
const res = await fetch("http://localhost:8000/api/v1/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body
});
const tokens = await res.json();
```

### Poll Crawl Status

```js
const res = await fetch(`http://localhost:8000/api/v1/admin/crawl-status/${taskId}`, {
  headers: { Authorization: `Bearer ${accessToken}` }
});
const status = await res.json();
```

### Widget Config

```js
const res = await fetch("http://localhost:8000/api/v1/widget/config", {
  headers: { "X-API-Key": widgetApiKey }
});
const config = await res.json();
```
