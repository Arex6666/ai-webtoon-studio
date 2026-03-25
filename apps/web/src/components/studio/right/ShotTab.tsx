'use client'

import { useFormContext } from 'react-hook-form'
import { PanelSpec } from '@/lib/schema'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Sparkles } from 'lucide-react'

export function ShotTab() {
  const { register, watch, setValue } = useFormContext<PanelSpec>()

  const shotType = watch('shot.shotType')
  const cameraMove = watch('shot.cameraMove')
  const durationSec = watch('shot.durationSec')
  const timeOfDay = watch('scene.timeOfDay')
  const weather = watch('scene.weather')

  return (
    <div className="p-4 space-y-5">
      {/* 1. Shot description textarea with Smart Fill */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
            镜头描述 (Shot Description)
          </Label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs text-primary gap-1"
            onClick={() => {
              // Smart Fill: build description from current shot/scene values
              const currentShotType = watch('shot.shotType')
              const currentCameraMove = watch('shot.cameraMove')
              const currentLocation = watch('scene.location')
              const currentMood = watch('scene.mood')
              const filled = [currentShotType, currentCameraMove, currentLocation, currentMood]
                .filter(Boolean)
                .join(', ')
              setValue('shot.description', filled)
            }}
          >
            <Sparkles className="w-3 h-3" />
            Smart Fill
          </Button>
        </div>
        <Textarea
          {...register('shot.description')}
          placeholder="描述镜头内容、构图、视觉重点..."
          rows={3}
          className="resize-none text-sm"
        />
      </div>

      {/* 2. Shot type + Camera move selects (side by side) */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
            景别
          </Label>
          <Select value={shotType} onValueChange={(value) => setValue('shot.shotType', value as PanelSpec['shot']['shotType'])}>
            <SelectTrigger>
              <SelectValue placeholder="选择景别" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ECU">极大特写 (ECU)</SelectItem>
              <SelectItem value="CU">特写 (CU)</SelectItem>
              <SelectItem value="MS">中景 (MS)</SelectItem>
              <SelectItem value="WS">全景 (WS)</SelectItem>
              <SelectItem value="Establishing">建立 (Establishing)</SelectItem>
              <SelectItem value="OTS">越肩 (OTS)</SelectItem>
              <SelectItem value="POV">主观 (POV)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
            运镜
          </Label>
          <Select value={cameraMove} onValueChange={(value) => setValue('shot.cameraMove', value as PanelSpec['shot']['cameraMove'])}>
            <SelectTrigger>
              <SelectValue placeholder="选择运镜" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="static">静止 (Static)</SelectItem>
              <SelectItem value="pan">摇摄 (Pan)</SelectItem>
              <SelectItem value="tilt">俯仰 (Tilt)</SelectItem>
              <SelectItem value="dolly_in">推近 (Dolly In)</SelectItem>
              <SelectItem value="dolly_out">拉远 (Dolly Out)</SelectItem>
              <SelectItem value="truck">横移 (Truck)</SelectItem>
              <SelectItem value="handheld">手持 (Handheld)</SelectItem>
              <SelectItem value="zoom">变焦 (Zoom)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* 3. Duration slider */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
            时长 (Duration)
          </Label>
          <span className="text-xs text-muted-foreground tabular-nums">
            {typeof durationSec === 'number' ? durationSec.toFixed(1) : '3.0'}s
          </span>
        </div>
        <Slider
          min={0.5}
          max={15}
          step={0.5}
          value={[typeof durationSec === 'number' ? durationSec : 3.0]}
          onValueChange={([val]) => setValue('shot.durationSec', val)}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>0.5s</span>
          <span>15s</span>
        </div>
      </div>

      {/* 4. Separator: 场景 */}
      <div className="flex items-center gap-2">
        <Separator className="flex-1" />
        <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wider px-1">
          场景
        </span>
        <Separator className="flex-1" />
      </div>

      {/* 5. Scene location + Mood inputs (side by side) */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
            场景位置
          </Label>
          <Input
            {...register('scene.location')}
            placeholder="e.g. 咖啡馆"
          />
        </div>

        <div className="space-y-2">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
            氛围
          </Label>
          <Input
            {...register('scene.mood')}
            placeholder="e.g. 温馨"
          />
        </div>
      </div>

      {/* 6. Time of day + Weather selects (side by side) */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
            时段
          </Label>
          <Select value={timeOfDay} onValueChange={(value) => setValue('scene.timeOfDay', value as PanelSpec['scene']['timeOfDay'])}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="day">白天 (Day)</SelectItem>
              <SelectItem value="night">夜晚 (Night)</SelectItem>
              <SelectItem value="dusk">黄昏 (Dusk)</SelectItem>
              <SelectItem value="dawn">黎明 (Dawn)</SelectItem>
              <SelectItem value="indoor">室内 (Indoor)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
            天气
          </Label>
          <Select value={weather} onValueChange={(value) => setValue('scene.weather', value as PanelSpec['scene']['weather'])}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="clear">晴天 (Clear)</SelectItem>
              <SelectItem value="rain">雨天 (Rain)</SelectItem>
              <SelectItem value="snow">雪天 (Snow)</SelectItem>
              <SelectItem value="fog">雾天 (Fog)</SelectItem>
              <SelectItem value="overcast">阴天 (Overcast)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  )
}
