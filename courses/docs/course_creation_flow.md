# Course Creation Flow with Stripe Integration

## Overview
This document explains how course creation works in the Little Learners Tech platform, including the automatic Stripe billing integration that happens when teachers create courses.

## Architecture Components

### 1. **Course Creation Endpoint**
- **File**: `courses/views.py`
- **Function**: `teacher_courses()` (POST method)
- **URL**: `POST /api/courses/teacher/`
- **Purpose**: Handles course creation requests from teachers

### 2. **Stripe Integration Utility**
- **File**: `courses/stripe_integration.py`
- **Purpose**: Handles all Stripe operations for course billing
- **Key Functions**:
  - `create_stripe_product_for_course()`
  - `update_stripe_product_for_course()`
  - `deactivate_stripe_product_for_course()`

### 3. **Django Admin Integration**
- **File**: `courses/admin.py`
- **Class**: `CourseAdmin`
- **Purpose**: Provides admin interface for course management with automatic Stripe synchronization
- **Key Feature**: `save_model()` override detects billing field changes and triggers Stripe updates

### 4. **Billing Models**
- **File**: `billings/models.py`
- **Models**: `BillingProduct`, `BillingPrice`
- **Purpose**: Store Stripe product and price information locally

## Course Creation Flow

### ASCII Flow Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Teacher       │    │   Django API    │    │  Stripe Utils   │    │   Stripe API    │
│   Dashboard     │    │   (courses/)    │    │ (stripe_integration.py) │   (External)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         │ 1. POST /api/courses/ │                       │                       │
         │    teacher/           │                       │                       │
         ├──────────────────────►│                       │                       │
         │                       │                       │                       │
         │ 2. Validate Course    │                       │                       │
         │    Data & Permissions │                       │                       │
         │                       │                       │                       │
         │ 3. Create Course      │                       │                       │
         │    in Database        │                       │                       │
         │                       │                       │                       │
         │ 4. Call Stripe Utils  │                       │                       │
         │    create_stripe_     │                       │                       │
         │    product_for_course │                       │                       │
         │                       ├──────────────────────►│                       │
         │                       │                       │                       │
         │ 5. Check Course       │                       │                       │
         │    Duration           │                       │                       │
         │    ≤ 4 weeks?         │                       │                       │
         │                       │                       │                       │
         │ 6a. Short Course:     │                       │                       │
         │    Create One-time    │                       │                       │
         │    Price Only         │                       │                       │
         │                       │                       │                       │
         │ 6b. Long Course:      │                       │                       │
         │    Create One-time +  │                       │                       │
         │    Monthly Prices     │                       │                       │
         │                       │                       │                       │
         │ 7. Create Stripe      │                       │                       │
         │    Product            │                       │                       │
         │                       │                       ├──────────────────────►│
         │                       │                       │                       │
         │ 8. Create Stripe      │                       │                       │
         │    Prices             │                       │                       │
         │                       │                       ├──────────────────────►│
         │                       │                       │                       │
         │ 9. Save Billing       │                       │                       │
         │    Products & Prices  │                       │                       │
         │    to Database        │                       │                       │
         │                       │                       │                       │
         │ 10. Return Course     │                       │                       │
         │     with Billing      │                       │                       │
         │     Setup Info        │                       │                       │
         │◄──────────────────────┤                       │                       │
```

## Detailed Process

### Step 1: Teacher Initiates Course Creation
- Teacher logs into dashboard
- Fills out course form with:
  - Title, description, content
  - Duration in weeks
  - Price
  - Other course details
- Frontend sends `POST /api/courses/teacher/` request

### Step 2: Backend Validation
- Django validates user permissions (teacher role)
- Validates course data using `CourseCreateUpdateSerializer`
- Ensures all required fields are present

### Step 3: Course Creation
- Django creates `Course` record in database
- Course is saved with teacher as owner
- Course ID is generated for Stripe integration

### Step 4: Stripe Integration
- Backend calls `create_stripe_product_for_course(course)`
- Utility function determines billing strategy based on duration:
  - **≤ 4 weeks**: One-time payment only
  - **> 4 weeks**: One-time payment + monthly subscription

### Step 5: Stripe Product Creation
- Utility creates Stripe Product with:
  - Course title as product name
  - Course description
  - Metadata (course_id, teacher_id, duration_weeks)

### Step 6: Stripe Price Creation
- **One-time Price**: Always created
  - Amount: Course price in cents
  - Currency: USD
  - Type: One-time payment
- **Monthly Price**: Created only for long courses
  - Amount: Course price in cents
  - Currency: USD
  - Type: Recurring monthly

### Step 7: Database Storage
- Utility saves `BillingProduct` record
- Utility saves `BillingPrice` records (1 or 2 depending on duration)
- All records linked to the course

### Step 8: Response
- Backend returns course details with billing setup information
- Includes Stripe product and price IDs
- Indicates billing strategy used

## Utility File Details

### `courses/stripe_integration.py`

This utility file contains three main functions:

#### `create_stripe_product_for_course(course)`
- **Purpose**: Creates Stripe product and prices for a new course
- **Parameters**: `course` - Django Course instance
- **Returns**: Dictionary with success status and Stripe IDs
- **Logic**:
  - Creates Stripe Product
  - Determines billing strategy based on `course.duration_weeks`
  - Creates appropriate prices
  - Saves to local database

#### `update_stripe_product_for_course(course)`
- **Purpose**: Updates existing Stripe product and prices when course is modified
- **Parameters**: `course` - Django Course instance
- **Returns**: Dictionary with success status and updated price IDs
- **Called From**: 
  - API endpoint: `CourseCreationView.put()` (when price/duration changes detected)
  - Django Admin: `CourseAdmin.save_model()` (when price/duration changes detected)
- **Logic**:
  - Finds existing `BillingProduct`
  - Updates Stripe product name, description, and metadata (including duration_weeks)
  - Deactivates all existing active prices in Stripe and database
  - Recalculates prices based on current course price and duration
  - Creates new prices based on billing strategy:
    - **≤ 4 weeks**: Creates only one-time price
    - **> 4 weeks**: Creates both one-time and monthly subscription prices
  - Updates local database records with new price information

#### `deactivate_stripe_product_for_course(course)`
- **Purpose**: Deactivates Stripe product when course is deleted
- **Parameters**: `course` - Django Course instance
- **Returns**: Dictionary with success status
- **Logic**:
  - Finds existing `BillingProduct`
  - Deactivates Stripe product
  - Deactivates all associated prices
  - Updates local database records

## Error Handling

### Stripe Integration Failures
- If Stripe operations fail, course creation still succeeds
- Errors are logged but don't prevent course creation
- Optional: Can be configured to delete course if Stripe is critical

### Database Errors
- If billing model creation fails, Stripe operations are rolled back
- Course creation fails if database operations fail

## API Response Example

```json
{
  "id": "course-uuid",
  "title": "Python for Kids",
  "description": "Learn Python programming basics",
  "price": 99.99,
  "duration_weeks": 8,
  "teacher": "teacher-uuid",
  "billing_setup": {
    "success": true,
    "product_id": "prod_abc123",
    "one_time_price_id": "price_xyz789",
    "monthly_price_id": "price_def456",
    "billing_strategy": "monthly_and_one_time"
  }
}
```

## Course Update Flow

Course updates can be performed through three methods, all of which trigger Stripe synchronization:

### API Updates (`PUT /api/courses/teacher/{course_id}/`)

**Main course update endpoint**

1. Course data is validated and updated
2. System checks if any billing-related fields changed:
   - `price` or `is_free`: Affects pricing amounts
   - `duration_weeks`: Affects billing strategy (one-time vs monthly subscription)
3. If any billing-related fields changed, `update_stripe_product_for_course()` is called:
   - Stripe product name and description are updated
   - All existing prices are deactivated in Stripe and database
   - New prices are created based on current course settings:
     - **≤ 4 weeks**: Only one-time price is created
     - **> 4 weeks**: Both one-time and monthly subscription prices are created
4. Local billing records are updated with new price information

### Course Introduction Updates (`PUT /api/courses/teacher/{course_id}/introduction/`)

**Course introduction/overview update endpoint**

1. Course introduction data is validated and updated
2. System stores original values (`price`, `duration_weeks`, `is_free`) before save
3. System checks if any billing-related fields changed:
   - `price` or `is_free`: Affects pricing amounts
   - `duration_weeks`: Affects billing strategy (one-time vs monthly subscription)
4. If any billing-related fields changed and `BillingProduct` exists:
   - `update_stripe_product_for_course()` is automatically called
   - Stripe prices are synchronized (same logic as main API updates)
   - Errors are logged but don't block the update

**Note**: This endpoint is primarily for updating introduction fields (overview, learning objectives, etc.), but if `duration_weeks` or `price` are included in the update, Stripe sync is automatically triggered.

### Django Admin Updates

When a course is updated through Django Admin interface:

1. `CourseAdmin.save_model()` intercepts the save operation
2. System stores original values (`price`, `duration_weeks`, `is_free`) before save
3. Course model is saved to database
4. System compares original vs new values to detect changes
5. If billing-related fields changed and `BillingProduct` exists:
   - `update_stripe_product_for_course()` is automatically called
   - Stripe prices are synchronized (same logic as API updates)
   - Admin interface shows success/warning message
6. If course doesn't have Stripe product yet (new courses), update is skipped (product created on publish)

### Important Notes:
- **All Update Methods**: API, Course Introduction, and Django Admin updates use the same Stripe synchronization logic
- **Duration Changes**: When `duration_weeks` changes from ≤4 weeks to >4 weeks, the system automatically creates a monthly subscription price option
- **Duration Changes**: When `duration_weeks` changes from >4 weeks to ≤4 weeks, the monthly subscription price is removed (only one-time price remains)
- **Price Changes**: When `price` changes, both one-time and monthly prices (if applicable) are recalculated and updated
- **Admin Feedback**: Django Admin shows success messages when Stripe sync succeeds, and warnings if it fails

## Course Deletion Flow

When a course is deleted via `DELETE /api/courses/teacher/{course_id}/`:

1. `deactivate_stripe_product_for_course()` is called
2. Stripe product is deactivated (not deleted)
3. All associated prices are deactivated
4. Local billing records are deactivated
5. Course is deleted from database

## Syllabus structure lock after enrollment

Once a course has any `active`, `completed`, or `paused` enrollment, lesson **structure** is locked via the teacher API:

| Action | Behavior when enrolled |
|--------|------------------------|
| Create lesson | Allowed; `order` is forced to `max(order)+1` (append only) |
| Reorder lessons | Blocked — `400` with `code: lesson_structure_locked` |
| Delete lesson | Blocked — same code |
| Update lesson `order` via PUT | Blocked — same code |

Course list/detail serializers expose `has_enrollments` so the teacher UI can disable drag/delete.

**Rationale:** Mid-sequence insert/reorder can auto-complete lessons behind a student’s pointer (`resync_after_lesson_structure_change`). Freezing order/delete after enrollment keeps progress stable; teachers who need a different syllabus should **clone** the course.

**Bypass:** Django admin can still delete or change lesson `order`. Use only for intentional cleanup.

## Course Cloning Flow

Teachers can create a brand-new course by cloning an existing one of their own.

### Endpoint
- **File**: `courses/views.py`
- **Class**: `CourseCloneView` (POST)
- **URL**: `POST /api/courses/create/{course_id}/clone/`
- **Auth**: teacher role required; the requester must own the source course.

### Request body
```json
{
  "include_content": false,
  "include_assessments": false,
  "title": "Copy of Introduction To Electronics"
}
```
- `include_content` - copy modules, lessons (+ materials) and the course introduction.
- `include_assessments` - copy quizzes, assignments, projects, tests and exams (requires `include_content`).
- `title` - optional; defaults to `"<source title> (Copy)"`.

### Phasing

The endpoint has two execution paths, chosen by the request flags:

- **Phase 1 - base-only clone (implemented, synchronous)**: when both flags are
  `false`, the clone is performed inline. This is cheap because the only media to copy
  is the single course image/thumbnail.
- **Phase 2 - content/assessment clone (not implemented yet)**: when either flag is
  `true`, the endpoint returns **HTTP 501**. Deep-copying lessons/assessments also
  requires duplicating potentially hundreds of GCS objects, which belongs in a
  background worker. The frontend keeps those options disabled until Phase 2 ships.

### Phase 1 process (base-only)

1. Validate teacher role and load the source course with ownership
   (`Course.objects.get(id=course_id, teacher=request.user)` → 404 otherwise).
2. In a transaction, copy the source `Course` row into a new instance with a fresh
   UUID and these overrides:
   - `teacher = request.user`, `status = 'draft'`, `featured = False`, `popular = False`
   - `title` = provided/derived title
   - `landing_page_url = ''` so it regenerates from the new title + id
   - `image` and `thumbnail` are each **duplicated to a NEW GCS object** via
     `_copy_course_image_to_new_object()` (see below).
3. Copy the `prerequisites` M2M relationships.
4. Create the clone's **own** Stripe product/prices via
   `create_stripe_product_for_course(clone)` (same as the create flow). If billing
   setup fails, the clone is deleted and a 500 is returned.
5. Return the new course via `CourseDetailSerializer` (same response shape as create,
   including `billing_setup` and a `message`), with HTTP 201.

What Phase 1 does **not** copy: modules, lessons, materials, the course introduction,
assessments, enrollments, submissions, attempts, grades, or classes.

### Why the course image is physically copied

GCS objects are hard-deleted when a material/image is deleted or replaced (see
`courses/signals.py`, `tutorx/services/storage.py`). If a clone simply reused the
source image URL, deleting/replacing the source image would break the clone. So the
clone gets an independent copy of the image.

#### `_copy_course_image_to_new_object(image_url)` (in `courses/views.py`)
- Parses a `https://storage.googleapis.com/<bucket>/<path>` URL down to the storage path.
- Copies the object to a new `clone-<uuid>-<filename>` path via `default_storage`.
- Returns the new GCS URL. If GCS is unavailable or the object is missing, it falls
  back to the original URL so a clone is never blocked by an image issue.

### Frontend integration

- `apiService.cloneCourse(courseId, { include_content, include_assessments, title })`
  in `src/services/api.ts`.
- `CloneCourseDialog` (`src/components/teacher/sections/CloneCourseDialog.tsx`) provides
  the title field and three cumulative options. The content/assessment options are
  disabled ("Coming soon") while Phase 2 is unbuilt (`CONTENT_CLONING_ENABLED = false`).
- Triggered from the course card's three-dot menu ("Clone Course") in
  `src/components/ui/course-card.tsx`, wired in the teacher `CoursesSection.tsx` which
  revalidates the `teacher-courses` list and toasts on success.

### Phase 2 (future) outline

Add a `clone_status` field to `Course` (`cloning | ready | failed`) + progress counters;
when a content flag is set, create the course row in `cloning` state, enqueue a worker
(Celery + Redis/Memorystore) that deep-copies modules/lessons/materials/assessments and
duplicates every referenced GCS object (rewriting URLs embedded in lesson content JSON),
and expose `GET /api/courses/create/{course_id}/clone-status/` for the frontend to poll.

## Configuration

### Environment Variables Required
- `STRIPE_SECRET_KEY`: Stripe secret key for API access
- `STRIPE_PUBLISHABLE_KEY`: Stripe publishable key (not used in backend)
- `STRIPE_WEBHOOK_SECRET`: Webhook secret for verification

### Database Models Required
- `Course` (courses app)
- `BillingProduct` (billings app)
- `BillingPrice` (billings app)

## Testing

### Local Development
1. Set up Stripe test keys
2. Create test course via API
3. Check Stripe Dashboard for created products
4. Verify database records are created

### Production
1. Use live Stripe keys
2. Monitor Stripe Dashboard for product creation
3. Check error logs for any failures
4. Verify webhook handling works correctly

## Troubleshooting

### Common Issues
1. **Stripe API Key Missing**: Check environment variables
2. **Database Connection**: Ensure billing models are migrated
3. **Stripe Rate Limits**: Implement retry logic if needed
4. **Webhook Failures**: Check webhook endpoint configuration

### Debugging
- Check Django logs for Stripe integration errors
- Verify Stripe Dashboard for created products
- Check database for billing records
- Test with Stripe CLI for local development
