from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.api import deps
from app.models.user import User
from app.core.config import settings
import json
import uuid
from datetime import datetime

# Try to import ChromaDB, handle gracefully if not available
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

router = APIRouter()

class MemoryItem(BaseModel):
    content: str
    memory_type: str = "fact"  # fact, preference, skill, experience, conversation
    tags: List[str] = []
    meta_data: Optional[Dict[str, Any]] = None

class MemoryResponse(BaseModel):
    id: str
    content: str
    memory_type: str
    tags: List[str]
    meta_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

class MemorySearchRequest(BaseModel):
    query: str
    memory_type: Optional[str] = None
    limit: int = 10

class MemorySearchResponse(BaseModel):
    memories: List[MemoryResponse]
    query: str
    total_results: int

# In production, initialize ChromaDB client
if CHROMA_AVAILABLE:
    try:
        chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT
        )
        # Get or create collection for user memories
        try:
            memory_collection = chroma_client.get_collection(name="user_memories")
        except:
            memory_collection = chroma_client.create_collection(name="user_memories")
    except Exception as e:
        print(f"ChromaDB connection failed: {e}")
        CHROMA_AVAILABLE = False
        chroma_client = None
        memory_collection = None
else:
    chroma_client = None
    memory_collection = None

# Fallback in-memory store for memories (when ChromaDB not available)
memory_store = {}

@router.post("", response_model=MemoryResponse)
def add_memory(
    memory_item: MemoryItem,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Add a memory item to long-term storage"""
    memory_id = str(uuid.uuid4())
    now = datetime.utcnow()

    memory_data = {
        "id": memory_id,
        "user_id": current_user.id,
        "content": memory_item.content,
        "memory_type": memory_item.memory_type,
        "tags": memory_item.tags,
        "meta_data": memory_item.meta_data or {},
        "created_at": now,
        "updated_at": now
    }

    # Store in ChromaDB if available
    if CHROMA_AVAILABLE and memory_collection:
        try:
            memory_collection.add(
                documents=[memory_item.content],
                metadatas=[{
                    "user_id": str(current_user.id),
                    "memory_type": memory_item.memory_type,
                    "tags": ",".join(memory_item.tags),
                    "created_at": now.isoformat(),
                    **(memory_item.meta_data or {})
                }],
                ids=[memory_id]
            )
        except Exception as e:
            print(f"ChromaDB storage failed: {e}")
            # Fallback to in-memory
            memory_store[memory_id] = memory_data
    else:
        # Use in-memory store
        memory_store[memory_id] = memory_data

    # Log for analytics
    background_tasks.add_task(log_memory_operation, db, current_user.id, "add", memory_item.memory_type)

    return MemoryResponse(
        id=memory_data["id"],
        content=memory_data["content"],
        memory_type=memory_data["memory_type"],
        tags=memory_data["tags"],
        meta_data=memory_data["meta_data"],
        created_at=memory_data["created_at"],
        updated_at=memory_data["updated_at"]
    )

@router.post("/search", response_model=MemorySearchResponse)
def search_memories(
    search_req: MemorySearchRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Search memories using semantic search"""
    if not CHROMA_AVAILABLE or not memory_collection:
        # Fallback to simple text search in memory store
        results = []
        for memory_id, memory_data in memory_store.items():
            if memory_data["user_id"] != current_user.id:
                continue
            if search_req.memory_type and memory_data["memory_type"] != search_req.memory_type:
                continue
            if search_req.query.lower() in memory_data["content"].lower():
                results.append(MemoryResponse(**{
                    k: v for k, v in memory_data.items() if k in MemoryResponse.__fields__
                }))

        return MemorySearchResponse(
            memories=results[:search_req.limit],
            query=search_req.query,
            total_results=len(results)
        )

    # Use ChromaDB for semantic search
    try:
        where_clause = {"user_id": str(current_user.id)}
        if search_req.memory_type:
            where_clause["memory_type"] = search_req.memory_type

        results = memory_collection.query(
            query_texts=[search_req.query],
            n_results=search_req.limit,
            where=where_clause
        )

        memories = []
        if results["ids"] and results["ids"][0]:
            for i, memory_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] and results["metadatas"][0] else {}
                document = results["documents"][0][i] if results["documents"] and results["documents"][0] else ""

                memory_obj = MemoryResponse(
                    id=memory_id,
                    content=document,
                    memory_type=metadata.get("memory_type", "unknown"),
                    tags=metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                    meta_data={k: v for k, v in metadata.items() if k not in ["user_id", "memory_type", "tags", "created_at"]},
                    created_at=datetime.fromisoformat(metadata.get("created_at", datetime.utcnow().isoformat())) if metadata.get("created_at") else datetime.utcnow(),
                    updated_at=datetime.fromisoformat(metadata.get("created_at", datetime.utcnow().isoformat())) if metadata.get("created_at") else datetime.utcnow()
                )
                memories.append(memory_obj)

        return MemorySearchResponse(
            memories=memories,
            query=search_req.query,
            total_results=len(memories)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")

@router.get("", response_model=List[MemoryResponse])
def list_memories(
    memory_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List user's memories"""
    if not CHROMA_AVAILABLE or not memory_collection:
        # Filter from in-memory store
        memories = []
        for memory_id, memory_data in memory_store.items():
            if memory_data["user_id"] != current_user.id:
                continue
            if memory_type and memory_data["memory_type"] != memory_type:
                continue
            memories.append(MemoryResponse(**{
                k: v for k, v in memory_data.items() if k in MemoryResponse.__fields__
            }))

        # Apply pagination
        sorted_memories = sorted(memories, key=lambda x: x.created_at, reverse=True)
        paginated = sorted_memories[offset:offset + limit]
        return paginated

    # In production, would use ChromaDB with pagination
    # For now, return empty list as placeholder
    return []

@router.delete("/{memory_id}")
def delete_memory(
    memory_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Delete a memory item"""
    # Delete from ChromaDB if available
    if CHROMA_AVAILABLE and memory_collection:
        try:
            memory_collection.delete(ids=[memory_id])
        except Exception as e:
            print(f"ChromaDB deletion failed: {e}")

    # Delete from in-memory store
    if memory_id in memory_store:
        if memory_store[memory_id]["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        del memory_store[memory_id]

    return {"message": "Memory deleted successfully"}

def log_memory_operation(db: Session, user_id: int, operation: str, memory_type: str):
    """Log memory operations for analytics"""
    print(f"Memory operation logged: user={user_id}, operation={operation}, type={memory_type}")