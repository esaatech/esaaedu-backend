"""
VideoTranscriptionService - Service for transcribing YouTube and video content

This service extracts text transcripts from YouTube videos and other video sources.
It can be used to get text content from videos for quiz/assignment generation.

Usage:
    from ai.video_transcription_service import VideoTranscriptionService
    
    service = VideoTranscriptionService()
    
    # Transcribe YouTube video
    transcript = service.transcribe_youtube("https://www.youtube.com/watch?v=VIDEO_ID")
    
    # Or transcribe any video URL
    transcript = service.transcribe_video("https://example.com/video.mp4")
"""
import logging
import re
import sys
import os
from typing import Optional, Dict, Any

# Handle both module import and direct execution
try:
    from .gemini_service import GeminiService
except ImportError:
    # If running as script, add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ai.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class VideoTranscriptionService:
    """
    Service for transcribing video content (YouTube and other sources).
    
    Uses youtube-transcript-api for YouTube videos (fastest method).
    Falls back to Vertex AI Gemini for other video sources or when transcripts unavailable.
    """
    
    def __init__(self):
        """Initialize the service"""
        self.gemini_service = GeminiService()
        logger.info("VideoTranscriptionService initialized")
    
    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL"""
        if not url:
            return False
        youtube_patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'youtube\.com/embed/',
            r'youtube\.com/v/'
        ]
        return any(re.search(pattern, url) for pattern in youtube_patterns)
    
    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        if not url:
            return None
        
        patterns = [
            r'youtube\.com/watch\?v=([^&]+)',
            r'youtu\.be/([^?]+)',
            r'youtube\.com/embed/([^?]+)',
            r'youtube\.com/v/([^?]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def transcribe_youtube(self, youtube_url: str, language_codes: Optional[list] = None) -> Dict[str, Any]:
        """
        Transcribe YouTube video using youtube-transcript-api.
        
        This is the fastest method as it directly fetches available transcripts
        from YouTube without downloading or processing video.
        
        Args:
            youtube_url: YouTube video URL
            language_codes: Optional list of language codes to try (e.g., ['en', 'en-US'])
                           Defaults to ['en'] if not provided
            
        Returns:
            Dictionary with:
            {
                'transcript': str,  # Full transcript text
                'success': bool,
                'method': str,  # 'youtube_api' or 'vertex_ai'
                'error': Optional[str]
            }
        """
        if not youtube_url:
            raise ValueError("youtube_url is required")
        
        if not self._is_youtube_url(youtube_url):
            raise ValueError(f"Invalid YouTube URL: {youtube_url}")
        
        video_id = self._extract_youtube_id(youtube_url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {youtube_url}")
        
        # Use youtube-transcript-api - simple fetch() method
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript
            
            # Default to English, but also try common languages
            if language_codes is None:
                # Try English first, then common languages
                language_codes = ['en', 'en-US', 'es', 'fr', 'de', 'it', 'pt']
            
            # Create API instance and fetch transcript
            api_instance = YouTubeTranscriptApi()
            
            try:
                # Use fetch() method - tries languages in order of priority
                fetched_transcript = api_instance.fetch(video_id, languages=language_codes)
                
                # Extract text from FetchedTranscript object (it's iterable)
                transcript_text_parts = []
                for snippet in fetched_transcript:
                    transcript_text_parts.append(snippet.text)
                
                transcript_text = ' '.join(transcript_text_parts)
                
                logger.info(f"Successfully transcribed YouTube video {video_id} using YouTube API (language: {fetched_transcript.language_code})")
                
                return {
                    'transcript': transcript_text,
                    'success': True,
                    'method': 'youtube_api',
                    'video_id': video_id,
                    'language': fetched_transcript.language_code,
                    'error': None
                }
                
            except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript) as e:
                logger.warning(f"YouTube transcript not available for {video_id}: {e}")
                logger.info("Falling back to Vertex AI transcription...")
                # Fall back to Vertex AI
                return self._transcribe_with_vertex_ai(youtube_url, video_id)
                
        except ImportError:
            logger.warning("youtube-transcript-api not installed, falling back to Vertex AI")
            # Fall back to Vertex AI if library not available
            return self._transcribe_with_vertex_ai(youtube_url, video_id)
        
        except Exception as e:
            logger.error(f"Error using YouTube transcript API: {e}", exc_info=True)
            logger.info("Falling back to Vertex AI transcription...")
            # Fall back to Vertex AI
            return self._transcribe_with_vertex_ai(youtube_url, video_id)
    
    def _transcribe_with_vertex_ai(self, video_url: str, video_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe video using Vertex AI Gemini (fallback method).
        
        This method uses Vertex AI's video processing capabilities to extract
        text from video content.
        
        Args:
            video_url: Video URL
            video_id: Optional video ID for logging
            
        Returns:
            Dictionary with transcript and metadata
        """
        try:
            from vertexai.generative_models import Part, GenerativeModel
            from google.api_core import exceptions as google_exceptions
            
            logger.info(f"Transcribing video with Vertex AI: {video_url}")
            
            # Get model
            model = self.gemini_service._get_model(
                system_instruction="You are a video transcription assistant. Extract and transcribe all spoken words and important text from the video. Return only the transcript text, no additional commentary."
            )
            
            # Create video part
            video_part = Part.from_uri(
                uri=video_url,
                mime_type="video/*"
            )
            
            # Generate transcript
            prompt = "Please transcribe all spoken words and important text from this video. Return only the transcript text, formatted clearly."
            
            response = model.generate_content(
                [prompt, video_part],
                generation_config={
                    'temperature': 0.1,  # Low temperature for accurate transcription
                    'max_output_tokens': 8192  # Increase max tokens to avoid truncation
                }
            )
            
            # Handle potential truncation - check if response was cut off
            transcript_text = response.text if hasattr(response, 'text') else str(response)
            
            # Log transcript length for debugging
            logger.info(f"Successfully transcribed video using Vertex AI (length: {len(transcript_text)} chars)")
            
            return {
                'transcript': transcript_text,
                'success': True,
                'method': 'vertex_ai',
                'video_id': video_id,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error transcribing with Vertex AI: {e}", exc_info=True)
            return {
                'transcript': '',
                'success': False,
                'method': 'vertex_ai',
                'video_id': video_id,
                'error': str(e)
            }
    
    def transcribe_video(self, video_url: str, language_codes: Optional[list] = None) -> Dict[str, Any]:
        """
        Transcribe any video URL (YouTube or other).
        
        For YouTube URLs, tries YouTube Transcript API first, then falls back to Vertex AI.
        For non-YouTube URLs, uses Vertex AI directly.
        
        Args:
            video_url: Video URL (YouTube or other)
            language_codes: Optional language codes for YouTube videos
            
        Returns:
            Dictionary with transcript and metadata
        """
        if not video_url:
            raise ValueError("video_url is required")
        
        # Check if it's a YouTube URL
        if self._is_youtube_url(video_url):
            return self.transcribe_youtube(video_url, language_codes)
        else:
            # For non-YouTube videos, use Vertex AI directly
            logger.info(f"Non-YouTube video URL detected, using Vertex AI: {video_url}")
            return self._transcribe_with_vertex_ai(video_url)
    
    def test(self):
        """
        Test function for the transcription service.
        
        Can be called directly:
        - From Django shell: VideoTranscriptionService().test()
        - From command line: python -m ai.video_transcription_service
        """
        print("\n" + "="*60)
        print("🧪 Testing VideoTranscriptionService")
        print("="*60)
        
        if not self.gemini_service.project_id:
            print("❌ GCP_PROJECT_ID not set!")
            print("   Set it in your .env file or environment variables")
            return
        
        print(f"✅ Project ID: {self.gemini_service.project_id}")
        print(f"✅ Location: {self.gemini_service.location}")
        print(f"✅ Model: {self.gemini_service.model_name}")
        print()
        
        # Test with a sample YouTube URL
        print("📝 Testing YouTube transcription...")
        print("   (Using a short educational video for testing)")
        print()
        
        # Use a well-known short educational video for testing
        # Example: A short Python tutorial video
        test_url = input("Enter YouTube URL to test (or press Enter for default): ").strip()
        
        if not test_url:
            print("⚠️  No URL provided. Please provide a YouTube URL to test.")
            print("   Example: https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            return
        
        try:
            print(f"\n🔍 Processing: {test_url}")
            print("   This may take a moment...")
            print()
            
            result = self.transcribe_video(test_url)
            
            if result['success']:
                print("✅ Transcription successful!")
                method = result['method']
                print(f"   Method used: {method}")
                
                # Verify we're using YouTube API first (not Vertex AI)
                if method == 'youtube_api':
                    print("   ✅ Correctly using YouTube Transcript API (fast method)")
                elif method == 'vertex_ai':
                    print("   ⚠️  Using Vertex AI fallback (slower method)")
                    print("   ⚠️  This means YouTube Transcript API was not available")
                
                if result.get('video_id'):
                    print(f"   Video ID: {result['video_id']}")
                if result.get('language'):
                    print(f"   Language: {result['language']}")
                print()
                print("📄 Transcript:")
                print("-" * 60)
                transcript = result['transcript']
                # Show first 500 characters
                if len(transcript) > 500:
                    print(transcript[:500])
                    print(f"\n... (truncated, total length: {len(transcript)} characters)")
                else:
                    print(transcript)
                print("-" * 60)
                print()
                print(f"📊 Transcript length: {len(transcript)} characters")
                print(f"📊 Word count: {len(transcript.split())} words")
            else:
                print(f"❌ Transcription failed: {result.get('error', 'Unknown error')}")
                print(f"   Method attempted: {result.get('method', 'unknown')}")
            
            print()
            print("="*60)
            print("✅ Test completed!")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            print()
            print("="*60)
            print("❌ Test failed")
            print("="*60)


if __name__ == "__main__":
    # Allow running as a script for testing
    import os
    import django
    import sys
    
    # Get the backend directory (parent of 'ai' directory)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Add backend directory to Python path BEFORE Django setup
    # This ensures Django can find the 'backend' module
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    
    # Setup Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    service = VideoTranscriptionService()
    service.test()

