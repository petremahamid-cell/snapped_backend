import pytest
from fastapi.testclient import TestClient
from app.main import app
import os
import shutil
from app.core.config import settings

client = TestClient(app)

# Test data
test_image_path = "tests/data/test_image.jpg"

@pytest.fixture(scope="module")
def setup_test_data():
    # Create test directories
    os.makedirs("tests/data", exist_ok=True)
    os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
    
    # Create a test image if it doesn't exist
    if not os.path.exists(test_image_path):
        # Create a simple test image
        from PIL import Image
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save(test_image_path)
    
    yield
    
    # Clean up
    if os.path.exists(test_image_path):
        os.remove(test_image_path)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Snapped AI API"}

def test_upload_image(setup_test_data):
    with open(test_image_path, "rb") as f:
        response = client.post(
            "/api/v1/images/upload",
            files={"file": ("test_image.jpg", f, "image/jpeg")}
        )
    assert response.status_code == 200
    result = response.json()
    assert "image_path" in result
    assert result["message"] == "Image uploaded successfully"
    
    # Clean up the uploaded file
    if os.path.exists(result["image_path"]):
        os.remove(result["image_path"])

def test_clip_image(setup_test_data):
    # First upload an image
    with open(test_image_path, "rb") as f:
        upload_response = client.post(
            "/api/v1/images/upload",
            files={"file": ("test_image.jpg", f, "image/jpeg")}
        )
    
    image_path = upload_response.json()["image_path"]
    
    # Now clip the image
    clip_data = {
        "image_path": image_path,
        "x": 10,
        "y": 10,
        "width": 50,
        "height": 50
    }
    
    response = client.post("/api/v1/images/clip", data=clip_data)
    assert response.status_code == 200
    result = response.json()
    assert "image_path" in result
    assert result["message"] == "Image clipped successfully"
    
    # Clean up the files
    if os.path.exists(image_path):
        os.remove(image_path)
    if os.path.exists(result["image_path"]):
        os.remove(result["image_path"])

# Note: We're not testing the actual search functionality as it requires a SerpAPI key
# and makes external API calls. In a real test suite, you would mock these calls.