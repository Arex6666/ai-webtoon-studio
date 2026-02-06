import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Edit2, Trash2, Box } from "lucide-react"
import type { PropAsset } from "@/lib/schema/assets.prop"
import { cn } from "@/lib/utils"

interface PropCardProps {
    prop: PropAsset
    onClick?: () => void
    onEdit?: (e: React.MouseEvent) => void
    onDelete?: (e: React.MouseEvent) => void
    className?: string
}

export function PropCard({ prop, onClick, onEdit, onDelete, className }: PropCardProps) {
    const thumbnail = prop.ref_image_paths?.[0]

    return (
        <Card
            className={cn(
                "group relative overflow-hidden transition-all hover:ring-2 hover:ring-primary/50 cursor-pointer",
                className
            )}
            onClick={onClick}
        >
            <div className="aspect-square bg-muted/30 relative">
                {thumbnail ? (
                    <img
                        src={thumbnail}
                        alt={prop.canonical_name}
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-muted-foreground gap-2">
                        <Box className="w-8 h-8 opacity-50" />
                    </div>
                )}

                {/* Status Badge */}
                <div className="absolute top-2 left-2">
                    <Badge variant={prop.status === 'ready' ? 'default' : 'secondary'} className="text-[10px] h-5">
                        {prop.category === 'hand_prop' ? 'Hand Prop' : 'Set Dressing'}
                    </Badge>
                </div>

                {/* Actions Overlay */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    <Button
                        size="icon"
                        variant="secondary"
                        className="h-8 w-8"
                        onClick={onEdit}
                    >
                        <Edit2 className="w-4 h-4" />
                    </Button>
                    <Button
                        size="icon"
                        variant="destructive"
                        className="h-8 w-8"
                        onClick={onDelete}
                    >
                        <Trash2 className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            <CardContent className="p-3">
                <div className="flex items-start justify-between gap-2">
                    <div>
                        <h4 className="font-medium text-sm truncate" title={prop.canonical_name}>
                            {prop.canonical_name}
                        </h4>
                        {prop.aliases.length > 0 && (
                            <p className="text-xs text-muted-foreground truncate">
                                {prop.aliases.join(', ')}
                            </p>
                        )}
                    </div>
                </div>

                {prop.visual_brief && (
                    <p className="text-xs text-muted-foreground line-clamp-2 mt-1.5">
                        {prop.visual_brief}
                    </p>
                )}
            </CardContent>
        </Card>
    )
}
