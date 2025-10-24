import { z } from "zod";

export const Role = z.enum(["owner", "project_manager", "site_supervisor", "collaborator"]);
export type Role = z.infer<typeof Role>;

export const Permission = z.enum([
  "projects:read",
  "projects:write",
  "projects:share",
  "tasks:read",
  "tasks:write",
  "reports:generate",
  "billing:manage"
]);
export type Permission = z.infer<typeof Permission>;

export const RolePermissions: Record<Role, Permission[]> = {
  owner: Permission.options,
  project_manager: [
    "projects:read",
    "projects:write",
    "projects:share",
    "tasks:read",
    "tasks:write",
    "reports:generate"
  ],
  site_supervisor: ["projects:read", "tasks:read", "tasks:write"],
  collaborator: ["projects:read", "tasks:read"]
};

export const AssignmentSchema = z.object({
  userId: z.string().uuid(),
  projectId: z.string().uuid(),
  role: Role
});

export type Assignment = z.infer<typeof AssignmentSchema>;

export function can(role: Role, permission: Permission) {
  return RolePermissions[role].includes(permission);
}
