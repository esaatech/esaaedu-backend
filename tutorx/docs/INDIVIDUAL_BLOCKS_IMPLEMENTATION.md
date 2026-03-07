# Individual Block Operations - Backend Implementation

> **Note (current architecture):** The per-block CRUD endpoints described in this document (`POST /api/tutorx/blocks/`, `GET/PUT/DELETE /api/tutorx/blocks/<block_id>/`) and the list/bulk endpoint (`GET/PUT /api/tutorx/lessons/<lesson_id>/blocks/`) have been **removed**. TutorX now uses a single content field: **GET** and **PUT** `/api/tutorx/lessons/<lesson_id>/content/` store the full BlockNote document as a JSON string in `Lesson.tutorx_content`. See the main `README.md` and `API_REFERENCE.md` for the current API.

## ✅ Changes Made (historical)

### 1. New View: `TutorXBlockCreateView`

**Endpoint**: `POST /api/tutorx/blocks/`

**Purpose**: Create a new TutorX block

**Request Body**:
```json
{
  "lesson": "lesson-uuid",
  "block_type": "text",
  "content": "Hello World",
  "order": 1,
  "metadata": {...}
}
```

**Response** (201 Created):
```json
{
  "id": "block-uuid",
  "lesson": "lesson-uuid",
  "block_type": "text",
  "content": "Hello World",
  "order": 1,
  "metadata": {...},
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Features**:
- ✅ Validates required fields (lesson, block_type, order)
- ✅ Checks permissions (only course teacher)
- ✅ Verifies lesson type is 'tutorx'
- ✅ Handles order conflicts by shifting existing blocks
- ✅ Returns created block with ID

---

### 2. Enhanced View: `TutorXBlockDetailView`

#### PUT Method (Update)

**Endpoint**: `PUT /api/tutorx/blocks/{block_id}/`

**Improvements**:
- ✅ Handles order conflicts when order is changed
- ✅ Shifts blocks appropriately when moving up/down
- ✅ Returns full block data including timestamps
- ✅ Uses `@transaction.atomic` for data integrity

#### DELETE Method (Delete)

**Endpoint**: `DELETE /api/tutorx/blocks/{block_id}/`

**Improvements**:
- ✅ Returns `204 No Content` (was returning 200)
- ✅ Deletes associated images from GCS
- ✅ Reorders remaining blocks to fill gaps
- ✅ Better error handling and logging

---

### 3. URL Configuration

**File**: `tutorx/urls.py`

**Changes**:
- Added `path('blocks/', views.TutorXBlockCreateView.as_view(), name='tutorx-block-create')`
- Reordered URLs to avoid conflicts (create route before action route)

**URL Order** (important for routing):
1. `lessons/<uuid:lesson_id>/blocks/` - List/bulk operations
2. `blocks/` - Create (POST)
3. `blocks/<uuid:block_id>/` - Get/Update/Delete
4. `blocks/<str:action_type>/` - AI actions

---

## 🔧 Order Conflict Handling

### When Creating a Block

If a block already exists at the requested order:
- All blocks with `order >= new_order` are shifted up by 1
- New block is inserted at the requested order

### When Updating a Block's Order

**Moving Down** (order increases):
- Blocks between old and new order are shifted up by 1

**Moving Up** (order decreases):
- Blocks between new and old order are shifted down by 1

### When Deleting a Block

- All blocks with `order > deleted_order` are shifted down by 1
- This fills the gap left by the deleted block

---

## 🔒 Permission & Validation

All endpoints verify:
1. ✅ User is authenticated
2. ✅ User is the course teacher
3. ✅ Lesson type is 'tutorx'
4. ✅ Required fields are present
5. ✅ Block exists (for update/delete)

---

## 📝 Error Responses

All endpoints return consistent error format:
```json
{
  "error": "Error message",
  "details": "Detailed error information (optional)"
}
```

**Status Codes**:
- `201 Created` - Block created successfully
- `200 OK` - Block updated/retrieved successfully
- `204 No Content` - Block deleted successfully
- `400 Bad Request` - Invalid data
- `401 Unauthorized` - Missing/invalid token
- `403 Forbidden` - User is not the course teacher
- `404 Not Found` - Lesson or block not found
- `500 Internal Server Error` - Server error

---

## 🧪 Testing

### Test Create Block
```bash
POST /api/tutorx/blocks/
{
  "lesson": "lesson-uuid",
  "block_type": "text",
  "content": "Test content",
  "order": 1,
  "metadata": {}
}
```

### Test Update Block
```bash
PUT /api/tutorx/blocks/{block_id}/
{
  "content": "Updated content",
  "order": 2
}
```

### Test Delete Block
```bash
DELETE /api/tutorx/blocks/{block_id}/
```

---

## 🔄 Migration Notes

- The bulk endpoint (`PUT /api/tutorx/lessons/{id}/blocks/`) is still available
- Individual endpoints are now the primary method for incremental saves
- Both approaches can coexist

---

## 📊 Benefits

✅ **Efficient**: Only processes changed blocks  
✅ **RESTful**: Follows REST principles  
✅ **Better Error Handling**: One block failure doesn't affect others  
✅ **Order Management**: Automatically handles order conflicts  
✅ **Image Cleanup**: Deletes orphaned images from GCS  
✅ **Transaction Safety**: Uses `@transaction.atomic` for data integrity  

