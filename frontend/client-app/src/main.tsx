import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { NativeDeepLinks } from "@/components/native-deep-links";
import App from "./App";
import "./globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
      <NativeDeepLinks />
    </BrowserRouter>
  </React.StrictMode>
);
