import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Members from './Members';
const member = { id: 'member', name: 'Member One', role_id: 1 };
const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const mount = role => {
  localStorage.setItem('userData', JSON.stringify({
    access_token: 'token', user_id: 'viewer', user_role: role,
    user_profile: { user_role: 'SUPER_ADMIN' },
  }));
  return render(<Members />);
};
beforeEach(() => {
  localStorage.clear();
  global.fetch = jest.fn().mockResolvedValue(response({ users: [member] }));
});
test.each(['ADMIN', 'SUPER_ADMIN'])('%s can list members with bearer authentication', async role => {
  mount(role);
  await screen.findByText('Member One');
  expect(fetch.mock.calls[0][0]).toContain('/users?admin_user_id=viewer&limit=100&offset=0');
  expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer token');
  expect(screen.getByRole('combobox').getAttribute('aria-disabled')).toBe(role === 'ADMIN' ? 'true' : null);
});
test.each(['USER', undefined, 'unknown'])('%s cannot list members or change roles', async role => {
  mount(role);
  await screen.findByText('Access denied');
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
});
test('SUPER_ADMIN can update another member role', async () => {
  mount('SUPER_ADMIN'); await screen.findByText('Member One');
  fetch.mockResolvedValueOnce(response({}));
  fireEvent.mouseDown(screen.getByRole('combobox'));
  fireEvent.click(await screen.findByRole('option', { name: 'ADMIN', exact: true }));
  await screen.findByText('Role updated successfully!');
  const [url, config] = fetch.mock.calls[1];
  expect(url).toContain('/users/member/role?admin_user_id=viewer');
  expect(config.method).toBe('PUT');
  expect(config.headers.get('Authorization')).toBe('Bearer token');
  expect(JSON.parse(config.body)).toEqual({ role_id: 2 });
});
test('SUPER_ADMIN self-role control remains disabled', async () => {
  fetch.mockResolvedValue(response({ users: [{ ...member, id: 'viewer' }] }));
  mount('SUPER_ADMIN'); await screen.findByText('Member One');
  expect(screen.getByRole('combobox')).toHaveAttribute('aria-disabled', 'true');
});
test('loads members beyond the first 100 without adding pagination UI', async () => {
  const firstPage = Array.from({ length: 100 }, (_, i) => ({ ...member, id: `id-${i}`, name: `Member ${i}` }));
  fetch.mockResolvedValueOnce(response({ users: firstPage, total: 101 }));
  fetch.mockResolvedValueOnce(response({ users: [{ ...member, name: 'Last Member' }], total: 101 }));
  mount('ADMIN');
  await screen.findByText('Last Member');
  expect(screen.getByText('Showing 101 results')).toBeInTheDocument();
  expect(fetch.mock.calls[1][0]).toContain('offset=100');
});
test('backend role-update denial leaves the member role and login intact', async () => {
  mount('SUPER_ADMIN'); await screen.findByText('Member One');
  fetch.mockResolvedValueOnce(response({ detail: 'Access denied' }, 403));
  fireEvent.mouseDown(screen.getByRole('combobox'));
  fireEvent.click(await screen.findByRole('option', { name: 'ADMIN', exact: true }));
  await screen.findByText('Access denied');
  expect(screen.getByRole('combobox')).toHaveTextContent('USER');
  expect(localStorage.getItem('userData')).not.toBeNull();
});
test('search discards stale results and restarts at offset zero', async () => {
  let resolve;
  fetch.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  mount('ADMIN'); await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText('Search Members'), { target: { value: 'Member' } });
  await screen.findByText('Member One');
  expect(fetch.mock.calls[1][0]).toContain('offset=0&search=Member');
  await act(async () => resolve(response({ users: [{ ...member, name: 'Stale Member' }] })));
  expect(screen.queryByText('Stale Member')).not.toBeInTheDocument();
});
