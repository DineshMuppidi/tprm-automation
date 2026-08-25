import { useState } from "react";
import { api, ApiError } from "../lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("sending");
    try {
      await api.requestLink(email);
      setStatus("sent");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.message) : "Something went wrong");
      setStatus("error");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-xl border border-slate-200 p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">Vendor Assessment Portal</h1>
        <p className="text-sm text-slate-500 mt-1 mb-6">
          Enter your work email to receive a sign-in link.
        </p>

        {status === "sent" ? (
          <div className="rounded-md bg-green-50 border border-green-200 text-green-800 text-sm p-3">
            If that email is registered, a sign-in link has been sent. It expires in 15 minutes.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              type="email"
              required
              placeholder="you@vendor.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-slate-300 p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={status === "sending"}
              className="w-full rounded-md bg-blue-600 text-white text-sm font-medium py-2 hover:bg-blue-700 disabled:opacity-60"
            >
              {status === "sending" ? "Sending..." : "Send sign-in link"}
            </button>
            {status === "error" && <p className="text-sm text-red-600">{error}</p>}
          </form>
        )}
      </div>
    </div>
  );
}
