import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, setSession } from "../lib/api";

export default function Verify() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("Missing sign-in token.");
      return;
    }
    api.verify(token)
      .then((session) => {
        setSession(session);
        navigate("/assessments", { replace: true });
      })
      .catch((err) => {
        setError(err instanceof ApiError ? "This link is invalid or has expired." : "Something went wrong.");
      });
  }, [params, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="text-center">
        {error ? (
          <>
            <p className="text-red-600 font-medium">{error}</p>
            <a href="/login" className="text-blue-600 text-sm hover:underline mt-2 inline-block">
              Request a new link
            </a>
          </>
        ) : (
          <p className="text-slate-500">Signing you in...</p>
        )}
      </div>
    </div>
  );
}
