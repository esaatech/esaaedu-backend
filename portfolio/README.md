# Portfolio App

## Overview

The Portfolio app provides a system for students to curate and showcase their graded project submissions in a professional portfolio format. Students can add projects to their portfolio, organize them with descriptions, tags, and categories, and share their portfolio publicly.

## Models

### Portfolio

Represents a student's portfolio. Each student has one portfolio (one-to-one relationship).

**Fields:**
- `student` (OneToOneField to User): The student who owns this portfolio
- `title` (CharField): Portfolio title (default: "My Portfolio")
- `bio` (TextField): Student bio/description
- `profile_image` (ImageField, optional): Profile picture
- `is_public` (BooleanField): Whether the portfolio is publicly accessible
- `custom_url` (SlugField, unique, optional): Custom URL slug for public access
- `created_at` (DateTimeField): Creation timestamp
- `updated_at` (DateTimeField): Last update timestamp

**Auto-creation:** A Portfolio is automatically created for each new User via a `post_save` signal.

### PortfolioItem

Represents a single project in a student's portfolio. Links a graded project submission to a portfolio with additional metadata.

**Fields:**
- `portfolio` (ForeignKey to Portfolio): The portfolio this item belongs to
- `project_submission` (ForeignKey to ProjectSubmission): The graded project submission
- `title` (CharField): Display title (can differ from project title)
- `description` (TextField): Rich text description of the project
- `category` (CharField, optional): Category (e.g., "Python", "Web Development")
- `tags` (JSONField): Array of tags
- `skills_demonstrated` (JSONField): Array of skills demonstrated
- `thumbnail_image` (ImageField, optional): Thumbnail image
- `screenshots` (JSONField, optional): Array of screenshot URLs
- `featured` (BooleanField): Whether this item is featured (pinned to top)
- `order` (IntegerField): Display order
- `is_visible` (BooleanField): Whether this item is visible in the portfolio
- `created_at` (DateTimeField): Creation timestamp
- `updated_at` (DateTimeField): Last update timestamp

**Constraints:**
- `unique_together`: (`portfolio`, `project_submission`) - Prevents duplicate entries
- Only graded project submissions can be added
- Only the student who owns the submission can add it to their portfolio

## API Endpoints

### Portfolio Management

#### `GET /api/portfolio/`
Get the authenticated student's portfolio.

**Response:**
```json
{
  "id": 1,
  "title": "My Portfolio",
  "bio": "Student bio...",
  "is_public": true,
  "custom_url": "john-doe",
  "items": [...]
}
```

#### `PUT /api/portfolio/`
Update portfolio settings (title, bio, is_public, custom_url).

**Request Body:**
```json
{
  "title": "Updated Title",
  "bio": "Updated bio",
  "is_public": true,
  "custom_url": "new-url"
}
```

### Portfolio Items

#### `GET /api/portfolio/items/`
List all portfolio items for the authenticated student.

**Response:**
```json
[
  {
    "id": 1,
    "title": "Project Title",
    "description": "...",
    "category": "Python",
    "tags": ["oop", "api"],
    "skills_demonstrated": ["problem-solving"],
    "featured": true,
    "order": 0,
    "is_visible": true,
    "project_submission": {...}
  }
]
```

#### `POST /api/portfolio/items/`
Add a project to the portfolio.

**Request Body (FormData):**
- `project_submission_id` (int, optional): ID of the project submission
- `share_token` (string, optional): Share token of the project submission
- `title` (string, required): Display title
- `description` (string, required): Rich text description
- `category` (string, optional): Category
- `tags` (JSON string, optional): Array of tags
- `skills_demonstrated` (JSON string, optional): Array of skills
- `featured` (boolean, optional): Whether to feature this item
- `order` (int, optional): Display order
- `is_visible` (boolean, optional): Visibility flag
- `thumbnail_image` (file, optional): Thumbnail image
- `screenshots` (JSON string, optional): Array of screenshot URLs

**Note:** Either `project_submission_id` or `share_token` must be provided.

**Validation:**
- Submission must belong to the authenticated student
- Submission must be graded (status = 'GRADED')
- Submission must not already be in the portfolio

#### `GET /api/portfolio/items/{id}/`
Get a specific portfolio item.

#### `PUT /api/portfolio/items/{id}/`
Update a portfolio item.

**Request Body (FormData):**
Same fields as POST, all optional.

#### `DELETE /api/portfolio/items/{id}/`
Remove a portfolio item.

#### `POST /api/portfolio/items/reorder/`
Reorder portfolio items.

**Request Body:**
```json
{
  "item_ids": [3, 1, 2, 4]
}
```

### Project Data for Portfolio Wizard

#### `GET /api/portfolio/project-from-token/{share_token}/`
Get project submission details using a share token. Used by the portfolio wizard to fetch project data before adding it to the portfolio.

**Response:**
```json
{
  "project": {
    "id": 23,
    "title": "Simple ATM System",
    "instructions": "...",
    "project_platform": {...}
  },
  "submission": {
    "id": 72,
    "content": "...",
    "file_url": "...",
    "submitted_at": "..."
  }
}
```

### Public Portfolio

#### `GET /api/portfolio/public/{custom_url}/`
Get a public portfolio by custom URL.

**Response:**
```json
{
  "id": 1,
  "title": "John's Portfolio",
  "bio": "...",
  "items": [...]
}
```

## Serializers

### PortfolioSerializer
Serializes Portfolio model with nested items.

### PortfolioItemSerializer
Serializes PortfolioItem with project submission details.

### PortfolioItemCreateSerializer
Handles creation of portfolio items with validation:
- Validates ownership of project submission
- Validates submission is graded
- Prevents duplicates
- Accepts either `project_submission_id` or `share_token`

### PortfolioItemUpdateSerializer
Handles updates to portfolio items (all fields optional).

## Views

### PortfolioDetailView
- `GET`: Retrieve student's portfolio
- `PUT`: Update portfolio settings

### PortfolioItemListView
- `GET`: List all portfolio items
- `POST`: Create a new portfolio item

### PortfolioItemDetailView
- `GET`: Retrieve a portfolio item
- `PUT`: Update a portfolio item
- `DELETE`: Delete a portfolio item

### PortfolioItemReorderView
- `POST`: Reorder portfolio items

### ProjectSubmissionForPortfolioView
- `GET`: Get project submission details by share token

### PublicPortfolioView
- `GET`: Get public portfolio by custom URL

## Permissions

All portfolio endpoints require authentication. Students can only:
- Access their own portfolio
- Add their own graded project submissions
- Modify their own portfolio items

## Signals

### `post_save` on User model
Automatically creates a Portfolio instance when a new User is created.

## Usage Example

```python
# Student adds a project to their portfolio
POST /api/portfolio/items/
Content-Type: multipart/form-data

project_submission_id=72
title=My Awesome Project
description=<p>This project demonstrates...</p>
category=Python
tags=["oop", "api"]
skills_demonstrated=["problem-solving"]
featured=true
is_visible=true
```

## Related Apps

- `courses`: Provides `ProjectSubmission` model
- `student`: Provides student-related functionality

