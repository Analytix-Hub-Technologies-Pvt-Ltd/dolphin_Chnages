// jest-dom adds custom jest matchers for asserting on DOM nodes.
import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

if (typeof globalThis.DOMMatrix === 'undefined') {
  globalThis.DOMMatrix = class DOMMatrix {};
}

globalThis.jest = vi;
