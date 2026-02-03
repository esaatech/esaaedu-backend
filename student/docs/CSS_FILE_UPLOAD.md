# CSS File Upload to Google Cloud Storage

## Overview

The CSS file upload system allows code snippets with CSS language to be uploaded to Google Cloud Storage (GCS) and referenced via public URLs. This enables CSS code to be used in HTML via `<link>` tags, making it accessible for web-based code execution environments.

## Key Features

- **Consistent URLs**: CSS file URLs remain stable across updates, ensuring HTML `<link>` tags continue to work
- **Cache Prevention**: Updated CSS files include cache-control headers to prevent stale content
- **Automatic Management**: Files are automatically uploaded, updated, and deleted based on code snippet operations
- **GCS Integration**: Uses Google Cloud Storage for reliable file hosting with public access

## Architecture

### Components

1. **`css_upload_utils.py`**: Core utility functions for CSS file operations
   - `upload_css_to_gcp()`: Uploads new CSS files or updates existing ones
   - `update_css_in_gcp()`: Updates existing CSS files in place
   - `delete_css_from_gcp()`: Deletes CSS files from GCS

2. **`CodeSnippet` Model**: Stores CSS file URLs in the `css_file_url` field
   - Only populated when `language == 'css'`
   - Contains the public GCS URL for the CSS file

3. **API Views**: Handle CSS file operations during snippet create/update/delete
   - `CodeSnippetCreateView`: Creates new CSS files
   - `CodeSnippetDetailView`: Updates or deletes CSS files

## How It Works

### Creating a New CSS Snippet

When a new code snippet with `language='css'` is created:

1. **Generate Unique Filename**: A new UUID is generated for the filename
   - Format: `{uuid}-{sanitized-title}.css`
   - Example: `0efee1e6-6c97-4f25-95a8-f6a74ecba5e0-code-snippet-jan-31-2026-10-38-am.css`

2. **Upload to GCS**: The CSS content is uploaded to GCS at path `css-files/{filename}`
   - Uses Django's `default_storage` for new files
   - File is made publicly readable

3. **Store URL**: The public GCS URL is saved to `snippet.css_file_url`
   - Format: `https://storage.googleapis.com/{bucket-name}/css-files/{filename}`

### Updating an Existing CSS Snippet

When an existing CSS snippet is updated, the system ensures URL consistency:

1. **Check for Existing File**: If `snippet.css_file_url` exists, the file is updated in place
   - Uses `update_css_in_gcp()` to preserve the same URL
   - Extracts the storage path from the existing URL

2. **Update via GCS Client**: Uses the Google Cloud Storage client directly
   - **Overwrites** the existing file (bypasses `GS_FILE_OVERWRITE = False` setting)
   - Sets cache-control headers: `no-cache, no-store, must-revalidate`
   - Sets content-type: `text/css`
   - Ensures file remains publicly readable

3. **URL Preservation**: The same URL is returned, maintaining consistency
   - HTML `<link>` tags continue to work without changes
   - No need to update references in other code

### Deleting a CSS Snippet

When a CSS snippet is deleted or language is changed away from CSS:

1. **Extract File Path**: Parses the `css_file_url` to get the GCS storage path
2. **Delete from GCS**: Removes the file from Google Cloud Storage
3. **Clear URL**: Sets `snippet.css_file_url = None`

## URL Consistency Mechanism

### Problem Solved

Previously, each CSS update generated a new UUID, creating a new file with a different URL. This broke HTML `<link>` tags that referenced the CSS file.

### Solution

The system uses the snippet's ID (`snippet.id`) as the unique identifier in the filename:

- **New Files**: Generate UUID → `{uuid}-{title}.css`
- **Updates**: Use snippet ID → `{snippet.id}-{title}.css`

However, the current implementation uses a different approach:

- **New Files**: Generate UUID for filename
- **Updates**: Use `update_css_in_gcp()` which updates the file at the existing URL path
- This preserves the exact same URL across all updates

### File Naming Convention

```
css-files/{unique-id}-{sanitized-title}.css
```

Where:
- `unique-id`: UUID for new files, snippet ID for updates (when using snippet_id parameter)
- `sanitized-title`: Title with special characters replaced, limited to 50 chars, lowercase

## Caching Prevention

### The Problem

Google Cloud Storage public URLs can be cached by browsers and CDNs. When a CSS file is updated, the public URL might show stale cached content while the authenticated URL shows the new content.

### The Solution

When updating CSS files, the system:

1. **Uses GCS Client Directly**: Bypasses Django's storage backend to have full control
2. **Sets Cache-Control Headers**: 
   ```
   Cache-Control: no-cache, no-store, must-revalidate
   ```
3. **Overwrites File**: Ensures the file is actually updated, not just a new version created

This ensures that:
- Browsers don't cache the CSS file
- CDNs don't serve stale content
- Public URLs immediately reflect updates

## API Integration

### Creating a CSS Snippet

**Endpoint**: `POST /api/student/code-snippets/create/`

**Request Body**:
```json
{
  "language": "css",
  "code": "h1 { color: blue; }",
  "title": "My Styles"
}
```

**Response**: Includes `css_file_url` with the public GCS URL

### Updating a CSS Snippet

**Endpoint**: `PATCH /api/student/code-snippets/{id}/`

**Request Body**:
```json
{
  "code": "h1 { color: red; }"
}
```

**Behavior**:
- If `css_file_url` exists: Updates the file in place (same URL)
- If `css_file_url` is null: Creates a new file (new URL)

### Deleting a CSS Snippet

**Endpoint**: `DELETE /api/student/code-snippets/{id}/`

**Behavior**: Automatically deletes the CSS file from GCS and clears `css_file_url`

## Technical Details

### Storage Backend

The system uses two approaches depending on the operation:

1. **Django's `default_storage`**: For new file uploads
   - Uses `storages.backends.gcloud.GoogleCloudStorage`
   - Respects `GS_FILE_OVERWRITE = False` setting

2. **GCS Client Direct**: For file updates
   - Uses `google.cloud.storage.Client` directly
   - Bypasses `GS_FILE_OVERWRITE` setting to ensure overwrite
   - Allows setting custom metadata (cache-control, content-type)

### File Path Extraction

When updating or deleting files, the system extracts the storage path from the URL:

```
https://storage.googleapis.com/{bucket}/css-files/{filename}
                                    ↓
                        css-files/{filename}
```

### Error Handling

- **Empty CSS Content**: Returns `(None, None)` and logs warning
- **GCS Not Configured**: Returns `(None, None)` and logs error
- **GCS Client Unavailable**: Falls back to `default_storage` for new files
- **Update Failures**: Falls back to creating a new file if update fails

### Debug Logging

The system includes comprehensive debug print statements (can be removed in production):
- Function entry/exit
- Parameter values
- File paths and URLs
- Success/failure status

## Usage in HTML

Once a CSS snippet is created, the `css_file_url` can be used in HTML:

```html
<link rel="stylesheet" href="{{ snippet.css_file_url }}">
```

The URL remains consistent across updates, so the HTML doesn't need to change when CSS is modified.

## Configuration Requirements

### Environment Variables

- `GCS_BUCKET_NAME`: Google Cloud Storage bucket name
- `GCS_PROJECT_ID`: Google Cloud project ID
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account credentials (optional)

### Django Settings

```python
GS_DEFAULT_ACL = 'publicRead'  # Make files publicly readable
GS_FILE_OVERWRITE = False      # Prevent accidental overwrites (bypassed for CSS updates)
GS_QUERYSTRING_AUTH = False    # Public access without authentication
```

### Python Dependencies

- `django-storages`: For default storage backend
- `google-cloud-storage`: For direct GCS client operations (optional, falls back if not available)

## File Lifecycle

1. **Creation**: New CSS snippet → Generate UUID → Upload to GCS → Store URL
2. **Update**: Existing CSS snippet → Extract path from URL → Update file in place → Same URL
3. **Deletion**: Delete snippet or change language → Extract path from URL → Delete from GCS → Clear URL

## Best Practices

1. **Always Check `css_file_url`**: Before using in HTML, verify it's not `None`
2. **Handle Updates Gracefully**: The system handles URL consistency automatically
3. **Monitor File Deletions**: Ensure CSS files are cleaned up when snippets are deleted
4. **Cache Considerations**: The system sets no-cache headers, but browsers may still cache aggressively

## Troubleshooting

### Public URL Shows Old Content

- Check cache-control headers are set: `no-cache, no-store, must-revalidate`
- Verify file was actually updated in GCS console
- Clear browser cache or use incognito mode
- Check if CDN is caching (if using Cloud CDN)

### URL Changes on Update

- Ensure `update_css_in_gcp()` is being called (not `upload_css_to_gcp()`)
- Check that `snippet.css_file_url` exists before update
- Verify GCS client is available and working

### File Not Deleted

- Check that `delete_css_from_gcp()` is called on snippet deletion
- Verify URL parsing logic extracts correct path
- Check GCS permissions for delete operations

