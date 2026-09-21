import React from "react";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("marked", () => ({
  __esModule: true,
  marked: { setOptions: vi.fn(), parse: (text) => text },
}));

vi.mock("dompurify", () => ({
  __esModule: true,
  default: { sanitize: (html) => html },
}));

vi.mock("./MediaPreviewModal", () => ({
  __esModule: true,
  default: () => null,
}));

vi.mock("./QuizDisplay", () => ({
  __esModule: true,
  default: () => null,
}));

import ChatMessage from "./ChatMessage";
import { ThemeModeProvider } from "../../context/ThemeModeContext";

const renderMessage = (msgProps = {}, extraProps = {}) => {
  const msg = {
    role: "assistant",
    content: "Here is your response",
    isStreaming: false,
    ...msgProps,
  };

  return render(
    <ThemeModeProvider>
      <ChatMessage
        msg={msg}
        videos_suggestions={[]}
        images_suggestions={[]}
        pdf_suggestions={[]}
        {...extraProps}
      />
    </ThemeModeProvider>
  );
};

describe("ChatMessage Media Attachments", () => {
  it("renders video suggestions, reference images, and reference PDFs when present", () => {
    const videos = [
      { id: "vid-1", title: "Centrifugal Pump Basics", url: "http://example.com/pump.mp4" },
    ];
    const images = [
      { id: "img-1", title: "Impeller Diagram", url: "http://example.com/pdf_images/impeller.png" },
    ];
    const pdfs = [
      { id: "pdf-1", title: "Pump Maintenance Manual", url: "http://example.com/manual.pdf" },
    ];

    renderMessage(
      { isThinking: false, isStreaming: false },
      {
        videos_suggestions: videos,
        images_suggestions: images,
        pdf_suggestions: pdfs,
      }
    );

    expect(screen.getByText("Video Suggestions")).toBeInTheDocument();
    expect(screen.getByText("Centrifugal Pump Basics")).toBeInTheDocument();
    expect(screen.getByText("Reference Images")).toBeInTheDocument();
    expect(screen.getByText("Impeller Diagram")).toBeInTheDocument();
    expect(screen.getByText("Reference PDFs")).toBeInTheDocument();
    expect(screen.getByText("Pump Maintenance Manual")).toBeInTheDocument();
  });

  it("limits media items to 4 when collapsed and expands on Show more click", async () => {
    const { fireEvent } = await import("@testing-library/react");
    const images = [
      { id: "img-1", title: "Image 1", url: "http://example.com/1.png" },
      { id: "img-2", title: "Image 2", url: "http://example.com/2.png" },
      { id: "img-3", title: "Image 3", url: "http://example.com/3.png" },
      { id: "img-4", title: "Image 4", url: "http://example.com/4.png" },
      { id: "img-5", title: "Image 5", url: "http://example.com/5.png" },
      { id: "img-6", title: "Image 6", url: "http://example.com/6.png" },
    ];

    renderMessage(
      { isThinking: false, isStreaming: false },
      { images_suggestions: images }
    );

    // First 4 items should be in document
    expect(screen.getByText("Image 1")).toBeInTheDocument();
    expect(screen.getByText("Image 4")).toBeInTheDocument();
    // 5th and 6th items must not be visible when collapsed
    expect(screen.queryByText("Image 5")).not.toBeInTheDocument();
    expect(screen.queryByText("Image 6")).not.toBeInTheDocument();

    // Click "Show more"
    const showMoreBtn = screen.getByText("Show more");
    fireEvent.click(showMoreBtn);

    // Now all 6 items should be visible
    expect(screen.getByText("Image 5")).toBeInTheDocument();
    expect(screen.getByText("Image 6")).toBeInTheDocument();

    // Click "Show less"
    const showLessBtn = screen.getByText("Show less");
    fireEvent.click(showLessBtn);

    // 5th and 6th items should be hidden again
    expect(screen.queryByText("Image 5")).not.toBeInTheDocument();
  });
});

describe("ChatMessage Related Courses", () => {
  it("renders related courses when checkLicCoursesData contains course objects", () => {
    const checkLicCoursesData = [
      {
        matched: true,
        user_type: "officer",
        data: {
          course: {
            CourseName: "Bridge Resource Management",
            CourseCode: "BRM-101",
          },
          topic_name: "Navigation Safety",
        },
      },
    ];

    renderMessage({ checkLicCoursesData });

    expect(screen.getByText("Related Courses")).toBeInTheDocument();
    expect(screen.getByText("Bridge Resource Management")).toBeInTheDocument();
    expect(screen.getByText("Topic: Navigation Safety")).toBeInTheDocument();
    expect(screen.getByText("LICENSED")).toBeInTheDocument();
  });

  it("handles string course names and nested arrays in checkLicCoursesData", () => {
    const checkLicCoursesData = [
      [
        {
          matched: false,
          user_type: "captain",
          data: {
            course: "Safety Management System Overview",
            topic_name: "SMS Core",
          },
        },
      ],
    ];

    renderMessage({ checkLicCoursesData });

    expect(screen.getByText("Related Courses")).toBeInTheDocument();
    expect(
      screen.getByText("Safety Management System Overview")
    ).toBeInTheDocument();
    expect(screen.getByText("Topic: SMS Core")).toBeInTheDocument();
    expect(screen.queryByText("LICENSED")).not.toBeInTheDocument();
  });

  it("filters out non-matched courses if the user is a student", () => {
    const checkLicCoursesData = [
      {
        matched: false,
        user_type: "student",
        data: {
          course: {
            CourseName: "Unlicensed Advanced Radar",
            CourseCode: "RAD-999",
          },
        },
      },
      {
        matched: true,
        user_type: "student",
        data: {
          course: {
            CourseName: "Basic Marine Firefighting",
            CourseCode: "BFF-001",
          },
        },
      },
    ];

    renderMessage({ checkLicCoursesData });

    expect(
      screen.queryByText("Unlicensed Advanced Radar")
    ).not.toBeInTheDocument();
    expect(screen.getByText("Basic Marine Firefighting")).toBeInTheDocument();
    expect(screen.getByText("LICENSED")).toBeInTheDocument();
  });

  it("renders related courses when provided via courses property", () => {
    const courses = [
      {
        matched: true,
        user_type: "officer",
        data: {
          course: {
            CourseName: "ECDIS Type Specific",
            CourseCode: "ECDIS-202",
          },
          topic_name: "Electronic Navigation",
        },
      },
    ];

    renderMessage({ courses });

    expect(screen.getByText("Related Courses")).toBeInTheDocument();
    expect(screen.getByText("ECDIS Type Specific")).toBeInTheDocument();
  });
});
