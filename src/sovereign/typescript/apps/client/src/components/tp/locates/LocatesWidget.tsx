/**
 * tp-locates widget — root component.
 *
 * Renders the Securities Locate request panel inside Studio.
 * Registered in the Studio Platform widget registry under id "tp-locates".
 *
 * Permissions required:
 *   locates:view    — render the widget
 *   locates:submit  — submit locate requests
 *   locates:export  — download locate history as CSV
 *   locates:approve     — approve pending locate requests (prime brokerage only)
 *   locates:bulk-export — NEW in v3.2: schedule overnight bulk CSV exports via shared worker
 */
import React from "react";
import { useLocatesStore } from "./store/locatesStore";
import { LocatesTable } from "./components/LocatesTable";
import { LocatesSubmitForm } from "./components/LocatesSubmitForm";
import { LocatesExportButton } from "./components/LocatesExportButton";
import { LocatesBulkExportScheduler } from "./components/LocatesBulkExportScheduler";
import { LocatesApprovalQueue } from "./components/LocatesApprovalQueue";
import { usePermissions } from "@cs/studio-platform/permissions";

export function LocatesWidget() {
  const { locates, pendingApprovals, isLoading } = useLocatesStore();
  const { hasPermission } = usePermissions();

  return (
    <div className="locates-widget">
      <div className="locates-widget__toolbar">
        <LocatesSubmitForm />
        <LocatesExportButton locates={locates} />
        {hasPermission("locates:bulk-export") && (
          <LocatesBulkExportScheduler />
        )}
      </div>
      {hasPermission("locates:approve") && (
        <LocatesApprovalQueue pendingApprovals={pendingApprovals} />
      )}
      <LocatesTable locates={locates} isLoading={isLoading} />
    </div>
  );
}
