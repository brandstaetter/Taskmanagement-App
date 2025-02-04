from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi.testclient import TestClient

from taskmanagement_app.core.config import get_settings

settings = get_settings()


def test_create_task(client: TestClient) -> None:
    """Test creating a new task."""
    task_data: Dict[str, Any] = {
        "title": "New Task",
        "description": "Task Description",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == task_data["title"]
    assert data["description"] == task_data["description"]
    assert data["state"] == task_data["state"]


def test_read_task(client: TestClient) -> None:
    """Test reading a single task."""
    # First create a task
    task_data: Dict[str, Any] = {
        "title": "Task to Read",
        "description": "Task Description",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo",
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
    assert data["state"] == task_data["state"]


def test_read_tasks(client: TestClient) -> None:
    """Test reading multiple tasks."""
    # Create multiple tasks
    task_data1: Dict[str, Any] = {
        "title": "Task 1",
        "description": "Description 1",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo",
    }
    task_data2: Dict[str, Any] = {
        "title": "Task 2",
        "description": "Description 2",
        "due_date": (datetime.now() + timedelta(days=2)).date().isoformat(),
        "state": "todo",
    }

    response1 = client.post("/api/v1/tasks", json=task_data1)
    assert response1.status_code == 200
    response2 = client.post("/api/v1/tasks", json=task_data2)
    assert response2.status_code == 200

    # Get all tasks
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    tasks = {task["title"]: task for task in data}
    assert task_data1["title"] in tasks
    assert task_data2["title"] in tasks


def test_task_workflow(client: TestClient) -> None:
    """Test the complete task workflow: create -> start -> complete."""
    # Create a task
    task_data: Dict[str, Any] = {
        "title": "Workflow Task",
        "description": "Testing workflow",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    task = response.json()
    assert task["state"] == "todo"

    # Start the task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 200
    task = response.json()
    assert task["state"] == "in_progress"
    assert task["started_at"] is not None

    # Complete the task
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 200
    task = response.json()
    assert task["state"] == "done"
    assert task["completed_at"] is not None


def test_delete_task(client: TestClient) -> None:
    """Test deleting a task."""
    # Create a task
    task_data: Dict[str, Any] = {
        "title": "Task to Delete",
        "description": "This will be deleted",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    task = response.json()

    # Delete the task
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200

    # Verify task is deleted
    response = client.get(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 404


def test_invalid_task_transitions(client: TestClient) -> None:
    """Test invalid task state transitions."""
    # Create a task
    task_data: Dict[str, Any] = {
        "title": "Invalid Transitions Task",
        "description": "Testing invalid transitions",
        "due_date": (datetime.now() + timedelta(days=1)).date().isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    task = response.json()

    # Try to complete a task that hasn't been started
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 400

    # Start the task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 200

    # Try to start an already started task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 400

    # Complete the task
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 200

    # Try to start a completed task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 400

    # Try to complete an already completed task
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 400
