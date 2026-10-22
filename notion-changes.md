# Notion Documentation Changes

> **Review the proposed updates below, edit if needed, then merge this PR to apply them to Notion.**

**Commit**: `181c30ff` — Merge pull request #16 from harshmeet-cs/feat/risk-v4.2-bulk-approve  
**Generated**: 2026-10-22T10:45:36Z

---

## [Studio FE — Widget Catalog (Demo)](https://app.notion.com/p/4011d2a6e55181ecbcc3ef7d25af0d7b)

### Widget Registry

**Current content in Notion:**
```
3 widgets registered: tp-locates v3.3.0, tp-blotter v1.9.0, tp-risk v4.1.0. All owned by Studio FE. Widgets self-register at module load time via registry.register() in widgetRegistry.ts — duplicate IDs throw at runtime.
```

**Proposed replacement** *(edit between the markers, then merge)*:

<!-- notion-update: {"pageId": "4011d2a6-e551-81ec-bcc3-ef7d25af0d7b", "pageTitle": "Studio FE — Widget Catalog (Demo)", "section": "Widget Registry"} -->
Updated as of this merge. Version bumped from 4.1.0 to 4.2.0. New permission(s): locates:bulk-approve, risk:pdf-export. See widgetRegistry.ts for full details.
<!-- /notion-update -->

### Required Permissions

**Current content in Notion:**
```
tp-locates requires locates:view, locates:export, locates:approve, locates:bulk-export, locates:stream. tp-blotter requires blotter:view. tp-risk requires risk:view, risk:scenarios, risk:export. Missing permissions show a permission-denied placeholder instead of the widget.
```

**Proposed replacement** *(edit between the markers, then merge)*:

<!-- notion-update: {"pageId": "4011d2a6-e551-81ec-bcc3-ef7d25af0d7b", "pageTitle": "Studio FE — Widget Catalog (Demo)", "section": "Required Permissions"} -->
Updated as of this merge. New permission(s): locates:bulk-approve, risk:pdf-export. Missing permissions result in a permission-denied placeholder.
<!-- /notion-update -->

### Module Federation Entrypoints

**Current content in Notion:**
```
studio-locates loads from [window.REMOTES.locates]/v3.3/remoteEntry.js, studio-blotter from [window.REMOTES.blotter]/remoteEntry.js, studio-risk from [window.REMOTES.risk]/v4.1/remoteEntry.js. Remote URLs are injected at runtime from the window.REMOTES config map. react and react-dom are shared singletons pinned to ^18.0.0.
```

**Proposed replacement** *(edit between the markers, then merge)*:

<!-- notion-update: {"pageId": "4011d2a6-e551-81ec-bcc3-ef7d25af0d7b", "pageTitle": "Studio FE — Widget Catalog (Demo)", "section": "Module Federation Entrypoints"} -->
Updated as of this merge. Remote entry path updated from v3.3 to v3.4. Remote URLs are injected at runtime from the REMOTES config map.
<!-- /notion-update -->

### Widget Search

**Current content in Notion:**
```
Keywords indexed per widget — tp-locates: locate, borrow, short, availability, export, csv, approve, workflow, bulk. tp-blotter: blotter, orders, trades, executions. tp-risk: risk, exposure, greeks, pnl, scenarios, stress-test, export, report. Search is case-insensitive prefix match via searchMeta.keywords in each registry entry.
```

**Proposed replacement** *(edit between the markers, then merge)*:

<!-- notion-update: {"pageId": "4011d2a6-e551-81ec-bcc3-ef7d25af0d7b", "pageTitle": "Studio FE — Widget Catalog (Demo)", "section": "Widget Search"} -->
Updated as of this merge. Version bumped from 4.1.0 to 4.2.0. New permission(s): locates:bulk-approve, risk:pdf-export. See widgetRegistry.ts for full details.
<!-- /notion-update -->

---

_To rollback after merge: comment `/notion-rollback sha=<sha>` on any commit in this repo._
