import type { AppProps } from "next/app";
import { useEffect } from "react";
import "@/styles/globals.css";
import { startAutoNetworkReporter } from "@/lib/autoNetwork";

export default function App({ Component, pageProps }: AppProps) {
  // Any device running KUDOS auto-reports its real network link (guest-safe).
  useEffect(() => startAutoNetworkReporter(), []);

  return <Component {...pageProps} />;
}
