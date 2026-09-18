import { render, screen } from '@testing-library/react';
import App from './App';
import { ThemeModeProvider } from './context/ThemeModeContext';

test('renders login screen when unauthenticated', async () => {
  render(
    <ThemeModeProvider>
      <App />
    </ThemeModeProvider>
  );
  const signInElement = await screen.findByRole('button', { name: /sign in/i });
  expect(signInElement).toBeInTheDocument();
});
