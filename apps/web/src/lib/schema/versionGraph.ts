import { z } from 'zod'

// ============ Commit Schema ============

export const commitSchema = z.object({
    id: z.string(),
    parentId: z.string().nullable(),
    message: z.string(),
    author: z.string().default('user'),
    createdAt: z.string(),
    snapshotRef: z.string(), // localStorage key or backend ID
})

export type Commit = z.infer<typeof commitSchema>

// ============ Version Graph Schema ============

export const versionGraphSchema = z.object({
    commits: z.record(z.string(), commitSchema),
    branches: z.record(z.string(), z.string()), // branchName -> commitId
    head: z.object({
        branch: z.string(),
        commitId: z.string(),
    }),
})

export type VersionGraph = z.infer<typeof versionGraphSchema>

// ============ Factory Functions ============

export function createVersionGraph(): VersionGraph {
    return {
        commits: {},
        branches: { main: '' },
        head: { branch: 'main', commitId: '' },
    }
}

export function createCommit(
    message: string,
    parentId: string | null,
    snapshotRef: string,
    author: string = 'user'
): Commit {
    return {
        id: `commit-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        parentId,
        message,
        author,
        createdAt: new Date().toISOString(),
        snapshotRef,
    }
}

// ============ Diff Summary ============

export const diffSummarySchema = z.object({
    panelsChanged: z.number(),
    clipsChanged: z.number(),
    bindingsChanged: z.number(),
    changes: z.array(z.object({
        type: z.enum(['panel', 'clip', 'binding', 'setting']),
        id: z.string(),
        field: z.string(),
        from: z.any().optional(),
        to: z.any().optional(),
    })),
})

export type DiffSummary = z.infer<typeof diffSummarySchema>

export function createEmptyDiffSummary(): DiffSummary {
    return {
        panelsChanged: 0,
        clipsChanged: 0,
        bindingsChanged: 0,
        changes: [],
    }
}
