import { Announcement } from '../../models/announcement.model';

export const MOCK_ANNOUNCEMENTS: Announcement[] = [
  {
    id: 'ann-001', title: 'Planned work at West Weir substation',
    content: 'Crews will inspect equipment at West Weir substation on April 20, 2026 from 2:00 AM to 6:00 AM UTC. Switching plans and inspection records may be unavailable during the work.',
    priority: 'high', status: 'published',
    createdAt: '2026-04-16T10:00:00Z', publishedAt: '2026-04-16T10:30:00Z', expiresAt: '2026-04-21T00:00:00Z',
    createdBy: 'Frank Wilson', targetAudience: 'all',
  },
  {
    id: 'ann-002', title: 'Pilot: outage report summaries',
    content: 'A pilot group can create summaries of outage reports. Contact your administrator to join the pilot.',
    priority: 'medium', status: 'draft',
    createdAt: '2026-04-15T14:00:00Z',
    createdBy: 'Alice Johnson', targetAudience: 'editors',
  },
  {
    id: 'ann-003', title: 'Inspection photo storage increased',
    content: 'Field Services storage has increased from 5 GB to 10 GB for inspection photos. No action is required.',
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
    id: 'ann-005', title: 'Updated Hollinmere operations console',
    content: 'The operations console now includes shared work packs, feeder search, and updated system health reports.',
    priority: 'low', status: 'archived',
    createdAt: '2026-03-01T12:00:00Z', publishedAt: '2026-03-01T12:30:00Z',
    createdBy: 'Alice Johnson', targetAudience: 'all',
  },
];
