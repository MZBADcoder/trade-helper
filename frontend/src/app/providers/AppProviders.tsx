import React from "react";
import { BrowserRouter } from "react-router-dom";

import { SessionProvider } from "@/entities/session";

type AppProvidersProps = {
  children: React.ReactNode;
};

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <SessionProvider>
      <BrowserRouter>{children}</BrowserRouter>
    </SessionProvider>
  );
}
