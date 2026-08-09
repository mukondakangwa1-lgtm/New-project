import { useEffect, useRef, useState } from "react";

interface PasswordInputProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  minLength?: number;
  autoComplete?: string;
}

export default function PasswordInput({
  value,
  onChange,
  placeholder,
  minLength,
  autoComplete,
}: PasswordInputProps) {
  const [autoVisible, setAutoVisible] = useState(false);
  const [pinned, setPinned] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setAutoVisible(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setAutoVisible(false), 2000);
    onChange(e);
  };

  const visible = pinned || autoVisible;

  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={handleChange}
        placeholder={placeholder || "••••••••"}
        minLength={minLength}
        autoComplete={autoComplete}
        required
        className="w-full rounded border px-3 py-2 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-primary"
      />
      <button
        type="button"
        onClick={() => {
          setPinned((p) => !p);
          if (timerRef.current) clearTimeout(timerRef.current);
        }}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm"
        title={pinned ? "Hide password" : "Show password"}
        aria-label={pinned ? "Hide password" : "Show password"}
      >
        {visible ? "🙈" : "👁"}
      </button>
    </div>
  );
}