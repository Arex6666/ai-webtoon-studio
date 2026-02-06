'use client'

import { useState, useEffect } from 'react'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useStudioStore } from '@/lib/store/studioStore'
import type { PanelSpec } from '@/lib/schema/panelSpec'
import {
    Loader2,
    Save,
    X,
    Camera,
    MessageSquare,
    Users,
    Map,
    Sparkles,
    Sun,
    Cloud,
} from 'lucide-react'

// Shot types (matching schema)
const SHOT_TYPES = [
    { value: 'ECU', label: '特写 (ECU)' },
    { value: 'CU', label: '近景 (CU)' },
    { value: 'MS', label: '中景 (MS)' },
    { value: 'WS', label: '全身 (WS)' },
    { value: 'Establishing', label: '建立镜头' },
    { value: 'OTS', label: '过肩镜头' },
    { value: 'POV', label: '主观视角' },
]

// Camera moves (matching schema)
const CAMERA_MOVES = [
    { value: 'static', label: '静止' },
    { value: 'pan', label: '横摇' },
    { value: 'tilt', label: '纵摇' },
    { value: 'dolly_in', label: '推进' },
    { value: 'dolly_out', label: '拉远' },
    { value: 'truck', label: '轨道' },
    { value: 'handheld', label: '手持' },
    { value: 'zoom', label: '变焦' },
]

// Time of day
const TIME_OF_DAY = [
    { value: 'day', label: '白天' },
    { value: 'night', label: '夜晚' },
    { value: 'dusk', label: '黄昏' },
    { value: 'dawn', label: '黎明' },
    { value: 'indoor', label: '室内' },
]

// Weather
const WEATHER_OPTIONS = [
    { value: 'clear', label: '晴朗' },
    { value: 'rain', label: '雨天' },
    { value: 'snow', label: '雪天' },
    { value: 'fog', label: '大雾' },
    { value: 'overcast', label: '阴天' },
]

interface PanelEditorModalProps {
    panelId: string | null
    onClose: () => void
}

export function PanelEditorModal({ panelId, onClose }: PanelEditorModalProps) {
    const { panelSpecs, setPanelSpec, characters, panelList } = useStudioStore()
    const [saving, setSaving] = useState(false)

    // Get current panel spec
    const spec = panelId ? panelSpecs[panelId] : null
    // Get panel from list for additional info
    const panel = panelList.find(p => p.id === panelId)

    // Editable fields (local state)
    const [shotDescription, setShotDescription] = useState('')
    const [shotType, setShotType] = useState<string>('MS')
    const [cameraMove, setCameraMove] = useState<string>('static')
    const [sceneLocation, setSceneLocation] = useState('')
    const [sceneMood, setSceneMood] = useState('')
    const [timeOfDay, setTimeOfDay] = useState<string>('day')
    const [weather, setWeather] = useState<string>('clear')
    const [dialogueText, setDialogueText] = useState('')
    const [selectedCharacters, setSelectedCharacters] = useState<string[]>([])

    // Load spec data when panelId changes
    useEffect(() => {
        if (spec) {
            setShotDescription(spec.shot?.description || '')
            setShotType(spec.shot?.shotType || 'MS')
            setCameraMove(spec.shot?.cameraMove || 'static')
            setSceneLocation(spec.scene?.location || '')
            setSceneMood(spec.scene?.mood || '')
            setTimeOfDay(spec.scene?.timeOfDay || 'day')
            setWeather(spec.scene?.weather || 'clear')
            // Flatten dialogue lines to single text for simple editing
            const dialogueLines = spec.dialogue?.lines || []
            setDialogueText(dialogueLines.map(l => `${l.speaker}: ${l.text}`).join('\n'))
            setSelectedCharacters(spec.characters || [])
        }
    }, [spec, panelId])

    // Handle save
    const handleSave = async () => {
        if (!panelId || !spec) return

        setSaving(true)
        try {
            // Parse dialogue text back to lines
            const lines = dialogueText
                .split('\n')
                .filter(Boolean)
                .map(line => {
                    const match = line.match(/^([^:]+):\s*(.+)$/)
                    if (match) {
                        return { speaker: match[1].trim(), text: match[2].trim(), type: 'speech' as const }
                    }
                    return { speaker: 'Narrator', text: line.trim(), type: 'narration' as const }
                })

            const updated: PanelSpec = {
                ...spec,
                shot: {
                    ...spec.shot,
                    shotType: shotType as PanelSpec['shot']['shotType'],
                    cameraMove: cameraMove as PanelSpec['shot']['cameraMove'],
                    description: shotDescription,
                },
                scene: {
                    ...spec.scene,
                    location: sceneLocation,
                    mood: sceneMood,
                    timeOfDay: timeOfDay as PanelSpec['scene']['timeOfDay'],
                    weather: weather as PanelSpec['scene']['weather'],
                },
                dialogue: {
                    lines,
                },
                characters: selectedCharacters,
                meta: {
                    ...spec.meta,
                    updatedAt: new Date().toISOString(),
                },
            }

            setPanelSpec(panelId, updated)
            onClose()
        } finally {
            setSaving(false)
        }
    }

    // Smart Fill using LLM
    const [analyzing, setAnalyzing] = useState(false)
    const handleSmartFill = async () => {
        const currentChapterId = useStudioStore.getState().chapterId
        if (!currentChapterId) return

        const text = [shotDescription, dialogueText].filter(Boolean).join('\n')
        if (!text.trim()) {
            alert('请填写描述或对白以便分析')
            return
        }

        setAnalyzing(true)
        try {
            const { panelsApi } = await import('@/lib/api/services')
            const result = await panelsApi.analyze(currentChapterId, text)

            if (result.success && result.data) {
                const d = result.data

                // Update fields if returned
                if (d.shot_type) setShotType(d.shot_type)
                if (d.camera_move) setCameraMove(d.camera_move)
                if (d.time_of_day) setTimeOfDay(d.time_of_day)
                if (d.mood) setSceneMood(d.mood)

                // Match scene name if found
                if (d.scene_id) {
                    // Find scene name from assets
                    const scenes = useStudioStore.getState().scenes
                    const scene = scenes.find((s) => s.id === d.scene_id)
                    if (scene) setSceneLocation(scene.name)
                }

                // Match characters
                if (d.character_ids?.length) {
                    const charNames = d.character_ids
                        .map(id => characters.find(c => c.id === id)?.name)
                        .filter((n): n is string => !!n)

                    // Merge with existing
                    const newSet = new Set([...selectedCharacters, ...charNames])
                    setSelectedCharacters(Array.from(newSet))
                }
            } else {
                alert('分析失败: ' + (result.error || '未知错误'))
            }
        } catch (error) {
            console.error('Analysis error:', error)
            alert('请求分析失败')
        } finally {
            setAnalyzing(false)
        }
    }

    // Toggle character selection
    const toggleCharacter = (charName: string) => {
        setSelectedCharacters((prev) =>
            prev.includes(charName)
                ? prev.filter((c) => c !== charName)
                : [...prev, charName]
        )
    }

    // Get preview image from panel
    const previewImage = panel?.previewUrl

    return (
        <Dialog open={!!panelId} onOpenChange={() => onClose()}>
            <DialogContent className="max-w-4xl h-[650px] p-0 gap-0 bg-zinc-900 border-white/10">
                <DialogHeader className="p-4 pb-0 border-b border-white/5">
                    <DialogTitle className="flex items-center gap-2">
                        <Camera className="w-5 h-5 text-primary" />
                        编辑分镜 #{spec?.index !== undefined ? spec.index + 1 : '-'}
                    </DialogTitle>
                </DialogHeader>

                {!spec ? (
                    <div className="flex-1 flex items-center justify-center">
                        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <div className="flex flex-1 overflow-hidden">
                        {/* Left: Preview */}
                        <div className="w-2/5 p-4 flex flex-col border-r border-white/5">
                            <div className="flex-1 relative rounded-lg overflow-hidden bg-zinc-800 border border-white/5">
                                {previewImage ? (
                                    <img
                                        src={previewImage}
                                        alt="Preview"
                                        className="w-full h-full object-contain"
                                    />
                                ) : (
                                    <div className="w-full h-full flex flex-col items-center justify-center text-muted-foreground">
                                        <Camera className="w-16 h-16 opacity-20" />
                                        <p className="mt-4 text-sm">暂无预览</p>
                                    </div>
                                )}
                            </div>

                            {/* Panel info */}
                            <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                                <p>状态: <Badge variant="outline" className="text-xs">{spec.render?.status || 'Draft'}</Badge></p>
                                {panel?.description && (
                                    <p className="line-clamp-2">动作: {panel.description}</p>
                                )}
                            </div>
                        </div>

                        {/* Right: Edit Form */}
                        <ScrollArea className="w-3/5">
                            <div className="p-4 space-y-4">
                                {/* Shot Description */}
                                <div>
                                    <div className="flex items-center justify-between mb-1">
                                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                                            <Sparkles className="w-3 h-3" />
                                            镜头描述
                                        </Label>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-5 px-2 text-[10px] text-purple-400 hover:text-purple-300 hover:bg-purple-500/10"
                                            onClick={handleSmartFill}
                                            disabled={analyzing}
                                        >
                                            {analyzing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Sparkles className="w-3 h-3 mr-1" />}
                                            智能填充参数
                                        </Button>
                                    </div>
                                    <Textarea
                                        value={shotDescription}
                                        onChange={(e) => setShotDescription(e.target.value)}
                                        placeholder="描述画面中发生的动作、人物姿态、表情..."
                                        className="bg-zinc-800 border-white/10 min-h-[80px]"
                                    />
                                </div>

                                {/* Shot Type & Camera Move */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <Label className="text-xs text-muted-foreground mb-1 block">
                                            镜头类型
                                        </Label>
                                        <Select value={shotType} onValueChange={setShotType}>
                                            <SelectTrigger className="bg-zinc-800 border-white/10">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent className="bg-zinc-800 border-white/10">
                                                {SHOT_TYPES.map((st) => (
                                                    <SelectItem key={st.value} value={st.value}>
                                                        {st.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div>
                                        <Label className="text-xs text-muted-foreground mb-1 block">
                                            镜头运动
                                        </Label>
                                        <Select value={cameraMove} onValueChange={setCameraMove}>
                                            <SelectTrigger className="bg-zinc-800 border-white/10">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent className="bg-zinc-800 border-white/10">
                                                {CAMERA_MOVES.map((cm) => (
                                                    <SelectItem key={cm.value} value={cm.value}>
                                                        {cm.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>

                                {/* Scene Location & Mood */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <Label className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                                            <Map className="w-3 h-3" />
                                            场景位置
                                        </Label>
                                        <Input
                                            value={sceneLocation}
                                            onChange={(e) => setSceneLocation(e.target.value)}
                                            placeholder="例如: 咖啡厅"
                                            className="bg-zinc-800 border-white/10"
                                        />
                                    </div>
                                    <div>
                                        <Label className="text-xs text-muted-foreground mb-1 block">
                                            氛围
                                        </Label>
                                        <Input
                                            value={sceneMood}
                                            onChange={(e) => setSceneMood(e.target.value)}
                                            placeholder="例如: 温馨、紧张"
                                            className="bg-zinc-800 border-white/10"
                                        />
                                    </div>
                                </div>

                                {/* Time of Day & Weather */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <Label className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                                            <Sun className="w-3 h-3" />
                                            时间
                                        </Label>
                                        <Select value={timeOfDay} onValueChange={setTimeOfDay}>
                                            <SelectTrigger className="bg-zinc-800 border-white/10">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent className="bg-zinc-800 border-white/10">
                                                {TIME_OF_DAY.map((td) => (
                                                    <SelectItem key={td.value} value={td.value}>
                                                        {td.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div>
                                        <Label className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                                            <Cloud className="w-3 h-3" />
                                            天气
                                        </Label>
                                        <Select value={weather} onValueChange={setWeather}>
                                            <SelectTrigger className="bg-zinc-800 border-white/10">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent className="bg-zinc-800 border-white/10">
                                                {WEATHER_OPTIONS.map((w) => (
                                                    <SelectItem key={w.value} value={w.value}>
                                                        {w.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>

                                {/* Dialogue */}
                                <div>
                                    <Label className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                                        <MessageSquare className="w-3 h-3" />
                                        对白 (每行格式: 角色名: 台词)
                                    </Label>
                                    <Textarea
                                        value={dialogueText}
                                        onChange={(e) => setDialogueText(e.target.value)}
                                        placeholder="林晚: 你好&#10;陈默: 好久不见"
                                        className="bg-zinc-800 border-white/10 min-h-[80px] font-mono text-sm"
                                    />
                                </div>

                                {/* Characters */}
                                <div>
                                    <Label className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                                        <Users className="w-3 h-3" />
                                        出场角色
                                    </Label>
                                    <div className="flex flex-wrap gap-2">
                                        {characters.length > 0 ? (
                                            characters.map((char) => (
                                                <Badge
                                                    key={char.id}
                                                    variant={selectedCharacters.includes(char.name) ? 'default' : 'outline'}
                                                    className="cursor-pointer transition-colors"
                                                    onClick={() => toggleCharacter(char.name)}
                                                >
                                                    {char.name}
                                                    {selectedCharacters.includes(char.name) && (
                                                        <X className="w-3 h-3 ml-1" />
                                                    )}
                                                </Badge>
                                            ))
                                        ) : (
                                            <p className="text-xs text-muted-foreground">暂无角色资产</p>
                                        )}
                                    </div>
                                    {/* Show currently selected characters not in assets */}
                                    {selectedCharacters.filter(c => !characters.find(ch => ch.name === c)).length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            {selectedCharacters.filter(c => !characters.find(ch => ch.name === c)).map(c => (
                                                <Badge key={c} variant="secondary" className="text-xs">
                                                    {c}
                                                    <X className="w-3 h-3 ml-1 cursor-pointer" onClick={() => toggleCharacter(c)} />
                                                </Badge>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </ScrollArea>
                    </div>
                )}

                <DialogFooter className="p-4 border-t border-white/5">
                    <Button variant="outline" className="border-white/10" onClick={onClose}>
                        取消
                    </Button>
                    <Button onClick={handleSave} disabled={saving} className="gap-2">
                        {saving ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <Save className="w-4 h-4" />
                        )}
                        保存
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
