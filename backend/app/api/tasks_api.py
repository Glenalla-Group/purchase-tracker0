"""
Tasks API Endpoints
FastAPI routes for managing tasks, columns, and comments
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel
import json
import logging

from app.config.database import get_db
from app.models.database import Task, TaskColumn, TaskComment, User, TaskPriorityEnum

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])
logger = logging.getLogger(__name__)


# ========================
# API Response Wrapper
# ========================

class APIResponse(BaseModel):
    """Standard API response wrapper"""
    status: int = 200  # 200 = SUCCESS, -1 = ERROR (matches frontend ResultStatus enum)
    data: Any
    message: str = ""
    
    class Config:
        arbitrary_types_allowed = True


# ========================
# Request/Response Models
# ========================

# Column Models
class TaskColumnCreate(BaseModel):
    """Model for creating a new task column"""
    title: str
    position: Optional[int] = None


class TaskColumnUpdate(BaseModel):
    """Model for updating a task column"""
    title: Optional[str] = None
    position: Optional[int] = None


class TaskColumnResponse(BaseModel):
    """Model for task column response"""
    id: int
    title: str
    position: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Task Models
class TaskCreate(BaseModel):
    """Model for creating a new task"""
    column_id: int
    title: str
    description: Optional[str] = None
    priority: str = "Medium"  # "Low", "Medium", "High"
    assignee_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None
    due_date: Optional[date] = None
    attachments: Optional[List[str]] = None
    position: Optional[int] = None


class TaskUpdate(BaseModel):
    """Model for updating a task"""
    column_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    assignee_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None
    due_date: Optional[date] = None
    attachments: Optional[List[str]] = None
    position: Optional[int] = None


class TaskResponse(BaseModel):
    """Model for task response"""
    id: int
    column_id: int
    title: str
    description: Optional[str] = None
    priority: str
    assignee_ids: Optional[List[int]] = None
    assignees: Optional[List[dict]] = None
    tags: Optional[List[str]] = None
    due_date: Optional[date] = None
    attachments: Optional[List[str]] = None
    position: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Comment Models
class TaskCommentCreate(BaseModel):
    """Model for creating a new task comment"""
    task_id: int
    user_id: int
    content: str


class TaskCommentUpdate(BaseModel):
    """Model for updating a task comment"""
    content: str


class TaskCommentResponse(BaseModel):
    """Model for task comment response"""
    id: int
    task_id: int
    user_id: int
    username: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Board Data Model (for frontend kanban)
class BoardDataResponse(BaseModel):
    """Model for complete board data (columns, tasks, column order)"""
    tasks: dict[str, TaskResponse]
    columns: dict[str, TaskColumnResponse]
    columnOrder: List[str]


# ========================
# Helper Functions
# ========================

def parse_json_field(value: Optional[str]) -> Optional[List]:
    """Parse JSON string field to list"""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def serialize_json_field(value: Optional[List]) -> Optional[str]:
    """Serialize list to JSON string"""
    if not value:
        return None
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return None


# ========================
# Users Endpoint (for assignee selection)
# ========================

@router.get("/users", response_model=APIResponse)
def get_users(db: Session = Depends(get_db)):
    """Get all users for assignee selection"""
    try:
        users = db.query(User).filter(User.is_active == True).order_by(User.username).all()
        user_list = [{"id": u.id, "username": u.username, "email": u.email} for u in users]
        return APIResponse(data=user_list, message="Users retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================
# Column Endpoints
# ========================

@router.get("/columns", response_model=APIResponse)
def get_columns(db: Session = Depends(get_db)):
    """Get all task columns ordered by position"""
    try:
        columns = db.query(TaskColumn).order_by(TaskColumn.position).all()
        column_data = [TaskColumnResponse.model_validate(col) for col in columns]
        return APIResponse(data=column_data, message="Columns retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching columns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/columns", response_model=APIResponse)
def create_column(column: TaskColumnCreate, db: Session = Depends(get_db)):
    """Create a new task column"""
    try:
        # If position not provided, set to end
        if column.position is None:
            max_position = db.query(func.max(TaskColumn.position)).scalar() or -1
            column.position = max_position + 1
        
        new_column = TaskColumn(
            title=column.title,
            position=column.position
        )
        db.add(new_column)
        db.commit()
        db.refresh(new_column)
        
        return APIResponse(
            data=TaskColumnResponse.model_validate(new_column),
            message="Column created successfully"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating column: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/columns/{column_id}", response_model=APIResponse)
def update_column(column_id: int, column: TaskColumnUpdate, db: Session = Depends(get_db)):
    """Update a task column"""
    try:
        db_column = db.query(TaskColumn).filter(TaskColumn.id == column_id).first()
        if not db_column:
            raise HTTPException(status_code=404, detail="Column not found")
        
        if column.title is not None:
            db_column.title = column.title
        if column.position is not None:
            db_column.position = column.position
        
        db.commit()
        db.refresh(db_column)
        
        return APIResponse(
            data=TaskColumnResponse.model_validate(db_column),
            message="Column updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating column: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/columns/{column_id}", response_model=APIResponse)
def delete_column(column_id: int, db: Session = Depends(get_db)):
    """Delete a task column (cascades to tasks)"""
    try:
        db_column = db.query(TaskColumn).filter(TaskColumn.id == column_id).first()
        if not db_column:
            raise HTTPException(status_code=404, detail="Column not found")
        
        db.delete(db_column)
        db.commit()
        
        return APIResponse(data=None, message="Column deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting column: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================
# Task Endpoints
# ========================

@router.get("", response_model=APIResponse)
def get_tasks(
    column_id: Optional[int] = Query(None, description="Filter by column ID"),
    db: Session = Depends(get_db)
):
    """Get all tasks, optionally filtered by column"""
    try:
        query = db.query(Task)
        if column_id:
            query = query.filter(Task.column_id == column_id)
        
        tasks = query.order_by(Task.column_id, Task.position).all()
        
        task_responses = []
        for task in tasks:
            task_dict = TaskResponse.model_validate(task).model_dump()
            task_dict["assignee_ids"] = parse_json_field(task.assignee_ids)
            task_dict["tags"] = parse_json_field(task.tags)
            task_dict["attachments"] = parse_json_field(task.attachments)
            
            # Get assignee usernames
            if task_dict["assignee_ids"]:
                assignees = db.query(User).filter(User.id.in_(task_dict["assignee_ids"])).all()
                task_dict["assignees"] = [{"id": u.id, "username": u.username} for u in assignees]
            
            task_responses.append(task_dict)
        
        return APIResponse(data=task_responses, message="Tasks retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}", response_model=APIResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get a single task by ID"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task_dict = TaskResponse.model_validate(task).model_dump()
        task_dict["assignee_ids"] = parse_json_field(task.assignee_ids)
        task_dict["tags"] = parse_json_field(task.tags)
        task_dict["attachments"] = parse_json_field(task.attachments)
        
        if task_dict["assignee_ids"]:
            assignees = db.query(User).filter(User.id.in_(task_dict["assignee_ids"])).all()
            task_dict["assignees"] = [{"id": u.id, "username": u.username} for u in assignees]
        
        return APIResponse(data=task_dict, message="Task retrieved successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=APIResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    """Create a new task"""
    try:
        # Verify column exists
        column = db.query(TaskColumn).filter(TaskColumn.id == task.column_id).first()
        if not column:
            raise HTTPException(status_code=404, detail="Column not found")
        
        # If position not provided, set to end of column
        if task.position is None:
            max_position = db.query(func.max(Task.position)).filter(
                Task.column_id == task.column_id
            ).scalar() or -1
            task.position = max_position + 1
        
        # Validate and normalize priority
        priority_value = task.priority
        try:
            # Convert to enum to validate, then get the value string
            priority_enum = TaskPriorityEnum(priority_value)
            priority_value = priority_enum.value  # Get the string value ("Low", "Medium", "High")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {task.priority}. Must be one of: Low, Medium, High")
        
        new_task = Task(
            column_id=task.column_id,
            title=task.title,
            description=task.description,
            priority=priority_value,  # Store as string value
            assignee_ids=serialize_json_field(task.assignee_ids),
            tags=serialize_json_field(task.tags),
            due_date=task.due_date,
            attachments=serialize_json_field(task.attachments),
            position=task.position
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        task_dict = TaskResponse.model_validate(new_task).model_dump()
        task_dict["assignee_ids"] = task.assignee_ids
        task_dict["tags"] = task.tags
        task_dict["attachments"] = task.attachments
        
        return APIResponse(data=task_dict, message="Task created successfully")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{task_id}", response_model=APIResponse)
def update_task(task_id: int, task: TaskUpdate, db: Session = Depends(get_db)):
    """Update a task"""
    try:
        db_task = db.query(Task).filter(Task.id == task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.column_id is not None:
            column = db.query(TaskColumn).filter(TaskColumn.id == task.column_id).first()
            if not column:
                raise HTTPException(status_code=404, detail="Column not found")
            db_task.column_id = task.column_id
        
        # Update fields - check if field was provided (not None)
        # Note: Pydantic will include fields even if None, so we check explicitly
        if task.title is not None:
            db_task.title = task.title
        if task.description is not None:
            db_task.description = task.description
        if task.priority is not None:
            try:
                priority_enum = TaskPriorityEnum(task.priority)
                db_task.priority = priority_enum.value  # Store as string value
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid priority: {task.priority}")
        # Update assignee_ids (can be empty list)
        if task.assignee_ids is not None:
            db_task.assignee_ids = serialize_json_field(task.assignee_ids)
        # Update tags (can be empty list)
        if task.tags is not None:
            db_task.tags = serialize_json_field(task.tags)
        # Update due_date - allow None to clear the date
        # Check if due_date was provided in the request (not just default None)
        if hasattr(task, 'model_dump'):
            task_dict = task.model_dump(exclude_unset=True)
            if 'due_date' in task_dict:
                db_task.due_date = task.due_date
        elif task.due_date is not None:
            db_task.due_date = task.due_date
        if task.attachments is not None:
            db_task.attachments = serialize_json_field(task.attachments)
        if task.position is not None:
            db_task.position = task.position
        
        logger.info(f"Updating task {task_id} with fields: title={task.title}, priority={task.priority}, assignee_ids={task.assignee_ids}")
        
        db.commit()
        db.refresh(db_task)
        
        # Parse JSON fields before creating response
        assignee_ids = parse_json_field(db_task.assignee_ids)
        tags = parse_json_field(db_task.tags)
        attachments = parse_json_field(db_task.attachments)
        
        # Build response dict manually to avoid validation issues with JSON string fields
        task_dict = {
            "id": db_task.id,
            "column_id": db_task.column_id,
            "title": db_task.title,
            "description": db_task.description,
            "priority": db_task.priority,
            "assignee_ids": assignee_ids,
            "tags": tags,
            "due_date": db_task.due_date,
            "attachments": attachments,
            "position": db_task.position,
            "created_at": db_task.created_at,
            "updated_at": db_task.updated_at,
        }
        
        # Get assignee usernames if assignee_ids exist
        if assignee_ids:
            assignees = db.query(User).filter(User.id.in_(assignee_ids)).all()
            task_dict["assignees"] = [{"id": u.id, "username": u.username} for u in assignees]
        else:
            task_dict["assignees"] = []
        
        return APIResponse(data=task_dict, message="Task updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}", response_model=APIResponse)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Delete a task"""
    try:
        db_task = db.query(Task).filter(Task.id == task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        db.delete(db_task)
        db.commit()
        
        return APIResponse(data=None, message="Task deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================
# Board Data Endpoint (for frontend kanban)
# ========================

@router.get("/board/data", response_model=APIResponse)
def get_board_data(db: Session = Depends(get_db)):
    """Get complete board data (columns, tasks, column order) for kanban view"""
    try:
        # Get all columns ordered by position
        columns = db.query(TaskColumn).order_by(TaskColumn.position).all()
        
        # Get all tasks ordered by column and position
        tasks = db.query(Task).order_by(Task.column_id, Task.position).all()
        
        # Build column order list
        column_order = [f"column-{col.id}" for col in columns]
        
        # Build columns dict
        columns_dict = {}
        for col in columns:
            columns_dict[f"column-{col.id}"] = {
                "id": f"column-{col.id}",
                "title": col.title,
                "taskIds": []
            }
        
        # Build tasks dict and assign to columns
        tasks_dict = {}
        for task in tasks:
            task_id = f"task-{task.id}"
            column_key = f"column-{task.column_id}"
            
            if column_key in columns_dict:
                columns_dict[column_key]["taskIds"].append(task_id)
            
            # Get assignee user objects
            assignee_ids = parse_json_field(task.assignee_ids) or []
            assignees = []
            if assignee_ids:
                assignee_users = db.query(User).filter(User.id.in_(assignee_ids)).all()
                assignees = [{"id": u.id, "username": u.username} for u in assignee_users]
            
            task_dict = {
                "id": task_id,
                "title": task.title,
                "priority": task.priority,  # Already a string value ("Low", "Medium", "High")
                "assignee": assignee_ids,
                "assignees": assignees,
                "tags": parse_json_field(task.tags) or [],
                "date": task.due_date.isoformat() if task.due_date else None,
                "description": task.description,
                "attachments": parse_json_field(task.attachments) or [],
                "comments": []
            }
            tasks_dict[task_id] = task_dict
        
        board_data = {
            "tasks": tasks_dict,
            "columns": columns_dict,
            "columnOrder": column_order
        }
        
        return APIResponse(data=board_data, message="Board data retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching board data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================
# Comment Endpoints
# ========================

@router.get("/{task_id}/comments", response_model=APIResponse)
def get_task_comments(task_id: int, db: Session = Depends(get_db)):
    """Get all comments for a task"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        comments = db.query(TaskComment).filter(TaskComment.task_id == task_id).order_by(TaskComment.created_at).all()
        
        comment_responses = []
        for comment in comments:
            comment_dict = TaskCommentResponse.model_validate(comment).model_dump()
            if comment.user:
                comment_dict["username"] = comment.user.username
            comment_responses.append(comment_dict)
        
        return APIResponse(data=comment_responses, message="Comments retrieved successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching comments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comments", response_model=APIResponse)
def create_comment(comment: TaskCommentCreate, db: Session = Depends(get_db)):
    """Create a new task comment"""
    try:
        task = db.query(Task).filter(Task.id == comment.task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        user = db.query(User).filter(User.id == comment.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        new_comment = TaskComment(
            task_id=comment.task_id,
            user_id=comment.user_id,
            content=comment.content
        )
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)
        
        comment_dict = TaskCommentResponse.model_validate(new_comment).model_dump()
        comment_dict["username"] = user.username
        
        return APIResponse(data=comment_dict, message="Comment created successfully")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/comments/{comment_id}", response_model=APIResponse)
def update_comment(comment_id: int, comment: TaskCommentUpdate, db: Session = Depends(get_db)):
    """Update a task comment"""
    try:
        db_comment = db.query(TaskComment).filter(TaskComment.id == comment_id).first()
        if not db_comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        db_comment.content = comment.content
        db.commit()
        db.refresh(db_comment)
        
        comment_dict = TaskCommentResponse.model_validate(db_comment).model_dump()
        if db_comment.user:
            comment_dict["username"] = db_comment.user.username
        
        return APIResponse(data=comment_dict, message="Comment updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/comments/{comment_id}", response_model=APIResponse)
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    """Delete a task comment"""
    try:
        db_comment = db.query(TaskComment).filter(TaskComment.id == comment_id).first()
        if not db_comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        db.delete(db_comment)
        db.commit()
        
        return APIResponse(data=None, message="Comment deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

