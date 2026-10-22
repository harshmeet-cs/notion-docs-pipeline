/**
 * tp-locates widget — root component.
 *
 * Renders the Securities Locate request panel inside Studio.
 * Registered in the Studio Platform widget registry under id "tp-locates".
 *
 * Permissions required:
 *   locates:view    — render the widget
 *   locates:submit  — submit locate requests
 */
import React from "react";
import { useLocatesStore } from "./store/locatesStore";
import { LocatesTable } from "./components/LocatesTable";
import { LocatesSubmitForm } from "./components/LocatesSubmitForm";

export function LocatesWidget() {
  const { locates, isLoading } = useLocatesStore();

  return (
    <div className="locates-widget">
      <LocatesSubmitForm />
      <LocatesTable locates={locates} isLoading={isLoading} />
    </div>
  );
}
