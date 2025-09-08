# Teacher App

## Overview
This app handles teacher-specific functionality for the Little Learners Tech platform.

## Note
⚠️ **This app was created later in the development process.** Most teacher-related views and functionality are still located in the `courses` app. This app will gradually be expanded to consolidate all teacher-specific features.

## Current Structure
- **Models**: Teacher profile management
- **Views**: Teacher profile CRUD operations
- **Serializers**: Teacher profile data serialization
- **URLs**: Teacher profile endpoints

## Future Migration
The following functionality will be moved from the `courses` app to this app:
- Teacher dashboard views
- Course management views
- Student management views
- Class scheduling views
- Quiz and lesson management views

## Dependencies
- `users` app (for User and TeacherProfile models)
- `courses` app (for course-related functionality)
