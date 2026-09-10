# Frontend API Contract for Landing Page

When a user clicks "Send Rescue Alert" on the `landing/index.html` page, the frontend must make the following HTTP request.

## Authentication
A JWT token is required. Ensure the user is logged in, and pass the token in the headers.

## Endpoint

`POST /api/v1/rescues`

## Headers

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

## Request Body

```json
{
  "species": "Dog",
  "description": "Injured dog near Linking Road, unable to move.",
  "latitude": 19.0760,
  "longitude": 72.8777,
  "address_text": "Linking Road, Bandra West, Mumbai",
  "bleeding": false,
  "can_walk": false,
  "conscious": true,
  "vehicle_accident": true,
  "breathing_difficulty": false,
  "image_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg"
}
```

## Response Body (Success: 200 OK)

```json
{
  "id": "e2f6a9b4-1c23-4e89-b2f1-c4d5e6f7a8b9",
  "case_number": "PR-E2F6A9",
  "animal_id": null,
  "reporter_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "species": "Dog",
  "description": "Injured dog near Linking Road, unable to move.",
  "latitude": 19.076,
  "longitude": 72.8777,
  "address_text": "Linking Road, Bandra West, Mumbai",
  "triage_score": 100,
  "triage_priority": "CRITICAL",
  "triage_reason": "Vehicle collision reported, Animal unable to walk",
  "status": "TRIAGED",
  "created_at": "2026-09-10T12:00:00Z",
  "updated_at": "2026-09-10T12:00:00Z",
  "closed_at": null
}
```

## Error Responses

**401 Unauthorized**: Token missing or invalid.
**422 Validation Error**: Missing required fields or incorrect data types.
