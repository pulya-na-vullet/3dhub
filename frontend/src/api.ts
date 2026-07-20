export type DesignerLoginResponse = {
  token: string;
  expires_at: string;
  designer: { id: number; full_name: string; login: string };
};

export type QueueBrief = {
  brief_id: string;
  brief_number: string;
  site_name: string;
  description: string;
  agreed_price: string;
  designer_share_amount: string;
  status: string;
  designer_name: string | null;
  eta: string;
  updated_at: string;
};

export type QueueResponse = {
  viewer: { id: number; full_name: string };
  results: QueueBrief[];
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail ?? "Ошибка запроса");
  }
  return payload as T;
}

export function login(login: string, password: string): Promise<DesignerLoginResponse> {
  return request<DesignerLoginResponse>("/api/v1/designer/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login, password })
  });
}

export function getQueue(token: string): Promise<QueueResponse> {
  return request<QueueResponse>("/api/v1/designer/briefs", {
    headers: { Authorization: `Bearer ${token}` }
  });
}

export function claimBrief(token: string, briefId: string, eta: string) {
  return request<{ brief_id: string; status: string; designer_name: string; eta: string }>(
    `/api/v1/designer/briefs/${briefId}/claim`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ eta })
    }
  );
}
