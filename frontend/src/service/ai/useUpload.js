"use client";

import { useCallback } from "react";
import { getTokensInfo } from "../auth/token";

export function useUploadImageService() {
    return useCallback(async (file) => {
        const tokens = getTokensInfo();
        const formData = new FormData();
        formData.append("file", file);

        const headers = new Headers();
        if (tokens?.token) {
            headers.set("Authorization", `Bearer ${tokens.token}`);
        }
        const res = await fetch(`/ai/upload`, {
            method: "POST",
            headers,
            body: formData,
        });

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Upload failed: ${res.status} - ${errorText}`);
        }

        return res.json();
    }, []);
}