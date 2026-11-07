import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useNavigate, useLocation } from 'react-router-dom';
import FeedbackPage from './FeedbackPage';
import AdminSidebar from '../../components/admin/AdminSidebar';
import { fetchFeedbackDetail, fetchFeedbackStats, fetchPendingFeedback, fetchApprovedFeedback } from '../../api/feedbackApi';

// CRA's Jest resolver predates React Router 7's package exports.
jest.mock('react-router-dom', () => {
  global.TextEncoder = require('util').TextEncoder;
  return jest.requireActual('react-router');
}, { virtual: true });

jest.mock('../../context/ThemeModeContext', () => ({ useThemeMode: () => ({ fontLevel: 0 }) }));
jest.mock('../../api/feedbackApi', () => ({
  fetchFeedbackStats: jest.fn().mockResolvedValue({}),
  fetchPendingFeedback: jest.fn().mockResolvedValue([]),
  fetchApprovedFeedback: jest.fn().mockResolvedValue([]),
  fetchFeedbackDetail: jest.fn().mockResolvedValue({ id: '42' }),
}));
jest.mock('../../components/feedback/FeedbackDashboard', () => () => <h1>Dashboard content</h1>);
jest.mock('../../components/feedback/PendingFeedbackList', () => ({ onSelectItem }) => <button onClick={() => onSelectItem('42')}>Open pending item</button>);
jest.mock('../../components/feedback/ApprovedFeedbackList', () => () => <h1>Approved content</h1>);
jest.mock('../../components/feedback/PendingDetailView', () => ({ item, onBack }) => <button onClick={onBack}>Pending detail {item?.id}</button>);
jest.mock('../../components/feedback/ApprovedDetailView', () => () => <h1>Approved detail</h1>);

function Harness() {
  const navigate = useNavigate();
  const location = useLocation();
  return <><AdminSidebar /><button onClick={() => navigate(-1)}>Browser back</button><output>{location.pathname}</output><FeedbackPage /></>;
}

beforeEach(() => {
  localStorage.setItem('userData', JSON.stringify({ user_role: 'ADMIN' }));
  jest.clearAllMocks();
  fetchFeedbackStats.mockResolvedValue({});
  fetchPendingFeedback.mockResolvedValue([]);
  fetchApprovedFeedback.mockResolvedValue([]);
  fetchFeedbackDetail.mockResolvedValue({ id: '42' });
});
afterEach(() => localStorage.clear());

test('main sidebar switches sections and browser Back restores the previous section', async () => {
  render(<MemoryRouter initialEntries={['/admin/feedback/dashboard']}><Harness /></MemoryRouter>);
  expect(screen.getByText('Dashboard content')).toBeInTheDocument();
  expect(screen.queryByText('Feedback & Quality Review')).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Pending'));
  expect(await screen.findByText('Open pending item')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Open pending item'));
  expect(await screen.findByText('Pending detail 42')).toBeInTheDocument();
  expect(screen.getByText('/admin/feedback/pending/42')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Approved'));
  expect(await screen.findByText('Approved content')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Browser back'));
  expect(await screen.findByText('Pending detail 42')).toBeInTheDocument();
});

test('direct detail URL loads the correct section and returns to its list', async () => {
  render(<MemoryRouter initialEntries={['/admin/feedback/pending/42']}><Harness /></MemoryRouter>);
  fireEvent.click(await screen.findByText('Pending detail 42'));
  expect(await screen.findByText('Open pending item')).toBeInTheDocument();
  expect(fetchFeedbackDetail).toHaveBeenCalledWith('42');
  expect(screen.getByText('/admin/feedback/pending')).toBeInTheDocument();
});
