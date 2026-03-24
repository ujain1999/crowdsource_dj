# Crowdsource DJ
> Escape the tyranny of the AUX authoritarian

A music streaming application where users can create or join rooms to listen to music together with synchronized playback and chat.

## Features

- **Room Management**: Create rooms with unique 12-character codes or join existing ones
- **Music Queue**: Add songs via YouTube URL or search query
- **Synchronized Playback**: All listeners hear the same track at the same position
- **Real-time Chat**: Room-based messaging for participants
- **Admin Controls**: Room creators can manage playback and queue


## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.14+
- PostgreSQL 14+

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Start server
python main.py
# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Frontend Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
# Frontend runs at http://localhost:5173
```

## Project Structure

```
crowdsource_dj_new/
├── src/                      # React frontend
│   ├── components/           # UI components
│   │   ├── AudioPlayer.tsx   # Music player
│   │   ├── Chat.tsx          # Chat
│   │   ├── Queue.tsx         # Song queue
│   │   ├── SearchBar.tsx     # Song search
│   │   ├── AuthModal.tsx     # Sign in/up
│   │   └── ThemeToggle.tsx   # Theme switch
│   ├── contexts/             # State management
│   │   ├── ThemeContext.tsx  # Theme state
│   │   ├── RoomContext.tsx   # Room state
│   │   └── AuthContext.tsx   # Auth state
│   ├── pages/
│   │   ├── LandingPage.tsx   # Join/create room
│   │   └── RoomPage.tsx      # Main room
│   └── utils/
│       ├── api.ts            # REST API calls
│       ├── websocket.ts      # WebSocket client
│       └── auth.ts           # Auth utilities
├── backend/                  # FastAPI backend
│   ├── main.py               # App entry point
│   ├── routes/               # API endpoints
│   │   ├── auth.py           # Authentication
│   │   ├── rooms.py          # Room management
│   │   ├── songs.py          # Song/queue API
│   │   ├── chat.py           # Chat messages
│   │   └── ws.py             # WebSocket handler
│   └── websocket_manager.py  # WebSocket coordination
└── dist/                     ßß# Production build
```

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rooms/create` | POST | Create a new room |
| `/api/rooms/{code}` | GET | Get room details |
| `/api/auth/register` | POST | User registration |
| `/api/auth/login` | POST | User login |
| `/api/songs/{room_code}/add` | POST | Add song to queue |
| `/api/songs/{room_code}/queue` | GET | Get room queue |
| `/api/ws/{room_code}/{user_id}/{username}` | WS | Real-time sync |

## Environment Variables

### Backend (.env)

```
DATABASE_URL=postgresql://user:password@localhost:5432/crowdsource_dj
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
HOST=0.0.0.0
PORT=8000
DEBUG=True
ALLOWED_ORIGINS=["http://localhost:5173"]
```

### Frontend (.env)

```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

## Development

```bash
# Run type check
npm run type-check

# Build for production
npm run build
```

## Future Improvements
- Reccomendations
- Autoplay
- Keyboard navigation
- Better admin controls
- Voteskip functionality
