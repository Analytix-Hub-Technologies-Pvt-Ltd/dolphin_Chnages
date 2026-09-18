import { vi } from "vitest";

vi.mock("axios", () => ({
  __esModule: true,
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    isCancel: vi.fn(() => false),
  },
}));

import { sendMessageStream, checkLicCourses } from "./fetchApi";

// jsdom does not provide the text encoding globals the stream parser relies on.
const { TextDecoder, TextEncoder } = require("util");
if (typeof global.TextDecoder === "undefined") global.TextDecoder = TextDecoder;
if (typeof global.TextEncoder === "undefined") global.TextEncoder = TextEncoder;

// Builds a fetch Response whose body streams the given string pieces.
const mockResponse = (pieces, contentType) => {
  const encoder = new TextEncoder();
  let index = 0;

  return {
    ok: true,
    headers: { get: () => contentType },
    json: async () => JSON.parse(pieces.join("")),
    body: {
      getReader: () => ({
        read: async () =>
          index >= pieces.length
            ? { done: true, value: undefined }
            : { done: false, value: encoder.encode(pieces[index++]) },
      }),
    },
  };
};

const collectChunks = async (pieces, contentType = "text/event-stream") => {
  global.fetch = vi.fn().mockResolvedValue(mockResponse(pieces, contentType));
  const chunks = [];
  await sendMessageStream("session-1", "hello", "user-1", undefined, (c) =>
    chunks.push(c)
  );
  return chunks;
};

const payload = {
  type: "query",
  content: "### Maintenance Procedure for Pumps",
  sections: [
    {
      topic_code: "d39427f2-3601-e611-80bd-000c29b080c2",
      topic_name: "CMS Demo Company SMS & Maritime Standard",
      content: "### Maintenance Procedure for Pumps",
    },
  ],
  videos: [{ id: "v1", title: "Centrifugal Pump", url: "http://example/v1.mp4" }],
  question_suggestions: ["What safety equipment is required?"],
  metadata: { source_layer: "Company SMS / QMS + Core Maritime" },
};

describe("sendMessageStream", () => {
  afterEach(() => {
    delete global.fetch;
  });

  it("delivers a JSON response as a single chunk", async () => {
    const chunks = await collectChunks(
      [JSON.stringify(payload)],
      "application/json"
    );

    expect(chunks).toEqual([payload]);
  });

  it("falls back to parsing the whole body when the content type is not JSON", async () => {
    // Pretty-printed and split across reads, as a non-streaming server sends it.
    const body = JSON.stringify(payload, null, 4);
    const chunks = await collectChunks(
      [body.slice(0, 40), body.slice(40, 200), body.slice(200)],
      "text/plain"
    );

    expect(chunks).toEqual([payload]);
  });

  it("delivers a trailing SSE event that has no newline after it", async () => {
    const chunks = await collectChunks([
      'data: {"type":"content","token":"A"}\n\n',
      'data: {"type":"content","token":"B"}',
    ]);

    expect(chunks).toEqual([
      { type: "content", token: "A" },
      { type: "content", token: "B" },
    ]);
  });

  it("still parses a normal SSE stream without re-delivering the whole body", async () => {
    const chunks = await collectChunks([
      'data: {"type":"content","token":"Hello "}\n',
      'data: {"type":"content","token":"world"}\n',
      'data: {"type":"suggestions","question_suggestions":["Next?"]}\n',
      "data: [DONE]\n",
    ]);

    expect(chunks).toEqual([
      { type: "content", token: "Hello " },
      { type: "content", token: "world" },
      { type: "suggestions", question_suggestions: ["Next?"] },
    ]);
  });

  it("does not emit anything for an empty body", async () => {
    const chunks = await collectChunks([""]);
    expect(chunks).toEqual([]);
  });
});

describe("checkLicCourses", () => {
  afterEach(() => {
    delete global.fetch;
  });

  it("calls /course/check-topic-course with topic_code, optional distinct source_code, and user_id", async () => {
    const mockData = {
      matched: true,
      user_type: "Officer",
      data: {
        course: { CourseName: "Marine Engineering Safety", CourseCode: "MES-01" },
        topic_name: "Pump Maintenance",
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    });

    const result = await checkLicCourses({
      topic_code: "b1923283-fa54-ec11-b83c-00505682a06a",
      source_code: "37c19a13-40fe-e511-80bd-000c29b080c2",
      user_id: "user-123",
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain("/course/check-topic-course");
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/json");

    const sentBody = JSON.parse(options.body);
    expect(sentBody).toEqual({
      topic_code: "b1923283-fa54-ec11-b83c-00505682a06a",
      source_code: "37c19a13-40fe-e511-80bd-000c29b080c2",
      user_id: "user-123",
    });

    expect(result).toEqual(mockData);
  });

  it("does not duplicate topic_code as source_code when source_code is omitted", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ matched: true }),
    });

    await checkLicCourses({
      topic_code: "b1923283-fa54-ec11-b83c-00505682a06a",
      user_id: "user-123",
    });

    const [, options] = global.fetch.mock.calls[0];
    const sentBody = JSON.parse(options.body);
    expect(sentBody).toEqual({
      topic_code: "b1923283-fa54-ec11-b83c-00505682a06a",
      user_id: "user-123",
    });
    expect(sentBody.source_code).toBeUndefined();
  });

  it("skips network call and returns null when topic code is empty", async () => {
    global.fetch = vi.fn();

    const result = await checkLicCourses({
      topic_code: "",
      user_id: "user-123",
    });

    expect(global.fetch).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });

  it("supports passing source_code instead of topic_code", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ matched: true }),
    });

    await checkLicCourses({
      source_code: "ad87ecc5-41fe-e511-80bd-000c29b080c2",
      user_id: "user-456",
    });

    const [, options] = global.fetch.mock.calls[0];
    const sentBody = JSON.parse(options.body);
    expect(sentBody.topic_code).toBe("ad87ecc5-41fe-e511-80bd-000c29b080c2");
    expect(sentBody.user_id).toBe("user-456");
  });

  it("returns null on non-ok HTTP responses without throwing", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    });

    const result = await checkLicCourses({
      topic_code: "c0c14451-fa6b-ec11-b83d-00505682a06a",
      user_id: "user-1",
    });

    expect(result).toBeNull();
  });

  it("returns null on network/fetch errors without throwing", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network Error"));

    const result = await checkLicCourses({
      topic_code: "c0c14451-fa6b-ec11-b83d-00505682a06a",
      user_id: "user-1",
    });

    expect(result).toBeNull();
  });
});
