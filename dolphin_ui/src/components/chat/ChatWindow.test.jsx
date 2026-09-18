import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("axios", () => ({
  __esModule: true,
  default: { isCancel: vi.fn(() => false) },
}));

// marked ships ESM-only, and markdown rendering is not what this test exercises.
vi.mock("marked", () => ({
  __esModule: true,
  marked: { setOptions: vi.fn(), parse: (text) => text },
}));

vi.mock("../../api/fetchApi", () => ({
  __esModule: true,
  ensureSession: vi.fn(),
  sendMessageStream: vi.fn(),
  checkDocumentGapsStream: vi.fn(),
  checkLicCourses: vi.fn(),
}));

vi.mock("../../api/apiAuth", () => ({
  __esModule: true,
  fetchUserProfile: vi.fn(),
}));

// Stubbed so the test does not pull in react-pdf / react-player through ChatMessage.
vi.mock("./ChatMessage", () => ({
  __esModule: true,
  default: ({ msg, videos_suggestions }) =>
    React.createElement(
      "div",
      {
        "data-testid": "chat-message",
        "data-role": msg.role,
        "data-videos": String((videos_suggestions || []).length),
        "data-suggestions": String((msg.question_suggestions || []).length),
        "data-company": msg.company_answer || "",
        "data-courses": String((msg.checkLicCoursesData || []).length),
      },
      msg.content
    ),
}));

import ChatWindow from "./ChatWindow";
import { ThemeModeProvider } from "../../context/ThemeModeContext";
import { ensureSession, sendMessageStream, checkLicCourses } from "../../api/fetchApi";
import { fetchUserProfile } from "../../api/apiAuth";

// jsdom does not implement this.
window.HTMLElement.prototype.scrollIntoView = jest.fn();

const Harness = () => {
  const [messages, setmessages] = React.useState([]);
  const [disableNewChat, setDisableNewChat] = React.useState(false);
  const [currentSessionId, setCurrentSessionId] = React.useState("session-1");

  return (
    <ThemeModeProvider>
      <ChatWindow
        userId="user-1"
        currentSessionData={undefined}
        currentSessionId={currentSessionId}
        setCurrentSessionId={setCurrentSessionId}
        activeIndex={0}
        loading={false}
        fetchSessions={jest.fn()}
        messages={messages}
        setmessages={setmessages}
        setDisableNewChat={setDisableNewChat}
        disableNewChat={disableNewChat}
      />
    </ThemeModeProvider>
  );
};

const sendQuery = () => {
  const input = screen.getByPlaceholderText("Message Dolphin AI");
  fireEvent.change(input, { target: { value: "pump maintenance" } });
  fireEvent.keyDown(input, { key: "Enter", shiftKey: false });
};

const assistantMessage = () =>
  screen
    .getAllByTestId("chat-message")
    .find((el) => el.getAttribute("data-role") === "assistant");

const streamChunks = (...chunks) => {
  sendMessageStream.mockImplementation(
    async (sessionId, text, userId, signal, onChunk) => {
      chunks.forEach((chunk) => onChunk(chunk));
    }
  );
};

const fullResponse = {
  type: "query",
  content: "### Maintenance Procedure for Pumps",
  sections: [
    {
      topic_code: "COMPANY_SMS",
      topic_name: "CMS Demo Company SMS & Maritime Standard",
      content: "### Maintenance Procedure for Pumps",
    },
  ],
  video_suggestions: [],
  videos: [{ id: "v1", title: "Centrifugal Pump", url: "http://example/v1.mp4" }],
  images: [],
  pdfs: [],
  question_suggestions: ["What safety equipment is required?"],
  metadata: { source_layer: "Company SMS / QMS + Core Maritime" },
};

describe("ChatWindow streaming", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    ensureSession.mockResolvedValue("session-1");
    fetchUserProfile.mockResolvedValue(null);
    checkLicCourses.mockResolvedValue(null);
  });

  it("renders a complete response object delivered as one chunk", async () => {
    streamChunks(fullResponse);

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(assistantMessage()).toHaveTextContent(
        "Maintenance Procedure for Pumps"
      );
    });

    expect(assistantMessage()).toHaveAttribute("data-videos", "1");
    expect(assistantMessage()).toHaveAttribute("data-suggestions", "1");
  });

  it("still appends token chunks from a real stream", async () => {
    streamChunks(
      { type: "content", token: "Hello " },
      { type: "content", token: "world" }
    );

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(assistantMessage()).toHaveTextContent("Hello world");
    });
  });

  it("keeps company_content out of the assistant answer", async () => {
    streamChunks(
      { type: "content", token: "Main answer" },
      { type: "company_content", content: "Company SMS extract" }
    );

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(assistantMessage()).toHaveTextContent("Main answer");
    });

    expect(assistantMessage()).toHaveAttribute(
      "data-company",
      "Company SMS extract"
    );
  });

  it("suppresses media for an out-of-scope answer", async () => {
    streamChunks({
      ...fullResponse,
      content:
        "This topic is not covered in the available course material at this time.",
    });

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(assistantMessage()).toHaveTextContent(
        "not covered in the available course material"
      );
    });

    expect(assistantMessage()).toHaveAttribute("data-videos", "0");
  });

  it("triggers checkLicCourses when source_topic event arrives with topic_code", async () => {
    checkLicCourses.mockResolvedValue([
      {
        matched: true,
        data: {
          course: { CourseName: "Marine Safety", CourseCode: "MS-101" },
          topic_name: "Pump Procedures",
        },
      },
    ]);

    streamChunks({
      type: "source_topic",
      topic_code: "c0c14451-fa6b-ec11-b83d-00505682a06a",
      topic_name: "CMS Demo Company SMS",
    });

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(checkLicCourses).toHaveBeenCalledWith(
        expect.objectContaining({
          topic_code: "c0c14451-fa6b-ec11-b83d-00505682a06a",
          user_id: "user-1",
        })
      );
    });

    await waitFor(() => {
      expect(assistantMessage()).toHaveAttribute("data-courses", "1");
    });
  });

  it("skips checkLicCourses for pseudo-codes like COMPANY_SMS or GAP_ANALYSIS", async () => {
    streamChunks({
      type: "query",
      content: "Here is company manual extract.",
      sections: [
        {
          topic_code: "COMPANY_SMS",
          topic_name: "Company SMS Section",
        },
      ],
    });

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(assistantMessage()).toHaveTextContent("Here is company manual extract.");
    });

    expect(checkLicCourses).not.toHaveBeenCalled();
    expect(assistantMessage()).toHaveAttribute("data-courses", "0");
  });

  it("triggers checkLicCourses on topic_codes delivered in media stream chunk", async () => {
    checkLicCourses.mockResolvedValue({
      matched: true,
      data: {
        course: { CourseName: "ECDIS Simulation", CourseCode: "ECDIS-300" },
        topic_name: "Electronic Navigation",
      },
    });

    streamChunks(
      { type: "content", token: "Nav info." },
      {
        type: "media",
        topic_codes: ["a59e3a51-33a3-ef11-bf7c-0050568291a6"],
        videos: [],
        images: [],
        pdfs: [],
      }
    );

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(checkLicCourses).toHaveBeenCalledWith(
        expect.objectContaining({
          topic_code: "a59e3a51-33a3-ef11-bf7c-0050568291a6",
        })
      );
    });

    await waitFor(() => {
      expect(assistantMessage()).toHaveAttribute("data-courses", "1");
    });
  });

  it("triggers checkLicCourses on source_topic stream chunk and preserves data across subsequent tokens", async () => {
    checkLicCourses.mockResolvedValue({
      matched: true,
      data: {
        course: { CourseName: "Navigation Standards", CourseCode: "NAV-201" },
        topic_name: "Bridge Protocols",
      },
    });

    streamChunks(
      {
        type: "source_topic",
        topic_code: "d9e87123-fa6b-ec11-b83d-00505682a06a",
        source_code: "37c19a13-40fe-e511-80bd-000c29b080c2",
        topic_name: "Bridge Operations",
      },
      { type: "content", token: "First token. " },
      { type: "content", token: "Second token." }
    );

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(checkLicCourses).toHaveBeenCalledWith(
        expect.objectContaining({
          topic_code: "d9e87123-fa6b-ec11-b83d-00505682a06a",
          source_code: "37c19a13-40fe-e511-80bd-000c29b080c2",
        })
      );
    });

    await waitFor(() => {
      expect(assistantMessage()).toHaveTextContent(
        "First token. Second token."
      );
      expect(assistantMessage()).toHaveAttribute("data-courses", "1");
    });
  });

  it("disables textarea and send actions while streaming response", async () => {
    let resolveStream;
    const streamPromise = new Promise((resolve) => {
      resolveStream = resolve;
    });

    sendMessageStream.mockImplementation(async () => {
      await streamPromise;
    });

    render(<Harness />);
    const textarea = screen.getByPlaceholderText("Message Dolphin AI");
    expect(textarea).not.toBeDisabled();

    sendQuery();

    await waitFor(() => {
      expect(textarea).toBeDisabled();
    });

    // Resolve stream and verify it re-enables
    resolveStream();
    await waitFor(() => {
      expect(textarea).not.toBeDisabled();
    });
  });

  it("processes courses stream chunk and preserves courses in message", async () => {
    streamChunks(
      { type: "content", token: "Here is your answer." },
      {
        type: "courses",
        courses: [
          {
            matched: true,
            data: {
              course: { CourseName: "Maritime Law", CourseCode: "LAW-101" },
              topic_name: "Regulations",
            },
          },
        ],
      }
    );

    render(<Harness />);
    sendQuery();

    await waitFor(() => {
      expect(assistantMessage()).toHaveTextContent("Here is your answer.");
      expect(assistantMessage()).toHaveAttribute("data-courses", "1");
    });
  });
});
