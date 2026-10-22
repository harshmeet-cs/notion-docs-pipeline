/**
 * tp-locates widget — root component.
 *
 * Renders the Securities Locate request panel inside Studio.
 * Registered in the Studio Platform widget registry under id "tp-locates".
 *
 * Permissions required:
 *   locates:view    — render the widget
 *   locates:submit  — submit locate requests
 *   locates:export  — NEW in v3: download locate history as CSV
 */
import React from "react";
import { useLocatesStore } from "./store/locatesStore";
import { LocatesTable } from "./components/LocatesTable";
import { LocatesSubmitForm } from "./components/LocatesSubmitForm";
import { LocatesExportButton } from "./components/LocatesExportButton";

export function LocatesWidget() {
  const { locates, isLoading } = useLocatesStore();

  return (
    <div className="locates-widget">
      <div className="locates-widget__toolbar">
        <LocatesSubmitForm />
        <LocatesExportButton locates={locates} />
      </div>
      <LocatesTable locates={locates} isLoading={isLoading} />
    </div>
  );
}
