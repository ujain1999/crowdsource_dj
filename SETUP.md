# Setup Guide

This guide covers the complete setup process for running Crowdsource DJ locally.

## Prerequisites

- **Node.js** 18 or higher
- **Python** 3.14 or higher
- **npm** (comes with Node.js)
- **PostgreSQL** 14 or higher

## Backend Setup

### 1. Navigate to Backend Directory

```bash
cd backend
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

```bash
# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```
# Create the database first (if not exists)
createdb crowdsource_dj

DATABASE_URL=postgresql://user:password@localhost:5432/crowdsource_dj
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
HOST=0.0.0.0
PORT=8000
DEBUG=True
ALLOWED_ORIGINS=["http://localhost:5173"]
```

### 6. Start Backend Server

```bash
python main.py
```

The backend runs at `http://localhost:8000`. API documentation is available at `http://localhost:8000/docs`.

## Frontend Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment (Optional)

```bash
cp .env.example .env
```

Default values work for local development:
```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
```

The frontend runs at `http://localhost:5173`.

## Running Both Services

You'll need two terminal sessions:

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python main.py
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

## Testing the Application

1. Open `http://localhost:5173` in your browser
2. Click "Create Room" to create a new room
3. Share the room code with another browser tab/window
4. Open `http://localhost:5173` in the second tab
5. Enter the room code and click "Join Room"
6. Add songs using the search bar
7. Test synchronized playback across both tabs

## Available Scripts

### Frontend

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run type-check` | Run TypeScript type check |

### Backend

| Command | Description |
|---------|-------------|
| `python main.py` | Start server (development) |
| `uvicorn main:app --reload` | Start with auto-reload |

## Troubleshooting

### Backend Issues

- **Port 8000 in use**: Change the PORT in `.env` or kill the process using that port
- **Database error**: Ensure PostgreSQL is running and the database exists
- **Module not found**: Ensure virtual environment is activated and dependencies installed

### Frontend Issues

- **Connection refused**: Ensure backend is running at `http://localhost:8000`
- **WebSocket errors**: Check browser console for connection issues
- **Build errors**: Run `npm run type-check` to identify TypeScript issues

### Common Solutions

```bash
# Clear node_modules and reinstall
rm -rf node_modules
npm install

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +

# Clear Vite cache
rm -rf node_modules/.vite
```

## Production Build

### Frontend

```bash
npm run build
```

The built files are in the `dist/` directory and can be served by any static file server.

### Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

For production, use a proper ASGI server like Gunicorn with Uvicorn workers.

## Architecture Notes

- **WebSockets**: Used for real-time queue updates and synchronized playback
- **PostgreSQL**: Primary database
- **JWT**: Token-based authentication for protected routes
- **Tailwind CSS**: Utility-first styling with custom theme support
