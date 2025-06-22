import { useEffect, useState } from 'react';
import TrackGrid from './components/TrackGrid';
import PlayerBar from './components/PlayerBar';

export interface Track {
  title: string;
  artist: string;
  file: string;
  thumbnail: string;
}

function App() {
  const [, setQueue] = useState<Track[]>([]);
  const [current, setCurrent] = useState<Track | null>(null);
  const [suggestions, setSuggestions] = useState<Track[]>([]);

  useEffect(() => {
    fetch('http://127.0.0.1:5000/api/suggestions')
      .then(res => res.json())
      .then(setSuggestions);

    fetch('http://127.0.0.1:5000/api/queue')
      .then(res => res.json())
      .then(setQueue);
  }, []);

  const playTrack = (track: Track) => {
    setCurrent(track);
  };

  return (
    <div className="flex h-screen bg-zinc-900 text-white">
      {/* Sidebar */}
      <aside className="w-60 bg-zinc-950 p-4 flex flex-col gap-6 shadow-lg">
        <h1 className="text-2xl font-bold">🎵 DJ</h1>
        <nav className="flex flex-col gap-3 text-zinc-300">
          <button className="hover:text-white text-left">🏠 Home</button>
          <button className="hover:text-white text-left">🔍 Search</button>
          <button className="hover:text-white text-left">📁 Library</button>
          <button className="hover:text-white text-left">🕘 History</button>
          <button className="hover:text-white text-left">⬆️ Upload</button>
        </nav>
        <div className="mt-auto text-xs text-zinc-500">© 2025 Crowdsource DJ</div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-zinc-900 px-6 py-4 flex justify-between items-center border-b border-zinc-800">
          <input
            type="text"
            placeholder="Search..."
            className="bg-zinc-800 text-white px-4 py-2 rounded w-1/3"
          />
          <div className="flex items-center gap-4">
            <button className="bg-blue-600 px-4 py-2 rounded hover:bg-blue-700 text-white">Upload</button>
            <div className="w-8 h-8 rounded-full bg-zinc-600" />
          </div>
        </header>

        {/* Track grid */}
        <main className="flex-1 overflow-y-auto p-6">
          <h2 className="text-2xl font-bold mb-4">Recommended For You</h2>
          <TrackGrid tracks={suggestions} onPlay={playTrack} />
        </main>

        {/* Player */}
        <PlayerBar track={current} />
      </div>
    </div>
  );
}

export default App;
