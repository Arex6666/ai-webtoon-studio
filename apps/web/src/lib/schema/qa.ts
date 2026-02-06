import { z } from 'zod'

// ============ QA Rules ============

export const qaRulesSchema = z.object({
    identity: z.boolean().default(true),
    anatomy: z.boolean().default(true),
    text: z.boolean().default(true),
    flicker: z.boolean().default(true),
})

export type QARules = z.infer<typeof qaRulesSchema>

// ============ QA Config ============

export const qaConfigSchema = z.object({
    threshold: z.number().min(0).max(1).default(0.75),
    maxIssues: z.number().min(0).max(10).default(3),
    rulesEnabled: qaRulesSchema,
})

export type QAConfig = z.infer<typeof qaConfigSchema>

// ============ QA Result ============

export const qaResultSchema = z.object({
    score: z.number().min(0).max(1),
    issues: z.array(z.string()),
    analyzedAt: z.string(),
})

export type QAResult = z.infer<typeof qaResultSchema>

// ============ Factory Functions ============

export function createDefaultQAConfig(): QAConfig {
    return {
        threshold: 0.75,
        maxIssues: 3,
        rulesEnabled: {
            identity: true,
            anatomy: true,
            text: true,
            flicker: true,
        },
    }
}

// ============ QA Issue Categories ============

export const QA_ISSUE_CATEGORIES = {
    identity: [
        'Character face inconsistent',
        'Character identity mismatch',
        'Different character appearance',
    ],
    anatomy: [
        'Hand anatomy issues',
        'Body proportion incorrect',
        'Limb positioning unnatural',
    ],
    text: [
        'Text legibility issue',
        'Text rendering artifact',
        'Speech bubble overlap',
    ],
    flicker: [
        'Frame flickering detected',
        'Temporal inconsistency',
        'Motion artifact',
    ],
    background: [
        'Background mismatch',
        'Scene inconsistency',
        'Environment discontinuity',
    ],
    artifact: [
        'Visual artifact detected',
        'Noise or blur issue',
        'Rendering glitch',
    ],
}

export function suggestFixStrategy(issues: string[]): 'inpaint' | 'redraw_char' | 'redraw_bg' | 'reroll' {
    const issueText = issues.join(' ').toLowerCase()

    if (issueText.includes('identity') || issueText.includes('character') || issueText.includes('face')) {
        return 'redraw_char'
    }
    if (issueText.includes('background') || issueText.includes('scene') || issueText.includes('environment')) {
        return 'redraw_bg'
    }
    if (issueText.includes('artifact') || issueText.includes('blur') || issueText.includes('noise')) {
        return 'inpaint'
    }
    return 'reroll'
}
