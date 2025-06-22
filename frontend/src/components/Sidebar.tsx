const Sidebar = () => (
  <aside className="w-60 bg-zinc-950 p-4 flex flex-col gap-6 shadow-lg">
    <h1 className="text-2xl font-bold text-white">🎵 DJ</h1>
    <nav className="flex flex-col gap-3 text-zinc-300">
      <button className="hover:text-white text-left">🏠 Home</button>
      <button className="hover:text-white text-left">🔍 Search</button>
      <button className="hover:text-white text-left">📁 Library</button>
      <button className="hover:text-white text-left">🕘 History</button>
      <button className="hover:text-white text-left">⬆️ Upload</button>
    </nav>
    <div className="mt-auto text-xs text-zinc-500">© 2025 Crowdsource DJ</div>
  </aside>
);

export default Sidebar;
