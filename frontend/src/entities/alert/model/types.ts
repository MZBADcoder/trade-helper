export type Alert = {
  id: number;
  ticker: string;
  rule_key: string;
  priority: string;
  message: string;
  created_at?: string | null;
};
