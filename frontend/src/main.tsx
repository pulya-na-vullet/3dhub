import React from "react";
import ReactDOM from "react-dom/client";
import { createTheme, CssBaseline, ThemeProvider } from "@mui/material";
import { ruRU } from "@mui/material/locale";
import { App } from "./App";

const theme = createTheme(
  {
    palette: {
      mode: "dark",
      primary: { main: "#4f8cff" },
      secondary: { main: "#22d3ee" },
      background: {
        default: "#09090f",
        paper: "#12131d"
      }
    },
    shape: { borderRadius: 14 }
  },
  ruRU
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
