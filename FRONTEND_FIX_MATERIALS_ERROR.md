# Frontend Fix: materials.map is not a function

## Problem
The API returns materials in this structure:
```json
{
  "lesson_id": "...",
  "lesson_title": "...",
  "materials": [...],  // Array is here
  "total_count": 5
}
```

But your frontend code is trying to call `.map()` directly on the response, not on `response.materials`.

## Solution

### Fix 1: Correct Data Access

In your `GenerateQuizAssignmentDialog.tsx`, update the materials loading:

```tsx
// ❌ WRONG - This causes the error
const loadMaterials = async () => {
  const response = await fetch(...);
  const data = await response.json();
  const materialsList = data.map(...);  // ERROR: data is an object, not array
};

// ✅ CORRECT - Access the materials array
const loadMaterials = async () => {
  try {
    const response = await fetch(
      `${API_URL}/api/courses/lessons/${lessonId}/materials/`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    );
    
    if (!response.ok) {
      throw new Error('Failed to load materials');
    }
    
    const data = await response.json();
    
    // ✅ Access the materials array from the response
    const materialsList = Array.isArray(data.materials) 
      ? data.materials 
      : [];
    
    setMaterials(materialsList);
  } catch (error) {
    console.error('Failed to load materials:', error);
    setMaterials([]); // Set empty array on error
  }
};
```

### Fix 2: Add Safety Checks

Always check if materials is an array before using `.map()`:

```tsx
// In your component render
const materialsToDisplay = Array.isArray(materials) ? materials : [];

return (
  <div>
    {materialsToDisplay.map((material) => (
      // ... render material
    ))}
  </div>
);
```

### Fix 3: Two Buttons Implementation

Update your component to have TWO buttons:

```tsx
// In CourseManagement.tsx or wherever you have the quiz creation
<div className="flex gap-3">
  {/* Manual Create Button */}
  <button
    onClick={() => {
      // Navigate to manual quiz creation
      navigate(`/lessons/${lessonId}/quizzes/create`);
    }}
    className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
  >
    Create Quiz
  </button>

  {/* AI Create Button */}
  <button
    onClick={() => setShowAIDialog(true)}
    className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2"
  >
    <span>✨</span>
    Create Quiz with AI
  </button>
</div>
```

## Complete Fixed Example

```tsx
// GenerateQuizAssignmentDialog.tsx - Fixed version
import { useState, useEffect } from 'react';

export function GenerateQuizAssignmentDialog({ lessonId, isOpen, onClose, onGenerate }) {
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Question configuration
  const [totalQuestions, setTotalQuestions] = useState(10);
  const [multipleChoiceCount, setMultipleChoiceCount] = useState(7);
  const [trueFalseCount, setTrueFalseCount] = useState(3);

  // Load materials when dialog opens
  useEffect(() => {
    if (isOpen && lessonId) {
      loadMaterials();
    }
  }, [isOpen, lessonId]);

  const loadMaterials = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/courses/lessons/${lessonId}/materials/`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to load materials');
      }

      const data = await response.json();
      
      // ✅ FIX: Access materials array from response
      const materialsList = Array.isArray(data.materials) 
        ? data.materials 
        : [];
      
      setMaterials(materialsList);
    } catch (err) {
      console.error('Failed to load materials:', err);
      setError(err.message);
      setMaterials([]); // Set empty array on error
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl shadow-xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4">Generate Quiz with AI</h2>

        {/* Materials Selection */}
        <div className="mb-6">
          <h3 className="font-semibold mb-3">Select Materials</h3>
          
          {loading && <p>Loading materials...</p>}
          {error && <p className="text-red-600">Error: {error}</p>}
          
          {/* ✅ FIX: Always check if array before mapping */}
          {!loading && !error && Array.isArray(materials) && materials.length > 0 ? (
            <div className="space-y-2 max-h-40 overflow-y-auto border p-3 rounded">
              {materials.map((material) => (
                <label key={material.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    value={material.id}
                    className="rounded"
                  />
                  <span>{material.title} ({material.material_type})</span>
                </label>
              ))}
            </div>
          ) : !loading && !error ? (
            <p className="text-gray-500">No materials available for this lesson</p>
          ) : null}
        </div>

        {/* Question Configuration */}
        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-sm font-medium mb-2">
              Total Questions
            </label>
            <input
              type="number"
              min="1"
              max="50"
              value={totalQuestions}
              onChange={(e) => setTotalQuestions(parseInt(e.target.value) || 1)}
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Multiple Choice
            </label>
            <input
              type="number"
              min="0"
              max={totalQuestions}
              value={multipleChoiceCount}
              onChange={(e) => setMultipleChoiceCount(parseInt(e.target.value) || 0)}
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              True/False
            </label>
            <input
              type="number"
              min="0"
              max={totalQuestions}
              value={trueFalseCount}
              onChange={(e) => setTrueFalseCount(parseInt(e.target.value) || 0)}
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              const selectedMaterials = Array.from(
                document.querySelectorAll('input[type="checkbox"]:checked')
              ).map(cb => cb.value);
              
              onGenerate({
                material_ids: selectedMaterials,
                total_questions: totalQuestions,
                multiple_choice_count: multipleChoiceCount,
                true_false_count: trueFalseCount,
              });
            }}
            className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg"
          >
            Generate Quiz
          </button>
        </div>
      </div>
    </div>
  );
}
```

## Key Points

1. **Always access `data.materials`** not just `data`
2. **Use `Array.isArray()` check** before calling `.map()`
3. **Set empty array `[]` as fallback** if materials is not an array
4. **Two buttons**: "Create Quiz" (manual) and "Create Quiz with AI" (opens dialog)

## API Response Structure

The materials endpoint returns:
```json
{
  "lesson_id": "uuid",
  "lesson_title": "Lesson Title",
  "materials": [
    {
      "id": "uuid",
      "title": "Material Title",
      "material_type": "video",
      ...
    }
  ],
  "total_count": 5
}
```

So always use `response.materials` or `data.materials` to get the array.

