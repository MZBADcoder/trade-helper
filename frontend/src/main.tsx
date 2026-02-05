import "@fontsource/ibm-plex-sans/latin.css";
import "@fontsource/jetbrains-mono/latin.css";
import React from "react";
import ReactDOM from "react-dom/client";

import { App, AppProviders } from "@/app";
import "@/app/styles/theme.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  </React.StrictMode>
);
