# Frontend Quiz & Assignment Creation with AI Dialog

This document provides example frontend code for creating quizzes and assignments with AI, including a dialog for configuring question counts.

## React/Next.js Example

### 1. Quiz Creation Component with AI Dialog

```tsx
import { useState } from 'react';
import { AIGenerateQuizDialog } from './AIGenerateQuizDialog';

interface QuizCreationButtonsProps {
  lessonId: string;
  materialIds: string[];
  onQuizCreated?: (quiz: any) => void;
  onManualCreate?: () => void;
}

export function QuizCreationButtons({ 
  lessonId, 
  materialIds, 
  onQuizCreated,
  onManualCreate 
}: QuizCreationButtonsProps) {
  const [showAIDialog, setShowAIDialog] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleAICreate = () => {
    setShowAIDialog(true);
  };

  const handleManualCreate = () => {
    if (onManualCreate) {
      onManualCreate();
    } else {
      // Navigate to manual quiz creation page
      window.location.href = `/lessons/${lessonId}/quizzes/create`;
    }
  };

  const handleAIGenerate = async (config: {
    totalQuestions: number;
    multipleChoiceCount: number;
    trueFalseCount: number;
  }) => {
    setIsGenerating(true);
    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/teacher/lessons/${lessonId}/ai/generate-quiz/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            material_ids: materialIds,
            total_questions: config.totalQuestions,
            multiple_choice_count: config.multipleChoiceCount,
            true_false_count: config.trueFalseCount,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to generate quiz');
      }

      const quiz = await response.json();
      setShowAIDialog(false);
      
      if (onQuizCreated) {
        onQuizCreated(quiz);
      }
    } catch (error) {
      console.error('Error generating quiz:', error);
      alert(error instanceof Error ? error.message : 'Failed to generate quiz');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <>
      <div className="flex gap-3">
        {/* Manual Create Button */}
        <button
          onClick={handleManualCreate}
          className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
        >
          Create Quiz
        </button>

        {/* AI Create Button */}
        <button
          onClick={handleAICreate}
          disabled={isGenerating || materialIds.length === 0}
          className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {isGenerating ? (
            <>
              <span className="animate-spin">⏳</span>
              Generating...
            </>
          ) : (
            <>
              <span>✨</span>
              Create Quiz with AI
            </>
          )}
        </button>
      </div>

      {/* AI Generation Dialog */}
      {showAIDialog && (
        <AIGenerateQuizDialog
          isOpen={showAIDialog}
          onClose={() => setShowAIDialog(false)}
          onGenerate={handleAIGenerate}
          isGenerating={isGenerating}
        />
      )}
    </>
  );
}
```

### 2. AI Quiz Generation Dialog Component

```tsx
// AIGenerateQuizDialog.tsx
import { useState, useEffect } from 'react';

interface AIGenerateQuizDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onGenerate: (config: {
    totalQuestions: number;
    multipleChoiceCount: number;
    trueFalseCount: number;
  }) => void;
  isGenerating: boolean;
}

export function AIGenerateQuizDialog({
  isOpen,
  onClose,
  onGenerate,
  isGenerating,
}: AIGenerateQuizDialogProps) {
  // Default values: 10 total, 7 multiple choice, 3 true/false
  const [totalQuestions, setTotalQuestions] = useState(10);
  const [multipleChoiceCount, setMultipleChoiceCount] = useState(7);
  const [trueFalseCount, setTrueFalseCount] = useState(3);

  // Auto-update counts when total changes
  useEffect(() => {
    const ratio = totalQuestions / 10; // Original total
    setMultipleChoiceCount(Math.round(7 * ratio));
    setTrueFalseCount(totalQuestions - Math.round(7 * ratio));
  }, [totalQuestions]);

  // Ensure counts add up to total
  useEffect(() => {
    const sum = multipleChoiceCount + trueFalseCount;
    if (sum !== totalQuestions) {
      // Adjust true/false to match total
      setTrueFalseCount(totalQuestions - multipleChoiceCount);
    }
  }, [multipleChoiceCount, totalQuestions]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGenerate({
      totalQuestions,
      multipleChoiceCount,
      trueFalseCount,
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl">
        <h2 className="text-2xl font-bold mb-4">Generate Quiz with AI</h2>
        <p className="text-gray-600 mb-6">
          Configure the number and types of questions to generate.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Total Questions */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Total Questions
            </label>
            <input
              type="number"
              min="1"
              max="50"
              value={totalQuestions}
              onChange={(e) => setTotalQuestions(parseInt(e.target.value) || 1)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              required
            />
          </div>

          {/* Multiple Choice Count */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Multiple Choice Questions
            </label>
            <input
              type="number"
              min="0"
              max={totalQuestions}
              value={multipleChoiceCount}
              onChange={(e) => {
                const value = parseInt(e.target.value) || 0;
                setMultipleChoiceCount(Math.min(value, totalQuestions));
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              {multipleChoiceCount} of {totalQuestions} questions
            </p>
          </div>

          {/* True/False Count */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              True/False Questions
            </label>
            <input
              type="number"
              min="0"
              max={totalQuestions}
              value={trueFalseCount}
              onChange={(e) => {
                const value = parseInt(e.target.value) || 0;
                setTrueFalseCount(Math.min(value, totalQuestions));
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              {trueFalseCount} of {totalQuestions} questions
            </p>
          </div>

          {/* Summary */}
          <div className="bg-purple-50 p-3 rounded-lg">
            <p className="text-sm text-purple-800">
              <strong>Summary:</strong> {totalQuestions} total questions
              ({multipleChoiceCount} multiple choice, {trueFalseCount} true/false)
            </p>
            {multipleChoiceCount + trueFalseCount !== totalQuestions && (
              <p className="text-xs text-red-600 mt-1">
                ⚠️ Counts don't match total. Adjusting automatically.
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isGenerating}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isGenerating || multipleChoiceCount + trueFalseCount !== totalQuestions}
              className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGenerating ? 'Generating...' : 'Generate Quiz'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

### 3. Assignment Creation Component (Similar Structure)

```tsx
// AIGenerateAssignmentDialog.tsx
import { useState, useEffect } from 'react';

interface AIGenerateAssignmentDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onGenerate: (config: {
    totalQuestions: number;
    essayCount: number;
    fillBlankCount: number;
  }) => void;
  isGenerating: boolean;
}

export function AIGenerateAssignmentDialog({
  isOpen,
  onClose,
  onGenerate,
  isGenerating,
}: AIGenerateAssignmentDialogProps) {
  // Default values: 5 total, 2 essay, 3 fill-in-the-blank
  const [totalQuestions, setTotalQuestions] = useState(5);
  const [essayCount, setEssayCount] = useState(2);
  const [fillBlankCount, setFillBlankCount] = useState(3);

  // Auto-update counts when total changes
  useEffect(() => {
    const ratio = totalQuestions / 5; // Original total
    setEssayCount(Math.round(2 * ratio));
    setFillBlankCount(totalQuestions - Math.round(2 * ratio));
  }, [totalQuestions]);

  // Ensure counts add up to total
  useEffect(() => {
    const sum = essayCount + fillBlankCount;
    if (sum !== totalQuestions) {
      setFillBlankCount(totalQuestions - essayCount);
    }
  }, [essayCount, totalQuestions]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGenerate({
      totalQuestions,
      essayCount,
      fillBlankCount,
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl">
        <h2 className="text-2xl font-bold mb-4">Generate Assignment with AI</h2>
        <p className="text-gray-600 mb-6">
          Configure the number and types of questions to generate.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Total Questions */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Total Questions
            </label>
            <input
              type="number"
              min="1"
              max="30"
              value={totalQuestions}
              onChange={(e) => setTotalQuestions(parseInt(e.target.value) || 1)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
              required
            />
          </div>

          {/* Essay Count */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Essay Questions
            </label>
            <input
              type="number"
              min="0"
              max={totalQuestions}
              value={essayCount}
              onChange={(e) => {
                const value = parseInt(e.target.value) || 0;
                setEssayCount(Math.min(value, totalQuestions));
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              {essayCount} of {totalQuestions} questions
            </p>
          </div>

          {/* Fill-in-the-Blank Count */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Fill-in-the-Blank Questions
            </label>
            <input
              type="number"
              min="0"
              max={totalQuestions}
              value={fillBlankCount}
              onChange={(e) => {
                const value = parseInt(e.target.value) || 0;
                setFillBlankCount(Math.min(value, totalQuestions));
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              {fillBlankCount} of {totalQuestions} questions
            </p>
          </div>

          {/* Summary */}
          <div className="bg-purple-50 p-3 rounded-lg">
            <p className="text-sm text-purple-800">
              <strong>Summary:</strong> {totalQuestions} total questions
              ({essayCount} essay, {fillBlankCount} fill-in-the-blank)
            </p>
            {essayCount + fillBlankCount !== totalQuestions && (
              <p className="text-xs text-red-600 mt-1">
                ⚠️ Counts don't match total. Adjusting automatically.
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isGenerating}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isGenerating || essayCount + fillBlankCount !== totalQuestions}
              className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              {isGenerating ? 'Generating...' : 'Generate Assignment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

### 4. Assignment Creation Buttons Component

```tsx
import { useState } from 'react';
import { AIGenerateAssignmentDialog } from './AIGenerateAssignmentDialog';

interface AssignmentCreationButtonsProps {
  lessonId: string;
  materialIds: string[];
  onAssignmentCreated?: (assignment: any) => void;
  onManualCreate?: () => void;
}

export function AssignmentCreationButtons({ 
  lessonId, 
  materialIds, 
  onAssignmentCreated,
  onManualCreate 
}: AssignmentCreationButtonsProps) {
  const [showAIDialog, setShowAIDialog] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleAIGenerate = async (config: {
    totalQuestions: number;
    essayCount: number;
    fillBlankCount: number;
  }) => {
    setIsGenerating(true);
    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/teacher/lessons/${lessonId}/ai/generate-assignment/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            material_ids: materialIds,
            total_questions: config.totalQuestions,
            essay_count: config.essayCount,
            fill_blank_count: config.fillBlankCount,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to generate assignment');
      }

      const assignment = await response.json();
      setShowAIDialog(false);
      
      if (onAssignmentCreated) {
        onAssignmentCreated(assignment);
      }
    } catch (error) {
      console.error('Error generating assignment:', error);
      alert(error instanceof Error ? error.message : 'Failed to generate assignment');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <>
      <div className="flex gap-3">
        <button
          onClick={() => onManualCreate?.()}
          className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
        >
          Create Assignment
        </button>
        <button
          onClick={() => setShowAIDialog(true)}
          disabled={isGenerating || materialIds.length === 0}
          className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
        >
          {isGenerating ? 'Generating...' : '✨ Create Assignment with AI'}
        </button>
      </div>

      {showAIDialog && (
        <AIGenerateAssignmentDialog
          isOpen={showAIDialog}
          onClose={() => setShowAIDialog(false)}
          onGenerate={handleAIGenerate}
          isGenerating={isGenerating}
        />
      )}
    </>
  );
}
```

## API Request Format

### Quiz Generation
```json
POST /api/teacher/lessons/{lesson_id}/ai/generate-quiz/
{
  "material_ids": ["uuid1", "uuid2"],
  "total_questions": 10,
  "multiple_choice_count": 7,
  "true_false_count": 3
}
```

### Assignment Generation
```json
POST /api/teacher/lessons/{lesson_id}/ai/generate-assignment/
{
  "material_ids": ["uuid1", "uuid2"],
  "total_questions": 5,
  "essay_count": 2,
  "fill_blank_count": 3
}
```

## Features

1. **Two Buttons**: Manual creation and AI generation
2. **Configurable Dialog**: Teachers can adjust question counts
3. **Auto-validation**: Ensures counts add up correctly
4. **Default Values**: 
   - Quiz: 10 total (7 MC, 3 T/F)
   - Assignment: 5 total (2 essay, 3 fill-in-the-blank)
5. **Loading States**: Shows progress during generation
6. **Error Handling**: Graceful error messages

