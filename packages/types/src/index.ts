import { z } from "zod";

export const ProjectId = z.string().uuid();
export type ProjectId = z.infer<typeof ProjectId>;

export const ProjectSchema = z.object({
  id: ProjectId,
  name: z.string().min(3),
  clientName: z.string().min(2),
  startDate: z.coerce.date(),
  endDate: z.coerce.date().optional(),
  status: z.enum(["planning", "active", "on_hold", "completed"]),
  budget: z.number().nonnegative().optional()
});

export type Project = z.infer<typeof ProjectSchema>;

export const PaginatedResponse = <Schema extends z.ZodTypeAny>(itemSchema: Schema) =>
  z.object({
    data: z.array(itemSchema),
    cursor: z.object({
      next: z.string().nullable(),
      previous: z.string().nullable()
    })
  });
