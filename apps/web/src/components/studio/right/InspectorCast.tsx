'use client'

import { useState, useEffect } from 'react'
import { useFormContext } from 'react-hook-form'
import { PanelSpec } from '@/lib/schema'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { useStudioStore } from '@/lib/store/studioStore'
import { chaptersApi, assetsApi } from '@/lib/api/services'
import { User, AlertCircle, Upload, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface CharacterInfo {
  id: string
  name: string
  asset_id?: string | null
  pending?: boolean
  face_embedding_path?: string | null
  reference_images?: string[]
  // S5-01: 参考图状态
  reference_image_status?: 'none' | 'generating' | 'ready' | 'failed'
  reference_image_path?: string | null
}

export function InspectorCast() {
  const { watch, setValue } = useFormContext<PanelSpec>()
  const { chapterId, characters: storeCharacters } = useStudioStore()
  const selectedCharacters = watch('characters') || []

  const [characters, setCharacters] = useState<CharacterInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null)

  // 从 AssetsLock 获取角色数据
  useEffect(() => {
    if (!chapterId) return

    setLoading(true)
    setError(null)

    chaptersApi.getAssetsLock(chapterId)
      .then((lock) => {
        // 从 AssetsLock.characters 提取角色
        const chars: CharacterInfo[] = []
        if (lock.characters) {
          Object.entries(lock.characters).forEach(([id, char]: [string, any]) => {
            chars.push({
              id: id,
              name: char.name || id,
              asset_id: char.asset_id,
              pending: !char.face_embedding_path,
              face_embedding_path: char.face_embedding_path,
              reference_images: char.reference_images || [],
              reference_image_status: char.reference_image_status || 'none',
              reference_image_path: char.reference_image_path
            })
          })
        }
        setCharacters(chars)
      })
      .catch((err) => {
        console.warn('Failed to load AssetsLock:', err)
        // 降级：使用 store 中的角色
        setCharacters(storeCharacters.map(c => ({
          id: c.id,
          name: c.name,
          pending: c.face_embedding_status !== 'ready',
          face_embedding_path: c.face_embedding_status === 'ready' ? 'exists' : null
        })))
      })
      .finally(() => setLoading(false))
  }, [chapterId, storeCharacters])

  // Poll for updates if any character is generating
  useEffect(() => {
    if (!chapterId) return

    const interval = setInterval(() => {
      // Check if any character is generating locally
      const isGenerating = characters.some(c => c.reference_image_status === 'generating')

      if (isGenerating) {
        chaptersApi.getAssetsLock(chapterId)
          .then((lock) => {
            if (lock.characters) {
              setCharacters(prev => prev.map(c => {
                const updated = lock.characters[c.id]
                if (updated) {
                  return {
                    ...c,
                    reference_image_status: updated.reference_image_status,
                    reference_image_path: updated.reference_image_path,
                    face_embedding_path: updated.face_embedding_path,
                    pending: !updated.face_embedding_path
                  }
                }
                return c
              }))
            }
          })
          .catch(() => { })
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [chapterId, characters])

  const handleRegenerate = async (e: React.MouseEvent, char: CharacterInfo) => {
    e.stopPropagation()
    if (!char.asset_id || regeneratingId) return

    try {
      setRegeneratingId(char.id)
      await assetsApi.regenerateReference(char.asset_id)

      // Optimistic update
      setCharacters(chars => chars.map(c =>
        c.id === char.id ? { ...c, reference_image_status: 'generating' } : c
      ))
    } catch (err) {
      console.error('Failed to regenerate:', err)
    } finally {
      setRegeneratingId(null)
    }
  }

  const toggleCharacter = (characterName: string) => {
    const newCharacters = selectedCharacters.includes(characterName)
      ? selectedCharacters.filter((c) => c !== characterName)
      : [...selectedCharacters, characterName]
    setValue('characters', newCharacters)
  }

  // 加载中
  if (loading) {
    return (
      <div className="p-4 flex items-center justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // 空状态：没有可用角色
  if (characters.length === 0) {
    return (
      <div className="p-4 space-y-4">
        <div className="space-y-2">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">角色绑定</Label>
          <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/10 border border-white/5">
            <AlertCircle className="w-5 h-5 text-amber-500/70 mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <p className="text-sm text-foreground/70">还没有角色资产</p>
              <p className="text-xs text-muted-foreground">
                请先粘贴剧本并运行 AI 分镜，系统会自动提取角色用于一致性控制。
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4">
      <div className="space-y-2">
        <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">角色绑定</Label>
        <div className="space-y-2">
          {characters.map((character) => (
            <div key={character.id} className="flex items-center space-x-3 p-2 rounded-lg hover:bg-muted/10 transition-colors group">
              <Checkbox
                id={character.id}
                checked={selectedCharacters.includes(character.name)}
                onCheckedChange={() => toggleCharacter(character.name)}
              />

              {/* 头像/封面 */}
              <div className="relative w-8 h-8 rounded overflow-hidden bg-muted/30 flex-shrink-0 group-hover:ring-1 ring-white/20">
                {character.reference_image_status === 'ready' && character.reference_image_path ? (
                  <img src={character.reference_image_path} alt={character.name} className="w-full h-full object-cover" />
                ) : character.reference_image_status === 'generating' ? (
                  <div className="w-full h-full flex items-center justify-center bg-blue-500/10">
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                  </div>
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <User className="w-4 h-4 text-muted-foreground/50" />
                  </div>
                )}

                {/* 悬浮重新生成按钮 */}
                {(character.reference_image_status === 'failed' || character.reference_image_status === 'ready') && character.asset_id && (
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity cursor-pointer"
                    onClick={(e) => handleRegenerate(e, character)}
                    title="重新生成参考图">
                    <RefreshCw className="w-3 h-3 text-white" />
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 flex-1 min-w-0">
                <label
                  htmlFor={character.id}
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer truncate"
                  title={character.name}
                >
                  {character.name}
                </label>
              </div>

              {/* 状态标签 */}
              <div className="flex-shrink-0">
                {character.face_embedding_path ? (
                  <span className="text-[10px] text-green-500/70 bg-green-500/10 px-1.5 py-0.5 rounded border border-green-500/20">Ready</span>
                ) : character.reference_image_status === 'generating' ? (
                  <span className="text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/20">生成中</span>
                ) : character.reference_image_status === 'failed' ? (
                  <span className="text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded border border-red-500/20">失败</span>
                ) : (
                  <span className="text-[10px] text-amber-500/70 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">待提取</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="text-xs text-muted-foreground">
        已选: {selectedCharacters.length} 个角色
      </div>

      {/* 提示：如何完善角色 */}
      {characters.some(c => !c.face_embedding_path) && (
        <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <p className="text-xs text-blue-400">
            💡 角色显示"待提取"表示尚未上传参考图提取 FaceID，可在"一致性"Tab 操作。
          </p>
        </div>
      )}
    </div>
  )
}
