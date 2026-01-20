# Marketing App - Program Landing Pages

## Overview

The `marketing` app manages program landing pages for SEO-friendly category/program URLs (e.g., `/math`, `/coding`). Programs can include specific courses or all courses from a category, with hero media, promotions, and discount codes.

## Model: Program

### Purpose
The `Program` model represents a marketing program that groups courses together for landing page display. Programs can be category-based (all courses in a category) or course-specific (selected courses).

### Fields

#### Basic Information
- **`id`**: UUIDField (primary key, auto-generated)
- **`name`**: CharField - Program name (e.g., "Math Program", "Coding Program")
- **`slug`**: SlugField - SEO-friendly URL slug (auto-generated from name, unique)
- **`description`**: TextField - Program description displayed on landing page

#### Hero Section
- **`hero_media`**: FileField - Hero image or video file (uploaded to GCS automatically)
  - Supports images: jpg, jpeg, png, gif, webp
  - Supports videos: mp4, webm, mov
  - Upload path: `marketing/programs/hero_media/`
  - Drag-and-drop or click to upload in admin
- **`hero_media_url`**: URLField (read-only, auto-generated) - GCS URL for hero media (auto-generated from `hero_media` file)
- **`hero_media_type`**: CharField - Type of media: 'image' or 'video' (auto-detected from file extension, default: 'image')
- **`hero_title`**: CharField - Main headline displayed over hero media (e.g., "LIVE ONLINE MATH PROGRAMS")
- **`hero_subtitle`**: CharField - Optional subtitle or tagline displayed below hero title
- **`hero_features`**: JSONField - List of features displayed in hero section (e.g., ["Canadian Curriculum", "Small Groups", "Real Results"])
- **`hero_value_propositions`**: JSONField - List of value propositions/marketing slogans (e.g., ["Build confidence. Improve results.", "Track progress. Support your child's success."])

#### Program Overview Section
- **`program_overview_features`**: JSONField - List of program features with checkmarks (e.g., ["Live Classes", "Small Groups", "Tests & Exams", "Parent Reports", "Canadian Curriculum"])

#### Trust Strip Section
- **`trust_strip_features`**: JSONField - List of trust indicators (e.g., ["Live Classes", "Small Groups", "Tests & Exams", "Parent Reports", "Canadian Curriculum"])

#### Call to Action
- **`cta_text`**: CharField - Call-to-action button text (default: "Start Learning Today")

#### Status
- **`is_active`**: BooleanField - Whether program is active and visible (default: True)

#### Discount & Promotion
- **`discount_enabled`**: BooleanField - If True, users can enter discount code during enrollment (works with Stripe) (default: False)
- **`promotion_message`**: TextField - Promotion message to display on landing page (optional)
- **`promo_code`**: CharField - Stripe promotion code (optional)

#### Course Selection (Mutually Exclusive)
- **`category`**: CharField - If set, loads all published courses with this category (optional)
- **`courses`**: ManyToManyField to Course - Specific courses to include (optional)

**Important**: Either `category` OR `courses` must be set, but not both. This is enforced by the model's `clean()` method.

#### Timestamps
- **`created_at`**: DateTimeField - Auto-set on creation
- **`updated_at`**: DateTimeField - Auto-updated on save

### Model Methods

#### `clean()`
Validates that either `category` OR `courses` is set (not both, not neither). Raises `ValidationError` if validation fails.

#### `save(*args, **kwargs)`
- Auto-generates slug from name if not provided
- Ensures slug uniqueness (appends counter if duplicate)
- Auto-generates `hero_media_url` from `hero_media` file if it exists
- Note: Validation happens in form's `clean()` method, not in model's `save()`

#### `get_courses()`
Returns courses for this program:
- If `category` is set: Returns all published courses with that category, ordered alphabetically by title
- If `courses` ManyToMany is set: Returns those specific courses, ordered alphabetically by title
- Returns empty queryset if neither is set

#### `get_seo_url(request=None)`
Returns full SEO URL for this program:
- Example: `https://www.sbtyacedemy.com/math`
- Uses `request.build_absolute_uri()` if request is provided
- Falls back to `settings.FRONTEND_URL` if request is None

#### `course_count` (property)
Returns the number of courses in this program:
- If `category` is set: Counts all published courses in that category
- If `courses` ManyToMany is set: Counts all selected courses (regardless of status)
- Returns 0 if neither is set

### Model Validation

The model enforces the following rules:
1. **Mutually Exclusive Selection**: Either `category` OR `courses` must be set, but not both
2. **Slug Uniqueness**: Slug is automatically made unique if duplicates exist
3. **Auto-slug Generation**: Slug is auto-generated from name if not provided
4. **File Type Validation**: `hero_media` file must be a valid image (jpg, png, gif, webp) or video (mp4, webm, mov)
5. **Media Type Auto-Detection**: `hero_media_type` is automatically set based on file extension

### Database Indexes

The model includes indexes on:
- `slug` (for fast lookups by slug)
- `is_active` (for filtering active programs)
- `category` (for category-based queries)

## Admin Interface

### ProgramAdmin Features

#### List Display
- Name, slug, category, course count, active status, discount enabled, created date, SEO URL

#### Filters
- Active status
- Discount enabled
- Hero media type
- Category
- Created date

#### Search
- Name, slug, category, description

#### Field Organization
Fields are organized into logical sections:
1. **Basic Information**: Name, slug, description, marketing URL
2. **Hero Section**: 
   - Hero media file upload (drag-and-drop or click to browse)
   - Hero media URL (read-only, auto-generated)
   - Hero media type (auto-detected)
   - Hero title, subtitle, features, value propositions
3. **Program Overview**: Features with checkmarks
4. **Trust Strip**: Trust indicators
5. **Call to Action**: CTA text
6. **Course Selection**: Category or courses (with warning about mutual exclusivity)
7. **Discount & Promotion**: Discount toggle, promotion message, promo code
8. **Status**: Active toggle
9. **Metadata**: ID, timestamps, SEO URL, course count

#### Custom Admin Features
- **Drag-and-Drop File Upload**: Upload hero images/videos directly in admin
- **Automatic GCS Upload**: Files are automatically uploaded to GCS on save
- **Automatic File Cleanup**: Old files are deleted from GCS when:
  - File is replaced with a new one
  - Clear checkbox is checked
  - Program is deleted
- **File Type Validation**: Only allows valid image/video file types
- **Auto-Detection**: Media type is automatically detected from file extension
- **SEO URL Display**: Shows full URL with copy button
- **Course Count Link**: Links to filtered course list in admin
- **JSON List Widgets**: User-friendly interface for editing feature lists
- **Mutual Exclusivity Enforcement**: JavaScript prevents selecting both category and courses
- **Validation**: Form validation ensures either category OR courses is set

## Usage Example

### Creating a Category-Based Program

```python
from marketing.models import Program
from django.core.files.uploadedfile import SimpleUploadedFile

# Create a program that includes all courses in "Mathematics" category
# Note: In admin, you can drag-and-drop or click to upload the file
# For programmatic creation, you would upload the file first, then use the file path
program = Program.objects.create(
    name="Math Program",
    description="Comprehensive math courses for all ages",
    category="Mathematics",
    hero_media_type="image",  # Auto-detected from file extension
    cta_text="Start Learning Math Today",
    is_active=True,
    discount_enabled=True,
    promotion_message="Special promotion: 20% off all math courses!",
    promo_code="MATH20"
)
# hero_media_url is auto-generated from hero_media file
# Slug is auto-generated: "math-program"
```

### Creating a Course-Specific Program

```python
from marketing.models import Program
from courses.models import Course

# Get specific courses
course1 = Course.objects.get(title="Python for Kids")
course2 = Course.objects.get(title="JavaScript Basics")

# Create program with specific courses
# Note: Upload hero_media file via admin or programmatically
program = Program.objects.create(
    name="Coding Program",
    description="Learn coding with our best courses",
    hero_media_type="video",  # Auto-detected from file extension
    cta_text="Start Coding Today"
)
program.courses.add(course1, course2)
# hero_media_url is auto-generated from hero_media file
# Slug is auto-generated: "coding-program"
```

### Getting Courses for a Program

```python
# Get all courses in the program (alphabetically ordered)
courses = program.get_courses()

# Get course count
count = program.course_count

# Get SEO URL
url = program.get_seo_url(request)
```

## File Upload & GCS Integration

### How It Works

1. **Upload**: User drags-and-drops or clicks to select a file in Django admin
2. **Validation**: File type is validated (images: jpg, png, gif, webp; videos: mp4, webm, mov)
3. **GCS Upload**: On save, file is automatically uploaded to GCS at `marketing/programs/hero_media/{filename}`
4. **URL Generation**: `hero_media_url` is automatically generated from the GCS file URL
5. **Media Type Detection**: `hero_media_type` is automatically set based on file extension
6. **Cleanup**: Old files are automatically deleted from GCS when:
   - File is replaced with a new one
   - Clear checkbox is checked and form is saved
   - Program is deleted

### Signals

The app includes a `pre_delete` signal that ensures files are deleted from GCS when a Program is deleted, even if admin delete is bypassed.

### Admin Interface

- **File Upload Widget**: Standard Django admin file upload widget with drag-and-drop support
- **Clear Checkbox**: Check "Clear" to remove the file (deletes from GCS and clears database field)
- **Read-only URL**: `hero_media_url` is read-only and shows the generated GCS URL

## Migration

After creating the model, run:

```bash
python manage.py makemigrations marketing
python manage.py migrate
```

## Implementation Status

- ✅ **Phase 1**: Backend - Create marketing app and Program model
- ✅ **Phase 2**: Backend - Admin interface with GCS media upload integration
- ⏳ **Phase 3**: Backend - API endpoint to fetch program by slug
- ⏳ **Phase 4**: Frontend - API service method
- ⏳ **Phase 5**: Frontend - ProgramLandingPage component
- ⏳ **Phase 6**: Frontend - Route configuration

## Related Documentation

- [Program Landing Page Phases](../backend-implementation/marketing/PROGRAM_LANDING_PAGE_PHASES.md) - Complete implementation plan

