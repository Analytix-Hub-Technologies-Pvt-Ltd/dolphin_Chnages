import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi } from "vitest";
import axios from "axios";
import Chatpage from "./Chatpage";
import { ThemeModeProvider } from "../../context/ThemeModeContext";

vi.mock("axios", () => ({
  __esModule: true,
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    isCancel: vi.fn(() => false),
  },
}));

vi.mock("marked", () => ({
  __esModule: true,
  marked: { setOptions: vi.fn(), parse: (text) => text },
}));

vi.mock("../../api/fetchApi", () => ({
  __esModule: true,
  fetchHealth: vi.fn().mockResolvedValue(true),
  ensureSession: vi.fn(),
  sendMessageStream: vi.fn(),
  checkDocumentGapsStream: vi.fn(),
  checkLicCourses: vi.fn().mockResolvedValue(null),
  deleteSession: vi.fn().mockResolvedValue(true),
}));

vi.mock("../../api/apiAuth", () => ({
  __esModule: true,
  fetchUserProfile: vi.fn().mockResolvedValue({
    id: "user-123",
    name: "Captain Mariner",
  }),
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();

describe("Chatpage session routing", () => {
  const mockSessions = [
    { session_id: "sess-abc", title: "Bridge Navigation", is_saved: false },
    { session_id: "sess-def", title: "Engine Room Ops", is_saved: true },
  ];

  beforeEach(() => {
    vi.clearAllMocks();

    axios.get.mockImplementation((url) => {
      if (url.includes("/sessions/sess-abc")) {
        return Promise.resolve({
          status: 200,
          data: {
            session_id: "sess-abc",
            title: "Bridge Navigation",
            messages: [
              { role: "user", content: "Tell me about radar navigation." },
              { role: "assistant", content: "Radar navigation utilizes ARPA..." },
            ],
          },
        });
      }
      if (url.includes("/sessions")) {
        return Promise.resolve({
          status: 200,
          data: mockSessions,
        });
      }
      return Promise.resolve({
        status: 200,
        data: { session_id: "unknown", title: "Chat", messages: [] },
      });
    });
  });

  it("loads and renders the session matching /session=:sessionSlug from the URL", async () => {
    render(
      <ThemeModeProvider>
        <MemoryRouter initialEntries={["/session=sess-abc"]}>
          <Routes>
            <Route
              path="/:sessionSlug"
              element={<Chatpage userId="user-123" setUserId={vi.fn()} onLogout={vi.fn()} />}
            />
          </Routes>
        </MemoryRouter>
      </ThemeModeProvider>
    );

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining("/sessions/sess-abc"),
        expect.anything()
      );
    });

    // Session title should appear
    await waitFor(() => {
      const titles = screen.getAllByText("Bridge Navigation");
      expect(titles.length).toBeGreaterThanOrEqual(1);
    });

    // Messages from the loaded session should appear
    await waitFor(() => {
      expect(
        screen.getByText("Tell me about radar navigation.")
      ).toBeInTheDocument();
    });
  });

  it("loads session with standard path /session/:sessionId", async () => {
    render(
      <ThemeModeProvider>
        <MemoryRouter initialEntries={["/session/sess-abc"]}>
          <Routes>
            <Route
              path="/session/:sessionId"
              element={<Chatpage userId="user-123" setUserId={vi.fn()} onLogout={vi.fn()} />}
            />
          </Routes>
        </MemoryRouter>
      </ThemeModeProvider>
    );

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining("/sessions/sess-abc"),
        expect.anything()
      );
    });

    await waitFor(() => {
      const titles = screen.getAllByText("Bridge Navigation");
      expect(titles.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows welcome screen on root path / with no session in URL", async () => {
    render(
      <ThemeModeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route
              path="/"
              element={<Chatpage userId="user-123" setUserId={vi.fn()} onLogout={vi.fn()} />}
            />
          </Routes>
        </MemoryRouter>
      </ThemeModeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/How can I/i)).toBeInTheDocument();
    });
  });

  it("does not trigger duplicate fetch if session is already loading", async () => {
    render(
      <ThemeModeProvider>
        <MemoryRouter initialEntries={["/session=sess-abc"]}>
          <Routes>
            <Route
              path="/:sessionSlug"
              element={<Chatpage userId="user-123" setUserId={vi.fn()} onLogout={vi.fn()} />}
            />
          </Routes>
        </MemoryRouter>
      </ThemeModeProvider>
    );

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining("/sessions/sess-abc"),
        expect.anything()
      );
    });

    // Should only be called once for sess-abc, no duplicate call
    const sessCalls = axios.get.mock.calls.filter((call) =>
      typeof call[0] === "string" && call[0].includes("/sessions/sess-abc")
    );
    expect(sessCalls.length).toBe(1);
  });
});
