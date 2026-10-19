import { Announcement } from '../../models/announcement.model';

export const MOCK_ANNOUNCEMENTS: Announcement[] = [
  {
    id: 'ann-001', title: 'Scheduled Maintenance Window',
    content: 'Fernwold file and spec uploads will be unavailable on April 20, 2026 from 2:00 AM to 6:00 AM UTC while the service is updated.',
    priority: 'high', status: 'published',
    createdAt: '2026-04-16T10:00:00Z', publishedAt: '2026-04-16T10:30:00Z', expiresAt: '2026-04-21T00:00:00Z',
    createdBy: 'Frank Wilson', targetAudience: 'all',
  },
  {
    id: 'ann-002', title: 'New Feature: AI Spec Summaries (Beta)',
    content: 'Selected users can try AI summaries for product specs. Ask your administrator to join the beta.',
    priority: 'medium', status: 'draft',
    createdAt: '2026-04-15T14:00:00Z',
    createdBy: 'Alice Johnson', targetAudience: 'editors',
  },
  {
    id: 'ann-003', title: 'Storage Quota Increase for Distributor Accounts',
    content: 'Starting today, each distributor account has 10 GB of storage, up from 5 GB.',
    priority: 'medium', status: 'published',
    createdAt: '2026-04-10T09:00:00Z', publishedAt: '2026-04-10T09:30:00Z',
    createdBy: 'Alice Johnson', targetAudience: 'all',
  },
  {
    id: 'ann-004', title: 'Security Update: Password Policy Change',
    content: 'Starting May 1, 2026, all accounts will be required to use passwords with a minimum of 12 characters including uppercase, lowercase, numbers, and special characters.',
    priority: 'critical', status: 'published',
    createdAt: '2026-04-08T08:00:00Z', publishedAt: '2026-04-08T08:30:00Z',
    createdBy: 'Frank Wilson', targetAudience: 'all',
  },
  {
    id: 'ann-005', title: 'Welcome to Fernwold',
    content: 'The Fernwold workspace includes shared files, product specs and a new admin dashboard.',
    priority: 'low', status: 'archived',
    createdAt: '2026-03-01T12:00:00Z', publishedAt: '2026-03-01T12:30:00Z',
    createdBy: 'Alice Johnson', targetAudience: 'all',
  },
];
