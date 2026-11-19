export interface ParityRun {
  run_id: string;
  generated_at: string;
  passed: boolean;
}

export interface ParityCheck {
  source: unknown;
  target: unknown;
  passed: boolean;
}

export interface ParityTable {
  source: string;
  depths: {
    count: { source: number; placed: number; unplaced: number; passed: boolean };
    profile: { fields: Record<string, Record<string, ParityCheck>>; passed: boolean };
    keyed_hash: { matched: number; mismatched: number; missing_in_target: number; extra_in_target: number; passed: boolean };
    sampled_values: { size: number; fields_compared: number; difference_count: number; passed: boolean };
  };
}

export interface ParityReport extends ParityRun {
  tables: Record<string, ParityTable>;
  exception_summary: Record<string, number>;
}

export interface OdlException {
  _id: string;
  reason: string;
  status: string;
  source_keys: string[];
  customer_ids: string[];
  detail: Record<string, string>;
}

export interface OdlPage<T> {
  items: T[];
  next_cursor: string | null;
}
