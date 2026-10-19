import type { ComponentType } from "react";
import { KycApp } from "./kyc/KycApp";
import { RefundsApp } from "./refunds/RefundsApp";

/** Apps register here (outside the foundation) so the shell, routes and Home stay app-agnostic. */
export type AppDefinition = {
  key: string;
  name: string;
  path: string;
  /** Rendered under `path/*`; the app owns its nested routes. */
  component: ComponentType;
};

export const APPS: AppDefinition[] = [
  { key: "kyc", name: "KYC", path: "/kyc", component: KycApp },
  { key: "refunds", name: "Refunds", path: "/refunds", component: RefundsApp },
];
