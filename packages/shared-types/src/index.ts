export type ModuleStatus = "planned" | "in-progress" | "ready";

export type PlatformModuleDescriptor = {
  key: string;
  label: string;
  status: ModuleStatus;
};
