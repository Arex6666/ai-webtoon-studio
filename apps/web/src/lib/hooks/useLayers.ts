/**
 * 图层 API Hooks
 */
import { useState, useCallback } from 'react';
import { Layer, LayerStack, LayerType } from '@/lib/schema/layers';

interface UseLayerSeparationOptions {
    onSuccess?: (result: LayerSeparationResult) => void;
    onError?: (error: Error) => void;
}

interface LayerSeparationResult {
    jobId: string;
    maskUrl: string | null;
    charUrl: string | null;
    bgUrl: string | null;
}

/**
 * 图层分离 Hook
 */
export function useLayerSeparation(options: UseLayerSeparationOptions = {}) {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);
    const [result, setResult] = useState<LayerSeparationResult | null>(null);

    const separate = useCallback(async (
        panelId: string,
        sourceImageUrl: string,
        pointCoords?: [number, number][]
    ) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch('/api/v1/generate/layer-separation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    panel_id: panelId,
                    source_image_url: sourceImageUrl,
                    point_coords: pointCoords,
                }),
            });

            if (!response.ok) {
                throw new Error(`Separation failed: ${response.statusText}`);
            }

            const data = await response.json();

            // 返回 job_id，需要轮询获取结果
            const jobResult: LayerSeparationResult = {
                jobId: data.job_id,
                maskUrl: null,
                charUrl: null,
                bgUrl: null,
            };

            setResult(jobResult);
            options.onSuccess?.(jobResult);

            return jobResult;

        } catch (err) {
            const error = err instanceof Error ? err : new Error('Unknown error');
            setError(error);
            options.onError?.(error);
            throw error;
        } finally {
            setIsLoading(false);
        }
    }, [options]);

    return {
        separate,
        isLoading,
        error,
        result,
    };
}

/**
 * 控制图估计 Hook
 */
export function useControlEstimate() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const estimate = useCallback(async (
        panelId: string,
        sourceImageUrl: string,
        type: 'depth' | 'pose'
    ) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch('/api/v1/generate/estimate-control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    panel_id: panelId,
                    source_image_url: sourceImageUrl,
                    estimate_type: type,
                }),
            });

            if (!response.ok) {
                throw new Error(`Estimation failed: ${response.statusText}`);
            }

            return await response.json();

        } catch (err) {
            const error = err instanceof Error ? err : new Error('Unknown error');
            setError(error);
            throw error;
        } finally {
            setIsLoading(false);
        }
    }, []);

    return {
        estimate,
        isLoading,
        error,
    };
}

/**
 * 图层包 Hook - 获取和管理 LayerPack
 */
export function useLayerPack(panelId: string) {
    const [stack, setStack] = useState<LayerStack | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const fetchLayers = useCallback(async () => {
        if (!panelId) return;

        setIsLoading(true);
        try {
            const response = await fetch(`/api/v1/panels/${panelId}/layerpacks/active`);
            if (!response.ok) throw new Error('Failed to fetch layerpack');

            const data = await response.json();

            // 转换为 LayerStack
            const layers: Layer[] = [
                { type: 'full', url: data.files?.full || data.full_url, visible: true, opacity: 1, blendMode: 'normal' },
                { type: 'char', url: data.files?.char, visible: !!data.files?.char, opacity: 1, blendMode: 'normal' },
                { type: 'bg', url: data.files?.bg, visible: false, opacity: 1, blendMode: 'normal' },
                { type: 'mask', url: data.files?.mask, visible: false, opacity: 1, blendMode: 'normal' },
                { type: 'depth', url: data.files?.depth, visible: false, opacity: 1, blendMode: 'normal' },
                { type: 'lineart', url: data.files?.lineart, visible: false, opacity: 1, blendMode: 'normal' },
            ];

            setStack({
                panelId,
                layerpackId: data.id,
                layers,
                width: data.width || 1080,
                height: data.height || 1920,
            });

        } catch (error) {
            console.error('Failed to fetch layerpack:', error);
        } finally {
            setIsLoading(false);
        }
    }, [panelId]);

    const updateLayerVisibility = useCallback((type: LayerType, visible: boolean) => {
        setStack(prev => {
            if (!prev) return prev;
            return {
                ...prev,
                layers: prev.layers.map(l =>
                    l.type === type ? { ...l, visible } : l
                ),
            };
        });
    }, []);

    const updateLayerOpacity = useCallback((type: LayerType, opacity: number) => {
        setStack(prev => {
            if (!prev) return prev;
            return {
                ...prev,
                layers: prev.layers.map(l =>
                    l.type === type ? { ...l, opacity } : l
                ),
            };
        });
    }, []);

    return {
        stack,
        isLoading,
        fetchLayers,
        updateLayerVisibility,
        updateLayerOpacity,
    };
}
