import os
import pytest
from pymongo import MongoClient
from bson.objectid import ObjectId
from app import app, mongo

TEST_DB_URI = "mongodb://localhost:27017/test_student_db"

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["MONGO_URI"] = TEST_DB_URI

    # Connect directly to the local test database
    direct_client = MongoClient(TEST_DB_URI)
    test_db = direct_client["test_student_db"]
    
    # Explicitly bind the app's PyMongo instances to the test database connection
    mongo.db = test_db
    mongo.cx = direct_client

    # Setup: clear and populate test data
    with app.app_context():
        mongo.db.students.delete_many({})
        mongo.db.students.insert_one({
            "_id": ObjectId("66fddff25f4b5f6a0a123456"),
            "name": "Test Student",
            "email": "test@student.com",
            "course": "Flask"
        })

    with app.test_client() as test_client:
        yield test_client

    # Teardown: drop test database and close connection
    with app.app_context():
        direct_client.drop_database("test_student_db")
        direct_client.close()


def test_home_page(client):
    """Test if home page loads correctly"""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Test Student" in response.data


def test_add_student(client):
    """Test adding a new student"""
    data = {"name": "New User", "email": "new@user.com", "course": "Python"}
    response = client.post('/add', data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"New User" in response.data


def test_update_student(client):
    """Test updating a student"""
    student_id = "66fddff25f4b5f6a0a123456"
    data = {"name": "Updated Name", "email": "updated@student.com", "course": "Updated Course"}
    response = client.post(f'/update/{student_id}', data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Updated Name" in response.data


def test_delete_student(client):
    """Test deleting a student"""
    # Add a temporary student
    with app.app_context():
        student_id = mongo.db.students.insert_one({
            "name": "Temp User",
            "email": "temp@user.com",
            "course": "Temp Course"
        }).inserted_id

    response = client.get(f'/delete/{student_id}', follow_redirects=True)
    assert response.status_code == 200
    assert b"Temp User" not in response.data