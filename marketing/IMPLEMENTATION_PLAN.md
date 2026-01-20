# Program Landing Page API Implementation Plan

## Overview
Create a public API endpoint to fetch Program details by slug, including all associated courses with full enrollment data (billing, classes, etc.).

## Endpoint
- **URL**: `/api/marketing/programs/<slug>/`
- **Method**: `GET`
- **Authentication**: Public (no authentication required)
- **Response**: Program details with courses array

---

## 1. Serializer: `ProgramSerializer`

### Location
`marketing/serializers.py`

### Fields to Include

**Important**: 
- The `category` field is **NOT** included in the serializer response
- The `category` field is only used internally/admin to determine which courses to include
- The API always returns a `courses` array (never a `category` string)
- In the view, if program has `category` set, we call `program.get_courses()` to convert it to Course objects before serializing

#### Program Fields
- `id` - UUID
- `name` - Program name
- `slug` - URL slug
- `description` - Program description
- `hero_media_url` - GCS URL for hero image/video
- `hero_media_type` - 'image' or 'video'
- `hero_title` - Main headline
- `hero_subtitle` - Subtitle
- `hero_features` - JSON array of features
- `hero_value_propositions` - JSON array of value propositions
- `program_overview_features` - JSON array of overview features
- `trust_strip_features` - JSON array of trust indicators
- `cta_text` - Call-to-action button text
- `is_active` - Active status
- `discount_enabled` - Whether discount is enabled
- `promotion_message` - Promotion message
- `promo_code` - Stripe promo code
- `seo_url` - Full marketing URL (e.g., `https://www.sbtyacedemy.com/math`)

#### Courses Array
- `courses` - Array of course objects (see Course Data Structure below)

### Course Data Structure (for each course in `courses` array)

Each course should include **ALL** data needed for enrollment, matching the structure returned by `/api/courses/public/{course_id}/introduction/`:

#### Basic Course Info (from CourseDetailSerializer)
- `id` - Course UUID
- `title` - Course title
- `description` - Short description
- `long_description` - Detailed description
- `category` - Course category
- `age_range` - Age range
- `level` - Course level
- `price` - Course price
- `features` - Course features array
- `image` - Course image URL
- `teacher_name` - Teacher full name
- `teacher_id` - Teacher UUID
- `schedule` - Schedule info
- `certificate` - Certificate availability
- `duration_weeks` - Duration in weeks
- `sessions_per_week` - Sessions per week
- `total_projects` - Number of projects
- `overview` - Course overview
- `learning_objectives` - Learning objectives
- `prerequisites_text` - Prerequisites
- `value_propositions` - Value propositions
- `average_rating` - Average review rating
- `review_count` - Number of reviews
- `reviews` - Reviews array (optional, can be limited)
- `landing_page_url` - Course landing page URL
- `get_landing_page_url` - Full course landing page URL

#### Billing Data (from `get_course_billing_data_helper`)
- `billing` - Object containing:
  - `stripe_product_id` - Stripe product ID
  - `pricing_options` - Object with:
    - `one_time` - Object with:
      - `amount` - One-time price
      - `currency` - "usd"
      - `stripe_price_id` - Stripe price ID
      - `savings` - Savings amount (if applicable)
    - `monthly` - Object (if available) with:
      - `amount` - Monthly price
      - `currency` - "usd"
      - `stripe_price_id` - Stripe price ID
      - `total_months` - Total months
      - `total_amount` - Total amount
  - `trial` - Object with:
    - `duration_days` - Trial duration in days
    - `available` - Whether trial is available
    - `requires_payment_method` - Whether payment method required

#### Available Classes (from `course_available_classes` endpoint)
- `available_classes` - Array of class objects, each containing:
  - `id` - Class UUID
  - `name` - Class name
  - `description` - Class description
  - `max_capacity` - Maximum capacity
  - `student_count` - Current student count
  - `course_id` - Course UUID
  - `course_title` - Course title
  - `sessions` - Array of session objects:
    - `session_number` - Session number
    - `day_of_week` - Day of week number
    - `day_name` - Day name (e.g., "Monday")
    - `start_time` - Start time (formatted)
    - `end_time` - End time (formatted)
    - `formatted_schedule` - Formatted schedule string
  - `formatted_schedule` - Overall formatted schedule
  - `session_count` - Number of sessions
  - `teacher_name` - Teacher name
  - `available_spots` - Available spots

---

## 2. View: `ProgramBySlugView`

### Location
`marketing/views.py`

### Class-Based View (APIView)
- **Permission**: `AllowAny` (public endpoint)
- **Method**: `GET`

### Logic Flow

1. **Fetch Program by Slug**
   - Get Program by `slug` parameter
   - Filter: `is_active=True`
   - Return 404 if not found

2. **Get Courses (Always Return Courses, Never Category)**
   - **If program has `category` set**:
     - Call `program.get_courses()` which internally converts category to Course objects
     - This fetches all published courses with that category (alphabetically ordered)
     - Result: List of Course objects
   - **If program has `courses` ManyToMany set**:
     - Use `program.get_courses()` which returns those specific courses (alphabetically ordered)
     - Result: List of Course objects
   - **Important**: The API response always contains a `courses` array. The `category` field is never returned - it's only used internally to determine which courses to fetch.

3. **Enrich Each Course with Full Data**
   For each course:
   - Use `CourseDetailSerializer` to get full course details
   - Add `billing` data using `get_course_billing_data_helper(course)` (from courses.views)
   - Add `available_classes` using the same logic as `course_available_classes` view
   - Combine into a single course object

4. **Serialize Program**
   - Use `ProgramSerializer` to serialize program
   - **Exclude `category` field** from response (it's only for admin/internal use)
   - Include enriched courses array

5. **Return Response**
   - Return JSON response with program data and courses array
   - Response always contains `courses` array, never `category` field

### Error Handling
- 404 if program not found or inactive
- 500 for server errors (with error message)

---

## 3. URL Configuration

### Location
`marketing/urls.py` (create if doesn't exist)

### Route
```python
path('api/marketing/programs/<slug:slug>/', views.ProgramBySlugView.as_view(), name='program_by_slug')
```

### Include in Main URLs
Add to main `backend/urls.py`:
```python
path('', include('marketing.urls')),
```

---

## 4. Response Structure

### Success Response (200)
```json
{
  "id": "uuid",
  "name": "Math Program",
  "slug": "math",
  "description": "Comprehensive math courses...",
  "hero_media_url": "https://storage.googleapis.com/.../hero.jpg",
  "hero_media_type": "image",
  "hero_title": "LIVE ONLINE MATH PROGRAMS",
  "hero_subtitle": "Build confidence. Improve results.",
  "hero_features": ["Canadian Curriculum", "Small Groups", "Real Results"],
  "hero_value_propositions": ["Build confidence. Improve results.", "Track progress..."],
  "program_overview_features": ["Live Classes", "Small Groups", "Tests & Exams"],
  "trust_strip_features": ["Live Classes", "Small Groups", "Tests & Exams"],
  "cta_text": "Start Learning Today",
  "is_active": true,
  "discount_enabled": true,
  "promotion_message": "Special promotion: 20% off!",
  "promo_code": "MATH20",
  "seo_url": "https://www.sbtyacedemy.com/math",
  "courses": [
    {
      "id": "course-uuid",
      "title": "Grade 5 Math",
      "description": "...",
      "long_description": "...",
      // ... all CourseDetailSerializer fields ...
      "billing": {
        "stripe_product_id": "...",
        "pricing_options": {
          "one_time": {
            "amount": 800.00,
            "currency": "usd",
            "stripe_price_id": "...",
            "savings": 200.00
          },
          "monthly": {
            "amount": 200.00,
            "currency": "usd",
            "stripe_price_id": "...",
            "total_months": 4,
            "total_amount": 800.00
          }
        },
        "trial": {
          "duration_days": 7,
          "available": true,
          "requires_payment_method": true
        }
      },
      "available_classes": [
        {
          "id": "class-uuid",
          "name": "Monday/Wednesday 4pm",
          "description": "...",
          "max_capacity": 10,
          "student_count": 5,
          "course_id": "course-uuid",
          "course_title": "Grade 5 Math",
          "sessions": [
            {
              "session_number": 1,
              "day_of_week": 1,
              "day_name": "Monday",
              "start_time": "04:00 PM",
              "end_time": "05:00 PM",
              "formatted_schedule": "Monday 4:00 PM - 5:00 PM"
            }
          ],
          "formatted_schedule": "Monday, Wednesday 4:00 PM - 5:00 PM",
          "session_count": 2,
          "teacher_name": "John Doe",
          "available_spots": 5
        }
      ]
    }
    // ... more courses ...
  ]
}
```

### Error Response (404)
```json
{
  "error": "Program not found",
  "details": "No active program found with slug 'math'"
}
```

---

## 5. Implementation Details

### Dependencies
- Import `CourseDetailSerializer` from `courses.serializers`
- Import `get_course_billing_data_helper` from `courses.views`
- Import `Class`, `ClassSession` from `courses.models`
- Import `Course` from `courses.models`
- Reuse existing helper functions where possible

### Helper Function Usage
- Use `program.get_courses()` method which already handles both cases:
  - If `category` is set: Returns all published courses with that category
  - If `courses` ManyToMany is set: Returns those specific courses
  - Always returns a QuerySet of Course objects (never returns category string)
- This method is already defined in the Program model, so we can use it directly
- The view will call `program.get_courses()` to get the Course objects, then enrich each with billing and classes data

### Performance Considerations
- Use `select_related` and `prefetch_related` for efficient queries
- Prefetch courses with related data (teacher, reviews, billing_product)
- Consider pagination if program has many courses (though unlikely)

### Code Reuse
- Reuse `get_course_billing_data_helper` for billing data
- Reuse `course_available_classes` logic for classes data
- Reuse `CourseDetailSerializer` for course details

---

## 6. Testing Checklist

- [ ] Test with category-based program
- [ ] Test with course-specific program
- [ ] Test with inactive program (should return 404)
- [ ] Test with non-existent slug (should return 404)
- [ ] Verify all course data is included
- [ ] Verify billing data is included for each course
- [ ] Verify available_classes is included for each course
- [ ] Test with program that has no courses
- [ ] Test with program that has courses without billing setup
- [ ] Test with program that has courses without classes

---

## 7. Next Steps After Implementation

1. **Frontend API Service**: Add method to fetch program by slug
2. **Frontend Component**: Create `ProgramLandingPage` component
3. **Frontend Routing**: Add route `/math`, `/coding`, etc. to map to program landing page
4. **Course Click Handler**: When user clicks a course, redirect to `/courses/{course_id}?landing=true` with all enrollment data ready

---

## Important Notes

### Category vs Courses
- **`category` field**: Only used internally/admin to determine which courses to include
- **API Response**: Always returns `courses` array, never `category` field
- **View Logic**: If program has `category` set, convert it to Course objects before serializing
- **Result**: Frontend always receives a `courses` array, regardless of how the program was configured

## Questions for Approval

1. Should we include all course reviews or limit them (e.g., latest 5)?
2. Should we paginate courses if a program has many courses?
3. Should we filter out courses that don't have billing setup?
4. Should we include discount/promotion info at the course level or only at program level?
5. Should courses be ordered alphabetically (as per `get_courses()`) or allow custom ordering?

