# HLS Video Playback – Frontend Integration

## Overview

Teacher-uploaded videos are now stored as **HLS (HTTP Live Streaming)**. The API returns a **playlist URL** (`.m3u8`) instead of a direct video file URL (e.g. `.mp4`). The frontend must use an HLS-capable player to play these URLs; a plain `<video src="...">` will not work for `.m3u8` in most browsers.

## Where the video URL comes from

- **Lesson video:** `Lesson.video_url` or the lesson payload’s `video_url` (for `video_audio` lessons).
- **Lesson material (audio/video):** `LessonMaterial.file_url` or the material payload’s `file_url`.

For teacher-uploaded videos, these URLs now point to the HLS playlist, for example:

- `https://storage.googleapis.com/<bucket>/hls/audio-video/<uuid>/playlist.m3u8`

Audio-only uploads and external links (e.g. YouTube) are unchanged and still use non-HLS URLs.

## Detecting HLS URLs

Treat a URL as HLS when:

- It ends with **`.m3u8`**, or  
- The response (or your own convention) indicates an HLS playlist.

Example:

```ts
function isHlsUrl(url: string): boolean {
  return typeof url === 'string' && url.trim().toLowerCase().endsWith('.m3u8');
}
```

Use this to choose between “HLS player” and “normal video/audio” (e.g. `<video src={url}>` or an iframe for YouTube).

## Playing HLS in the browser

- **Safari (iOS/macOS):** Native HLS support; you can use `<video src={playlistUrl} />` for `.m3u8`.
- **Chrome, Firefox, Edge, etc.:** No native HLS support; you need a JS library. **hls.js** is the standard choice.

### Option 1: hls.js (recommended for cross-browser)

1. Install: `npm install hls.js` (or use a script tag from a CDN).
2. Use a single `<video>` element; do **not** set `video.src` to the playlist URL. Instead, create an `Hls` instance and attach the playlist URL to it.

**Example (React):**

```tsx
import Hls from 'hls.js';

function VideoPlayer({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!src || !videoRef.current) return;

    const video = videoRef.current;

    if (Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(src);
      hls.attachMedia(video);
      return () => hls.destroy();
    }

    // Safari and other native HLS
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src;
      return;
    }

    // Fallback: not HLS or not supported (e.g. plain MP4)
    video.src = src;
  }, [src]);

  return <video ref={videoRef} controls playsInline />;
}
```

**Usage:** Use this component when `isHlsUrl(src)` is true; use a normal `<video src={url}>` (or your existing player) for non-HLS URLs.

### Option 2: Video.js with videojs-http-streaming

If you already use Video.js, enable **videojs-http-streaming** (VHS) so it can play HLS. Then set the source to the `.m3u8` URL (e.g. `{ src: url, type: 'application/vnd.apple.mpegurl' }`).

## End-to-end flow

1. Get the media URL from the API (e.g. `lesson.video_url` or `material.file_url`).
2. If `isHlsUrl(url)`:
   - Render your HLS player (e.g. the hls.js-based component above).
   - Pass the **same URL** (the `.m3u8` playlist) to the player; it will load segments automatically.
3. If not HLS (e.g. `.mp4`, YouTube, or audio):
   - Keep using your current `<video>` or audio player as before.

## CORS and cookies

Playlist and segment URLs are on Google Cloud Storage and are **public**. No auth or cookies are required for playback. If you see CORS errors, they are from GCS; the backend does not serve the video bytes itself.

## Summary

| Backend sends        | Frontend action                                      |
|----------------------|------------------------------------------------------|
| URL ending in `.m3u8`| Use HLS player (hls.js or native Safari `<video>`)   |
| Other video/audio URL| Use normal `<video>` or existing player              |

Using the playlist URL in an HLS-capable player (e.g. with hls.js) will fix “video not working” for teacher-uploaded videos.
