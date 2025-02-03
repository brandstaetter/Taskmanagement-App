from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import pytest
from typing import Dict

from app.db.models.task import TaskState

def test_create_task(client: TestClient):
    task_data = {
        "title": "New Task",
        "description": "Task Description",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo"
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == task_data["title"]
    assert data["description"] == task_data["description"]
    assert data["state"] == task_data["state"]

def test_read_task(client: TestClient):
    # First create a task
    task_data = {
        "title": "Task to Read",
        "description": "Task Description",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo"
    }
    create_response = client.post("/api/v1/tasks", json=task_data)
    assert create_response.status_code == 200
    created_task = create_response.json()
    
    # Now read the task
    response = client.get(f"/api/v1/tasks/{created_task['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == task_data["title"]
    assert data["description"] == task_data["description"]

def test_read_tasks(client: TestClient):
    # Create multiple tasks
    task_data1 = {
        "title": "Task 1",
        "description": "Description 1",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo"
    }
    task_data2 = {
        "title": "Task 2",
        "description": "Description 2",
        "due_date": (datetime.now() + timedelta(days=2)).date().isoformat(),
        "state": "in_progress"
    }
    
    client.post("/api/v1/tasks", json=task_data1)
    client.post("/api/v1/tasks", json=task_data2)
    
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

def test_task_workflow(client: TestClient):
    # First create a task
    task_data = {
        "title": "Task Workflow",
        "description": "Testing the complete task workflow",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo"
    }
    create_response = client.post("/api/v1/tasks", json=task_data)
    assert create_response.status_code == 200
    created_task = create_response.json()
    assert created_task["state"] == "todo"
    
    # Start the task
    start_response = client.post(f"/api/v1/tasks/{created_task['id']}/start")
    assert start_response.status_code == 200
    started_task = start_response.json()
    assert started_task["state"] == "in_progress"
    assert started_task["started_at"] is not None
    
    # Complete the task
    complete_response = client.post(f"/api/v1/tasks/{created_task['id']}/complete")
    assert complete_response.status_code == 200
    completed_task = complete_response.json()
    assert completed_task["state"] == "done"
    assert completed_task["completed_at"] is not None

def test_delete_task(client: TestClient):
    # First create a task
    task_data = {
        "title": "Task to Delete",
        "description": "This task will be deleted",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo"
    }
    create_response = client.post("/api/v1/tasks", json=task_data)
    created_task = create_response.json()
    
    # Delete the task
    response = client.delete(f"/api/v1/tasks/{created_task['id']}")
    assert response.status_code == 200
    
    # Verify task is deleted
    get_response = client.get(f"/api/v1/tasks/{created_task['id']}")
    assert get_response.status_code == 404

def test_invalid_task_transitions(client: TestClient):
    # Create a task
    task_data = {
        "title": "Invalid Transitions",
        "description": "Testing invalid state transitions",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo"
    }
    create_response = client.post("/api/v1/tasks", json=task_data)
    created_task = create_response.json()
    
    # Complete task without starting (should work)
    complete_response = client.post(f"/api/v1/tasks/{created_task['id']}/complete")
    assert complete_response.status_code == 200
    
    # Try to start completed task (should fail)
    start_response = client.post(f"/api/v1/tasks/{created_task['id']}/start")
    assert start_response.status_code == 400
    
    # Try to complete already completed task (should fail)
    complete_again_response = client.post(f"/api/v1/tasks/{created_task['id']}/complete")
    assert complete_again_response.status_code == 400
