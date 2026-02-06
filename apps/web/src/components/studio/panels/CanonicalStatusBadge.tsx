/**
 * CanonicalStatusBadge - 显示角色 Canonical 状态
 * P0-CH-04-04: 在 AssetsLockPanel 显示选优状态
 */
import React, { useState } from 'react';

interface CanonicalStatus {
    status: 'pending' | 'running' | 'succeeded' | 'failed';
    selected_path?: string;
    selected_score?: number;
    selection_reason?: string;
    candidates_count?: number;
    candidate_paths?: string[];
}

interface FaceEmbeddingStatus {
    status: 'ready' | 'missing' | 'failed';
    embedding_path?: string;
    det_score?: number;
    error_message?: string;
}

interface Props {
    characterName: string;
    canonical?: CanonicalStatus;
    faceEmbedding?: FaceEmbeddingStatus;
    onTriggerGenerate?: () => void;
}

export function CanonicalStatusBadge({
    characterName,
    canonical,
    faceEmbedding,
    onTriggerGenerate,
}: Props) {
    const [showDetails, setShowDetails] = useState(false);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'succeeded':
            case 'ready':
                return 'bg-green-500/20 text-green-400 border-green-500/30';
            case 'running':
                return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
            case 'failed':
                return 'bg-red-500/20 text-red-400 border-red-500/30';
            default:
                return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'succeeded':
            case 'ready':
                return '✓';
            case 'running':
                return '⟳';
            case 'failed':
                return '✗';
            default:
                return '○';
        }
    };

    const canonicalStatus = canonical?.status || 'pending';
    const embeddingStatus = faceEmbedding?.status || 'missing';

    return (
        <div className="space-y-2">
            {/* Canonical Status */}
            <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 w-16">定妆照:</span>
                <span
                    className={`px-2 py-0.5 text-xs rounded border ${getStatusColor(canonicalStatus)} cursor-pointer`}
                    onClick={() => setShowDetails(!showDetails)}
                >
                    {getStatusIcon(canonicalStatus)} {canonicalStatus}
                    {canonical?.selected_score && ` (${canonical.selected_score.toFixed(0)}分)`}
                </span>
                {canonicalStatus === 'pending' && onTriggerGenerate && (
                    <button
                        onClick={onTriggerGenerate}
                        className="text-xs text-blue-400 hover:text-blue-300"
                    >
                        生成
                    </button>
                )}
            </div>

            {/* FaceID Status */}
            <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 w-16">FaceID:</span>
                <span
                    className={`px-2 py-0.5 text-xs rounded border ${getStatusColor(embeddingStatus)}`}
                >
                    {getStatusIcon(embeddingStatus)} {embeddingStatus}
                    {faceEmbedding?.det_score && ` (${(faceEmbedding.det_score * 100).toFixed(0)}%)`}
                </span>
            </div>

            {/* Details Popover */}
            {showDetails && canonical?.selection_reason && (
                <div className="mt-2 p-2 bg-gray-800 rounded text-xs border border-gray-700">
                    <div className="font-semibold mb-1">选择原因:</div>
                    <div className="text-gray-300">{canonical.selection_reason}</div>

                    {canonical.candidates_count && canonical.candidates_count > 0 && (
                        <div className="mt-2 text-gray-500">
                            从 {canonical.candidates_count} 张候选中选出
                        </div>
                    )}

                    {/* Candidate Thumbnails (可选) */}
                    {canonical.candidate_paths && canonical.candidate_paths.length > 0 && (
                        <div className="mt-2 flex gap-1">
                            {canonical.candidate_paths.slice(0, 4).map((path, i) => (
                                <div
                                    key={i}
                                    className={`w-10 h-10 rounded border ${path === canonical.selected_path
                                            ? 'border-green-500 ring-1 ring-green-500'
                                            : 'border-gray-600'
                                        } overflow-hidden`}
                                >
                                    <img
                                        src={`/api/v1/storage/preview?key=${encodeURIComponent(path)}`}
                                        alt={`Candidate ${i + 1}`}
                                        className="w-full h-full object-cover"
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Error Message */}
            {faceEmbedding?.status === 'failed' && faceEmbedding.error_message && (
                <div className="text-xs text-red-400">
                    ⚠ {faceEmbedding.error_message}
                </div>
            )}
        </div>
    );
}

/**
 * CharacterAssetCard - 完整的角色资产卡片
 */
interface CharacterAssetCardProps {
    character: {
        asset_id: string;
        name: string;
        role_name?: string;
        binding_status: 'exact' | 'fuzzy' | 'pending';
        match_confidence?: number;
        canonical_status?: string;
        canonical_selected_path?: string;
        canonical_selected_score?: number;
        canonical_selection_reason?: string;
        canonical_candidates_count?: number;
        face_embedding?: FaceEmbeddingStatus;
    };
    onConfirmBinding?: () => void;
    onTriggerGenerate?: () => void;
}

export function CharacterAssetCard({
    character,
    onConfirmBinding,
    onTriggerGenerate,
}: CharacterAssetCardProps) {
    const bindingColor = {
        exact: 'border-green-500/50 bg-green-500/5',
        fuzzy: 'border-yellow-500/50 bg-yellow-500/5',
        pending: 'border-red-500/50 bg-red-500/5',
    }[character.binding_status];

    const bindingLabel = {
        exact: '✓ 已绑定',
        fuzzy: '? 待确认',
        pending: '○ 未绑定',
    }[character.binding_status];

    const isRenderReady =
        character.binding_status === 'exact' &&
        character.face_embedding?.status === 'ready';

    return (
        <div className={`p-3 rounded-lg border ${bindingColor}`}>
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <div>
                    <div className="font-medium text-white">{character.name}</div>
                    {character.role_name && character.role_name !== character.name && (
                        <div className="text-xs text-gray-500">角色: {character.role_name}</div>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <span
                        className={`text-xs px-2 py-0.5 rounded ${character.binding_status === 'exact'
                                ? 'bg-green-500/20 text-green-400'
                                : character.binding_status === 'fuzzy'
                                    ? 'bg-yellow-500/20 text-yellow-400'
                                    : 'bg-gray-500/20 text-gray-400'
                            }`}
                    >
                        {bindingLabel}
                    </span>
                    {isRenderReady && (
                        <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
                            可渲染
                        </span>
                    )}
                </div>
            </div>

            {/* Status */}
            <CanonicalStatusBadge
                characterName={character.name}
                canonical={{
                    status: (character.canonical_status as any) || 'pending',
                    selected_path: character.canonical_selected_path,
                    selected_score: character.canonical_selected_score,
                    selection_reason: character.canonical_selection_reason,
                    candidates_count: character.canonical_candidates_count,
                }}
                faceEmbedding={character.face_embedding}
                onTriggerGenerate={onTriggerGenerate}
            />

            {/* Actions */}
            {character.binding_status === 'fuzzy' && onConfirmBinding && (
                <button
                    onClick={onConfirmBinding}
                    className="mt-2 w-full py-1 text-xs bg-yellow-600/50 hover:bg-yellow-600/70 rounded"
                >
                    确认绑定
                </button>
            )}
        </div>
    );
}

export default CanonicalStatusBadge;
