import { PortalDatePipe } from './portal-date.pipe';
import moment from 'moment';

describe('PortalDatePipe', () => {
  const pipe = new PortalDatePipe();

  it('uses moment with the security fixes from 2.29.4 or newer', () => {
    const [major, minor, patch] = moment.version.split('.').map(Number);
    expect(major > 2 || (major === 2 && (minor > 29 || (minor === 29 && patch >= 4)))).toBeTrue();
  });

  afterEach(() => jasmine.clock().uninstall());

  it('formats ISO timestamps as a calendar date', () => {
    expect(pipe.transform('2026-03-14T12:00:00Z')).toBe('14 Mar 2026');
  });

  it('formats relative times', () => {
    jasmine.clock().install();
    jasmine.clock().mockDate(new Date('2026-03-14T12:00:00Z'));
    expect(pipe.transform('2026-03-12T12:00:00Z', 'relative')).toBe('2 days ago');
  });

  it('returns an empty string for missing values', () => {
    expect(pipe.transform(null)).toBe('');
    expect(pipe.transform(undefined, 'relative')).toBe('');
  });

  it('passes through values it cannot parse', () => {
    expect(pipe.transform('not a date')).toBe('not a date');
  });
});
