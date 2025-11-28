# Scheduling Workflow Analysis - Adding Test & Exam Events

## Current Implementation

### 1. Event Types - **HARDCODED** (Not from API)

#### Backend (`courses/models.py` lines 2091-2098):
```python
EVENT_TYPES = [
    ('lesson', 'Lesson'),
    ('meeting', 'Meeting'),
    ('project', 'Project'),
    ('break', 'Break'),
    ('test', 'Test'),        # ✅ ADDED
    ('exam', 'Exam'),        # ✅ ADDED
]
```

#### Frontend (`ScheduleTab.tsx` lines 1157-1160):
```tsx
<SelectItem value="lesson">📚 Lesson</SelectItem>
<SelectItem value="meeting">👥 Meeting</SelectItem>
<SelectItem value="break">☕ Break</SelectItem>
<SelectItem value="project">🎯 Project</SelectItem>
```

**Answer:** Event types are **HARDCODED** in both backend and frontend, NOT fetched from an endpoint.

---

## End-to-End Flow for Existing Event Types

### 1. **Lesson Events**

**Backend Model (`ClassEvent`):**
- `event_type = 'lesson'`
- `lesson` (ForeignKey to `Lesson`) - **REQUIRED**
- `lesson_type` (live/text/video/audio/interactive)
- `start_time` and `end_time` - **REQUIRED**
- `meeting_platform`, `meeting_link`, `meeting_id`, `meeting_password` (for live lessons)

**Frontend Flow:**
1. User selects "Lesson" from dropdown
2. Shows lesson selector dropdown (loads from `available_lessons` in API response)
3. When lesson selected → auto-populates `title`, `description`, `lesson_type`
4. User sets `start_time` and `end_time`
5. If `lesson_type === 'live'` → shows meeting platform options
6. On save → sends to `/api/courses/teacher/classes/<class_id>/events/` POST

**API Endpoint:**
- `GET /api/courses/teacher/classes/<class_id>/events/` - Returns events + `available_lessons`
- `POST /api/courses/teacher/classes/<class_id>/events/` - Creates event

**Validation:**
- `lesson` FK is required
- `start_time` and `end_time` required (non-project events)
- `end_time > start_time`

---

### 2. **Project Events**

**Backend Model (`ClassEvent`):**
- `event_type = 'project'`
- `project` (ForeignKey to `Project`) - **REQUIRED**
- `project_platform` (ForeignKey to `ProjectPlatform`) - **REQUIRED**
- `project_title` (cached for display)
- `due_date` - **REQUIRED** (instead of start_time/end_time)
- `submission_type` (link/image/video/etc.)

**Frontend Flow:**
1. User selects "Project" from dropdown
2. Shows project selector dropdown (loads from `available_projects` in API response)
3. Shows platform selector (loads from `available_platforms` in API response)
4. User sets `due_date` (not start_time/end_time)
5. User selects `submission_type`
6. On save → sends to API

**API Endpoint:**
- Same endpoints as lesson events
- Response includes `available_projects` and `available_platforms`

**Validation:**
- `project` FK is required
- `project_platform` FK is required
- `due_date` is required (replaces start_time/end_time)
- Project must belong to same course as class

---

### 3. **Meeting Events**

**Backend Model (`ClassEvent`):**
- `event_type = 'meeting'`
- `start_time` and `end_time` - **REQUIRED**
- `meeting_platform`, `meeting_link`, `meeting_id`, `meeting_password` (optional)

**Frontend Flow:**
1. User selects "Meeting" from dropdown
2. User sets `start_time` and `end_time`
3. Optional: Set meeting platform and link
4. On save → sends to API

**Validation:**
- `start_time` and `end_time` required
- `end_time > start_time`

---

### 4. **Break Events**

**Backend Model (`ClassEvent`):**
- `event_type = 'break'`
- `start_time` and `end_time` - **REQUIRED`
- No additional fields

**Frontend Flow:**
1. User selects "Break" from dropdown
2. User sets `start_time` and `end_time`
3. On save → sends to API

**Validation:**
- `start_time` and `end_time` required
- `end_time > start_time`

---

## Implementation Plan for Test & Exam Events

### Step 1: Update Backend Model ✅ **COMPLETED**

**File:** `courses/models.py`

✅ **Completed:**
- Added 'test' and 'exam' to `EVENT_TYPES`
- Added `assessment` ForeignKey to `ClassEvent` model
- Updated validation in `ClassEvent.clean()` to require assessment for test/exam events
- Updated validation to ensure assessment belongs to same course as class
- Updated Schedule description to include test/exam events
- Migration created: `0043_add_test_exam_event_types.py`

**Implementation:**
```python
EVENT_TYPES = [
    ('lesson', 'Lesson'),
    ('meeting', 'Meeting'),
    ('project', 'Project'),
    ('break', 'Break'),
    ('test', 'Test'),        # ✅ ADDED
    ('exam', 'Exam'),        # ✅ ADDED
]

assessment = models.ForeignKey(
    'CourseAssessment',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    help_text="Associated assessment (if event type is test or exam)"
)
```

---

### Step 2: Update Serializers ✅ **COMPLETED**

**File:** `courses/serializers.py`

✅ **Completed:**
- Updated `ClassEventCreateUpdateSerializer` to include `assessment` field
- Added validation for test/exam events requiring assessment
- Updated `ClassEventDetailSerializer` to include assessment fields (id, title, type)
- Updated `ClassEventListSerializer` to include assessment fields (title, type)

**Implementation:**
- `ClassEventCreateUpdateSerializer.fields` includes `'assessment'`
- Validation checks: `if event_type in ['test', 'exam']: require assessment`
- `ClassEventDetailSerializer` includes: `assessment`, `assessment_id`, `assessment_title`, `assessment_type`
- `ClassEventListSerializer` includes: `assessment_title`, `assessment_type`

---

### Step 3: Update API Endpoint ✅ **COMPLETED**

**File:** `courses/views.py` - `class_events()` function

✅ **Completed:**
- Added `CourseAssessment` and `CourseAssessmentListSerializer` to imports
- Updated `select_related()` to include `'assessment'` for performance
- Added query for `available_assessments` filtered by course
- Added `available_assessments` to GET response

**Implementation:**
```python
# Get available assessments for this course
available_assessments = CourseAssessment.objects.filter(
    course=class_instance.course
).order_by('order', 'created_at')
assessments_serializer = CourseAssessmentListSerializer(available_assessments, many=True)

return Response({
    # ... existing fields ...
    'available_assessments': assessments_serializer.data  # ✅ ADDED
}, status=status.HTTP_200_OK)
```

**API Response Now Includes:**
- `available_assessments`: Array of all assessments for the course (test and exam types)

---

### Step 3.5: Update Admin Interface ✅ **COMPLETED**

**File:** `courses/admin.py`

✅ **Completed:**
- Added `assessment` to `list_display`
- Added `assessment__title` to `search_fields`
- Added `assessment` to `Event Content` fieldset
- Updated Schedule description to mention test/exam events
- Updated `get_queryset()` to include `'assessment'` in `select_related()`

**Implementation:**
- Admin list view shows assessment column
- Admin edit form includes assessment field in Event Content section
- Searchable by assessment title
- Optimized queries with assessment preloaded

---

### Step 4: Update Frontend ⏳ **PENDING**

**File:** `ScheduleTab.tsx`

**1. Add to event type dropdown (line ~1157):**
```tsx
<SelectItem value="lesson">📚 Lesson</SelectItem>
<SelectItem value="meeting">👥 Meeting</SelectItem>
<SelectItem value="break">☕ Break</SelectItem>
<SelectItem value="project">🎯 Project</SelectItem>
<SelectItem value="test">📝 Test</SelectItem>        {/* NEW */}
<SelectItem value="exam">📋 Exam</SelectItem>        {/* NEW */}
```

**2. Update TypeScript interface (line ~31):**
```tsx
type: 'lesson' | 'meeting' | 'break' | 'project' | 'test' | 'exam';
```

**3. Add assessment fields to state (line ~75):**
```tsx
const [newEvent, setNewEvent] = useState({
  // ... existing fields ...
  assessmentId: '' as string,  // NEW
});
```

**4. Load available assessments:**
```tsx
const [courseAssessmentsData, setCourseAssessmentsData] = useState<{ [courseId: string]: any[] }>({});

const loadCourseAssessments = async (courseId: string) => {
  if (courseAssessmentsData[courseId]) return;
  
  try {
    const assessments = await apiService.getCourseAssessments(courseId);
    setCourseAssessmentsData(prev => ({
      ...prev,
      [courseId]: assessments
    }));
  } catch (error) {
    console.error('Failed to load assessments:', error);
  }
};
```

**5. Add assessment selector in form (similar to lesson/project selectors):**
```tsx
{newEvent.type === 'test' || newEvent.type === 'exam' ? (
  <div className="space-y-2">
    <Label>Assessment</Label>
    <Select
      value={newEvent.assessmentId}
      onValueChange={handleAssessmentSelect}
    >
      <SelectTrigger>
        <SelectValue placeholder="Select assessment" />
      </SelectTrigger>
      <SelectContent>
        {courseAssessmentsData[selectedClass.course_id]?.map(assessment => (
          <SelectItem key={assessment.id} value={assessment.id}>
            {assessment.title} ({assessment.assessment_type})
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  </div>
) : null}
```

**6. Handle assessment selection:**
```tsx
const handleAssessmentSelect = (assessmentId: string) => {
  const assessments = courseAssessmentsData[selectedClass.course_id] || [];
  const selectedAssessment = assessments.find(a => a.id === assessmentId);
  
  if (selectedAssessment) {
    setNewEvent(prev => ({
      ...prev,
      assessmentId: assessmentId,
      title: selectedAssessment.title,
      description: selectedAssessment.description || '',
    }));
  }
};
```

**7. Update save handler to include assessment:**
```tsx
const payload = {
  // ... existing fields ...
  assessment: newEvent.assessmentId || null,  // NEW
};
```

**8. Update event color mapping:**
```tsx
// In getEventColor function or constants
'test': '#ef4444',  // Red
'exam': '#dc2626',  // Dark red
```

---

### Step 5: Update API Service (Frontend) ⏳ **PENDING**

**File:** `src/services/api.ts`

**Note:** The assessments are already returned in the `getClassEvents()` response as `available_assessments`, so a separate API call may not be needed. However, if needed for other purposes:

```typescript
async getCourseAssessments(courseId: string): Promise<CourseAssessment[]> {
  const response = await this.request<CourseAssessment[]>(
    `/courses/teacher/courses/${courseId}/assessments/`,
    'GET'
  );
  return response;
}
```

**Alternative:** Use `available_assessments` from the existing `getClassEvents()` response.

---

## Summary

### Key Findings:
1. ✅ **Event types are HARDCODED** - Not fetched from API
2. ✅ **Pattern is consistent** - Each event type has:
   - Required FK relationship (lesson/project/assessment)
   - Type-specific fields
   - Validation logic
3. ✅ **Frontend mirrors backend** - Both need updates

### Implementation Status:

#### ✅ Backend - COMPLETED:
1. ✅ Add 'test' and 'exam' to `EVENT_TYPES` in model
2. ✅ Add `assessment` ForeignKey to `ClassEvent` model
3. ✅ Update validation logic in model and serializer
4. ✅ Update all serializers (CreateUpdate, Detail, List)
5. ✅ Update API endpoint to return `available_assessments`
6. ✅ Update admin interface (list_display, fieldsets, search)
7. ✅ Add migration for new field (`0043_add_test_exam_event_types.py`)

#### ⏳ Frontend - PENDING:
1. ⏳ Update frontend dropdown to include test/exam options
2. ⏳ Add assessment selector UI component
3. ⏳ Update TypeScript interfaces
4. ⏳ Add assessment state management
5. ⏳ Update save handler to include assessment
6. ⏳ Update event color mapping
7. ⏳ Handle assessment selection and auto-population

### Similarities to Existing Types:
- **Test/Exam** events are similar to **Lesson** events:
  - ✅ Require FK to related model (`CourseAssessment`) - **IMPLEMENTED**
  - ✅ Require `start_time` and `end_time` - **VALIDATED**
  - ⏳ Auto-populate title/description from assessment - **PENDING (Frontend)**
  - ✅ No additional fields needed (unlike projects which need platform) - **CONFIRMED**

### Backend API Ready:
The backend is **fully implemented** and ready for frontend integration:
- ✅ Model supports test/exam event types
- ✅ API returns `available_assessments` in GET requests
- ✅ API accepts `assessment` field in POST/PUT requests
- ✅ Validation ensures assessment is required for test/exam events
- ✅ Admin interface supports managing assessment events

