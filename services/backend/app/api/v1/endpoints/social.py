"""
Digital Campus - Social Hub Endpoints
Connected storage: MinIO/S3 (s3) + link/youtube/image fallback.
Dead types gdrive/dropbox/onedrive removed -> mapped to 'link'.
"""
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core import storage as store
from app.models import Comment, Post, Reaction, User
from app.schemas import (
    CommentCreate,
    CommentResponse,
    CommentWithAuthor,
    PostCreate,
    PostResponse,
    PostUpdate,
    PostWithAuthor,
    ReactionCreate,
    ReactionResponse,
    UserResponse,
)

router = APIRouter()

# Connected storage types only - dead external API types removed
CONNECTED_TYPES = {"s3", "link", "youtube", "image"}
DEAD_TO_LINK = {"gdrive", "dropbox", "onedrive", "drive", "g_drive"}

def _normalize_storage_type(t: str) -> str:
    t = (t or "link").lower().strip()
    if t in DEAD_TO_LINK:
        return "link"
    if t == "minio":
        return "s3"
    if t not in CONNECTED_TYPES:
        return "link"
    return t

# ──────────────────────────────────────────────
# IN-MEMORY PREVIEW CACHE (LRU)
# ──────────────────────────────────────────────

_PREVIEW_CACHE_MAX = 500
_preview_cache: OrderedDict = OrderedDict()  # post_id → cached_preview_data


def _get_cached_preview(post_id: int) -> Optional[dict]:
    if post_id in _preview_cache:
        _preview_cache.move_to_end(post_id)
        return _preview_cache[post_id]
    return None


def _set_cached_preview(post_id: int, data: dict):
    if post_id in _preview_cache:
        _preview_cache.move_to_end(post_id)
    _preview_cache[post_id] = data
    while len(_preview_cache) > _PREVIEW_CACHE_MAX:
        _preview_cache.popitem(last=False)


def _build_preview_data(post: Post) -> dict:
    return {
        "post_id": post.id,
        "title": post.title,
        "description": post.description,
        "storage_url": post.storage_url,
        "storage_type": post.storage_type,
        "content_type": post.content_type,
        "thumbnail_url": post.thumbnail_url,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────
# POSTS CRUD
# ──────────────────────────────────────────────


@router.get("/feed", response_model=list[PostWithAuthor])
def public_feed(
    skip: int = 0,
    limit: int = 20,
    tag: Optional[str] = None,
    storage_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Public feed — all public posts (no auth required)."""
    q = (
        db.query(Post)
        .options(joinedload(Post.user))
        .filter(Post.is_public == True)
    )
    if tag:
        q = q.filter(Post.tags.contains(tag))
    if storage_type:
        storage_type = _normalize_storage_type(storage_type)
        q = q.filter(Post.storage_type == storage_type)

    posts = q.order_by(Post.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for p in posts:
        result.append(
            PostWithAuthor(
                **PostResponse.model_validate(p).model_dump(),
                author=UserResponse.model_validate(p.user),
                reaction_count=len(p.reactions),
                comment_count=len(p.comments),
            )
        )
    return result


@router.get("/my", response_model=list[PostResponse])
def my_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's posts (including private)."""
    return (
        db.query(Post)
        .filter(Post.user_id == current_user.id)
        .order_by(Post.created_at.desc())
        .all()
    )


@router.get("/{post_id}", response_model=PostWithAuthor)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single post. Increments view count. Caches preview."""
    post = (
        db.query(Post)
        .options(joinedload(Post.user), joinedload(Post.reactions), joinedload(Post.comments))
        .filter(Post.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if not post.is_public and post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This post is private")

    post.view_count += 1
    db.commit()
    _set_cached_preview(post.id, _build_preview_data(post))

    return PostWithAuthor(
        **PostResponse.model_validate(post).model_dump(),
        author=UserResponse.model_validate(post.user),
        reaction_count=len(post.reactions),
        comment_count=len(post.comments),
    )


@router.get("/{post_id}/preview")
def get_preview(post_id: int):
    cached = _get_cached_preview(post_id)
    if cached:
        return {"source": "cache", "preview": cached}
    return {"source": "miss", "preview": None, "hint": "View the post first to cache it"}


@router.post("/", response_model=PostResponse, status_code=201)
def create_post(
    post_in: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a post linking to storage (s3/MinIO or external link)."""
    data = post_in.model_dump()
    data["storage_type"] = _normalize_storage_type(data.get("storage_type", "link"))
    post = Post(user_id=current_user.id, **data)
    db.add(post)
    db.commit()
    db.refresh(post)
    _set_cached_preview(post.id, _build_preview_data(post))
    return post


@router.post("/upload", response_model=PostResponse, status_code=201)
async def create_post_with_upload(
    title: str = Query(..., description="Post title"),
    description: str = Query("", description="Description"),
    tags: str = Query("", description="Comma-separated tags"),
    is_public: bool = Query(True),
    file: UploadFile = File(..., description="File to upload to MinIO/S3"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Connected upload: file -> MinIO/S3 (private, AES256) -> Post with storage_type=s3.
    Removes dead gdrive/dropbox flow. Uses PostgreSQL/SQLite for metadata, S3 for bytes.
    """
    if not file.filename:
        raise HTTPException(400, "Filename required")
    import io
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50MB)")
    if not store.settings.s3_is_configured:
        raise HTTPException(503, "Storage not enabled — start MinIO: docker-compose up -d minio")

    key = store.make_key("posts", file.filename, current_user.id)
    res = store.upload_file(io.BytesIO(content), key, file.content_type or "application/octet-stream")
    if not res.get("ok"):
        raise HTTPException(500, f"S3 upload failed: {res.get('error')}")

    post = Post(
        user_id=current_user.id,
        title=title,
        description=description,
        storage_url=res["key"],  # store S3 key, not public URL (private bucket)
        storage_type="s3",
        content_type=file.content_type or "",
        tags=tags,
        is_public=is_public,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    _set_cached_preview(post.id, _build_preview_data(post))
    return post


@router.get("/{post_id}/download")
def get_download_url(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get presigned download URL for s3 posts (private bucket)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    if not post.is_public and post.user_id != current_user.id:
        raise HTTPException(403, "Private post")
    if post.storage_type != "s3":
        # for link/youtube return stored url directly
        return {"storage_type": post.storage_type, "url": post.storage_url, "presigned": False}
    # s3 key -> presigned
    res = store.presigned_url(post.storage_url, 900)
    if not res.get("ok"):
        raise HTTPException(500, res.get("error"))
    return {"storage_type": "s3", "url": res["url"], "key": post.storage_url, "expires": 900}


@router.patch("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int,
    post_in: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found or not yours")
    data = post_in.model_dump(exclude_unset=True)
    if "storage_type" in data:
        data["storage_type"] = _normalize_storage_type(data["storage_type"])
    for field, value in data.items():
        setattr(post, field, value)
    db.commit()
    db.refresh(post)
    _set_cached_preview(post.id, _build_preview_data(post))
    return post


@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found or not yours")
    # if s3, also delete file (best-effort)
    if post.storage_type == "s3":
        try:
            store.delete_file(post.storage_url)
        except Exception:
            pass
    db.delete(post)
    db.commit()
    _preview_cache.pop(post_id, None)


# ──────────────────────────────────────────────
# COMMENTS
# ──────────────────────────────────────────────


@router.get("/{post_id}/comments", response_model=list[CommentWithAuthor])
def list_comments(post_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Comment)
        .options(joinedload(Comment.user))
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at)
        .all()
    )


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=201)
def add_comment(
    post_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    comment = Comment(post_id=post_id, user_id=current_user.id, content=body.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


# ──────────────────────────────────────────────
# REACTIONS
# ──────────────────────────────────────────────


@router.post("/{post_id}/react", response_model=ReactionResponse, status_code=201)
def toggle_reaction(
    post_id: int,
    body: ReactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = (
        db.query(Reaction)
        .filter(Reaction.post_id == post_id, Reaction.user_id == current_user.id, Reaction.emoji == body.emoji)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        return existing
    reaction = Reaction(post_id=post_id, user_id=current_user.id, emoji=body.emoji)
    db.add(reaction)
    db.commit()
    db.refresh(reaction)
    return reaction


@router.get("/cache/stats")
def cache_stats():
    return {
        "cached_items": len(_preview_cache),
        "max_size": _PREVIEW_CACHE_MAX,
        "post_ids": list(_preview_cache.keys())[-20:],
    }
