const Header = () => (
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
);

export default Header;
