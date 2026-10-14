import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Search, X } from "lucide-react";
import { searchApi } from "@/lib/api";

export function SearchBar() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [suggestError, setSuggestError] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setSuggestions([]);
      setSuggestError(false);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      searchApi
        .suggest(q)
        .then((s) => {
          if (cancelled) return;
          setSuggestions(s.slice(0, 6));
          setSuggestError(false);
        })
        .catch(() => {
          if (cancelled) return;
          setSuggestions([]);
          setSuggestError(true);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const go = useCallback(
    (q: string) => {
      if (q.trim()) {
        setSuggestions([]);
        navigate(`/search?q=${encodeURIComponent(q.trim())}`);
      }
    },
    [navigate]
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      go(query);
    },
    [query, go]
  );

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <Search
        size={18}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
      />
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search files, documents..."
        className="w-full pl-10 pr-10 py-3 bg-white border border-[#333] rounded-[4px] text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-otter-500 focus:border-transparent transition"
      />
      {query && (
        <button
          type="button"
          onClick={() => setQuery("")}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          <X size={16} />
        </button>
      )}
      {(suggestError || suggestions.length > 0) && (
        <ul className="absolute left-0 right-0 top-full z-20 mt-1 rounded-[4px] border border-[#ccc] bg-white py-1 text-sm shadow-lg">
          {suggestError ? (
            <li role="alert" className="px-4 py-2 text-[#c41230]">
              Suggestions unavailable. Search service error.
            </li>
          ) : (
            suggestions.map((s) => (
              <li key={s}>
                <button
                  type="button"
                  onClick={() => go(s)}
                  className="w-full px-4 py-2 text-left text-gray-900 hover:bg-gray-100"
                >
                  {s}
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </form>
  );
}
