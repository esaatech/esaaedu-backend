# GeminiImageService Documentation

## Overview

`GeminiImageService` provides image generation capabilities using Google Vertex AI's Imagen API. This service follows the same architectural pattern as `GeminiService` for consistency across the codebase.

## Features

- **Text-to-Image Generation**: Generate images from natural language prompts
- **Configurable Aspect Ratios**: Support for multiple aspect ratios (1:1, 9:16, 16:9, 4:3, 3:4)
- **Multiple Image Generation**: Generate 1-4 images per request
- **Safety Controls**: Configurable safety filter levels and person generation settings
- **Negative Prompts**: Specify what to avoid in generated images
- **Reproducible Results**: Optional seed parameter for consistent outputs

## Model Information

- **Default Model**: `imagegeneration@006` (Imagen 3)
- **Note**: "Nano Banana" (Gemini 2.5 Flash Image) and "Nano Banana Pro" (Gemini 3.0 Pro Image) are consumer-facing names that use Imagen technology. For Vertex AI, use `imagegeneration@006` or check for newer versions.

## Configuration

### Environment Variables

The service reads configuration from environment variables:

- `GCP_PROJECT_ID`: Google Cloud project ID (required)
- `VERTEX_AI_LOCATION`: Region (default: `us-central1`)
- `IMAGEN_MODEL`: Model name (default: `imagegeneration@006`)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON (optional)

### Example `.env` Configuration

```env
GCP_PROJECT_ID=your-project-id
VERTEX_AI_LOCATION=us-central1
IMAGEN_MODEL=imagegeneration@006
GOOGLE_APPLICATION_CREDENTIALS=.credentials/vertex-ai-service-account.json
```

## Usage

### Basic Usage

```python
from ai.gemini_image_service import GeminiImageService

# Initialize the service
service = GeminiImageService()

# Generate a single image
result = service.generate_image(
    prompt="A beautiful sunset over mountains",
    number_of_images=1,
    aspect_ratio="16:9"
)

# Access the generated image
image_bytes = result['images'][0]

# Save to file
service.save_image(image_bytes, "generated_image.png")
```

### Advanced Usage

```python
from ai.gemini_image_service import GeminiImageService

service = GeminiImageService()

# Generate multiple images with specific settings
result = service.generate_image(
    prompt="A serene landscape with mountains and a lake",
    number_of_images=2,
    aspect_ratio="16:9",
    negative_prompt="people, buildings, vehicles",
    safety_filter_level="block_some",
    person_generation="dont_allow",
    seed=42  # For reproducible results
)

# Process all generated images
for i, image_bytes in enumerate(result['images']):
    service.save_image(image_bytes, f"image_{i+1}.png")
```

## API Reference

### `generate_image()`

Generate image(s) from a text prompt.

#### Parameters

- `prompt` (str, required): Text description of the image to generate
- `number_of_images` (int, default: 1): Number of images to generate (1-4)
- `aspect_ratio` (str, default: "1:1"): Aspect ratio for the image
  - Supported: `"1:1"`, `"9:16"`, `"16:9"`, `"4:3"`, `"3:4"`
  - Note: `3:1` is not supported. Use `16:9` for wide landscape images.
- `negative_prompt` (str, optional): Text describing what to avoid in the image
- `safety_filter_level` (str, default: "block_some"): Safety filter level
  - Options: `"block_most"`, `"block_some"`, `"block_few"`, `"block_fewest"`
- `person_generation` (str, default: "dont_allow"): Person generation setting
  - Options: `"dont_allow"`, `"allow_adult"`, `"allow_all"`
- `seed` (int, optional): Random seed for reproducible results
- `**kwargs`: Additional generation parameters

#### Returns

Dictionary containing:
- `images`: List of image bytes (PNG format)
- `prompt`: The prompt used
- `model`: Model name used
- `number_of_images`: Number of images generated
- `aspect_ratio`: Aspect ratio used
- `negative_prompt`: Negative prompt if provided
- `safety_filter_level`: Safety filter level used
- `person_generation`: Person generation setting used

#### Raises

- `ValueError`: If required parameters are missing or invalid
- `Exception`: If API call fails

### `save_image()`

Save image bytes to a file.

#### Parameters

- `image_bytes` (bytes): Image data as bytes
- `filepath` (str): Path where to save the image

#### Returns

The filepath where the image was saved

#### Raises

- `Exception`: If file save fails

### `test()`

Direct test function for the service.

#### Parameters

- `test_prompt` (str, optional): Custom test prompt
- `save_test_image` (bool, default: False): Whether to save the generated test image

## Testing

### Command Line Testing

```bash
python -m ai.gemini_image_service
```

### Django Shell Testing

```python
from ai.gemini_image_service import GeminiImageService

service = GeminiImageService()
service.test(save_test_image=True)
```

### Custom Test

```python
from ai.gemini_image_service import GeminiImageService

service = GeminiImageService()

result = service.generate_image(
    prompt="Picture a pencil in the middle of two books. One book is on the left, and the other book is on the right. The pencil is exactly in the middle. white background",
    number_of_images=1,
    aspect_ratio="16:9"
)

service.save_image(result['images'][0], "pencil_books.png")
```

## Supported Aspect Ratios

| Ratio | Description | Use Case |
|-------|-------------|----------|
| `1:1` | Square | Profile pictures, thumbnails |
| `9:16` | Portrait | Mobile screens, vertical content |
| `16:9` | Landscape | Wide screens, banners (widest supported) |
| `4:3` | Standard | Traditional displays |
| `3:4` | Portrait Standard | Traditional portrait format |

**Note**: `3:1` ultra-wide aspect ratio is not supported by the Imagen API. Use `16:9` for wide landscape images.

## Safety Settings

### Safety Filter Levels

- `block_most`: Strictest filtering (most conservative)
- `block_some`: Default setting (balanced)
- `block_few`: Less restrictive
- `block_fewest`: Most permissive

### Person Generation

- `dont_allow`: No people in generated images (default)
- `allow_adult`: Allow adult figures only
- `allow_all`: Allow all person generation

## Error Handling

The service includes comprehensive error handling:

- **Missing Configuration**: Warns if `GCP_PROJECT_ID` is not set
- **Invalid Parameters**: Raises `ValueError` for invalid inputs
- **API Errors**: Catches and re-raises Google API errors with context
- **File Operations**: Handles file save errors gracefully

## Cost Considerations

⚠️ **Important**: Image generation can be expensive. Consider:

- **Usage Limits**: Monitor API usage and costs
- **Caching**: Cache generated images when possible
- **Batch Processing**: Generate multiple images in a single request when needed
- **Testing**: Use the test function to verify prompts before production use

## Architecture

The service follows the same pattern as `GeminiService`:

1. **Initialization**: Loads configuration and initializes Vertex AI
2. **Credential Management**: Handles service account credentials
3. **Model Loading**: Loads the Imagen model on demand
4. **Image Generation**: Calls Vertex AI API with parameters
5. **Response Processing**: Extracts image bytes from response
6. **Error Handling**: Comprehensive error handling and logging

## Integration with Other Services

This service is designed to work alongside other AI services:

- `GeminiService`: Text generation
- `GeminiAgent`: Function calling and structured outputs
- `ChatService`: Conversational AI

## Examples

### Example 1: Simple Image Generation

```python
from ai.gemini_image_service import GeminiImageService

service = GeminiImageService()
result = service.generate_image(
    prompt="A cute cartoon robot with big eyes",
    aspect_ratio="1:1"
)
service.save_image(result['images'][0], "robot.png")
```

### Example 2: Multiple Images with Negative Prompt

```python
from ai.gemini_image_service import GeminiImageService

service = GeminiImageService()
result = service.generate_image(
    prompt="A peaceful forest scene",
    number_of_images=3,
    aspect_ratio="16:9",
    negative_prompt="people, buildings, roads"
)

for i, img in enumerate(result['images']):
    service.save_image(img, f"forest_{i+1}.png")
```

### Example 3: Reproducible Results

```python
from ai.gemini_image_service import GeminiImageService

service = GeminiImageService()

# Generate with seed for reproducibility
result = service.generate_image(
    prompt="Abstract geometric pattern",
    seed=12345
)

service.save_image(result['images'][0], "pattern.png")
```

## Troubleshooting

### Common Issues

1. **"GCP_PROJECT_ID not set"**
   - Solution: Set `GCP_PROJECT_ID` in your `.env` file

2. **"Invalid aspect ratio"**
   - Solution: Use one of the supported aspect ratios (see Supported Aspect Ratios section)

3. **"Imagen API error: 400"**
   - Solution: Check your prompt for inappropriate content or invalid parameters

4. **Credential errors**
   - Solution: Ensure `GOOGLE_APPLICATION_CREDENTIALS` is set correctly or place credentials at `.credentials/vertex-ai-service-account.json`

## Future Enhancements

Potential improvements for future versions:

- Support for image editing (inpainting, outpainting)
- Support for image-to-image generation
- Batch processing capabilities
- Image quality/size configuration
- Support for newer model versions (e.g., `imagegeneration@007`)

## Related Documentation

- [SERVICES_WORKFLOW.md](./SERVICES_WORKFLOW.md): Function calling workflow
- [VERTEX_AI_WORKFLOW.md](./VERTEX_AI_WORKFLOW.md): Vertex AI setup and configuration
- [gemini_service.py](./gemini_service.py): Base text generation service

## License

Part of the Little Learners Tech Backend project.

