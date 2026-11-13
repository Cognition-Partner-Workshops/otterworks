import { Pipe, PipeTransform } from '@angular/core';
import moment from 'moment';

export type PortalDateStyle = 'date' | 'datetime' | 'relative';

@Pipe({ name: 'portalDate', standalone: true })
export class PortalDatePipe implements PipeTransform {
  transform(value: string | null | undefined, style: PortalDateStyle = 'date'): string {
    if (!value) {
      return '';
    }
    const parsed = moment(value);
    if (!parsed.isValid()) {
      return value;
    }
    switch (style) {
      case 'relative':
        return parsed.fromNow();
      case 'datetime':
        return parsed.format('D MMM YYYY, HH:mm');
      default:
        return parsed.format('D MMM YYYY');
    }
  }
}
