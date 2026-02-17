# Blog API

Public REST API for the Little Learners Tech blog. Posts are managed in Django Admin; only **published** posts are returned by the API.

## Base URL

- Development: `http://127.0.0.1:8000/api/blog/`
- List and detail are **public** (no authentication required). Create requires authentication.

## Endpoints

### List posts

**GET** `/api/blog/`

Returns a paginated list of published posts, ordered by `published_at` (newest first).

**Response fields (per item):**

| Field         | Type   | Description                    |
|--------------|--------|--------------------------------|
| `id`         | number | Post ID                        |
| `title`      | string | Post title                     |
| `slug`       | string | URL-safe slug (use for detail) |
| `excerpt`    | string | Short preview (~160 chars)     |
| `published_at` | string \| null | ISO 8601 datetime          |
| `author`     | object | `{ id, email }`                |

**Example:**

```bash
curl -s http://127.0.0.1:8000/api/blog/
```

---

### Get post by slug

**GET** `/api/blog/<slug>/`

Returns a single published post by its slug. Use the `slug` from the list response (e.g. `testing-testing`).

**Response fields:**

| Field         | Type   | Description              |
|--------------|--------|--------------------------|
| `id`         | number | Post ID                   |
| `title`      | string | Post title                |
| `slug`       | string | URL slug                  |
| `content`    | string | Full post body            |
| `author`     | object | `{ id, email }`           |
| `published_at` | string \| null | ISO 8601 datetime   |
| `created_at` | string | ISO 8601 datetime         |
| `updated_at` | string | ISO 8601 datetime         |

**Example:**

```bash
curl -s http://127.0.0.1:8000/api/blog/testing-testing
```

**Status codes:**

- `200` – Post found and published
- `404` – No published post with that slug

---

### Create post (from book export)

**POST** `/api/blog/create/`

Creates a **draft** blog post. Used by the frontend "Export as blog" flow when exporting a book. **Requires authentication** (Bearer token).

**Request body (JSON):**

| Field     | Type   | Required | Description                                                |
|-----------|--------|----------|------------------------------------------------------------|
| `title`   | string | Yes      | Post title                                                 |
| `content` | string | Yes      | Full post body (e.g. JSON string from book export)         |
| `excerpt` | string | No       | Short preview (~160 chars)                                 |

**Response:** Same shape as **Get post by slug** (created post; `status` will be `draft`). The post does not appear in the public list or detail API until it is set to **published** in Django Admin.

**Example:**

```bash
curl -X POST http://127.0.0.1:8000/api/blog/create/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "My Book", "content": "{\"description\": \"...\", \"pages\": [...]}"}'
```

**Status codes:**

- `201` – Post created (draft)
- `400` – Validation error (e.g. missing title or content)
- `401` – Unauthorized (missing or invalid token)

---

### My posts (authenticated, author-only)

**GET** `/api/blog/mine/`

Returns a list of the current user's posts (draft and published), ordered by `updated_at` (newest first). **Requires authentication** (Bearer token).

**Response fields (per item):** Same as list plus:

| Field         | Type   | Description        |
|---------------|--------|--------------------|
| `status`      | string | `draft` or `published` |
| `updated_at`  | string | ISO 8601 datetime  |

---

**GET** `/api/blog/mine/<id>/`

Returns a single post by primary key `id`. Allowed only if `post.author == request.user`. **Requires authentication.**

**Response:** Same shape as **Get post by slug** (full post including `content`).

---

**PATCH** `/api/blog/mine/<id>/`

Updates a post (title, content). Allowed only if `post.author == request.user`. **Always sets `status` to `draft`** so admin can review before republishing. **Requires authentication.**

**Request body (JSON):** `title` (optional), `content` (optional). At least one field required.

**Response:** Same shape as **Get post by slug** (updated post).

---

**DELETE** `/api/blog/mine/<id>/`

Deletes a post. Allowed only if `post.author == request.user`. **Requires authentication.**

**Response:** `204 No Content`.

---

## Model (admin)

- **Post**: `title`, `slug` (unique, can be auto from title), `content`, `author` (user), `status` (draft / published), `published_at`, timestamps.
- Only posts with `status=published` appear in the list and detail API.
- Slug is used in the URL; create/edit/publish posts in **Django Admin** → Blog → Blog posts.

---

## URL design

- List: `.../api/blog/`
- Create: `.../api/blog/create/`
- My list: `.../api/blog/mine/`
- My detail/update/delete: `.../api/blog/mine/<id>/`
- Public detail: `.../api/blog/<slug>/` (e.g. `.../api/blog/getting-started-with-coding`)

Slugs are URL-safe and derived from the title; they remain stable if the title changes (unless you change the slug in admin).

---

## File uploads (images in post content)

Images and other files embedded in post content (BlockNote) are uploaded by the frontend via the **teacher file upload** API (`/api/teacher/files/upload/`) with the storage path **`blog_files`**. If the backend restricts allowed upload paths, ensure `blog_files` is permitted so that blog post images upload successfully.
