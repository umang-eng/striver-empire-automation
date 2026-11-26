export interface CategorySubItem {
  name: string;
  template: string;
}

export interface CategoryGroup {
  id: string;
  label: string;
  main_templates: string[];
  subcategories: CategorySubItem[];
}

export interface CategoryCatalogResponse {
  groups: CategoryGroup[];
  site: string;
}

export type TaskStatus = "queued" | "running" | "completed" | "failed";

export interface FailureDetail {
  url: string;
  name_hint: string;
  reason: string;
}

export interface TaskStatusResponse {
  task_id: string;
  raw_message: string;
  category: string;
  discount_percent: string;
  status: TaskStatus;
  stage: string;
  stage_index: number;
  total_stages: number;
  progress_percent: number;
  products_discovered: number;
  products_extracted: number;
  failed_products: number;
  current_subcategory: string;
  subcategories: string[];
  failures: FailureDetail[];
  warnings: string[];
  excel_filename: string;
  pdf_filename: string;
  excel_ready: boolean;
  pdf_ready: boolean;
  error_message: string;
  created_at: string;
  started_at: string;
  completed_at: string;
  updated_at: string;
  deduplicated?: boolean;
}

export const PROGRESS_STAGES = [
  "Validating task",
  "Opening website",
  "Discovering subcategories",
  "Collecting product URLs",
  "Extracting product details",
  "Detecting sizes",
  "Categorizing products",
  "Calculating discounted prices",
  "Generating Excel",
  "Generating PDF",
  "Saving generated files",
] as const;
