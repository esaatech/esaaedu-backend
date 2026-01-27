# Admin Enrollment Functionality

## Overview

This document describes the admin enrollment functionality that allows administrators to register students for courses directly from the Django admin interface, bypassing the Stripe payment flow. This is useful for:
- Free courses
- Cash payments
- Scholarships
- Manual enrollments

## Implementation Phases

### Phase 1: Shared Enrollment Function

**File:** `student/utils.py`

Created a shared utility function `complete_enrollment_without_stripe()` that handles enrollment creation and class assignment without involving Stripe. This function:
- Creates or reactivates `EnrolledCourse` records
- Assigns students to classes (if specified)
- Handles different payment statuses (free, paid, scholarship)
- Is idempotent (can be called multiple times safely)
- Optionally creates Payment records for cash payments

**Key Features:**
- Atomic transactions for data integrity
- Automatic class assignment (if class is not full)
- Progress tracking initialization
- Payment record creation for cash payments (optional)

### Phase 2: Admin Interface Integration

**Files Modified:**
- `student/admin.py` - Admin form and interface
- `student/views.py` - Admin API endpoints
- `student/urls.py` - URL routes
- `student/static/admin/js/enrolled_course_admin.js` - JavaScript for dynamic loading

#### Performance Optimizations

To ensure fast form loading even with large datasets, the following optimizations were implemented:

1. **Autocomplete Fields (Lazy Loading)**
   - `student_profile` and `course` fields use Django's `autocomplete_fields`
   - Fields load empty initially - no database queries on page load
   - Results are fetched via AJAX only when you start typing
   - Searches as you type (e.g., typing "a" shows all students/courses starting with "a")
   - Dramatically reduces initial page load time from minutes to seconds

2. **Enrolled By Field Optimization**
   - `enrolled_by` field is readonly for new enrollments
   - Queryset limited to only the current logged-in admin user
   - Prevents loading all users/admins/teachers into dropdown
   - Automatically set to current admin user

3. **Class Instance Field Optimization**
   - Starts with empty queryset (`Class.objects.none()`)
   - Classes loaded on-demand via AJAX when "Load Classes" button is clicked
   - No initial database query for classes

4. **Query Optimization**
   - Added `select_related()` and `prefetch_related()` to admin queryset
   - Reduces database queries when viewing enrollment list

#### Features

1. **Dynamic Class Loading**
   - "Load Classes" button appears when a course is selected
   - Fetches classes via AJAX from `/api/student/admin/courses/<course_id>/classes/`
   - Shows spinner during loading
   - Populates dropdown with available classes

2. **Dynamic Lesson Loading**
   - "Load Lessons" button appears when a course is selected
   - Fetches lessons via AJAX from `/api/student/admin/courses/<course_id>/lessons/`
   - Shows spinner during loading
   - Populates dropdown with available lessons
   - `current_lesson` field is hidden initially in a collapsed section

3. **Form Validation**
   - Custom `LenientClassChoiceField` allows dynamic class selection
   - Custom `clean_class_instance()` validates class belongs to selected course
   - Custom `clean_current_lesson()` validates lesson belongs to selected course
   - Handles cases where classes/lessons are loaded via AJAX

4. **Autocomplete Search**
   - Student Profile: Search by email, first name, last name, or parent email
   - Course: Search by title or description
   - Results appear as you type (minimum 2 characters)
   - No need to load all records - only matching results are fetched

5. **Admin API Endpoints**
   - `GET /api/student/admin/courses/<course_id>/classes/` - Get classes for a course
   - `GET /api/student/admin/courses/<course_id>/lessons/` - Get lessons for a course
   - Both endpoints require admin/staff authentication via SessionAuthentication

## Usage

### Enrolling a Student from Admin

1. Navigate to Django Admin → Student → Enrolled courses
2. Click "Add Enrolled course"
3. Fill in required fields:
   - **Student profile**: Select the student
   - **Course**: Select the course
4. Click "Load Classes" button (appears after course selection)
5. Select a class (optional)
6. Click "Load Lessons" button if you want to set a current lesson (optional)
7. Set payment details:
   - **Payment status**: Choose from free, paid, pending, scholarship, etc.
   - **Amount paid**: Enter amount if payment_status is "paid"
   - **Payment due date**: Set if applicable
8. Click "Save"

### Payment Status Options

- **free**: No payment required (free courses)
- **paid**: Payment received (cash payments)
- **pending**: Payment pending
- **scholarship**: Student on scholarship
- **overdue**: Payment overdue

### Class Assignment

- Classes are automatically assigned when enrollment is created
- Student is added to the selected class if:
  - Class is not full (student_count < max_capacity)
  - Class is active
- If class is full, enrollment still succeeds but student is not added to class

## Technical Details

### Form Customization

The `EnrolledCourseAdminForm` includes:
- Custom `class_instance` field (not saved to model, used for enrollment)
- Dynamic queryset filtering based on selected course
- Custom validation methods
- Help text that updates based on course selection

### JavaScript Functionality

The `enrolled_course_admin.js` file:
- Monitors course field changes
- Enables/disables "Load Classes" and "Load Lessons" buttons
- Makes AJAX requests with session authentication
- Shows loading spinners
- Populates dropdowns dynamically
- Handles errors gracefully

### API Endpoints

#### Get Classes for Course
```
GET /api/student/admin/courses/<course_id>/classes/
```

**Authentication:** Session-based (admin/staff only)

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Class Name",
    "description": "Class description",
    "max_capacity": 20,
    "student_count": 15,
    "available_spots": 5,
    "teacher_name": "Teacher Name"
  }
]
```

#### Get Lessons for Course
```
GET /api/student/admin/courses/<course_id>/lessons/
```

**Authentication:** Session-based (admin/staff only)

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "Lesson Title",
    "description": "Lesson description",
    "type": "video",
    "order": 1,
    "duration": 30
  }
]
```

## Error Handling

- If course is not found, appropriate error messages are shown
- If class is full, enrollment succeeds but student is not added to class
- If class doesn't belong to course, validation error is raised
- AJAX errors are displayed to the user with helpful messages

## Future Enhancements (Phase 3 & 4)

### Phase 3: Free Course Check in Frontend
- Add free course check to frontend enrollment endpoints
- Bypass Stripe for free courses
- Use `complete_enrollment_without_stripe()` for free course enrollments

### Phase 4: Payment Record Creation
- Automatically create Payment records for cash payments
- Link Payment records to enrollments
- Track payment history

## Testing

To test the admin enrollment functionality:

1. Create a test course with classes
2. Create a test student profile
3. Navigate to admin enrollment form
4. Select course and click "Load Classes"
5. Verify classes appear in dropdown
6. Select a class and submit
7. Verify enrollment is created and student is added to class

## Troubleshooting

### Classes not loading
- Check browser console for JavaScript errors
- Verify API endpoint is accessible
- Check that user has admin/staff permissions
- Verify course has active classes

### Validation errors
- Ensure class belongs to selected course
- Check that class is active
- Verify course is selected before loading classes

### AJAX authentication errors
- Ensure user is logged into Django admin
- Check that SessionAuthentication is working
- Verify CSRF token is included in requests

## Related Files

- `student/utils.py` - Shared enrollment function
- `student/admin.py` - Admin form and interface
- `student/views.py` - API endpoints
- `student/urls.py` - URL configuration
- `student/static/admin/js/enrolled_course_admin.js` - JavaScript
- `student/models.py` - EnrolledCourse model

