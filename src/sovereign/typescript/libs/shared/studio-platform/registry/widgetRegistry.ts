/**
 * Studio Platform Widget Registry
 *
 * Central registry for all Studio widgets. Each widget calls registry.register()
 * at module load time to make itself discoverable by the host application.
 */
import type { WidgetRegistration } from "./types";

class WidgetRegistry {
  private readonly entries = new Map<string, WidgetRegistration>();

  register(entry: WidgetRegistration): void {
    if (this.entries.has(entry.id)) {
      throw new Error(`Widget "${entry.id}" is already registered.`);
    }
    this.entries.set(entry.id, entry);
  }

  get(id: string): WidgetRegistration | undefined {
    return this.entries.get(id);
  }

  getAll(): WidgetRegistration[] {
    return Array.from(this.entries.values());
  }
}

export const registry = new WidgetRegistry();

// Register built-in widgets
registry.register({
  id: "tp-locates",
  bundle: "@cs/studio-locates",
  version: "3.3.0",
  owner: "Studio FE",
  requiredPermissions: ["locates:view", "locates:export", "locates:approve", "locates:bulk-export", "locates:stream"],
  searchMeta: {
    keywords: ["locate", "borrow", "short", "availability", "export", "csv", "approve", "workflow", "bulk", "live", "stream"],
    description: "Submit, track, approve, bulk-export, and live-stream securities locate requests",
  },
});

registry.register({
  id: "tp-blotter",
  bundle: "@cs/studio-blotter",
  version: "1.9.0",
  owner: "Studio FE",
  requiredPermissions: ["blotter:view"],
  searchMeta: {
    keywords: ["blotter", "orders", "trades", "executions"],
    description: "Real-time order and execution blotter",
  },
});

registry.register({
  id: "tp-risk",
  bundle: "@cs/studio-risk",
  version: "4.1.0",
  owner: "Studio FE",
  requiredPermissions: ["risk:view", "risk:scenarios", "risk:export"],
  searchMeta: {
    keywords: ["risk", "exposure", "greeks", "pnl", "scenarios", "stress-test", "export", "report"],
    description: "Portfolio risk, P&L, scenario analysis, and reporting dashboard",
  },
});
