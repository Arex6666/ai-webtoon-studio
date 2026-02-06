/**
 * API 模块统一入口
 */

import { env } from '../utils/env'

// 导出所有类型
export * from './types'

// 导出所有 API 服务
export {
    projectsApi,
    chaptersApi,
    panelsApi,
    assetsApi,
    renderApi,
    typesetApi,
    composeApi,
    conversationsApi,
} from './services'

// 导出底层客户端（如需直接使用）
export { apiGet, apiPost, apiPatch, apiDelete, ApiError } from './client'

// 兼容旧代码的 api 对象
export const api = {
    baseUrl: env.API_BASE_URL,
}
