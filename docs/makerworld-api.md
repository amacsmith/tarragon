# MakerWorld Unofficial API Reference

## Authentication

MakerWorld uses a Bearer token authentication scheme. The token is passed via the `X-BBL` header.

### Authentication Header Format

```
X-BBL: <token>
Authorization: Bearer <token>
```

The `<token>` is a session token obtained after logging into MakerWorld.

> **Note**: All API calls require authentication. Use the `MAKERWORLD_TOKEN` environment variable to store your token.

## Endpoints Discovered

### Likes / favorites

**Endpoint:** `GET /v1/like/tudou`

**Purpose:** Like a model (like "tudou" potato)

**Curl Example:**
```bash
curl -X POST "https://api.makerworld.com/v1/like/tudou" \
  -H "X-BBL: $MAKERWORLD_TOKEN" \
  -H "Authorization: Bearer $MAKERWORLD_TOKEN"
```

### Collections

**Endpoint:** `POST /v1/favorites/collections`

**Purpose:** Create a new collection

**Request Body:**
```json
{
  "name": "My Collection"
}
```

**Curl Example:**
```bash
curl -X POST "https://api.makerworld.com/v1/favorites/collections" \
  -H "X-BBL: $MAKERWORLD_TOKEN" \
  -H "Authorization: Bearer $MAKERWORLD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Collection"}'
```

### Model Metadata

**Endpoint:** `GET /v1/things/:id`

**Purpose:** Fetch detailed information about a specific model

**Curl Example:**
```bash
curl "https://api.makerworld.com/v1/things/12345" \
  -H "X-BBL: $MAKERWORLD_TOKEN" \
  -H "Authorization: Bearer $MAKERWORLD_TOKEN"
```

**Response Fields (partial):**
- `id`: Model ID
- `name`: Model name
- `description`: Model description
- `author`: Author information
- `categories`: Model categories
- `stats`: View count, like count, comment count
- `files`: Available file formats and download links

### Download URL Resolution

**Pattern:** Model files are accessed via `/files/:id/:filename`

**Curl Example:**
```bash
curl "https://api.makerworld.com/files/12345/model.stl" \
  -H "X-BBL: $MAKERWORLD_TOKEN" \
  -H "Authorization: Bearer $MAKERWORLD_TOKEN" \
  -o model.stl
```

## Unverified / Needs Live Token

The following endpoints were referenced in code exploration but require a live token to verify:

### User Profile Endpoints

**Potentially discovered:**
- `GET /v1/users/:username` - User profile information
- `GET /v1/users/:username/things` - Models by user

**Status:** Unverified - needs live token to confirm

### Search API

**Potential endpoint:**
- `GET /v1/search` or `GET /v1/things/search`

**Status:** Unverified - search parameters and response format unknown

### Comments/Community Features

**Potential endpoints:**
- `POST /v1/things/:id/comments` - Add comment
- `GET /v1/things/:id/comments` - List comments

**Status:** Unverified - requires live token to verify

### Upload / Publish

**Potential endpoint:**
- `POST /v1/things` - Create new model upload

**Status:** Unverified - requires live token and multipart form data format

## Notes

- All discovered endpoints are based on reverse engineering and code references only
- Token format appears to be a JWT or similar cryptic string
- API appears to be a subset of BambuLab's API (hence `X-BBL` header)
- Some endpoints may be internal-only or require additional headers for certain responses

## References

- JMcrafter26/userscripts - makerworld-enhancements
- kloshi-io/makerworld-api-reverse
- Bambulab download URL patterns
