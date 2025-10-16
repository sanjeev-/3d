# Blender Movies Full-Stack Application

A complete full-stack application for creating, editing, and rendering animated movies using Blender, with a modern web interface.

## Architecture Overview

```
blender-movies/
├── backend/           # Django REST API
│   ├── users/        # User authentication and management
│   ├── projects/     # Movie projects, assets, characters
│   ├── scenes/       # 3D scenes with Blender integration
│   └── config/       # Django settings and URL configuration
├── frontend/          # React + TypeScript + Three.js
│   └── src/
│       ├── api/      # Backend API client
│       ├── stores/   # State management (Zustand)
│       ├── components/ # React components
│       └── types/    # TypeScript definitions
├── shared/            # Shared Python scripts
├── movies/            # Individual movie projects
└── media/             # Uploaded files and renders (gitignored)
```

## Features

### Backend (Django + DRF)
- **JWT Authentication** with token refresh
- **RESTful API** for all resources
- **Blender Integration** - Programmatically create and modify .blend files
- **Database Models**:
  - User (custom user model)
  - Project (movie projects with settings)
  - Scene (individual scenes with associated Blender files)
  - SceneObject (objects placed in scenes with transforms)
  - Asset & Character (reusable resources)
  - RenderJob (render queue management)

### Frontend (React + TypeScript)
- **Three.js Scene Viewer** using React Three Fiber
- **Real-time 3D editing** with object manipulation
- **Project Dashboard** for managing movies
- **Authentication** with JWT tokens
- **TypeScript** for type safety
- **State Management** using Zustand

## Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+
- Blender 3.6+ (installed and in PATH)
- FFmpeg (for video export)

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Create superuser:
```bash
python manage.py createsuperuser
```

6. Run development server:
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## API Endpoints

### Authentication
- `POST /api/auth/login/` - Login with username/password
- `POST /api/auth/refresh/` - Refresh access token
- `POST /api/users/` - Register new user
- `GET /api/users/me/` - Get current user info

### Projects
- `GET /api/projects/` - List all projects
- `POST /api/projects/` - Create new project
- `GET /api/projects/{id}/` - Get project details
- `PATCH /api/projects/{id}/` - Update project
- `DELETE /api/projects/{id}/` - Delete project
- `GET /api/projects/{id}/scenes/` - Get all scenes for a project

### Scenes
- `GET /api/scenes/` - List all scenes
- `POST /api/scenes/` - Create new scene
- `GET /api/scenes/{id}/` - Get scene details
- `PATCH /api/scenes/{id}/` - Update scene
- `DELETE /api/scenes/{id}/` - Delete scene
- `POST /api/scenes/{id}/add_object/` - Add object to scene
- `POST /api/scenes/{id}/update_object/` - Update object in scene
- `POST /api/scenes/{id}/render/` - Start render job

### Assets & Characters
- `GET /api/assets/` - List assets
- `POST /api/assets/` - Upload new asset
- `GET /api/characters/` - List characters
- `POST /api/characters/` - Create character

## Database Models

### User
- `id` - Primary key
- `username` - Unique username
- `email` - Unique email
- `avatar` - Profile picture
- `bio` - User biography

### Project
- `id` - UUID primary key
- `owner` - Foreign key to User
- `title` - Project title
- `description` - Project description
- `resolution_width`, `resolution_height` - Video resolution
- `fps` - Frames per second
- `render_engine` - CYCLES or EEVEE
- `render_samples` - Render quality

### Scene
- `id` - UUID primary key
- `project` - Foreign key to Project
- `name` - Scene name
- `frame_start`, `frame_end` - Frame range
- `blend_file` - Path to .blend file (auto-generated)
- `blend_file_version` - Version tracking
- `order` - Scene order in movie

### SceneObject
- `id` - UUID primary key
- `scene` - Foreign key to Scene
- `object_type` - CHARACTER, ASSET, LIGHT, or CAMERA
- `character`/`asset` - Optional foreign keys
- `position_x/y/z` - 3D position
- `rotation_x/y/z` - 3D rotation (Euler angles)
- `scale_x/y/z` - 3D scale
- `properties` - JSON field for additional data

## Blender Integration

The `BlenderService` class (backend/scenes/services.py) provides:

1. **Scene Creation**: Automatically generates .blend files when scenes are created
2. **Object Management**: Add/update objects in Blender files via API
3. **Scene Export**: Generate previews and renders

### How it Works:
1. Frontend sends REST API request to add/update scene objects
2. Backend updates database models
3. `BlenderService` executes Blender in headless mode with Python scripts
4. Blender modifies the .blend file
5. Frontend fetches updated scene data

## Frontend Components

### Dashboard
- Display user's projects in a grid
- Create new projects
- Navigate to project details

### SceneViewer (Three.js)
- 3D visualization of Blender scenes
- Interactive object selection
- Orbit controls for navigation

### SceneEditor
- Edit scene objects
- Modify transforms (position, rotation, scale)
- Add new objects to scene
- Real-time updates to Blender files

## State Management

Uses Zustand for global state:
- `authStore` - Authentication state and user info
- API responses cached in React component state

## Development Workflow

### Creating a New Movie

1. **Create Project** (via API or frontend):
```bash
POST /api/projects/
{
  "title": "My Movie",
  "description": "An awesome animated short",
  "fps": 24,
  "resolution_width": 1920,
  "resolution_height": 1080
}
```

2. **Create Scene**:
```bash
POST /api/scenes/
{
  "project": "<project-id>",
  "name": "Scene 1",
  "frame_start": 1,
  "frame_end": 120
}
```

3. **Add Objects to Scene** (via frontend Scene Editor or API):
```bash
POST /api/scenes/<scene-id>/add_object/
{
  "object_type": "ASSET",
  "name": "Cube",
  "position_x": 0,
  "position_y": 0,
  "position_z": 0
}
```

4. **Edit in Frontend**:
- Open scene in Scene Editor
- Use Three.js viewer to visualize
- Modify object transforms
- Changes automatically update Blender file

5. **Render**:
```bash
POST /api/scenes/<scene-id>/render/
{
  "preset": "medium"
}
```

## Running Migrations

After modifying models:

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

## Production Deployment

### Backend
- Set `DEBUG=False` in settings.py
- Configure PostgreSQL database
- Set up proper CORS_ALLOWED_ORIGINS
- Use Gunicorn or uWSGI
- Configure Celery for background render jobs
- Set up media file storage (S3, etc.)

### Frontend
```bash
npm run build
```
- Serve `dist/` directory with Nginx or CDN
- Configure proper API URL environment variable

## Environment Variables

Create `.env` file in backend:
```
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost/dbname
ALLOWED_HOSTS=localhost,127.0.0.1
```

Create `.env` file in frontend:
```
VITE_API_URL=http://localhost:8000/api
```

## Tech Stack

**Backend:**
- Django 4.2
- Django REST Framework
- djangorestframework-simplejwt
- django-cors-headers
- Python 3.9+

**Frontend:**
- React 18
- TypeScript 5
- Vite (build tool)
- React Three Fiber (@react-three/fiber)
- Three.js
- Zustand (state management)
- Axios (HTTP client)
- React Router DOM

**3D & Rendering:**
- Blender 3.6+ (headless)
- FFmpeg (video encoding)

## Future Enhancements

- [ ] Asset library browser
- [ ] Character rigging interface
- [ ] Animation timeline editor
- [ ] Real-time collaboration
- [ ] Cloud rendering with progress updates
- [ ] Video preview generation
- [ ] Advanced camera controls
- [ ] Material editor
- [ ] Lighting presets
- [ ] Sound integration

## Troubleshooting

### Backend Issues

**Blender not found:**
```bash
# Add Blender to PATH or specify full path in BlenderService
export PATH=$PATH:/path/to/blender
```

**Migration errors:**
```bash
python manage.py makemigrations --empty <appname>
```

### Frontend Issues

**CORS errors:**
- Check `CORS_ALLOWED_ORIGINS` in Django settings
- Verify Vite proxy configuration

**Three.js not rendering:**
- Check browser console for WebGL errors
- Ensure GPU acceleration is enabled

## License

[Your License Here]

## Contributors

[Your Name/Team]
