"""KUDOS Universal Memory API — write, retrieve, consolidate, clear."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.memory_store import (
    STORAGE_LAYERS,
    _memory_to_dict,
    clear_memories,
    consolidate_memories,
    get_memory,
    retrieve_memories,
    write_memory,
)
from app.models import User
from app.schemas.schemas import (
    MemoryClearResponse,
    MemoryCreate,
    MemoryResponse,
    MemoryRetrieveResponse,
)

router = APIRouter()


@router.get("", response_model=MemoryRetrieveResponse)
def retrieve_memory_endpoint(
    query: str = "",
    layers: str = "",
    limit: int = 8,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the most relevant memories for the current user."""
    requested = [l.strip() for l in layers.split(",") if l.strip()] if layers else None
    if requested:
        invalid = [l for l in requested if l not in STORAGE_LAYERS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid layer(s): {', '.join(invalid)}")
    memories = retrieve_memories(
        db, current_user.id, query=query, layers=requested, limit=min(max(limit, 1), 50)
    )
    return MemoryRetrieveResponse(
        query=query,
        memories=[MemoryResponse(**m) for m in map(_memory_to_dict, memories)],
    )


@router.post("", response_model=MemoryResponse, status_code=201)
def create_memory_endpoint(
    body: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store a memory for the current user."""
    try:
        record = write_memory(
            db,
            user_id=current_user.id,
            content=body.content,
            layer=body.layer,
            kind=body.kind,
            importance=body.importance,
            tags=body.tags,
            source=body.source,
            expires_at=body.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MemoryResponse(**_memory_to_dict(record))


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory_endpoint(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch one memory owned by the current user."""
    record = get_memory(db, memory_id, current_user.id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse(**_memory_to_dict(record))


@router.delete("/{memory_id}", response_model=MemoryClearResponse)
def delete_memory_endpoint(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a single memory."""
    record = get_memory(db, memory_id, current_user.id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete(record)
    db.commit()
    return MemoryClearResponse(deleted=1)


@router.post("/consolidate", response_model=MemoryClearResponse)
def consolidate_memory_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Promote well-used short-term memories into long-term storage."""
    promoted = consolidate_memories(db, current_user.id)
    return MemoryClearResponse(deleted=promoted)


@router.delete("", response_model=MemoryClearResponse)
def clear_memory_endpoint(
    layer: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Wipe the user's memories (optionally one layer)."""
    target = layer or None
    if target and target not in STORAGE_LAYERS:
        raise HTTPException(status_code=400, detail=f"Invalid layer: {target}")
    deleted = clear_memories(db, current_user.id, layer=target)
    return MemoryClearResponse(deleted=deleted)