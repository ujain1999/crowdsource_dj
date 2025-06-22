import type { Track } from '../App';

interface Props {
  track: Track | null;
}

const PlayerBar = ({ track }: Props) => {
  if (!track) return null;

  return (
    <div className="bg-zinc-950 border-t border-zinc-800 px-6 py-3 flex items-center gap-4">
      <div className="w-12 h-12 bg-zinc-700 rounded flex items-center justify-center text-zinc-400">🎵</div>
      <div className="flex-1">
        <p className="font-semibold text-white">{track.title}</p>
        <p className="text-sm text-zinc-400">{track.artist}</p>
      </div>
      <audio src={track.file} controls autoPlay className="w-72" />
    </div>
  );
};

export default PlayerBar;
