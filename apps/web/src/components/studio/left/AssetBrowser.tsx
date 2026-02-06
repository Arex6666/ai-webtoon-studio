'use client'

import { useState } from 'react'
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Button } from "@/components/ui/button"
import { useStudioStore } from "@/lib/store/studioStore"
import { assetsApi } from "@/lib/api/services"
import { Plus, Upload, User, Map, Palette, Box, Trash2, Loader2 } from "lucide-react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { CreateAssetModal } from "../modals/CreateAssetModal"
import { AssetDetailModal } from "../modals/AssetDetailModal"


export function AssetBrowser() {
  const { characters, scenes, styles, props, projectId, chapterId, setStudioData } = useStudioStore()
  const [isClearing, setIsClearing] = useState(false)

  const hasAnyAssets = characters.length > 0 || scenes.length > 0 || styles.length > 0 || props.length > 0

  const handleClearAssets = async () => {
    if (!projectId) return

    setIsClearing(true)
    try {
      const result = await assetsApi.clearAll(projectId, { hardDelete: true })
      console.log('Assets cleared:', result)

      // Refresh studio data
      if (chapterId) {
        const { chaptersApi } = await import('@/lib/api/services')
        const studioData = await chaptersApi.getStudio(chapterId)
        setStudioData(studioData)
      }
    } catch (error) {
      console.error('Failed to clear assets:', error)
      alert('清空资产失败: ' + (error instanceof Error ? error.message : '未知错误'))
    } finally {
      setIsClearing(false)
    }
  }

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null)
  const [selectedAssetType, setSelectedAssetType] = useState<'character' | 'scene'>('character')

  // 处理资产点击
  const handleAssetClick = (assetId: string, type: 'character' | 'scene') => {
    setSelectedAssetId(assetId)
    setSelectedAssetType(type)
  }

  // 刷新资产数据
  const handleAssetUpdated = async () => {
    if (chapterId) {
      const { chaptersApi } = await import('@/lib/api/services')
      const studioData = await chaptersApi.getStudio(chapterId)
      setStudioData(studioData)
    }
  }

  // Empty State: 没有任何资产
  if (!hasAnyAssets) {
    return (
      <div className="h-full flex flex-col">
        <div className="p-4 border-b border-white/5">
          <h3 className="font-semibold text-foreground/80">资产库</h3>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center space-y-4 max-w-xs">
            <div className="mx-auto w-12 h-12 rounded-xl bg-muted/20 border border-white/5 flex items-center justify-center">
              <User className="w-6 h-6 text-muted-foreground/30" />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground/70">还没有资产</p>
              <p className="text-xs text-muted-foreground">
                创建角色、场景和风格资产，用于 AI 分镜生成时的一致性控制。
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Button size="sm" className="w-full gap-2" onClick={() => setShowCreateModal(true)}>
                <Plus className="w-4 h-4" />
                创建资产
              </Button>
              <Button size="sm" variant="outline" className="w-full gap-2 border-white/10" onClick={() => setShowCreateModal(true)}>
                <Upload className="w-4 h-4" />
                导入资产
              </Button>
            </div>
          </div>
        </div>
        <CreateAssetModal open={showCreateModal} onOpenChange={setShowCreateModal} />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-white/5 flex items-center justify-between">
        <h3 className="font-semibold text-foreground/80">资产库</h3>
        <div className="flex items-center gap-1">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                disabled={isClearing}
              >
                {isClearing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent className="bg-zinc-900 border-white/10">
              <AlertDialogHeader>
                <AlertDialogTitle>确定清空所有资产？</AlertDialogTitle>
                <AlertDialogDescription>
                  这将永久删除项目中的所有角色、场景、物品资产。此操作不可撤销。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel className="bg-zinc-800 border-white/10 hover:bg-zinc-700">取消</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleClearAssets}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  确认清空
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => setShowCreateModal(true)}>
            <Plus className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {/* Characters */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <User className="w-4 h-4 text-muted-foreground" />
              <h4 className="text-sm font-medium">角色</h4>
              <span className="text-xs text-muted-foreground">({characters.length})</span>
            </div>
            {characters.length === 0 ? (
              <p className="text-xs text-muted-foreground pl-6">暂无角色</p>
            ) : (
              <div className="space-y-1">
                {characters.map((char) => (
                  <div
                    key={char.id}
                    className="text-sm p-2 hover:bg-accent rounded cursor-pointer flex items-center gap-2"
                    onClick={() => handleAssetClick(char.id, 'character')}
                  >
                    {char.thumbnail_url ? (
                      <img src={char.thumbnail_url} alt={char.name} className="w-6 h-6 rounded-full object-cover" />
                    ) : (
                      <div className="w-6 h-6 rounded-full bg-muted/30 flex items-center justify-center text-xs">
                        {char.name[0]}
                      </div>
                    )}
                    <span>{char.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Separator className="bg-white/5" />

          {/* Props */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Box className="w-4 h-4 text-muted-foreground" />
              <h4 className="text-sm font-medium">物品</h4>
              <span className="text-xs text-muted-foreground">({props.length})</span>
            </div>
            {props.length === 0 ? (
              <p className="text-xs text-muted-foreground pl-6">暂无物品</p>
            ) : (
              <div className="space-y-1">
                {props.map((prop) => (
                  <div
                    key={prop.id}
                    className="text-sm p-2 hover:bg-accent rounded cursor-pointer flex items-center gap-2"
                  >
                    {prop.thumbnail_url ? (
                      <img src={prop.thumbnail_url} alt={prop.name} className="w-6 h-6 rounded object-cover" />
                    ) : (
                      <div className="w-6 h-6 rounded bg-muted/30 flex items-center justify-center">
                        <Box className="w-3 h-3 text-muted-foreground/50" />
                      </div>
                    )}
                    <span>{prop.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Separator className="bg-white/5" />

          {/* Scenes */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Map className="w-4 h-4 text-muted-foreground" />
              <h4 className="text-sm font-medium">场景</h4>
              <span className="text-xs text-muted-foreground">({scenes.length})</span>
            </div>
            {scenes.length === 0 ? (
              <p className="text-xs text-muted-foreground pl-6">暂无场景</p>
            ) : (
              <div className="space-y-1">
                {scenes.map((scene) => (
                  <div
                    key={scene.id}
                    className="text-sm p-2 hover:bg-accent rounded cursor-pointer flex items-center gap-2"
                    onClick={() => handleAssetClick(scene.id, 'scene')}
                  >
                    {scene.thumbnail_url ? (
                      <img src={scene.thumbnail_url} alt={scene.name} className="w-6 h-6 rounded object-cover" />
                    ) : (
                      <div className="w-6 h-6 rounded bg-muted/30 flex items-center justify-center">
                        <Map className="w-3 h-3 text-muted-foreground/50" />
                      </div>
                    )}
                    <span>{scene.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Separator className="bg-white/5" />

          {/* Styles */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Palette className="w-4 h-4 text-muted-foreground" />
              <h4 className="text-sm font-medium">风格</h4>
              <span className="text-xs text-muted-foreground">({styles.length})</span>
            </div>
            {styles.length === 0 ? (
              <p className="text-xs text-muted-foreground pl-6">暂无风格</p>
            ) : (
              <div className="space-y-1">
                {styles.map((style) => (
                  <div
                    key={style.id}
                    className="text-sm p-2 hover:bg-accent rounded cursor-pointer"
                  >
                    {style.name}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </ScrollArea>
      <CreateAssetModal open={showCreateModal} onOpenChange={setShowCreateModal} />
      <AssetDetailModal
        assetId={selectedAssetId}
        assetType={selectedAssetType}
        onClose={() => setSelectedAssetId(null)}
        onAssetUpdated={handleAssetUpdated}
      />
    </div>
  )
}

