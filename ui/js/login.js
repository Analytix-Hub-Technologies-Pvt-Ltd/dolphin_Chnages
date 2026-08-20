const form = document.getElementById('login-form');
const messageEl = document.getElementById('login-message');
const loginButton = document.getElementById('login-button');

const setStatus = (text, isError = false) => {
  messageEl.textContent = text;
  messageEl.style.color = isError ? '#ff6b6b' : '#0c3b5d';
};

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  setStatus('');
  loginButton.disabled = true;
  loginButton.textContent = 'Signing in...';

  const email = form.email.value.trim();
  const password = form.password.value;

  if (!email || !password) {
    setStatus('Please provide both email and password.', true);
    loginButton.disabled = false;
    loginButton.textContent = 'Log in';
    return;
  }

  try {
    const response = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errorText = (await response.text()) || 'Login failed. Please try again.';
      throw new Error(errorText);
    }

    setStatus('Success! Redirecting...');
    window.location.href = '/ui/chat.html';
  } catch (error) {
    setStatus(error.message || 'Unable to login. Please try again.', true);
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = 'Log in';
  }
});
