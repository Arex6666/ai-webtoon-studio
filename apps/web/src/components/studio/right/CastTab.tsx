'use client'

import { useEffect, useState } from 'react'
import { useFormContext } from 'react-hook-form'
import { PanelSpec } from '@/lib/schema'
import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { chaptersApi, identityApi, assetsApi } from '@/lib/api/services'
import { useToast } from '@/hooks/use-toast'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Users,
  CheckCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  Upload,
} from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────────────────────

type FaceIDStatus = 'ready' | 'pending' | 'missing' | 'generating' | 'failed'

type AssetLockStatus = 'pending' | 'exact' | 'fuzzy' | 'none'

interface CastCharacter {
  id: string
  name: string
  asset_id?: string | null
  // Avatar
  thumbnail_url?: string | null
  canonical_image_url?: string | null
  // FaceID
  faceIdStatus: FaceIDStatus
  face_embedding_path?: string | null
  // Reference image generation
  reference_image_status?: 'none' | 'generating' | 'ready' | 'failed'
  reference_image_path?: string | null
  // Asset lock status
  lockStatus?: AssetLockStatus
}

// ─── FaceID Status Badge ──────────────────────────────────────────────────────

function FaceIDBadge({ status }: { status: FaceIDStatus }) {
  switch (status) {
    case 'ready':
      return (
        <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-[10px] px-1.5 py-0.5 gap-0.5">
          <CheckCircle className="w-2.5 h-2.5" />
          就绪
        </Badge>
      )
    case 'generating':
      return (
        <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 text-[10px] px-1.5 py-0.5 gap-0.5">
          <Loader2 className="w-2.5 h-2.5 animate-spin" />
          生成中
        </Badge>
      )
    case 'pending':
      return (
        <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30 text-[10px] px-1.5 py-0.5 gap-0.5">
          <AlertCircle className="w-2.5 h-2.5" />
          待确认
        </Badge>
      )
    case 'failed':
      return (
        <Badge className="bg-red-500/20 text-red-400 border-red-500/30 text-[10px] px-1.5 py-0.5 gap-0.5">
          <AlertCircle className="w-2.5 h-2.5" />
          失败
        </Badge>
      )
    default:
      return (
        <Badge variant="outline" className="text-[10px] px-1.5 py-0.5 text-muted-foreground gap-0.5">
          <AlertCircle className="w-2.5 h-2.5" />
          缺失
        </Badge>
      )
  }
}

// ─── Consistency Summary ──────────────────────────────────────────────────────

function ConsistencySummary({ characters }: { characters: CastCharacter[] }) {
  const readyCount = characters.filter(c => c.faceIdStatus === 'ready').length
  const total = characters.length

  const colorClass =
    readyCount === total && total > 0
      ? 'text-emerald-400'
      : readyCount > 0
        ? 'text-yellow-400'
        : 'text-muted-foreground'

  return (
    <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/5 bg-muted/5">
      <div className="flex items-center gap-1">
        {characters.map(c => (
          <span
            key={c.id}
            title={c.name}
            className={`w-2 h-2 rounded-full ${
              c.faceIdStatus === 'ready'
                ? 'bg-emerald-400'
                : c.faceIdStatus === 'generating'
                  ? 'bg-blue-400 animate-pulse'
                  : c.faceIdStatus === 'pending'
                    ? 'bg-yellow-400'
                    : 'bg-muted-foreground/40'
            }`}
          />
        ))}
      </div>
      <span className={`text-xs font-medium ${colorClass}`}>
        {readyCount}/{total} 就绪
      </span>
    </div>
  )
}

// ─── Character Card ───────────────────────────────────────────────────────────

function CharacterCard({
  character,
  isInScene,
  onToggle,
  onUpload,
  onRegenerate,
  isRegenerating,
}: {
  character: CastCharacter
  isInScene: boolean
  onToggle: () => void
  onUpload: (assetId: string) => void
  onRegenerate: (char: CastCharacter) => void
  isRegenerating: boolean
}) {
  const avatarUrl =
    character.reference_image_status === 'ready' && character.reference_image_path
      ? character.reference_image_path
      : character.canonical_image_url || character.thumbnail_url || null

  return (
    <div className="group flex items-center gap-3 p-2.5 rounded-lg hover:bg-muted/10 transition-colors cursor-default">
      {/* In-scene toggle */}
      <Checkbox
        id={`cast-${character.id}`}
        checked={isInScene}
        onCheckedChange={onToggle}
        className="flex-shrink-0"
      />

      {/* Avatar */}
      <div className="relative w-9 h-9 rounded overflow-hidden bg-muted/30 flex-shrink-0 ring-1 ring-white/5 group-hover:ring-white/15 transition-all">
        {character.reference_image_status === 'generating' ? (
          <div className="w-full h-full flex items-center justify-center bg-blue-500/10">
            <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
          </div>
        ) : avatarUrl ? (
          <img
            src={avatarUrl}
            alt={character.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Users className="w-4 h-4 text-muted-foreground/50" />
          </div>
        )}

        {/* Hover: Regenerate overlay */}
        {character.asset_id &&
          (character.faceIdStatus === 'ready' ||
            character.faceIdStatus === 'failed' ||
            character.reference_image_status === 'ready') && (
            <div
              className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity cursor-pointer"
              title="重新生成参考图"
              onClick={e => {
                e.stopPropagation()
                onRegenerate(character)
              }}
            >
              {isRegenerating ? (
                <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5 text-white" />
              )}
            </div>
          )}
      </div>

      {/* Name */}
      <label
        htmlFor={`cast-${character.id}`}
        className="flex-1 min-w-0 text-sm font-medium leading-none cursor-pointer truncate"
        title={character.name}
      >
        {character.name}
      </label>

      {/* FaceID badge + Upload button */}
      <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
        <FaceIDBadge status={character.faceIdStatus} />

        {character.asset_id && character.faceIdStatus !== 'generating' && (
          <Button
            size="sm"
            variant="ghost"
            className="h-5 px-1.5 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity gap-1"
            onClick={e => {
              e.stopPropagation()
              onUpload(character.asset_id!)
            }}
          >
            <Upload className="w-2.5 h-2.5" />
            上传参考
          </Button>
        )}
      </div>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function CastTab() {
  const { watch, setValue } = useFormContext<PanelSpec>()
  const { chapterId, storeCharacters, canRender, pendingAssetsCount, activeInspectorTab } =
    useStudioStore(
      useShallow(s => ({
        chapterId: s.chapterId,
        storeCharacters: s.characters,
        canRender: s.canRender,
        pendingAssetsCount: s.pendingAssetsCount,
        activeInspectorTab: s.activeInspectorTab,
      }))
    )

  const selectedCharacters: string[] = watch('characters') || []

  const [characters, setCharacters] = useState<CastCharacter[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null)

  const { toast } = useToast()

  // ── Data fetch ────────────────────────────────────────────────────────────

  const fetchData = async () => {
    if (!chapterId) return

    setLoading(true)
    setError(null)

    try {
      const lock = await chaptersApi.getAssetsLock(chapterId)

      const chars: CastCharacter[] = []
      if (lock.characters) {
        Object.entries(lock.characters).forEach(([id, char]: [string, any]) => {
          const embeddingPath = char.face_embedding_path || char.embedding_path
          const refStatus: CastCharacter['reference_image_status'] =
            char.reference_image_status || 'none'

          let faceIdStatus: FaceIDStatus = 'missing'
          if (embeddingPath) {
            faceIdStatus = 'ready'
          } else if (refStatus === 'generating') {
            faceIdStatus = 'generating'
          } else if (refStatus === 'failed') {
            faceIdStatus = 'failed'
          } else if (char.status === 'pending') {
            faceIdStatus = 'pending'
          }

          chars.push({
            id,
            name: char.name || id,
            asset_id: char.asset_id,
            thumbnail_url: char.thumbnail_url || null,
            canonical_image_url: char.canonical_image_url || null,
            faceIdStatus,
            face_embedding_path: embeddingPath || null,
            reference_image_status: refStatus,
            reference_image_path: char.reference_image_path || null,
            lockStatus: char.status,
          })
        })
      }
      setCharacters(chars)
    } catch (err) {
      console.warn('Failed to load AssetsLock, falling back to store:', err)
      // Fallback: use store characters
      setCharacters(
        storeCharacters.map(c => ({
          id: c.id,
          name: c.name,
          asset_id: undefined,
          thumbnail_url: c.thumbnail_url || null,
          faceIdStatus:
            c.face_embedding_status === 'ready'
              ? 'ready'
              : c.face_embedding_status === 'pending'
                ? 'pending'
                : 'missing',
          face_embedding_path: c.face_embedding_status === 'ready' ? 'exists' : null,
        }))
      )
      if (storeCharacters.length === 0) {
        setError('加载角色数据失败')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId])

  // Refresh when this tab becomes active
  useEffect(() => {
    if (activeInspectorTab === 'cast') {
      fetchData()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeInspectorTab])

  // Poll while any character is generating
  useEffect(() => {
    if (!chapterId) return

    const isGenerating = characters.some(c => c.reference_image_status === 'generating')
    if (!isGenerating) return

    const interval = setInterval(async () => {
      try {
        const lock = await chaptersApi.getAssetsLock(chapterId)
        if (!lock.characters) return
        setCharacters(prev =>
          prev.map(c => {
            const updated = lock.characters[c.id]
            if (!updated) return c
            const embeddingPath = updated.face_embedding_path || updated.embedding_path
            const refStatus = updated.reference_image_status || 'none'
            let faceIdStatus: FaceIDStatus = 'missing'
            if (embeddingPath) faceIdStatus = 'ready'
            else if (refStatus === 'generating') faceIdStatus = 'generating'
            else if (refStatus === 'failed') faceIdStatus = 'failed'
            else if (updated.status === 'pending') faceIdStatus = 'pending'

            return {
              ...c,
              faceIdStatus,
              face_embedding_path: embeddingPath || null,
              reference_image_status: refStatus,
              reference_image_path: updated.reference_image_path || null,
            }
          })
        )
      } catch {
        // silent
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [chapterId, characters])

  // ── Actions ───────────────────────────────────────────────────────────────

  const toggleCharacter = (characterName: string) => {
    const next = selectedCharacters.includes(characterName)
      ? selectedCharacters.filter(c => c !== characterName)
      : [...selectedCharacters, characterName]
    setValue('characters', next)
  }

  const handleUpload = (assetId: string) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.onchange = async (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return

      if (!file.type.startsWith('image/')) {
        toast({ title: '请选择图片文件', variant: 'destructive' })
        return
      }
      if (file.size > 10 * 1024 * 1024) {
        toast({ title: '图片大小不能超过 10MB', variant: 'destructive' })
        return
      }

      try {
        await identityApi.extractEmbedding(assetId, [file])
        toast({ title: '上传成功', description: 'FaceID 提取完成，一致性已更新' })
        fetchData()
      } catch (err) {
        console.error('Upload failed:', err)
        toast({
          title: '上传失败',
          description: '无法提取 FaceID，请确保图片包含清晰的人脸',
          variant: 'destructive',
        })
      }
    }
    input.click()
  }

  const handleRegenerate = async (char: CastCharacter) => {
    if (!char.asset_id || regeneratingId) return

    try {
      setRegeneratingId(char.id)
      await assetsApi.regenerateReference(char.asset_id)

      // Optimistic update
      setCharacters(prev =>
        prev.map(c =>
          c.id === char.id
            ? { ...c, reference_image_status: 'generating', faceIdStatus: 'generating' }
            : c
        )
      )
    } catch (err) {
      console.error('Regenerate failed:', err)
      toast({ title: '重新生成失败', variant: 'destructive' })
    } finally {
      setRegeneratingId(null)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading && characters.length === 0) {
    return (
      <div className="p-4 space-y-3">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    )
  }

  if (error && characters.length === 0) {
    return (
      <div className="p-6 text-center space-y-3">
        <AlertCircle className="w-8 h-8 text-red-400 mx-auto" />
        <p className="text-sm text-red-400">{error}</p>
        <Button variant="outline" size="sm" onClick={fetchData}>
          重试
        </Button>
      </div>
    )
  }

  if (characters.length === 0) {
    return (
      <div className="p-6 text-center space-y-3 text-muted-foreground">
        <Users className="w-10 h-10 mx-auto opacity-40" />
        <p className="text-sm">还没有角色资产</p>
        <p className="text-xs">请先粘贴剧本并运行 AI 分镜，系统会自动提取角色</p>
      </div>
    )
  }

  const readyCount = characters.filter(c => c.faceIdStatus === 'ready').length

  return (
    <ScrollArea className="h-full">
      {/* Consistency summary banner */}
      <ConsistencySummary characters={characters} />

      <div className="p-3 space-y-1">
        {/* Render-readiness indicator */}
        <div className="flex items-center justify-between px-1 pb-2">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
            角色绑定 · {selectedCharacters.length} 已选
          </span>
          <div className="flex items-center gap-1.5">
            {canRender ? (
              <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-[10px]">
                <CheckCircle className="w-2.5 h-2.5 mr-1" />
                可渲染
              </Badge>
            ) : pendingAssetsCount > 0 ? (
              <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 text-[10px]">
                <AlertCircle className="w-2.5 h-2.5 mr-1" />
                {pendingAssetsCount} 待确认
              </Badge>
            ) : null}
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5"
              onClick={fetchData}
              disabled={loading}
              title="刷新"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* Character cards */}
        {characters.map(char => (
          <CharacterCard
            key={char.id}
            character={char}
            isInScene={selectedCharacters.includes(char.name)}
            onToggle={() => toggleCharacter(char.name)}
            onUpload={handleUpload}
            onRegenerate={handleRegenerate}
            isRegenerating={regeneratingId === char.id}
          />
        ))}
      </div>

      {/* Tip: missing FaceID */}
      {readyCount < characters.length && (
        <div className="mx-3 mb-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <p className="text-xs text-blue-400">
            上传角色参考图以提取 FaceID，确保跨格一致性渲染。
          </p>
        </div>
      )}
    </ScrollArea>
  )
}
