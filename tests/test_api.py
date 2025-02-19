from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi.testclient import TestClient

from taskmanagement_app.core.config import get_settings

settings = get_settings()


def create_test_task(client: TestClient, title: str = "Test Task") -> Dict[str, Any]:
    """Create a test task with given title."""
    task_data: Dict[str, Any] = {
        "title": title,
        "description": "Test Description",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    return response.json()


def verify_task_state(task: Dict[str, Any], expected_state: str) -> None:
    """Verify task is in expected state with correct timestamp handling."""
    assert task["state"] == expected_state
    if expected_state == "todo":
        assert task["started_at"] is None
        assert task["completed_at"] is None
    elif expected_state == "in_progress":
        assert task["started_at"] is not None
        assert task["completed_at"] is None
    elif expected_state == "done":
        assert task["started_at"] is not None
        assert task["completed_at"] is not None
    elif expected_state == "archived":
        pass  # No specific timestamp requirements for archived state


def verify_reset_to_todo(client: TestClient, task_id: int) -> None:
    """Verify that a task can be reset to todo state."""
    response = client.patch(f"/api/v1/tasks/{task_id}/reset-to-todo")
    assert response.status_code == 200
    reset_task = response.json()
    verify_task_state(reset_task, "todo")


def test_create_task(client: TestClient) -> None:
    """Test creating a new task."""
    task_data: Dict[str, Any] = {
        "title": "New Task",
        "description": "Task Description",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
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
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
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
        "title": "Task 1 read tasks",
        "description": "Description 1",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "state": "todo",
    }
    task_data2: Dict[str, Any] = {
        "title": "Task 2 read tasks",
        "description": "Description 2",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "state": "todo",
    }

    response1 = client.post("/api/v1/tasks", json=task_data1)
    assert response1.status_code == 200
    print(f"Created task 1: {response1.json()}")

    response2 = client.post("/api/v1/tasks", json=task_data2)
    assert response2.status_code == 200
    print(f"Created task 2: {response2.json()}")

    # Get all non-archived tasks (default behavior)
    response = client.get("/api/v1/tasks")  # Default is include_archived=false
    assert response.status_code == 200
    data = response.json()
    print(f"Initial tasks: {data}")
    assert len(data) >= 2
    tasks = {task["title"]: task for task in data}
    assert task_data1["title"] in tasks
    assert task_data2["title"] in tasks

    # Archive one task
    task1_id = tasks[task_data1["title"]]["id"]
    start_response = client.post(f"/api/v1/tasks/{task1_id}/start")
    print(f"Start task response: {start_response.json()}")
    complete_response = client.post(f"/api/v1/tasks/{task1_id}/complete")
    print(f"Complete task response: {complete_response.json()}")
    archive_response = client.delete(f"/api/v1/tasks/{task1_id}")
    print(f"Archive task response: {archive_response.json()}")

    # Verify it's not in the default list
    response = client.get("/api/v1/tasks")  # Default is include_archived=false
    assert response.status_code == 200
    data = response.json()
    print(f"Tasks after archive (default): {data}")
    tasks = {task["title"]: task for task in data}
    assert task_data1["title"] not in tasks
    assert task_data2["title"] in tasks

    # Verify it is in the list when including archived tasks
    response = client.get("/api/v1/tasks", params={"include_archived": True})
    assert response.status_code == 200
    data = response.json()
    print(f"Tasks after archive (include_archived=True): {data}")
    tasks = {task["title"]: task for task in data}
    assert task_data1["title"] in tasks
    assert task_data2["title"] in tasks


def test_task_workflow(client: TestClient) -> None:
    """Test the complete task workflow: create -> start -> complete."""
    # Create a task
    task_data: Dict[str, Any] = {
        "title": "Workflow Task",
        "description": "Testing workflow",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
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
    """Test deleting (archiving) a task."""
    # Create a task
    task_data: Dict[str, Any] = {
        "title": "Task to Delete",
        "description": "This will be archived",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    task = response.json()

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

    # Delete (archive) the task
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200
    archived_task = response.json()
    assert archived_task["state"] == "archived"

    # Verify task is archived
    response = client.get(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200
    task = response.json()
    assert task["state"] == "archived"

    # Verify task is not in active tasks list
    response = client.get("/api/v1/tasks", params={"include_archived": False})
    assert response.status_code == 200
    tasks = response.json()
    assert not any(t["id"] == task["id"] for t in tasks)

    # Verify task is in the list when including archived tasks
    response = client.get("/api/v1/tasks", params={"include_archived": True})
    assert response.status_code == 200
    tasks = response.json()
    assert any(t["id"] == task["id"] for t in tasks)


def test_invalid_task_transitions(client: TestClient) -> None:
    """Test invalid task state transitions."""
    # Create a task
    task_data: Dict[str, Any] = {
        "title": "Invalid Transitions Task",
        "description": "Testing invalid transitions",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
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


def test_archive_task(client: TestClient) -> None:
    """Test archiving a task."""
    # Create and complete a task first
    task_data: Dict[str, Any] = {
        "title": "Task to Archive",
        "description": "This will be archived",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    task = response.json()

    # Start the task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 200

    # Complete the task
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 200

    # Archive the task
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200
    archived_task = response.json()
    assert archived_task["state"] == "archived"

    # Verify task is not in active tasks list
    response = client.get("/api/v1/tasks", params={"include_archived": False})
    assert response.status_code == 200
    tasks = response.json()
    assert not any(t["id"] == task["id"] for t in tasks)

    # Verify task is in the list when including archived tasks
    response = client.get("/api/v1/tasks", params={"include_archived": True})
    assert response.status_code == 200
    tasks = response.json()
    assert any(t["id"] == task["id"] for t in tasks)


def test_invalid_task_archive(client: TestClient) -> None:
    """Test invalid task archival attempts."""
    # Create a task
    task_data: Dict[str, Any] = {
        "title": "Task with Invalid Archive",
        "description": "Testing invalid archive",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    task = response.json()

    # Archive a task in todo state (should work now)
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200

    # Create another task for testing in_progress state
    response = client.post("/api/v1/tasks", json=task_data)
    assert response.status_code == 200
    task = response.json()

    # Start the task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 200

    # Try to archive an in-progress task (should fail)
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 400

    # Complete the task
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 200

    # Archive the completed task (should work)
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200

    # Try to archive an already archived task (should fail)
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 400


def test_task_filters(client: TestClient) -> None:
    """Test task filtering functionality."""
    # Create tasks with different states
    states = ["todo", "in_progress", "done", "archived"]
    tasks: Dict[str, Dict[str, Any]] = {}

    for state in states:
        task_data: Dict[str, Any] = {
            "title": f"{state.title()} Task",
            "description": f"Task in {state} state",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "state": "todo",
        }
        response = client.post("/api/v1/tasks", json=task_data)
        assert response.status_code == 200
        tasks[state] = response.json()

        # Move task through states
        task_id = tasks[state]["id"]
        if state in ["in_progress", "done", "archived"]:
            response = client.post(f"/api/v1/tasks/{task_id}/start")
            assert response.status_code == 200
        if state in ["done", "archived"]:
            response = client.post(f"/api/v1/tasks/{task_id}/complete")
            assert response.status_code == 200
        if state == "archived":
            response = client.delete(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200

    # Test filtering by state
    for state in states:
        # For archived tasks, we need to explicitly include them
        params = {"state": state}
        if state == "archived":
            params["include_archived"] = "True"

        response = client.get("/api/v1/tasks", params=params)
        assert response.status_code == 200
        filtered_tasks = response.json()

        # Verify only tasks in requested state are returned
        task_states = [t["state"] for t in filtered_tasks]
        assert all(
            s == state for s in task_states
        ), f"Expected all tasks to be in {state} state, got {task_states}"

        # Verify our test task is included
        assert any(
            t["id"] == tasks[state]["id"] for t in filtered_tasks
        ), f"Test task for state {state} not found in filtered results"

    # Test filtering by due date
    response = client.get(
        "/api/v1/tasks",
        params={
            "due_before": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        },
    )
    assert response.status_code == 200
    filtered_tasks = response.json()
    assert len(filtered_tasks) >= len(states) - 1  # All except archived


def test_task_search(client: TestClient) -> None:
    """Test task search functionality."""
    # Create task1
    task_data1 = {
        "title": "Team Meeting",
        "description": "Weekly sync",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "state": "todo",
    }

    # Create task2
    task_data2 = {
        "title": "Code Review",
        "description": "Review pull requests",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "state": "todo",
    }

    # Create task1
    print("\nCreating task1...")
    response = client.post("/api/v1/tasks", json=task_data1)
    assert response.status_code == 200, f"Failed to create task1: {response.text}"
    task1 = response.json()
    print(f"Created task1: {task1}")

    # Create task2
    print("\nCreating task2...")
    response = client.post("/api/v1/tasks", json=task_data2)
    assert response.status_code == 200, f"Failed to create task2: {response.text}"
    task2 = response.json()
    print(f"Created task2: {task2}")

    # Move task1 through states: todo -> in_progress -> done -> archived
    task1_id = task1["id"]

    # Start task1
    print("\nStarting task1...")
    response = client.post(f"/api/v1/tasks/{task1_id}/start")
    assert response.status_code == 200, f"Failed to start task1: {response.text}"
    task1 = response.json()
    print(f"Started task1: {task1}")
    assert task1["state"] == "in_progress"

    # Complete task1
    print("\nCompleting task1...")
    response = client.post(f"/api/v1/tasks/{task1_id}/complete")
    assert response.status_code == 200, f"Failed to complete task1: {response.text}"
    task1 = response.json()
    print(f"Completed task1: {task1}")
    assert task1["state"] == "done"

    # Archive task1 (only done tasks can be archived)
    print("\nArchiving task1...")
    response = client.delete(f"/api/v1/tasks/{task1_id}")
    assert response.status_code == 200, f"Failed to archive task1: {response.text}"
    task1 = response.json()
    print(f"Archived task1: {task1}")
    assert task1["state"] == "archived"

    # Test searching by title (default: don't include archived)
    print("\nSearching for 'meeting' without archived...")
    response = client.get("/api/v1/tasks/search/", params={"q": "meeting"})
    assert response.status_code == 200, f"Search failed: {response.text}"
    results = response.json()
    print(f"Search results for 'meeting' (without archived): {results}")
    assert not any(
        t["id"] == task1["id"] for t in results
    ), "Archived task should not be found"
    assert not any(
        t["id"] == task2["id"] for t in results
    ), "Task without 'meeting' in title/description should not be found"

    # Test searching with archived tasks included
    print("\nSearching for 'meeting' with archived...")
    response = client.get(
        "/api/v1/tasks/search/", params={"q": "meeting", "include_archived": True}
    )
    assert response.status_code == 200, f"Search with archived failed: {response.text}"
    results = response.json()
    print(f"Search results for 'meeting' (with archived): {results}")
    assert any(
        t["id"] == task1["id"] for t in results
    ), "Archived task should be found when include_archived=True"
    assert not any(
        t["id"] == task2["id"] for t in results
    ), "Task without 'meeting' in title/description should not be found"

    # Test searching by description
    print("\nSearching for 'pull requests'...")
    response = client.get("/api/v1/tasks/search/", params={"q": "pull requests"})
    assert response.status_code == 200, f"Search by description failed: {response.text}"
    results = response.json()
    print(f"Search results for 'pull requests': {results}")
    assert not any(
        t["id"] == task1["id"] for t in results
    ), "Task without 'pull requests' in title/description should not be found"
    assert any(
        t["id"] == task2["id"] for t in results
    ), "Task with 'pull requests' in description should be found"

    # Test case-insensitive search
    print("\nTesting case-insensitive search...")
    response = client.get("/api/v1/tasks/search/", params={"q": "MEETING"})
    assert (
        response.status_code == 200
    ), f"Case-insensitive search failed: {response.text}"
    results = response.json()
    print(f"Search results for 'MEETING': {results}")
    assert not any(
        t["id"] == task1["id"] for t in results
    ), "Archived task should not be found"
    assert not any(
        t["id"] == task2["id"] for t in results
    ), "Task without 'meeting' in title/description should not be found"


def test_read_due_tasks(client: TestClient) -> None:
    """Test reading due tasks."""
    # Create a task due soon
    task_data1: Dict[str, Any] = {
        "title": "Due Task",
        "description": "This task is due soon",
        "due_date": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data1)
    assert response.status_code == 200
    task1 = response.json()

    # Create a task not due soon
    task_data2: Dict[str, Any] = {
        "title": "Not Due Task",
        "description": "This task is not due soon",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data2)
    assert response.status_code == 200
    task2 = response.json()

    # Create a due task that will be archived
    task_data3: Dict[str, Any] = {
        "title": "Due Archived Task",
        "description": "This task is due soon but archived",
        "due_date": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
        "state": "todo",
    }
    response = client.post("/api/v1/tasks", json=task_data3)
    assert response.status_code == 200
    task3 = response.json()

    # Move task3 through states: todo -> in_progress -> done -> archived
    task3_id = task3["id"]
    response = client.post(f"/api/v1/tasks/{task3_id}/start")
    assert response.status_code == 200
    task3 = response.json()
    assert task3["state"] == "in_progress"

    response = client.post(f"/api/v1/tasks/{task3_id}/complete")
    assert response.status_code == 200
    task3 = response.json()
    assert task3["state"] == "done"

    response = client.delete(f"/api/v1/tasks/{task3_id}")
    assert response.status_code == 200
    task3 = response.json()
    assert task3["state"] == "archived"

    # Get due tasks
    response = client.get("/api/v1/tasks/due/")
    assert response.status_code == 200
    due_tasks = response.json()

    # Verify only non-archived due task is returned
    assert any(t["id"] == task1["id"] for t in due_tasks), "Due task should be included"
    assert not any(
        t["id"] == task2["id"] for t in due_tasks
    ), "Not due task should be excluded"
    assert not any(
        t["id"] == task3["id"] for t in due_tasks
    ), "Archived due task should be excluded"


def test_reset_task_to_todo(client: TestClient) -> None:
    """Test resetting tasks to todo state from various states."""
    # Test resetting from in_progress
    task = create_test_task(client, "Reset from In Progress")
    
    # Start the task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 200
    verify_task_state(response.json(), "in_progress")
    
    # Reset to todo
    verify_reset_to_todo(client, task["id"])
    
    # Test resetting from done
    task = create_test_task(client, "Reset from Done")
    
    # Complete the task (start -> complete)
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 200
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 200
    verify_task_state(response.json(), "done")
    
    # Reset to todo
    verify_reset_to_todo(client, task["id"])
    
    # Test resetting from archived
    task = create_test_task(client, "Reset from Archived")
    
    # Archive the task (it's in todo state, which is allowed)
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200
    verify_task_state(response.json(), "archived")
    
    # Reset to todo
    verify_reset_to_todo(client, task["id"])
    
    # Test resetting a non-existent task
    response = client.patch("/api/v1/tasks/99999/reset-to-todo")
    assert response.status_code == 404


def test_task_state_transitions_edge_cases(client: TestClient) -> None:
    """Test edge cases in task state transitions."""
    task = create_test_task(client, "Edge Case Task")
    
    # Try to complete a task without starting it first
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 400
    
    # Try to start an already started task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 200
    verify_task_state(response.json(), "in_progress")
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 400
    
    # Try to complete an already completed task
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 200
    verify_task_state(response.json(), "done")
    response = client.post(f"/api/v1/tasks/{task['id']}/complete")
    assert response.status_code == 400
    
    # Try to start a completed task
    response = client.post(f"/api/v1/tasks/{task['id']}/start")
    assert response.status_code == 400
    
    # Try operations on a non-existent task
    response = client.post("/api/v1/tasks/99999/start")
    assert response.status_code == 404
    response = client.post("/api/v1/tasks/99999/complete")
    assert response.status_code == 404
