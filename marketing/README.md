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
- **`hero_media_url`**: URLField - GCS URL for hero image or video (used as background)
- **`hero_media_type`**: CharField - Type of media: 'image' or 'video' (default: 'image')
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
- Calls `full_clean()` to run validation before saving

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
Returns the number of courses in this program (calls `get_courses().count()`)

### Model Validation

The model enforces the following rules:
1. **Mutually Exclusive Selection**: Either `category` OR `courses` must be set, but not both
2. **Slug Uniqueness**: Slug is automatically made unique if duplicates exist
3. **Auto-slug Generation**: Slug is auto-generated from name if not provided

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
1. **Basic Information**: Name, slug, description
2. **Hero Media**: Media URL and type
3. **Call to Action**: CTA text
4. **Course Selection**: Category or courses (with warning about mutual exclusivity)
5. **Discount & Promotion**: Discount toggle, promotion message, promo code
6. **Status**: Active toggle
7. **Metadata**: ID, timestamps, SEO URL, course count

#### Custom Admin Features
- **SEO URL Display**: Shows full URL with copy button
- **Course Count Link**: Links to filtered course list in admin
- **Validation**: Ensures clean() is called on save

## Usage Example

### Creating a Category-Based Program

```python
from marketing.models import Program

# Create a program that includes all courses in "Mathematics" category
program = Program.objects.create(
    name="Math Program",
    description="Comprehensive math courses for all ages",
    category="Mathematics",
    hero_media_url="https://storage.googleapis.com/.../math-hero.jpg",
    hero_media_type="image",
    cta_text="Start Learning Math Today",
    is_active=True,
    discount_enabled=True,
    promotion_message="Special promotion: 20% off all math courses!",
    promo_code="MATH20"
)
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
program = Program.objects.create(
    name="Coding Program",
    description="Learn coding with our best courses",
    hero_media_url="https://storage.googleapis.com/.../coding-hero.mp4",
    hero_media_type="video",
    cta_text="Start Coding Today"
)
program.courses.add(course1, course2)
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

## Migration

After creating the model, run:

```bash
python manage.py makemigrations marketing
python manage.py migrate
```

## Next Steps

1. **Phase 2**: Admin interface with GCS media upload integration
2. **Phase 3**: API endpoint to fetch program by slug
3. **Phase 4**: Frontend API service method
4. **Phase 5**: Frontend ProgramLandingPage component
5. **Phase 6**: Frontend route configuration

## Related Documentation

- [Program Landing Page Phases](../backend-implementation/marketing/PROGRAM_LANDING_PAGE_PHASES.md) - Complete implementation plan

