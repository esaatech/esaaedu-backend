# Scheduling Workflow Analysis - Adding Test & Exam Events

## Current Implementation

### 1. Event Types - **HARDCODED** (Not from API)

#### Backend (`courses/models.py` lines 2091-2096):
```python
EVENT_TYPES = [
    ('lesson', 'Lesson'),
    ('meeting', 'Meeting'),
    ('project', 'Project'),
    ('break', 'Break'),
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

### Step 1: Update Backend Model

**File:** `courses/models.py`

```python
EVENT_TYPES = [
    ('lesson', 'Lesson'),
    ('meeting', 'Meeting'),
    ('project', 'Project'),
    ('break', 'Break'),
    ('test', 'Test'),        # NEW
    ('exam', 'Exam'),        # NEW
]
```

**Add ForeignKey to ClassEvent model:**
```python
assessment = models.ForeignKey(
    CourseAssessment,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    help_text="Associated assessment (if event type is test or exam)"
)
```

**Update validation in `ClassEvent.clean()`:**
```python
if self.event_type in ['test', 'exam']:
    if not self.assessment:
        raise ValidationError("Assessment events must have an associated assessment")
    
    # Assessment must belong to same course as class
    if self.assessment and self.class_instance:
        if self.assessment.course != self.class_instance.course:
            raise ValidationError("Assessment must belong to the same course as the class")
```

---

### Step 2: Update Serializer

**File:** `courses/serializers.py`

**Update `ClassEventCreateUpdateSerializer`:**
```python
fields = [
    'title', 'description', 'event_type', 'start_time', 'end_time', 
    'lesson', 'project', 'project_platform', 'project_title', 'due_date', 'submission_type',
    'lesson_type', 'meeting_platform', 'meeting_link', 'meeting_id', 'meeting_password',
    'assessment'  # NEW
]
```

**Update validation:**
```python
# Validate assessment events
if event_type in ['test', 'exam']:
    if not data.get('assessment'):
        raise serializers.ValidationError("Assessment events must have an associated assessment")
```

**Update `ClassEventDetailSerializer`:**
```python
assessment_id = serializers.CharField(source='assessment.id', read_only=True)
assessment_title = serializers.CharField(source='assessment.title', read_only=True)
assessment_type = serializers.CharField(source='assessment.assessment_type', read_only=True)

fields = [
    # ... existing fields ...
    'assessment', 'assessment_id', 'assessment_title', 'assessment_type'  # NEW
]
```

---

### Step 3: Update API Endpoint

**File:** `courses/views.py` - `class_events()` function

**Add available assessments to GET response:**
```python
# Get available assessments for this course
from .models import CourseAssessment
available_assessments = CourseAssessment.objects.filter(course=class_instance.course)
assessments_serializer = CourseAssessmentListSerializer(available_assessments, many=True)

return Response({
    'class_id': class_id,
    'class_name': class_instance.name,
    'course_id': str(class_instance.course.id),
    'course_name': class_instance.course.title,
    'events': serializer.data,
    'available_projects': projects_serializer.data,
    'available_platforms': platforms_serializer.data,
    'available_lessons': lessons_serializer.data,
    'available_assessments': assessments_serializer.data  # NEW
}, status=status.HTTP_200_OK)
```

---

### Step 4: Update Frontend

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

### Step 5: Update API Service (Frontend)

**File:** `src/services/api.ts`

**Add method to fetch assessments:**
```typescript
async getCourseAssessments(courseId: string): Promise<CourseAssessment[]> {
  const response = await this.request<CourseAssessment[]>(
    `/courses/teacher/courses/${courseId}/assessments/`,
    'GET'
  );
  return response;
}
```

---

## Summary

### Key Findings:
1. ✅ **Event types are HARDCODED** - Not fetched from API
2. ✅ **Pattern is consistent** - Each event type has:
   - Required FK relationship (lesson/project/assessment)
   - Type-specific fields
   - Validation logic
3. ✅ **Frontend mirrors backend** - Both need updates

### Implementation Steps:
1. ✅ Add 'test' and 'exam' to `EVENT_TYPES` in model
2. ✅ Add `assessment` ForeignKey to `ClassEvent` model
3. ✅ Update validation logic
4. ✅ Update serializers
5. ✅ Update API endpoint to return `available_assessments`
6. ✅ Update frontend dropdown
7. ✅ Add assessment selector UI
8. ✅ Update save handler
9. ✅ Add migration for new field

### Similarities to Existing Types:
- **Test/Exam** will be similar to **Lesson** events:
  - Require FK to related model (`CourseAssessment`)
  - Require `start_time` and `end_time`
  - Auto-populate title/description from assessment
  - No additional fields needed (unlike projects which need platform)

