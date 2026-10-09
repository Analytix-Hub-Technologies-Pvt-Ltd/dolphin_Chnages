import { ALLOWED_FEEDBACK_EMAILS, getCurrentUserRole, isFeedbackAuthorized } from "./feedbackAuth";

afterEach(() => localStorage.clear());

test.each(["ADMIN", "SUPER_ADMIN"])("allows %s without an allowlisted email", (role) => {
  expect(isFeedbackAuthorized("other@example.com", role)).toBe(true);
  expect(isFeedbackAuthorized("", role)).toBe(true);
});

test("preserves email access for existing reviewers", () => {
  expect(isFeedbackAuthorized(` ${ALLOWED_FEEDBACK_EMAILS[0].toUpperCase()} `, "USER")).toBe(true);
});

test.each(["USER", "", undefined, "admin"])("denies unlisted users with role %s", (role) => {
  expect(isFeedbackAuthorized("other@example.com", role)).toBe(false);
  expect(isFeedbackAuthorized(null, role)).toBe(false);
});

test("reads the platform role rather than the company role", () => {
  localStorage.setItem("userData", JSON.stringify({ user_role: "USER", role: "ADMIN" }));
  expect(getCurrentUserRole()).toBe("USER");
  localStorage.setItem("userData", JSON.stringify({ user_role: "SUPER_ADMIN" }));
  expect(getCurrentUserRole()).toBe("SUPER_ADMIN");
});

test.each([null, "null", "{invalid", "{}"])("handles missing or malformed login data: %s", (value) => {
  if (value !== null) localStorage.setItem("userData", value);
  expect(getCurrentUserRole()).toBe("");
});
