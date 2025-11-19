# Efficient Lesson Completion Status Solution

## Current Problems

1. **N+1 Query Problem**: If we query `StudentLessonProgress` for each lesson individually, we get:
   - 1 query for course
   - 1 query for lessons
   - N queries for progress (one per lesson)
   - **Total: 2 + N queries** ❌

2. **Status Not Populated**: `LessonListSerializer.status` returns `None` because there's no `get_status()` method

3. **Frontend Inference**: Frontend guesses completion from `current_lesson_id` and `order`, which is error-prone

4. **Data Inconsistency**: `completed_lessons_count` can drift from actual `StudentLessonProgress` records

---

## Proposed Efficient Solution

### Strategy: **Bulk Prefetch with Context Mapping**

### How It Works:

1. **Single Bulk Query**: Use `prefetch_related` to load ALL progress records in ONE query
2. **In-Memory Dictionary**: Create `{lesson_id: status}` mapping (O(1) lookup)
3. **Context Passing**: Pass dictionary through serializer context
4. **O(1) Lookup**: Serializer uses dictionary to get status (no additional queries)

### Performance:
- **Before**: 2 + N queries (N = number of lessons)
- **After**: 3 queries total (course, lessons, progress - all prefetched)
- **Improvement**: Constant time regardless of lesson count ✅

---

## Implementation Details

### Step 1: Update View to Prefetch Progress

**Important Note**: `StudentLessonProgress` records are **NOT created on enrollment**. They are created lazily (on-demand) when:
- A lesson is marked complete
- A quiz is taken
- Progress is first tracked

This means most lessons won't have progress records initially, so we need to handle missing records.

```python
# courses/views.py - student_course_lessons()

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def student_course_lessons(request, course_id):
    try:
        course = get_object_or_404(Course, id=course_id)
        student_profile = request.user.student_profile
        
        enrollment = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course=course,
            status__in=['active', 'completed']
        ).prefetch_related(  # ✅ KEY OPTIMIZATION
            'lesson_progress__lesson'  # Prefetch all progress records (may be empty for new enrollments)
        ).first()
        
        if not enrollment:
            return Response(
                {'error': 'You are not enrolled in this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Build progress status map (ONE-TIME operation)
        progress_map = {}
        current_lesson_id = str(enrollment.current_lesson.id) if enrollment.current_lesson else None
        
        # First, process lessons WITH progress records
        for progress in enrollment.lesson_progress.all():
            lesson_id = str(progress.lesson.id)
            # Determine status based on progress record
            if progress.status == 'completed':
                status = 'completed'
            elif progress.status == 'in_progress':
                status = 'current' if lesson_id == current_lesson_id else 'in_progress'
            else:  # 'not_started' or 'locked'
                # Determine if locked or available
                if lesson_id == current_lesson_id:
                    status = 'current'
                elif progress.lesson.order == 1:
                    status = 'current'  # First lesson is always available
                else:
                    status = 'locked'  # Not started and not current
            
            progress_map[lesson_id] = status
        
        # Then, handle lessons WITHOUT progress records (lazy initialization)
        # These are lessons that haven't been accessed yet
        for lesson in course.lessons.all():
            lesson_id = str(lesson.id)
            if lesson_id not in progress_map:  # No progress record exists
                if lesson_id == current_lesson_id:
                    status = 'current'
                elif lesson.order == 1:
                    status = 'current'  # First lesson is always available
                else:
                    # Check if previous lessons are completed to determine if unlocked
                    # For now, default to locked (can be enhanced later)
                    status = 'locked'
                progress_map[lesson_id] = status
        
        # Pass progress map through context
        serializer = CourseWithLessonsSerializer(
            course, 
            context={
                'student_profile': student_profile,
                'lesson_status_map': progress_map,  # ✅ Pass the map
                'current_lesson_id': current_lesson_id
            }
        )
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch course lessons', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
```

### Step 2: Update LessonListSerializer to Use Status Map

```python
# courses/serializers.py - LessonListSerializer

class LessonListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for lesson list (first API call)
    Returns minimal lesson data for the course page
    """
    status = serializers.SerializerMethodField()  # ✅ Change to SerializerMethodField
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'type', 'duration', 'order', 
            'status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_status(self, obj):
        """Get lesson status from progress map (O(1) lookup)"""
        lesson_status_map = self.context.get('lesson_status_map', {})
        lesson_id = str(obj.id)
        
        # O(1) dictionary lookup - no additional queries!
        status = lesson_status_map.get(lesson_id, 'locked')
        
        return status
```

### Step 3: Update CourseWithLessonsSerializer to Pass Context

```python
# courses/serializers.py - CourseWithLessonsSerializer

class CourseWithLessonsSerializer(serializers.ModelSerializer):
    lessons = LessonListSerializer(many=True, read_only=True)
    
    def to_representation(self, instance):
        """Override to pass context to nested lessons"""
        representation = super().to_representation(instance)
        
        # Context is automatically passed to nested serializers
        # No additional changes needed!
        
        return representation
```

---

## Status Determination Logic

### Status Values:
- `'completed'`: Lesson has `StudentLessonProgress` with `status='completed'`
- `'current'`: Lesson is the `enrollment.current_lesson` OR first lesson
- `'in_progress'`: Lesson has `StudentLessonProgress` with `status='in_progress'` but not current
- `'locked'`: Lesson not started and not the current lesson

### Priority Order:
1. Check `StudentLessonProgress.status == 'completed'` → `'completed'`
2. Check if lesson is `current_lesson` → `'current'`
3. Check `StudentLessonProgress.status == 'in_progress'` → `'in_progress'`
4. Check if lesson is first lesson (order=1) → `'current'`
5. Default → `'locked'`

---

## Benefits

### 1. **Performance**
- **Before**: 2 + N queries (N = number of lessons)
- **After**: 3 queries total (constant time)
- **Example**: 20 lessons = 22 queries → 3 queries (87% reduction)

### 2. **Accuracy**
- Uses actual `StudentLessonProgress` records
- No frontend inference needed
- Handles edge cases (out-of-order completion, etc.)

### 3. **Maintainability**
- Single source of truth (`StudentLessonProgress`)
- Clear status determination logic
- Easy to debug and test

### 4. **Scalability**
- Performance doesn't degrade with more lessons
- Works efficiently for courses with 100+ lessons

---

## Alternative Approaches Considered

### ❌ Option 1: Database Annotation
```python
# Using annotate() to add status in queryset
lessons = Lesson.objects.annotate(
    progress_status=Subquery(...)
)
```
**Problem**: Complex subquery, harder to maintain, less flexible

### ❌ Option 2: Property on Lesson Model
```python
# Add @property to Lesson model
@property
def status(self):
    # Query progress here
```
**Problem**: N+1 queries, called for each lesson individually

### ✅ Option 3: Bulk Prefetch (Our Solution)
**Advantages**: 
- Single query for all progress
- O(1) lookup in serializer
- Flexible and maintainable

---

## Migration Path

1. **Phase 1**: Implement bulk prefetch in view
2. **Phase 2**: Update `LessonListSerializer` to use `SerializerMethodField`
3. **Phase 3**: Test with existing data
4. **Phase 4**: Remove frontend inference logic (optional cleanup)

---

## Testing Checklist

- [ ] Test with course with 0 lessons
- [ ] Test with course with 1 lesson
- [ ] Test with course with 20+ lessons
- [ ] Test with no progress records (all locked)
- [ ] Test with some completed, some in progress
- [ ] Test with out-of-order completion
- [ ] Verify query count (should be 3 queries max)
- [ ] Test performance with 100+ lessons

---

## Summary

**The efficient solution uses:**
1. **Bulk Prefetch**: Load all progress in one query
2. **Context Mapping**: Pass status map through serializer context
3. **O(1) Lookup**: Dictionary lookup in serializer (no additional queries)

**Result**: Constant-time performance regardless of lesson count, accurate status from actual data, and no frontend inference needed.

