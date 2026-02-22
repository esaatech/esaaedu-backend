# Student Course Page API Documentation

API for the student course page: course overview (intro + reviews), pause/drop enrollment, and submit course review. All endpoints require the user to be **authenticated** and **enrolled** in the course (where applicable).

**Base path**: `/api/student/` (exact prefix depends on project URL config.)

---

## 1. Course overview (GET)

Returns read-only course introduction, current enrollment info, and verified reviews for "What Students Say".

**Endpoint:** `GET /api/student/courses/<course_id>/overview/`

**Authentication:** Required (Bearer token)

**Authorization:** User must have `role == 'student'`, a `student_profile`, and be enrolled in the course (`status` in `active`, `completed`, or `paused`). Otherwise 403.

**Response:** JSON

```typescript
interface StudentCourseOverviewResponse {
  introduction: {
    title: string;
    overview: string;
    learning_objectives: string[];
    prerequisites_text: string;
    duration_weeks: number | null;
    duration: string;
    sessions_per_week: number | null;
    total_projects: number | null;
    value_propositions: string[];
  };
  enrollment: {
    id: string;   // enrollment UUID
    status: string;  // 'active' | 'completed' | 'paused'
  } | null;
  reviews: Array<{
    id: number;
    student_name: string;
    student_age: number | null;
    display_name: string;
    rating: number;
    star_rating: boolean[];
    review_text: string;
    is_verified: boolean;
    is_featured: boolean;
    created_at: string;
  }>;
}
```

Only reviews with `is_verified === true` are included. New student-submitted reviews appear after admin verification.

**Implementation:** `student/views.py` → `StudentCourseOverviewView`  
**Serializer:** `student/serializers.py` → `StudentCourseOverviewSerializer`

---

## 2. Enrollment status (Pause / Drop) (PATCH)

Allows the student to set their enrollment status to **paused** (no more notifications) or **dropped** (course removed from list; re-registration required to rejoin).

**Endpoint:** `PATCH /api/student/enrolled-courses/<enrollment_id>/status/`

**Authentication:** Required (Bearer token)

**Authorization:** User must be a student and the enrollment must belong to their `student_profile`. Otherwise 403/404.

**Request body:**

```json
{ "status": "paused" }
```
or
```json
{ "status": "dropped" }
```

Only `"paused"` and `"dropped"` are accepted. Any other value returns 400.

**Response (200):**

```json
{
  "message": "Enrollment status updated to paused",
  "status": "paused"
}
```

**Implementation:** `student/views.py` → `StudentEnrollmentStatusView`

---

## 3. Submit course review (POST)

Creates a course review. The review is stored with `is_verified: false`; admin must verify it in Django admin before it appears in the course overview.

**Endpoint:** `POST /api/student/courses/<course_id>/reviews/`

**Authentication:** Required (Bearer token)

**Authorization:** User must have `role == 'student'`, a `student_profile`, and be enrolled in the course (`active`, `completed`, or `paused`). Otherwise 403.

**Request body:**

| Field         | Type   | Required | Description                          |
|---------------|--------|----------|--------------------------------------|
| `rating`      | number | Yes      | 1–5                                  |
| `review_text` | string | Yes      | Non-empty review content             |
| `student_age` | number | No       | 5–18 (optional)                      |
| `parent_name` | string | No       | Optional display name for parent     |

**Example:**

```json
{
  "rating": 5,
  "review_text": "Great course, my child loved it!"
}
```

**Response (201):** The created review as returned by `CourseReviewSerializer` (includes `id`, `student_name`, `rating`, `review_text`, `is_verified`, `created_at`, etc.). `student_name` is derived from the authenticated user (`get_full_name()` or email).

**Errors:** 400 if `rating` or `review_text` is missing or invalid.

**Implementation:** `student/views.py` → `StudentCourseReviewCreateView`  
**Model:** `courses.models.CourseReview` (created with `is_verified=False`)

---

## Summary

| Feature           | Method | URL pattern                                      | View                            |
|------------------|--------|--------------------------------------------------|---------------------------------|
| Course overview  | GET    | `/api/student/courses/<course_id>/overview/`      | `StudentCourseOverviewView`     |
| Pause / Drop     | PATCH  | `/api/student/enrolled-courses/<id>/status/`     | `StudentEnrollmentStatusView`   |
| Submit review    | POST   | `/api/student/courses/<course_id>/reviews/`      | `StudentCourseReviewCreateView` |

**URL config:** `student/urls.py`

---

## Related documentation (backend)

- [ADMIN_ENROLLMENT.md](./ADMIN_ENROLLMENT.md) – Admin enrollment form and flows.
