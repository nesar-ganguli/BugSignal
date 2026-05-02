const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type HealthResponse = {
  app: string;
  status: string;
  ollama: {
    reachable: boolean;
    model: string;
    model_available?: boolean;
    available_models?: string[];
    error?: string;
  };
};

export type UploadTicketsResponse = {
  filename: string;
  bytes_received: number;
  status: string;
  message: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const fallback = `${response.status} ${response.statusText}`;
    let detail = fallback;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? fallback;
    } catch {
      detail = fallback;
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function uploadTickets(file: File): Promise<UploadTicketsResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<UploadTicketsResponse>("/tickets/upload", {
    method: "POST",
    body: formData,
  });
}
