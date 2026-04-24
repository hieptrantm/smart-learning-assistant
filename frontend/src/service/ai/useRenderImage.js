"use client";

import { useCallback } from "react";
import { getTokensInfo } from "../auth/token";

export function useRenderImageService() {
    return useCallback(async (filename) => {
        const tokens = getTokensInfo();
        
        const headers = new Headers();
        if (tokens?.token) {
            headers.set("Authorization", `Bearer ${tokens.token}`);
        }

        const res = await fetch(`/ai/get-image?filename=${filename}`, {
            method: "GET",
            headers,
        });

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Get image failed: ${res.status} - ${errorText}`);
        }

        const blob = await res.blob();
        return URL.createObjectURL(blob);
    }, []);
}