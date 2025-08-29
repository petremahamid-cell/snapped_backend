# Snapped AI

A FastAPI backend for finding similar products from uploaded images.

## Features

- Upload and clip images
- Find similar products using Google Reverse Image Search via SerpAPI
- Filter out duplicate products
- Store search results for future reference

## API Endpoints

### Image Upload and Processing

- `POST /api/v1/images/upload`: Upload an image
- `POST /api/v1/images/clip`: Clip an uploaded image

### Product Search

- `POST /api/v1/images/search`: Search for similar products using an uploaded image

### Search History

- `GET /api/v1/images/searches/{search_id}`: Get results of a previous search
- `GET /api/v1/images/searches`: Get recent search results

## Setup and Installation

1. Clone the repository:
   ```
   git clone https://github.com/Eugene0910-super/Snapped_ai.git
   cd Snapped_ai
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On Unix (Linux/Mac)
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Create a `.env` file in the root directory (you can copy from `.env.example`)
   - Add your SerpAPI API key and other configuration options:
     ```
     SERPAPI_API_KEY=your_serpapi_api_key
     DATABASE_URL=sqlite:///./app.db
     MAX_SIMILAR_PRODUCTS=30
     HOST=0.0.0.0
     PORT=12000
     
     # Cloudinary settings (optional)
     CLOUDINARY_CLOUD_NAME=your_cloud_name
     CLOUDINARY_API_KEY=your_api_key
     CLOUDINARY_API_SECRET=your_api_secret
     USE_CLOUDINARY=false
     ```

5. Initialize the database:
   ```
   python -c "from app.db.init_db import init_db; import asyncio; asyncio.run(init_db())"
   ```

6. Run the application:
   ```
   python run.py
   ```

For more detailed setup instructions, see [SETUP.md](SETUP.md).

## API Documentation

Once the application is running, you can access the API documentation at:
- Swagger UI: `http://localhost:12000/docs`
- ReDoc: `http://localhost:12000/redoc`

## Python Compatibility

This application is compatible with:
- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13 (using SQLAlchemy 1.4)

## Performance Optimization

The application is optimized for fast response times:

1. **Asynchronous Processing**:
   - Asynchronous API calls to SerpAPI
   - Background tasks for database operations
   - Non-blocking I/O operations

2. **Caching Strategy**:
   - In-memory caching for development
   - Redis caching for production (optional)
   - Configurable TTL for cached results

3. **Database Optimization**:
   - SQLite optimizations (WAL mode, memory-mapped I/O)
   - Efficient indexing for faster queries
   - Connection pooling

4. **Algorithmic Efficiency**:
   - Efficient duplicate filtering algorithm
   - Thread pool for CPU-bound operations
   - Lazy loading of search results

5. **Error Handling and Resilience**:
   - Retry mechanism with exponential backoff
   - Circuit breaker pattern for external API calls
   - Graceful degradation when services are unavailable

6. **Monitoring and Profiling**:
   - Request timing middleware
   - Performance logging
   - Benchmarking tools

## Image Storage Options

The application supports three options for storing uploaded images:

1. **Local Storage** (default):
   - Images are stored in the `app/static/uploads` directory
   - Served directly from the FastAPI application
   - Simple setup with no external dependencies
   - Suitable for development and small-scale deployments

2. **Hybrid Storage** (optional):
   - Images are stored both locally and in Cloudinary
   - Provides redundancy and flexibility
   - Uses Cloudinary for public URLs when available
   - Falls back to local storage if Cloudinary is unavailable

3. **Cloudinary-Only Storage** (recommended for production):
   - Images are stored exclusively in Cloudinary
   - No local storage of images (only temporary files during processing)
   - Automatic CDN distribution for faster global access
   - Image transformations and optimizations
   - Better scalability for production deployments
   - Direct cropping in Cloudinary for better performance

### Enabling Cloudinary Storage

To enable Cloudinary storage:
1. Install the Cloudinary package: `pip install cloudinary`
2. Set up your Cloudinary credentials in the `.env` file:

#### For Hybrid Storage (both local and Cloudinary):
```
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
USE_CLOUDINARY=true
SAVE_LOCAL_COPY=true
REQUIRE_CLOUDINARY=false
```

#### For Cloudinary-Only Storage (recommended for production):
```
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
USE_CLOUDINARY=true
SAVE_LOCAL_COPY=false
REQUIRE_CLOUDINARY=true
```

3. Restart the application

### Cloudinary Configuration Options

- `USE_CLOUDINARY`: Enable or disable Cloudinary integration
- `SAVE_LOCAL_COPY`: Whether to save a local copy of images in addition to Cloudinary
- `REQUIRE_CLOUDINARY`: If true, the application will raise an error if Cloudinary upload fails; if false, it will fall back to local storage

The application will automatically use the appropriate storage method based on your configuration.

## Running with Redis Cache

For improved performance in production, you can run the application with Redis caching:

```bash
# Start Redis and the API with Docker Compose
docker-compose up -d

# Or run locally with Redis
./run_with_redis.sh
```

## Benchmarking

You can benchmark the API performance using the included benchmark script:

```bash
python benchmark.py --requests 100 --concurrent 10
```