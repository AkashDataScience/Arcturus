import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
import { Network, RefreshCw, ZoomIn, ZoomOut, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';

const LIMIT = 150;

export const KnowledgeGraphExplorer: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const cyRef = useRef<Core | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedNode, setSelectedNode] = useState<{ id: string; label: string; type: string } | null>(null);
    const spaces = useAppStore((s) => s.spaces);
    const currentSpaceId = useAppStore((s) => s.currentSpaceId);
    const setCurrentSpaceId = useAppStore((s) => s.setCurrentSpaceId);
    const fetchSpaces = useAppStore((s) => s.fetchSpaces);

    const fetchAndRender = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { nodes, edges } = await api.getGraphExplore(
                currentSpaceId ?? undefined,
                LIMIT
            );
            if (!containerRef.current) return;

            // Destroy previous instance
            if (cyRef.current) {
                cyRef.current.destroy();
                cyRef.current = null;
            }

            const elements: ElementDefinition[] = [
                ...nodes.map((n) => ({ data: { id: n.id, label: n.label, type: n.type } })),
                ...edges.map((e, i) => ({
                    data: { id: `e${i}`, source: e.source, target: e.target, relType: e.type },
                })),
            ];

            const cy = cytoscape({
                container: containerRef.current,
                elements,
                style: [
                    {
                        selector: 'node',
                        style: {
                            label: 'data(label)',
                            'text-valign': 'bottom',
                            'text-halign': 'center',
                            'font-size': '10px',
                            'text-margin-y': 4,
                            width: 24,
                            height: 24,
                            'background-color': 'hsl(var(--primary))',
                            color: 'hsl(var(--background))',
                            'text-wrap': 'ellipsis',
                            'text-max-width': '80px',
                            'border-width': 2,
                            'border-color': 'hsl(var(--primary) / 0.5)',
                        },
                    },
                    {
                        selector: 'node:selected',
                        style: {
                            'border-width': 3,
                            'border-color': 'hsl(var(--primary))',
                            'background-color': 'hsl(var(--primary) / 0.9)',
                        },
                    },
                    {
                        selector: 'edge',
                        style: {
                            width: 1.5,
                            'line-color': 'hsl(var(--muted-foreground) / 0.6)',
                            'target-arrow-color': 'hsl(var(--muted-foreground) / 0.6)',
                            'target-arrow-shape': 'triangle',
                            'curve-style': 'bezier',
                        },
                    },
                ],
                layout: {
                    name: 'cose',
                    idealEdgeLength: 80,
                    nodeOverlap: 20,
                    padding: 40,
                },
                minZoom: 0.2,
                maxZoom: 3,
                wheelSensitivity: 0.3,
            });

            cy.on('tap', 'node', (evt) => {
                const n = evt.target;
                const data = n.data();
                setSelectedNode({ id: data.id, label: data.label, type: data.type });
            });
            cy.on('tap', (evt) => {
                if (evt.target === cy) setSelectedNode(null);
            });

            cyRef.current = cy;
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Failed to load graph';
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [currentSpaceId]);

    useEffect(() => {
        fetchSpaces();
    }, [fetchSpaces]);

    useEffect(() => {
        fetchAndRender();
        return () => {
            if (cyRef.current) {
                cyRef.current.destroy();
                cyRef.current = null;
            }
        };
    }, [fetchAndRender]);

    const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.2);
    const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() / 1.2);
    const handleFit = () => cyRef.current?.fit(undefined, 40);

    return (
        <div className="h-full flex flex-col bg-background">
            {/* Toolbar */}
            <div className="flex items-center justify-between gap-2 p-2 border-b border-border/50 bg-muted/20 shrink-0">
                <div className="flex items-center gap-2">
                    <Select value={currentSpaceId ?? '__global__'} onValueChange={(v) => setCurrentSpaceId(v === '__global__' ? null : v)}>
                        <SelectTrigger className="w-[180px] h-8 text-xs bg-background">
                            <SelectValue placeholder="Space" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__global__">Global</SelectItem>
                            {spaces.map((s) => (
                                <SelectItem key={s.space_id} value={s.space_id}>
                                    {s.name || 'Unnamed'}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={fetchAndRender} disabled={loading}>
                        {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                        Refresh
                    </Button>
                </div>
                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleZoomOut} title="Zoom out">
                        <ZoomOut className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleFit} title="Fit">
                        <Network className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleZoomIn} title="Zoom in">
                        <ZoomIn className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* Graph canvas / content */}
            <div className="flex-1 min-h-0 relative">
                {loading && (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-background/80">
                        <Loader2 className="w-12 h-12 animate-spin text-primary" />
                        <p className="mt-2 text-sm text-muted-foreground">Loading knowledge graph...</p>
                    </div>
                )}
                {error && (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center p-8 text-center">
                        <AlertCircle className="w-12 h-12 text-destructive mb-2" />
                        <p className="text-sm text-destructive mb-4">{error}</p>
                        <Button variant="outline" size="sm" onClick={fetchAndRender}>
                            <RefreshCw className="w-4 h-4 mr-2" /> Retry
                        </Button>
                    </div>
                )}
                <div
                    ref={containerRef}
                    className={cn(
                        "w-full h-full min-h-[300px] rounded-lg",
                        (loading || error) && "opacity-30 pointer-events-none"
                    )}
                />
            </div>

            {/* Selected node detail */}
            {selectedNode && (
                <div className="p-3 border-t border-border/50 bg-muted/20 text-xs shrink-0">
                    <span className="font-semibold text-foreground">{selectedNode.label}</span>
                    <span className="text-muted-foreground ml-2">({selectedNode.type})</span>
                </div>
            )}
        </div>
    );
};
