import { useEffect, useState, type ReactNode } from "react";
import { ApiError, getAdminKey, setAdminKey } from "../lib/api";

interface Props {
  children: ReactNode;
  /** A cheap admin-gated call used to validate the key; throws ApiError(403) if wrong. */
  probe: () => Promise<unknown>;
}

export default function AdminGate({ children, probe }: Props) {
  const [adminKey, setAdminKeyState] = useState(getAdminKey());
  const [unlocked, setUnlocked] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getAdminKey()) {
      setUnlocked(false);
      return;
    }
    probe().then(() => setUnlocked(true)).catch(() => setUnlocked(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleUnlock(e: React.FormEvent) {
    e.preventDefault();
    setAdminKey(adminKey);
    probe()
      .then(() => { setUnlocked(true); setError(""); })
      .catch((err) => setError(err instanceof ApiError ? "Invalid admin key." : "Could not reach the API."));
  }

  if (unlocked === null) {
    return <p className="text-center text-slate-400 mt-12 text-sm">Checking access...</p>;
  }

  if (!unlocked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <form onSubmit={handleUnlock} className="bg-white rounded-xl border border-slate-200 p-8 w-full max-w-sm space-y-3">
          <h1 className="text-lg font-semibold">Admin Access</h1>
          <input
            type="password" placeholder="Admin key" value={adminKey}
            onChange={(e) => setAdminKeyState(e.target.value)}
            className="w-full rounded-md border border-slate-300 p-2 text-sm"
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="w-full rounded-md bg-blue-600 text-white text-sm font-medium py-2 hover:bg-blue-700">
            Unlock
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
