# Frontend Video Transcription with SWR and Skeleton UI

This document provides example frontend code for implementing video transcription with SWR (stale-while-revalidate) and skeleton loading UI.

## React/Next.js Example

### 1. Install Dependencies

```bash
npm install swr
# or
yarn add swr
```

### 2. Video Transcription Component with SWR

```tsx
import { useState } from 'react';
import useSWR from 'swr';
import { VideoTranscribeSkeleton } from './VideoTranscribeSkeleton';

interface VideoMaterial {
  id: string;
  video_url: string;
  transcript?: string;
  has_transcript: boolean;
  language?: string;
  language_name?: string;
  method_used?: string;
  word_count?: number;
}

interface TranscribeResponse {
  video_material: VideoMaterial;
  has_transcript: boolean;
  is_transcribing: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Fetcher function for SWR
const fetcher = async (url: string) => {
  const token = localStorage.getItem('authToken'); // Adjust based on your auth setup
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch');
  }
  
  return response.json();
};

export function VideoTranscribeForm({ videoMaterialId }: { videoMaterialId: string }) {
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // SWR hook - automatically revalidates and shows stale data
  const { data, error: swrError, mutate, isLoading } = useSWR<TranscribeResponse>(
    `${API_BASE}/api/teacher/video-materials/${videoMaterialId}/transcribe/`,
    fetcher,
    {
      // SWR configuration for stale-while-revalidate
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2000, // Dedupe requests within 2 seconds
      // Show stale data immediately while revalidating
      keepPreviousData: true,
    }
  );

  const handleTranscribe = async () => {
    setIsTranscribing(true);
    setError(null);

    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch(
        `${API_BASE}/api/teacher/video-materials/${videoMaterialId}/transcribe/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            language_codes: ['en', 'en-US'], // Optional
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to transcribe video');
      }

      const result = await response.json();
      
      // Update SWR cache with new data
      await mutate({
        video_material: result.video_material,
        has_transcript: true,
        is_transcribing: false,
      }, false); // false = don't revalidate immediately, we just got fresh data
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsTranscribing(false);
    }
  };

  // Show skeleton while loading (first time)
  if (isLoading && !data) {
    return <VideoTranscribeSkeleton />;
  }

  // Show error state
  if (swrError || error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-red-800">
          {error || 'Failed to load video material'}
        </p>
        <button
          onClick={() => mutate()}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const videoMaterial = data?.video_material;
  const hasTranscript = data?.has_transcript || videoMaterial?.has_transcript;

  return (
    <div className="space-y-4">
      {/* Video Info */}
      <div className="p-4 bg-gray-50 rounded-lg">
        <h3 className="font-semibold text-lg mb-2">Video Information</h3>
        <p className="text-sm text-gray-600">
          <strong>URL:</strong> {videoMaterial?.video_url}
        </p>
        {videoMaterial?.method_used && (
          <p className="text-sm text-gray-600 mt-1">
            <strong>Method:</strong> {videoMaterial.method_used === 'youtube_api' ? 'YouTube API' : 'Vertex AI'}
          </p>
        )}
      </div>

      {/* Transcript Section */}
      <div className="p-4 border rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-lg">Transcript</h3>
          {hasTranscript && videoMaterial?.word_count && (
            <span className="text-sm text-gray-500">
              {videoMaterial.word_count} words
            </span>
          )}
        </div>

        {/* Show skeleton while transcribing */}
        {isTranscribing ? (
          <VideoTranscribeSkeleton />
        ) : hasTranscript && videoMaterial?.transcript ? (
          <div className="space-y-2">
            {videoMaterial.language_name && (
              <p className="text-sm text-gray-500">
                Language: {videoMaterial.language_name}
              </p>
            )}
            <div className="p-3 bg-gray-50 rounded border max-h-96 overflow-y-auto">
              <p className="text-sm whitespace-pre-wrap">
                {videoMaterial.transcript}
              </p>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <p>No transcript available</p>
            <button
              onClick={handleTranscribe}
              disabled={isTranscribing}
              className="mt-4 px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isTranscribing ? 'Transcribing...' : 'Transcribe Video'}
            </button>
          </div>
        )}
      </div>

      {/* SWR Status Indicator (optional, for debugging) */}
      {data && (
        <div className="text-xs text-gray-400 text-center">
          {isLoading ? 'Revalidating...' : 'Up to date'}
        </div>
      )}
    </div>
  );
}
```

### 3. Skeleton Loading Component

```tsx
// VideoTranscribeSkeleton.tsx
export function VideoTranscribeSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Video Info Skeleton */}
      <div className="p-4 bg-gray-50 rounded-lg">
        <div className="h-5 bg-gray-200 rounded w-1/4 mb-3"></div>
        <div className="h-4 bg-gray-200 rounded w-3/4"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2 mt-2"></div>
      </div>

      {/* Transcript Section Skeleton */}
      <div className="p-4 border rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <div className="h-6 bg-gray-200 rounded w-1/4"></div>
          <div className="h-4 bg-gray-200 rounded w-20"></div>
        </div>
        
        <div className="space-y-2">
          <div className="h-4 bg-gray-200 rounded w-32"></div>
          <div className="p-3 bg-gray-50 rounded border space-y-2">
            <div className="h-4 bg-gray-200 rounded w-full"></div>
            <div className="h-4 bg-gray-200 rounded w-full"></div>
            <div className="h-4 bg-gray-200 rounded w-5/6"></div>
            <div className="h-4 bg-gray-200 rounded w-4/6"></div>
            <div className="h-4 bg-gray-200 rounded w-full"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

### 4. Tailwind CSS Configuration (if using Tailwind)

Make sure you have Tailwind configured. The skeleton uses Tailwind classes. If not using Tailwind, replace with your CSS framework or custom styles.

## Key Features

1. **SWR Stale-While-Revalidate**: Shows cached/stale data immediately while fetching fresh data in the background
2. **Skeleton UI**: Shows loading placeholders instead of blank screens
3. **Error Handling**: Graceful error states with retry functionality
4. **Optimistic Updates**: Updates UI immediately after transcription completes
5. **Cache Headers**: Backend sends proper cache headers for optimal SWR behavior

## API Endpoints Used

- `GET /api/teacher/video-materials/{id}/transcribe/` - Get current transcript status (for SWR)
- `POST /api/teacher/video-materials/{id}/transcribe/` - Trigger transcription

## Benefits

- **Better UX**: Users see content immediately (stale data) while fresh data loads
- **Reduced Loading States**: Skeleton UI provides visual feedback
- **Automatic Revalidation**: SWR automatically refetches when window regains focus
- **Deduplication**: Multiple components requesting same data only trigger one request

