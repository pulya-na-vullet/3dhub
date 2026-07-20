import { useMemo, useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Toolbar,
  Typography
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import AssignmentTurnedInIcon from "@mui/icons-material/AssignmentTurnedIn";
import { claimBrief, getQueue, login, QueueBrief } from "./api";

const STATUS_LABELS: Record<string, string> = {
  queued: "В очереди",
  assigned: "Назначена",
  in_progress: "В работе",
  needs_clarification: "Нужно уточнение",
  clarification_provided: "Уточнение получено",
  done: "Готово"
};

function statusColor(status: string): "default" | "success" | "warning" | "info" {
  if (status === "queued") return "info";
  if (status === "assigned" || status === "in_progress") return "warning";
  if (status === "done") return "success";
  return "default";
}

export function App() {
  const [token, setToken] = useState<string>("");
  const [designerName, setDesignerName] = useState<string>("");
  const [loginValue, setLoginValue] = useState("");
  const [passwordValue, setPasswordValue] = useState("");
  const [briefs, setBriefs] = useState<QueueBrief[]>([]);
  const [error, setError] = useState("");
  const [etaModal, setEtaModal] = useState<{ open: boolean; briefId: string }>({
    open: false,
    briefId: ""
  });
  const [etaValue, setEtaValue] = useState("");

  const isLoggedIn = token.length > 0;

  const grouped = useMemo(
    () => ({
      queued: briefs.filter((b) => b.status === "queued"),
      taken: briefs.filter((b) => b.status !== "queued")
    }),
    [briefs]
  );

  async function handleLogin() {
    setError("");
    try {
      const result = await login(loginValue, passwordValue);
      setToken(result.token);
      setDesignerName(result.designer.full_name);
      await refreshQueue(result.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    }
  }

  async function refreshQueue(activeToken = token) {
    if (!activeToken) return;
    setError("");
    try {
      const result = await getQueue(activeToken);
      setBriefs(result.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки очереди");
    }
  }

  async function claim() {
    if (!etaModal.briefId) return;
    setError("");
    try {
      await claimBrief(token, etaModal.briefId, etaValue);
      setEtaModal({ open: false, briefId: "" });
      setEtaValue("");
      await refreshQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка назначения задачи");
    }
  }

  return (
    <Box sx={{ minHeight: "100vh", background: "radial-gradient(circle at top, #1b2140, #09090f 55%)" }}>
      <AppBar position="static" color="transparent" elevation={0}>
        <Toolbar>
          <AssignmentTurnedInIcon sx={{ mr: 1 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            HUB Designer Portal
          </Typography>
          {isLoggedIn && (
            <Button color="inherit" onClick={() => setToken("")}>
              Выйти
            </Button>
          )}
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

        {!isLoggedIn ? (
          <Card sx={{ maxWidth: 520, mx: "auto", mt: 8 }}>
            <CardContent>
              <Typography variant="h5" gutterBottom>
                Вход дизайнера
              </Typography>
              <Typography variant="body2" sx={{ opacity: 0.8, mb: 3 }}>
                Используйте логин и пароль, полученные в Max-боте после регистрации.
              </Typography>
              <Stack spacing={2}>
                <TextField label="Логин" value={loginValue} onChange={(e) => setLoginValue(e.target.value)} />
                <TextField
                  label="Пароль"
                  type="password"
                  value={passwordValue}
                  onChange={(e) => setPasswordValue(e.target.value)}
                />
                <Button variant="contained" size="large" onClick={handleLogin}>
                  Войти
                </Button>
              </Stack>
            </CardContent>
          </Card>
        ) : (
          <>
            <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 3 }}>
              <Typography variant="h5">Здравствуйте, {designerName}</Typography>
              <IconButton onClick={() => refreshQueue()} color="primary">
                <RefreshIcon />
              </IconButton>
            </Stack>

            <Typography variant="h6" sx={{ mb: 2 }}>
              Свободные задачи ({grouped.queued.length})
            </Typography>
            <Box
              sx={{
                display: "grid",
                gap: 2,
                mb: 5,
                gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }
              }}
            >
              {grouped.queued.map((brief) => (
                <Box key={brief.brief_id}>
                  <Card>
                    <CardContent>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                        <Typography variant="subtitle1">{brief.brief_number}</Typography>
                        <Chip label={STATUS_LABELS[brief.status]} color={statusColor(brief.status)} />
                      </Stack>
                      <Typography variant="body2" sx={{ opacity: 0.8, mb: 1 }}>
                        ID: {brief.brief_id} · Точка: {brief.site_name}
                      </Typography>
                      <Typography variant="body1" sx={{ mb: 2 }}>
                        {brief.description || "Описание отсутствует"}
                      </Typography>
                      <Typography variant="body2" sx={{ mb: 2 }}>
                        Цена: {brief.agreed_price} · Ваша доля: {brief.designer_share_amount}
                      </Typography>
                      <Button
                        variant="contained"
                        onClick={() => setEtaModal({ open: true, briefId: brief.brief_id })}
                      >
                        Взять в работу
                      </Button>
                    </CardContent>
                  </Card>
                </Box>
              ))}
            </Box>

            <Typography variant="h6" sx={{ mb: 2 }}>
              Уже взятые задачи ({grouped.taken.length})
            </Typography>
            <Box
              sx={{
                display: "grid",
                gap: 2,
                gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }
              }}
            >
              {grouped.taken.map((brief) => (
                <Box key={brief.brief_id}>
                  <Card sx={{ border: "1px solid rgba(255,255,255,0.08)" }}>
                    <CardContent>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                        <Typography variant="subtitle1">{brief.brief_number}</Typography>
                        <Chip label={STATUS_LABELS[brief.status] ?? brief.status} color={statusColor(brief.status)} />
                      </Stack>
                      <Typography variant="body2" sx={{ opacity: 0.8, mb: 1 }}>
                        ID: {brief.brief_id} · Точка: {brief.site_name}
                      </Typography>
                      <Typography variant="body2">
                        Исполнитель: {brief.designer_name ?? "не назначен"}{brief.eta ? ` · Срок: ${brief.eta}` : ""}
                      </Typography>
                    </CardContent>
                  </Card>
                </Box>
              ))}
            </Box>
          </>
        )}
      </Container>

      <Dialog open={etaModal.open} onClose={() => setEtaModal({ open: false, briefId: "" })}>
        <DialogTitle>Укажите срок выполнения</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="Срок (например, 2 дня)"
            value={etaValue}
            onChange={(e) => setEtaValue(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEtaModal({ open: false, briefId: "" })}>Отмена</Button>
          <Button variant="contained" onClick={claim} disabled={!etaValue.trim()}>
            Подтвердить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
