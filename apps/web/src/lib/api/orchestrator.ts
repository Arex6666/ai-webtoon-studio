import { client } from './client'

export const orchestratorApi = {
    // 会话管理
    getSession: (sessionId: string, projectId: string) =>
        client.post(`/orchestrator/sessions/${sessionId}`, { project_id: projectId }),

    getSessionStatus: (sessionId: string, projectId: string) =>
        client.get(`/orchestrator/sessions/${sessionId}/status?project_id=${projectId}`),

    // 分镜操作
    createStoryboard: (sessionId: string, projectId: string, prompt: string) =>
        client.post('/orchestrator/storyboard/create', {
            session_id: sessionId,
            project_id: projectId,
            prompt
        }),

    modifyStoryboard: (sessionId: string, projectId: string, instruction: string) =>
        client.post('/orchestrator/storyboard/modify', {
            session_id: sessionId,
            project_id: projectId,
            instruction
        }),

    // 资产绑定
    bindAssets: (sessionId: string, projectId: string) =>
        client.post('/orchestrator/assets/bind', {
            session_id: sessionId,
            project_id: projectId
        }),

    // 渲染计划
    createRenderPlan: (sessionId: string, projectId: string, panelIds?: string[]) =>
        client.post('/orchestrator/render/plan', {
            session_id: sessionId,
            project_id: projectId,
            panel_ids: panelIds
        })
}
