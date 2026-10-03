export type UserSettings = {
  sim_capital: number | null;
  risk_pct: number | null;
  max_positions: number | null;
  max_position_pct: number | null;
};

export const SETTINGS_LIMITS = {
  risk_pct: "0,01 a 5",
  max_positions: "1 a 30",
  max_position_pct: "0,01 a 100",
};

export function settingsComplete(s: UserSettings | null): boolean {
  return !!s && Object.values(s).every((v) => v !== null);
}
