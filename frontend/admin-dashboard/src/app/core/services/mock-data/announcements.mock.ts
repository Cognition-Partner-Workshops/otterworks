import { Announcement } from '../../models/announcement.model';

export const MOCK_ANNOUNCEMENTS: Announcement[] = [
  {
    id: 'ann-001', title: 'Scheduled Maintenance Window',
    content: 'Quillstead Vault and Quillstead Notes will be unavailable April 20, 2026, from 2:00 AM to 6:00 AM UTC. File uploads and real-time editing will resume after maintenance.',
    priority: 'high', status: 'published',
    createdAt: '2026-04-16T10:00:00Z', publishedAt: '2026-04-16T10:30:00Z', expiresAt: '2026-04-21T00:00:00Z',
    createdBy: 'Frank Wilson', targetAudience: 'all',
  },
  {
    id: 'ann-002', title: 'Research notes pilot',
    content: 'Research notes are available to a small pilot group. Contact your administrator to request access.',
    priority: 'medium', status: 'draft',
    createdAt: '2026-04-15T14:00:00Z',
    createdBy: 'Alice Johnson', targetAudience: 'editors',
  },
  {
    id: 'ann-003', title: 'Workspace storage update',
    content: 'Advisory workspaces now have 10 GB of storage, up from 5 GB. Administrators do not need to change account settings.',
    priority: 'medium', status: 'published',
    createdAt: '2026-04-10T09:00:00Z', publishedAt: '2026-04-10T09:30:00Z',
    createdBy: 'Alice Johnson', targetAudience: 'all',
  },
  {
    id: 'ann-004', title: 'Security Update: Password Policy Change',
    content: 'Starting May 1, 2026, passwords must contain at least 12 characters, including uppercase and lowercase letters, a number, and a special character.',
    priority: 'critical', status: 'published',
    createdAt: '2026-04-08T08:00:00Z', publishedAt: '2026-04-08T08:30:00Z',
    createdBy: 'Frank Wilson', targetAudience: 'all',
  },
  {
    id: 'ann-005', title: 'Quillstead workspace update',
    content: 'Quillstead Notes supports real-time editing, and Quillstead Search covers client files and research notes.',
    priority: 'low', status: 'archived',
    createdAt: '2026-03-01T12:00:00Z', publishedAt: '2026-03-01T12:30:00Z',
    createdBy: 'Alice Johnson', targetAudience: 'all',
  },
];
