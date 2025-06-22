import type { Track } from '../App';

interface Props {
  tracks: Track[];
  onPlay: (track: Track) => void;
}

const TrackGrid = ({ tracks, onPlay }: Props) => (
  <div className="inline-grid grid-cols-5 gap-4">
    {tracks.map((track, i) => (
      <div
        key={i}
        onClick={() => onPlay(track)}
        className="bg-zinc-800 hover:bg-zinc-700 cursor-pointer rounded-lg p-4 transition"
      >
        <div className="aspect-square bg-zinc-600 rounded mb-3 flex items-center justify-center text-zinc-400 text-4xl">
          <img className='object-scale-down' src={track.thumbnail}></img>
        </div>
        <h3 className="text-white font-semibold truncate">{track.title}</h3>
        <p className="text-sm text-zinc-400 truncate">{track.artist}</p>
      </div>
    ))}
  </div>
);

export default TrackGrid;
