import { create } from 'zustand';

export interface Page {
    id: string;
    query: string;
    template: string;
    status: 'pending' | 'generating' | 'complete' | 'failed';
    sections: any[];
    citations: any;
    created_at: string;
    updated_at?: string;
    created_by: string;
    folder_id?: string;
    tags?: string[];
}

interface PagesStore {
    pages: Page[];
    selectedPage: Page | null;
    isLoading: boolean;
    isGenerating: boolean;
    setPages: (pages: Page[]) => void;
    setSelectedPage: (page: Page | null) => void;
    setIsLoading: (loading: boolean) => void;
    setIsGenerating: (generating: boolean) => void;
}

export const usePagesStore = create<PagesStore>((set) => ({
    pages: [],
    selectedPage: null,
    isLoading: false,
    isGenerating: false,
    setPages: (pages) => set({ pages }),
    setSelectedPage: (page) => set({ selectedPage: page }),
    setIsLoading: (isLoading) => set({ isLoading }),
    setIsGenerating: (isGenerating) => set({ isGenerating }),
}));
